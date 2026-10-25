"""Vérifie que GenericJoint d'Exudyn réalise chaque liaison normalisée, en grands déplacements.

Pour chaque liaison : un solide relié au bâti, repère de liaison volontairement incliné,
force et couple constants quelconques, 0,2 s de simulation. On contrôle :
1. les invariants géométriques PHYSIQUES de la liaison (avec d = déplacement du point du solide
   initialement au centre de liaison, en base de liaison ; D[i,j] = e_i(0) . e_j(1)) ;
2. que les ddl libres ont effectivement bougé ;
3. que le torseur de liaison (ForceLocal, TorqueLocal) est nul sur les ddl libres.
"""
import numpy as np
import exudyn as exu
from exudyn.utilities import *  # noqa: F401,F403 (API Exudyn : Inertia*, ObjectGround, Rotation*)

from liaisons import LIAISONS

TOL = 1e-6          # tolérance sur les invariants (m ou sans dimension)
SEUIL_LIBRE = 1e-5  # un ddl libre doit avoir bougé d'au moins cela
TOL_EFFORT = 1e-6   # N ou N·m

# Invariants physiques de chaque liaison : fonctions (d, D) -> liste de valeurs devant rester nulles
INVARIANTS = {
    "encastrement":        lambda d, D: [*d, *(D - np.eye(3)).ravel()],
    "pivot":               lambda d, D: [*d, D[0, 0] - 1],
    "glissiere":           lambda d, D: [d[1], d[2], *(D - np.eye(3)).ravel()],
    "pivot_glissant":      lambda d, D: [d[1], d[2], D[0, 0] - 1],
    "rotule_a_doigt":      lambda d, D: [*d, D[0, 1]],          # cardan : x0 ⟂ y1
    "rotule":              lambda d, D: [*d],
    "appui_plan":          lambda d, D: [d[2], D[2, 2] - 1],
    "lineaire_annulaire":  lambda d, D: [d[1], d[2]],
    "lineaire_rectiligne": lambda d, D: [d[2], D[2, 0]],        # ligne x1 dans le plan de normale z0
    "ponctuelle":          lambda d, D: [d[2]],
}

Rj = RotationMatrixZ(0.4) @ RotationMatrixY(-0.3) @ RotationMatrixX(0.2)
PJ = np.array([0.2, -0.1, 0.3])
PG = PJ + Rj @ [0.05, 0.03, 0.02]  # CdG décalé du centre de liaison


def rot_vec(R):
    angle = np.arccos(np.clip((np.trace(R) - 1) / 2, -1, 1))
    if angle < 1e-12:
        return np.zeros(3)
    return np.array([R[2, 1] - R[1, 2], R[0, 2] - R[2, 0], R[1, 0] - R[0, 1]]) / (2 * np.sin(angle)) * angle


def simuler(liaisons_a_creer):
    """liaisons_a_creer : liste de (position globale, constrainedAxes)."""
    SC = exu.SystemContainer()
    mbs = SC.AddSystem()
    sol = mbs.AddObject(ObjectGround())
    corps = mbs.CreateRigidBody(inertia=InertiaCuboid(density=2000, sideLengths=[0.3, 0.2, 0.1]),
                                referencePosition=PG.tolist())
    jts = [mbs.CreateGenericJoint(itemNumbers=[sol, corps], position=list(p), rotationMatrixAxes=Rj,
                                  constrainedAxes=ax, show=False) for p, ax in liaisons_a_creer]
    mk = mbs.AddMarker(MarkerBodyRigid(bodyNumber=corps, localPosition=[0, 0, 0]))
    mkJ = mbs.AddMarker(MarkerBodyRigid(bodyNumber=corps, localPosition=(PJ - PG).tolist()))
    mbs.AddLoad(Force(markerNumber=mk, loadVector=(Rj @ [3.0, -2.0, 5.0]).tolist()))
    mbs.AddLoad(Torque(markerNumber=mk, loadVector=(Rj @ [0.7, 0.5, -0.9]).tolist()))
    mbs.Assemble()
    ss = exu.SimulationSettings()
    ss.timeIntegration.endTime = 0.2
    ss.timeIntegration.numberOfSteps = 400
    ss.timeIntegration.verboseMode = 0
    mbs.SolveDynamic(ss)

    A1 = np.array(mbs.GetNodeOutput(mbs.GetObject(corps)["nodeNumber"],
                                    exu.OutputVariableType.RotationMatrix)).reshape(3, 3)
    d = Rj.T @ (np.array(mbs.GetMarkerOutput(mkJ, exu.OutputVariableType.Position)) - PJ)
    D = Rj.T @ A1 @ Rj
    r = Rj.T @ rot_vec(A1)
    torseurs = [(np.array(mbs.GetObjectOutput(j, exu.OutputVariableType.ForceLocal)),
                 np.array(mbs.GetObjectOutput(j, exu.OutputVariableType.TorqueLocal))) for j in jts]
    return d, D, r, torseurs


def verifier(nom, axes, d, D, r, F, M):
    err_inv = np.abs(INVARIANTS[nom](d, D)).max()
    bloq = np.array(axes, bool)
    mvt = np.concatenate([d, r])
    libres_bougent = bool((np.abs(mvt[~bloq]) > SEUIL_LIBRE).all()) if (~bloq).any() else True
    eff = np.concatenate([F, M])
    eff_libres = np.abs(eff[~bloq]).max() if (~bloq).any() else 0.0
    ok = err_inv < TOL and libres_bougent and eff_libres < TOL_EFFORT
    return ok, err_inv, libres_bougent, eff_libres


def main():
    tout_ok = True
    print(f"{'liaison':34} {'invariant':>10} {'libres':>7} {'eff. libres':>11}  verdict")
    for nom, axes in LIAISONS.items():
        if nom == "helicoidale":
            continue
        d, D, r, [(F, M)] = simuler([(PJ, axes)])
        ok, e, lb, el = verifier(nom, axes, d, D, r, F, M)
        tout_ok &= ok
        print(f"{nom:34} {e:10.1e} {str(lb):>7} {el:11.1e}  {'OK' if ok else 'ÉCHEC'}")

    # Linéaire rectiligne réalisée par association en parallèle de deux ponctuelles (même normale)
    a = Rj @ [0.1, 0, 0]
    d, D, r, tors = simuler([(PJ - a, LIAISONS["ponctuelle"]), (PJ + a, LIAISONS["ponctuelle"])])
    # torseur équivalent au centre, en base de liaison (les deux ForceLocal sont en base Rj)
    F = sum(t[0] for t in tors)
    M = sum(t[1] for t in tors) + np.cross([-0.1, 0, 0], tors[0][0]) + np.cross([0.1, 0, 0], tors[1][0])
    ok, e, lb, el = verifier("lineaire_rectiligne", LIAISONS["lineaire_rectiligne"], d, D, r, F, M)
    print(f"{'lineaire_rectiligne (2 ponctuelles)':34} {e:10.1e} {str(lb):>7} {el:11.1e}  {'OK' if ok else 'ÉCHEC'}")
    print("\nBILAN : la liaison linéaire rectiligne directe est attendue en ÉCHEC (grandes rotations) ;"
          " toutes les autres doivent être OK.")


if __name__ == "__main__":
    main()
