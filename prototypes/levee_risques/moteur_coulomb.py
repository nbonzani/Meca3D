"""Lot 1a, risque 3 : frottement de Coulomb (EX-15).

Formulation évaluée : ObjectConnectorRigidBodySpringDamper entre le bâti et le corps, repère de marqueur = repère de
la liaison (axe = x), avec springForceTorqueUserFunction qui renvoie
    force  : F_x = f·|N|·tanh(v_x / v_eps)          (glissière)
    couple : C_x = f·r·|R_rad|·tanh(w_x / v_eps)    (pivot)
où |N| (|R_rad|) = norme de la composante transverse de ForceLocal de la liaison parfaite correspondante
(multiplicateurs de Lagrange). Deux variantes de lecture de la réaction :
  - 'courant'  : réaction lue dans la configuration courante (itération de Newton en cours : boucle implicite
                 résolue par le point fixe de Newton) ;
  - 'pas_prec' : réaction figée au début du pas (PreStepUserFunction) : formulation explicite, retard d'un pas.
Jacobien : Exudyn dérive numériquement l'objet à user function ; la mise à jour de la matrice `damping` (pente à
l'origine d = f·|N|/v_eps) est donc facultative : le cas (b') montre des résultats identiques sans elle.

Cas (a) glissement f = 0,2 ; (b) adhérence f = 0,7 ; (c) pivot : disque, arrêt à t = ω0·R²/(2·f·r·g).
"""
import sys
from pathlib import Path

import numpy as np
import exudyn as exu
from exudyn.utilities import *  # noqa: F401,F403

sys.path.insert(0, str(Path(__file__).parent))
from commun import PIVOT, R_AXE_Z, reglages, utf8  # noqa: E402

G = 9.81


def _frottement(mbs, sol, corps, joint, rot_marker, f, v_eps, mode, mode_charge, rayon=1.0, jac=True):
    """Ajoute le connecteur de frottement. mode_charge : 'force' (glissière) ou 'couple' (pivot, rayon = r)."""
    m0 = mbs.AddMarker(MarkerBodyRigid(bodyNumber=sol, localPosition=[0, 0, 0],
                                       localHT=exu.HT(rotation=rot_marker, translation=[0, 0, 0])))
    m1 = mbs.AddMarker(MarkerBodyRigid(bodyNumber=corps, localPosition=[0, 0, 0]))
    nd = mbs.AddNode(NodeGenericData(initialCoordinates=[0], numberOfDataCoordinates=1))
    etat = dict(N=0.0, v=0.0)
    idx = 0 if mode_charge == "force" else 3

    def reaction_courante():
        F = mbs.GetObjectOutput(joint, exu.OutputVariableType.ForceLocal)
        return float(np.hypot(F[1], F[2]))

    def uf(mbs_, t, itemNumber, u, rot, v, w, k, d, rj0, rj1, off):
        N = reaction_courante() if mode == "courant" else etat["N"]
        vit = v[0] if mode_charge == "force" else w[0]
        out = [0.0] * 6
        out[idx] = f * rayon * N * np.tanh(vit / v_eps)
        return out

    damp = np.zeros((6, 6))
    c = mbs.AddObject(ObjectConnectorRigidBodySpringDamper(
        markerNumbers=[m0, m1], nodeNumber=nd, stiffness=np.zeros((6, 6)), damping=damp,
        springForceTorqueUserFunction=uf))

    def prestep(mbs_, t):
        etat["N"] = reaction_courante()
        dd = np.zeros((6, 6))
        dd[idx, idx] = f * rayon * etat["N"] / v_eps
        if jac:
            mbs_.SetObjectParameter(c, "damping", dd)
        return True

    mbs.SetPreStepUserFunction(prestep)
    return c, etat


