"""Chaîne SolidCraft -> Exudyn, sans saisie manuelle de la géométrie ni des inerties.

Entrées (exportées depuis SolidCraft, configuration de référence θ = 0) :
- export/bielle_export.json : occurrences (transformations), liaisons (type, occurrences, point et axe z
  en repère LOCAL de l'occurrence), occurrences fixes ;
- export/bielle.urdf : masse, centre de gravité et matrice d'inertie de chaque composant.

Étapes :
1. lecture des solides (masse, CdG, inertie en repère monde) ;
2. proposition d'une liaison normalisée pour chaque liaison SolidCraft, puis CHOIX DE L'ÉLÈVE
   (ici : rotule en B remplacée par linéaire annulaire pour rendre le mécanisme isostatique) ;
3. construction du modèle Exudyn, liaison L01 pilotée par la loi d'entrée ;
4. comparaison des torseurs avec la solution de référence Newton-Euler du prototype exudyn_bielle.

Lancer avec l'environnement du prototype :
    ../exudyn_bielle/.venv/Scripts/python chaine_solidcraft_exudyn.py
"""
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
import exudyn as exu
from exudyn.utilities import *  # noqa: F401,F403

ICI = Path(__file__).parent
sys.path.insert(0, str(ICI.parent / "exudyn_bielle"))
import bielle_manivelle as REF  # noqa: E402  (loi d'entrée et solution de référence)
from liaisons import LIAISONS  # noqa: E402

G = [0, -9.81, 0]

# Proposition automatique : type SolidCraft -> liaison normalisée
PROPOSITION = {
    "revolute": "pivot", "slider": "glissiere", "cylindrical": "pivot_glissant",
    "planar": "appui_plan", "ball": "rotule", "rigid": "encastrement",
}
# Liaisons dont l'axe SolidCraft (z) est l'axe x de notre convention ; les autres : z -> z
A_AXE = {"pivot", "glissiere", "pivot_glissant", "lineaire_annulaire", "helicoidale"}

# Décisions de l'élève (ce que Meca3D lui ferait valider dans l'interface)
CHOIX_ELEVE = {"L23_rotule": "lineaire_annulaire"}
PILOTE = "L01_pivot"


# --- Lecture SolidCraft ------------------------------------------------------
def transform_occurrence(occ):
    """La matrice 'transform' est stockée par colonnes : transform[i] = i-ème colonne."""
    T = np.array(occ["transform"]).T
    return T[:3, :3], T[:3, 3] / 1000.0          # rotation, translation (m)


def rpy(r, p, y):
    return RotationMatrixZ(y) @ RotationMatrixY(p) @ RotationMatrixX(r)


def lire_urdf(chemin):
    """Pose monde de chaque lien (valeurs articulaires nulles), puis inertie en repère monde."""
    racine = ET.parse(chemin).getroot()
    poses = {"base_link": (np.eye(3), np.zeros(3))}
    joints = racine.findall("joint")
    while len(poses) < len(racine.findall("link")):
        for j in joints:
            parent, enfant = j.find("parent").get("link"), j.find("child").get("link")
            if parent in poses and enfant not in poses:
                o = j.find("origin")
                xyz = np.array([float(v) for v in o.get("xyz").split()])
                R0 = rpy(*[float(v) for v in o.get("rpy").split()])
                Rp, tp = poses[parent]
                poses[enfant] = (Rp @ R0, Rp @ xyz + tp)
    solides = {}
    for lien in racine.findall("link"):
        inert = lien.find("inertial")
        if inert is None:
            continue
        Rl, tl = poses[lien.get("name")]
        o = inert.find("origin")
        xyz = np.array([float(v) for v in o.get("xyz").split()])
        Ri = Rl @ rpy(*[float(v) for v in o.get("rpy").split()])
        a = inert.find("inertia").attrib
        I = np.array([[a["ixx"], a["ixy"], a["ixz"]], [a["ixy"], a["iyy"], a["iyz"]],
                      [a["ixz"], a["iyz"], a["izz"]]], dtype=float)
        solides[lien.get("name")] = dict(masse=float(inert.find("mass").get("value")),
                                         cdg=Rl @ xyz + tl, inertie=Ri @ I @ Ri.T)
    return solides


def repere_liaison(liaison, z):
    """Base de liaison (colonnes) à partir du seul axe z SolidCraft ; le reste est complété arbitrairement."""
    z = z / np.linalg.norm(z)
    aux = np.array([1.0, 0, 0]) if abs(z[0]) < 0.9 else np.array([0, 1.0, 0])
    u = np.cross(z, aux); u /= np.linalg.norm(u)
    v = np.cross(z, u)
    if liaison in A_AXE:          # axe de la liaison = x local
        return np.column_stack([z, u, v])
    return np.column_stack([u, v, z])  # normale = z local


def lire_modele():
    d = json.loads((ICI / "export/bielle_export.json").read_text(encoding="utf-8"))
    comp = {c["id"]: c["name"] for c in d["components"]}
    occs = {o["id"]: dict(nom=comp[o["component"]], fixe=o["grounded"], T=transform_occurrence(o))
            for o in d["occurrences"]}
    inerties = lire_urdf(ICI / "export/bielle.urdf")
    liaisons = []
    for j in d["assembly"]["joints"]:
        propose = PROPOSITION.get(j["kind"])
        retenu = CHOIX_ELEVE.get(j["name"], propose)
        R, t = occs[j["a"]["occurrence"]]["T"]
        p = R @ (np.array(j["a"]["snap"]["point"]) / 1000.0) + t
        z = R @ np.array(j["a"]["snap"]["z"])
        liaisons.append(dict(nom=j["name"], type_sc=j["kind"], propose=propose, retenu=retenu,
                             a=j["a"]["occurrence"], b=j["b"]["occurrence"], point=p,
                             R=repere_liaison(retenu, z)))
    return occs, inerties, liaisons


