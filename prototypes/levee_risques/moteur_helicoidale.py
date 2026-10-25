"""Lot 1a, risque 2 : liaison hélicoïdale et couplage vis-écrou (EX-14).

Hélicoïdale = pivot glissant [0,1,1,0,1,1] (axe x) + couplage au niveau vitesse  v_x - (p/2π)·ω_x = 0
(commun.couplage_vitesse, un seul corps : l'écrou est le bâti).

Cas 1 : ω = 10 rad/s imposé (contrainte vitesse supplémentaire) -> v attendue = p·ω/2π = 7,9577 mm/s.
Cas 2 : couple moteur 2 N·m sur la vis, effort résistant axial F0 = 2π·C/p = 2 513,27 N -> équilibre (a = α = 0),
        effort axial lu dans le multiplicateur du couplage = 2 513,27 N (1e-3) ; sensibilité à F0·(1 ± 1e-3).
Cas 3 : même chargement, ω = 10 rad/s imposé -> le multiplicateur du pilotage doit être nul (équilibre).
"""
import sys
from pathlib import Path

import numpy as np
import exudyn as exu
from exudyn.utilities import *  # noqa: F401,F403

sys.path.insert(0, str(Path(__file__).parent))
from commun import PIVOT_GLISSANT, R_AXE_X, couplage_vitesse, lambda_couplage, reglages, utf8  # noqa: E402

P = 0.005
PAS_HEL = P / (2 * np.pi)          # m/rad
OMEGA = 10.0
T_MONTEE = 0.2
C_MOTEUR = 2.0
F_EQ = 2 * np.pi * C_MOTEUR / P    # 2513,27 N


def th_t(t):
    return OMEGA / 2 * (1 - np.cos(np.pi * t / T_MONTEE)) if t < T_MONTEE else OMEGA


def modele(pilote, couple=0.0, force=0.0):
    SC = exu.SystemContainer()
    mbs = SC.AddSystem()
    sol = mbs.AddObject(ObjectGround())
    vis = mbs.CreateRigidBody(inertia=InertiaCylinder(density=7800, length=0.1, outerRadius=0.01, axis=0),
                              referencePosition=[0, 0, 0])
    mbs.CreateGenericJoint(itemNumbers=[sol, vis], position=[0, 0, 0], rotationMatrixAxes=R_AXE_X,
                           constrainedAxes=PIVOT_GLISSANT, show=False)
    cpl = couplage_vitesse(mbs, vis, None, [1, 0, 0, -PAS_HEL, 0, 0], None)
    pil = couplage_vitesse(mbs, vis, None, [0, 0, 0, 1, 0, 0], None, terme_t=th_t) if pilote else None
    if couple:
        mbs.CreateTorque(itemNumber=vis, loadVector=[couple, 0, 0], bodyFixed=False)
    if force:
        mbs.CreateForce(itemNumber=vis, loadVector=[-force, 0, 0])
    sv = mbs.AddSensor(SensorBody(bodyNumber=vis, storeInternal=True, outputVariableType=exu.OutputVariableType.Velocity))
    sp = mbs.AddSensor(SensorBody(bodyNumber=vis, storeInternal=True, outputVariableType=exu.OutputVariableType.Position))
    sw = mbs.AddSensor(SensorBody(bodyNumber=vis, storeInternal=True,
                                  outputVariableType=exu.OutputVariableType.AngularVelocity))
    sa = mbs.AddSensor(SensorBody(bodyNumber=vis, storeInternal=True,
                                  outputVariableType=exu.OutputVariableType.Acceleration))
    sal = mbs.AddSensor(SensorBody(bodyNumber=vis, storeInternal=True,
                                   outputVariableType=exu.OutputVariableType.AngularAcceleration))
    return mbs, cpl, pil, dict(v=sv, p=sp, w=sw, a=sa, al=sal)


def lancer(pilote, couple=0.0, force=0.0, t_fin=1.0, pas=1e-3):
    mbs, cpl, pil, s = modele(pilote, couple, force)
    mbs.Assemble()
    mbs.SolveDynamic(reglages(t_fin, int(round(t_fin / pas))))
    d = {k: mbs.GetSensorStoredData(v) for k, v in s.items()}
    out = dict(v=d["v"][-1, 1], x=d["p"][-1, 1], w=d["w"][-1, 1], a=d["a"][-1, 1], al=d["al"][-1, 1],
               lam_cpl=lambda_couplage(mbs, cpl), lam_pil=lambda_couplage(mbs, pil) if pil is not None else None,
               xmax=np.max(np.abs(d["p"][:, 1])))
    return out


if __name__ == "__main__":
    utf8()
    print("=== Hélicoïdale / vis-écrou p = 5 mm, EX-14 ===")
    v_att = P * OMEGA / (2 * np.pi)
    r = lancer(True)
    print("Cas 1 : ω = %.9f rad/s ; v = %.6f mm/s (attendu %.4f)  écart relatif = %.2e"
          % (r["w"], r["v"] * 1e3, v_att * 1e3, abs(r["v"] - v_att) / v_att))
    # x(t) attendu = p/2π · θ(t) ; θ(1 s) = ω/2·T_MONTEE + ω·(1 - T_MONTEE)
    th_fin = OMEGA / 2 * T_MONTEE + OMEGA * (1.0 - T_MONTEE)
    print("        x(1 s) = %.6f mm ; attendu p·θ/2π = %.6f mm ; écart relatif = %.2e"
          % (r["x"] * 1e3, PAS_HEL * th_fin * 1e3, abs(r["x"] - PAS_HEL * th_fin) / (PAS_HEL * th_fin)))
    print("Cas 2 : C = 2 N·m, F0 = %.4f N (attendu 2513,27), équilibre libre (départ au repos)" % F_EQ)
    r = lancer(False, couple=C_MOTEUR, force=F_EQ)
    print("        x_max = %.3e m, |v| = %.3e m/s, |a| = %.3e m/s2, |α| = %.3e rad/s2"
          % (r["xmax"], abs(r["v"]), abs(r["a"]), abs(r["al"])))
    print("        effort axial lu dans le couplage = %.4f N (attendu 2513,27 ; écart relatif %.2e -> %s)"
          % (r["lam_cpl"], abs(abs(r["lam_cpl"]) - F_EQ) / F_EQ,
             "OK" if abs(abs(r["lam_cpl"]) - F_EQ) / F_EQ < 1e-3 else "KO"))
    for fac in (1.001, 0.999):
        r2 = lancer(False, couple=C_MOTEUR, force=F_EQ * fac, t_fin=0.1)
        print("        sensibilité : F0 x %.3f -> α = %.1f rad/s2, x(0,1 s) = %.3e m (déséquilibre détectable)"
              % (fac, r2["al"], r2["x"]))
    print("Cas 3 : mêmes charges, ω = 10 rad/s imposé : multiplicateurs")
    r = lancer(True, couple=C_MOTEUR, force=F_EQ)
    print("        pilotage : %.3e N·m (nul = équilibre) ; couplage = %.4f N (attendu 2513,27)"
          % (r["lam_pil"], r["lam_cpl"]))
    r = lancer(True, couple=C_MOTEUR, force=F_EQ * 1.001)
    print("        F0 x 1,001 : pilotage = %.4f N·m (écart attendu ≈ 2·1e-3 = 2e-3 N·m)" % r["lam_pil"])