# ----------------------------------------------------------------- cas (a) et (b) : bloc sur plan incliné
def bloc(f, v_eps=1e-3, mode="courant", pas=1e-3, t_fin=1.0, theta_deg=30.0, jacobien_damping=True):
    th = np.radians(theta_deg)
    SC = exu.SystemContainer()
    mbs = SC.AddSystem()
    sol = mbs.AddObject(ObjectGround())
    A = RotationMatrixZ(-th)                       # x local -> direction de plus grande pente (cos, -sin, 0)
    b = mbs.CreateRigidBody(inertia=InertiaCuboid(density=1000.0, sideLengths=[0.1, 0.1, 0.1]),
                            referencePosition=[0, 0, 0], referenceRotationMatrix=A, gravity=[0, -G, 0])
    j = mbs.CreateGenericJoint(itemNumbers=[sol, b], position=[0, 0, 0], rotationMatrixAxes=A,
                               constrainedAxes=[0, 1, 1, 1, 1, 1], show=False)
    if f > 0:
        _frottement(mbs, sol, b, j, A, f, v_eps, mode, "force", jac=jacobien_damping)
    s_pos = mbs.AddSensor(SensorBody(bodyNumber=b, storeInternal=True, outputVariableType=exu.OutputVariableType.Position))
    s_acc = mbs.AddSensor(SensorBody(bodyNumber=b, storeInternal=True, outputVariableType=exu.OutputVariableType.Acceleration))
    s_vel = mbs.AddSensor(SensorBody(bodyNumber=b, storeInternal=True, outputVariableType=exu.OutputVariableType.Velocity))
    mbs.Assemble()
    mbs.SolveDynamic(reglages(t_fin, int(round(t_fin / pas))))
    u = np.array([np.cos(th), -np.sin(th), 0.0])
    pos = mbs.GetSensorStoredData(s_pos)[:, 1:4] @ u
    vel = mbs.GetSensorStoredData(s_vel)[:, 1:4] @ u
    acc = mbs.GetSensorStoredData(s_acc)[:, 1:4] @ u
    return dict(x=pos[-1], xmax=np.max(np.abs(pos)), v=vel[-1], a=acc[-1], a_moy=(vel[-1] - vel[len(vel) // 2]) /
                (0.5 * t_fin))


# ----------------------------------------------------------------- cas (c) : disque sur pivot frottant
R_D, E_D, R_AX, F_D, W0 = 0.1, 0.02, 0.005, 0.1, 10.0
T_ARRET = W0 * R_D**2 / (2 * F_D * R_AX * G)       # 10,194 s


def disque(v_eps=1e-2, mode="courant", pas=5e-3, t_fin=12.0, f=F_D):
    SC = exu.SystemContainer()
    mbs = SC.AddSystem()
    sol = mbs.AddObject(ObjectGround())
    b = mbs.CreateRigidBody(inertia=InertiaCylinder(density=7800.0, length=E_D, outerRadius=R_D, axis=2),
                            referencePosition=[0, 0, 0], gravity=[0, -G, 0],
                            initialAngularVelocity=[0, 0, W0])
    j = mbs.CreateGenericJoint(itemNumbers=[sol, b], position=[0, 0, 0], rotationMatrixAxes=R_AXE_Z,
                               constrainedAxes=PIVOT, show=False)
    _frottement(mbs, sol, b, j, R_AXE_Z, f, v_eps, mode, "couple", rayon=R_AX)
    s_w = mbs.AddSensor(SensorBody(bodyNumber=b, storeInternal=True,
                                   outputVariableType=exu.OutputVariableType.AngularVelocity))
    ss = reglages(t_fin, int(round(t_fin / pas)), ecriture=pas)
    mbs.Assemble()
    mbs.SolveDynamic(ss)
    d = mbs.GetSensorStoredData(s_w)
    t, w = d[:, 0], d[:, 3]
    return t, w


# ----------------------------------------------------------------- cas (d) : pendule, réaction couplée au frottement
def pendule(f=0.3, rayon=0.02, v_eps=1e-2, mode="courant", pas=1e-3, t_fin=3.0):
    """Barre pesante lâchée à l'horizontale ; la réaction du pivot dépend de l'accélération donc du frottement
    (boucle implicite réelle). Retourne (t, angle)."""
    L = 0.5
    SC = exu.SystemContainer()
    mbs = SC.AddSystem()
    sol = mbs.AddObject(ObjectGround())
    b = mbs.CreateRigidBody(inertia=InertiaCuboid(density=7800.0, sideLengths=[L, 0.02, 0.02]),
                            referencePosition=[L / 2, 0, 0], gravity=[0, -G, 0])
    j = mbs.CreateGenericJoint(itemNumbers=[sol, b], position=[0, 0, 0], rotationMatrixAxes=R_AXE_Z,
                               constrainedAxes=PIVOT, show=False)
    _frottement(mbs, sol, b, j, R_AXE_Z, f, v_eps, mode, "couple", rayon=rayon)
    s_r = mbs.AddSensor(SensorBody(bodyNumber=b, storeInternal=True, outputVariableType=exu.OutputVariableType.RotationMatrix))
    mbs.Assemble()
    mbs.SolveDynamic(reglages(t_fin, int(round(t_fin / pas)), ecriture=pas))
    d = mbs.GetSensorStoredData(s_r)
    return d[:, 0], np.unwrap(np.arctan2(d[:, 4], d[:, 1]))


def t_arret(t, w, seuil=1e-2):
    """Premier instant où |ω| < seuil (rad/s)."""
    i = np.argmax(np.abs(w) < seuil)
    if np.abs(w[i]) >= seuil:
        return np.nan
    return t[i]


if __name__ == "__main__":
    utf8()
    th = np.radians(30.0)
    a_att = G * (np.sin(th) - 0.2 * np.cos(th))
    print("=== Frottement de Coulomb, EX-15 ===")
    print("Valeurs SPEC : a = %.5f m/s2, x(1 s) = %.5f m ; tan 30° = %.4f ; t_arret = %.3f s"
          % (a_att, a_att / 2, np.tan(th), T_ARRET))
    print("-- (a) glissement f = 0,2, départ au repos")
    for mode in ("courant", "pas_prec"):
        for pas in (1e-2, 2e-3, 1e-3):
            for ve in (1e-2, 1e-3, 1e-4):
                r = bloc(0.2, v_eps=ve, mode=mode, pas=pas)
                print("   %-8s h=%.0e v_eps=%.0e : a = %.5f (écart rel. %.2e), x(1 s) = %.5f (écart rel. %.2e)"
                      % (mode, pas, ve, r["a"], abs(r["a"] - a_att) / a_att, r["x"], abs(r["x"] - a_att / 2) / (a_att / 2)))
    print("-- (b) adhérence f = 0,7 (critère : déplacement sur 1 s < 1e-3 m)")
    for mode in ("courant", "pas_prec"):
        for pas in (1e-2, 2e-3, 1e-3):
            for ve in (1e-2, 1e-3, 1e-4, 1e-5):
                r = bloc(0.7, v_eps=ve, mode=mode, pas=pas)
                print("   %-8s h=%.0e v_eps=%.0e : x(1 s) = %.3e m, x_max = %.3e m, v = %.2e m/s, a = %.2e -> %s"
                      % (mode, pas, ve, r["x"], r["xmax"], r["v"], r["a"], "OK" if r["xmax"] < 1e-3 else "KO"))
    print("-- (c) disque sur pivot frottant : t_arret attendu %.3f s (2 %%)" % T_ARRET)
    for mode in ("courant", "pas_prec"):
        for pas in (2e-2, 5e-3, 1e-3):
            for ve in (1e-1, 1e-2, 1e-3):
                t, w = disque(v_eps=ve, mode=mode, pas=pas)
                ta = t_arret(t, w)
                print("   %-8s h=%.0e v_eps=%.0e : t(|ω|<0,01) = %.3f s (écart %.2f %%), ω(5 s) = %.4f (attendu %.4f)"
                      % (mode, pas, ve, ta, 100 * abs(ta - T_ARRET) / T_ARRET,
                         np.interp(5.0, t, w), W0 - 5.0 * W0 / T_ARRET))
    print("-- (b') adhérence sans jacobien d'amortissement (damping = 0 dans le connecteur)")
    for pas in (1e-2, 1e-3):
        for ve in (1e-3, 1e-4):
            try:
                r = bloc(0.7, v_eps=ve, mode="courant", pas=pas, jacobien_damping=False)
                print("   h=%.0e v_eps=%.0e : x_max = %.3e m, a = %.2e" % (pas, ve, r["xmax"], r["a"]))
            except Exception as e:  # noqa: BLE001
                print("   h=%.0e v_eps=%.0e : ÉCHEC du solveur (%s)" % (pas, ve, str(e)[:60].replace(chr(10), " ")))
    print("-- (d) pendule à frottement de pivot (réaction couplée au frottement) : angle à t = 3 s (rad)")
    t, ref = pendule(mode="courant", pas=1e-4)
    a_ref = ref[-1]
    print("   référence (courant, h=1e-4, v_eps=1e-2) : %.6f rad" % a_ref)
    for mode in ("courant", "pas_prec"):
        for pas in (1e-2, 5e-3, 1e-3):
            t, ang = pendule(mode=mode, pas=pas)
            print("   %-8s h=%.0e : angle = %.6f rad, écart à la référence = %.2e rad" % (mode, pas, ang[-1], abs(ang[-1] - a_ref)))