# --- Modèle Exudyn ---------------------------------------------------------------
def construire(occs, inerties, liaisons):
    SC = exu.SystemContainer()
    mbs = SC.AddSystem()
    sol = mbs.AddObject(ObjectGround())
    corps = {}
    for oid, o in occs.items():
        if o["fixe"]:
            corps[oid] = sol
            continue
        s = inerties[o["nom"]]
        corps[oid] = mbs.CreateRigidBody(
            inertia=RigidBodyInertia(mass=s["masse"], inertiaTensor=s["inertie"], inertiaTensorAtCOM=True),
            referencePosition=s["cdg"].tolist(), gravity=G)

    def offset(mbs, t, i, p):
        return [0, 0, 0, REF.theta(t), 0, 0]

    def offset_t(mbs, t, i, p):
        return [0, 0, 0, REF.theta_t(t), 0, 0]

    jts = {}
    for L in liaisons:
        axes = list(LIAISONS[L["retenu"]])
        kw = {}
        if L["nom"] == PILOTE:
            axes[3] = 1
            kw = dict(offsetUserFunction=offset, offsetUserFunction_t=offset_t)
        jts[L["nom"]] = mbs.CreateGenericJoint(itemNumbers=[corps[L["a"]], corps[L["b"]]],
                                               position=L["point"].tolist(), rotationMatrixAxes=L["R"],
                                               constrainedAxes=axes, show=False, **kw)
    return mbs, corps, sol, jts


def simuler():
    occs, inerties, liaisons = lire_modele()
    print("Solides lus (URDF) :")
    for nom, s in inerties.items():
        print(f"  {nom:10} m = {s['masse']:.4f} kg  G = {np.round(s['cdg'], 4)}  Izz = {s['inertie'][2, 2]:.4e}")
    print("Liaisons (SolidCraft -> proposée -> retenue par l'élève) :")
    for L in liaisons:
        print(f"  {L['nom']:14} {L['type_sc']:8} -> {L['propose']:10} -> {L['retenu']}")
    mbs, corps, sol, jts = construire(occs, inerties, liaisons)
    capt = {}
    for L in liaisons:
        n = L["nom"]
        capt[n + "F"] = mbs.AddSensor(SensorObject(objectNumber=jts[n], storeInternal=True,
                                                   outputVariableType=exu.OutputVariableType.ForceLocal))
        capt[n + "M"] = mbs.AddSensor(SensorObject(objectNumber=jts[n], storeInternal=True,
                                                   outputVariableType=exu.OutputVariableType.TorqueLocal))
    for oid, c in corps.items():
        if c != sol:
            capt[f"R{oid}"] = mbs.AddSensor(SensorBody(bodyNumber=c, storeInternal=True,
                                                       outputVariableType=exu.OutputVariableType.RotationMatrix))
    ss = exu.SimulationSettings()
    ss.timeIntegration.endTime = REF.T_FIN
    ss.timeIntegration.numberOfSteps = REF.N_PAS
    ss.timeIntegration.verboseMode = 0
    ss.timeIntegration.generalizedAlpha.spectralRadius = 0.9
    ss.solution.file.write = False
    ss.solution.sensors.writePeriod = 0.002
    mbs.Assemble()
    mbs.SolveDynamic(ss)
    data = {k: mbs.GetSensorStoredData(s) for k, s in capt.items()}
    return occs, liaisons, data


def comparer():
    occs, liaisons, d = simuler()
    t = d[PILOTE + "F"][:, 0]
    # action de a sur b en repère monde : -(R_a(t) · R_liaison · F_local)
    def action(nom, i, moment=False):
        L = next(x for x in liaisons if x["nom"] == nom)
        Ra = np.eye(3) if occs[L["a"]]["fixe"] else d[f"R{L['a']}"][i, 1:].reshape(3, 3)
        v = d[nom + ("M" if moment else "F")][i, 1:]
        return -(Ra @ L["R"] @ v)

    paires = [("O", "L01_pivot"), ("A", "L12_pivot"), ("B", "L23_rotule")]
    print(f"\n{'grandeur':26} {'max |réf|':>10} {'écart relatif':>14}")
    pire = 0.0
    for cle, nom in paires:
        ex = np.array([action(nom, i)[:2] for i in range(len(t))])
        rf = np.array([REF.reference(x)[cle] for x in t])
        e = np.abs(ex - rf).max() / np.abs(rf).max()
        pire = max(pire, e)
        print(f"{'réaction ' + cle + ' (' + nom + ')':26} {np.abs(rf).max():10.3f} {e:14.2e}")
    C = np.array([action(PILOTE, i, moment=True)[2] for i in range(len(t))])
    Cr = np.array([REF.reference(x)["C"] for x in t])
    e = np.abs(C - Cr).max() / np.abs(Cr).max()
    pire = max(pire, e)
    print(f"{'couple moteur':26} {np.abs(Cr).max():10.3f} {e:14.2e}")
    N = np.array([action("L30_glissiere", i)[1] for i in range(len(t))])
    Nr = np.array([REF.reference(x)["N"] for x in t])
    e = np.abs(N - Nr).max() / np.abs(Nr).max()
    pire = max(pire, e)
    print(f"{'normale piston':26} {np.abs(Nr).max():10.3f} {e:14.2e}")
    print(f"\nPire écart relatif, chaîne SolidCraft -> Exudyn : {pire:.2e}")


if __name__ == "__main__":
    comparer()
