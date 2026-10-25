"""Lot 1a, risque 1 : engrenage (EX-14).

Deux pivots sur le bâti (axes z parallèles), couplage omega2 = -k·omega1, k = Z1/Z2 = 1/3.
Formulation : ObjectConnectorCoordinateVector au niveau vitesse (constraintUserFunction + jacobianUserFunction)
sur les coordonnées nodales (paramètres d'Euler) des deux corps ; voir commun.couplage_vitesse.

Cas A : omega_e = 30 rad/s imposé (pivot motorisé par offsetUserFunction) -> omega_s attendu = -10 rad/s (|.| = 10).
Cas B : Ce = 1 N·m moteur, couple résistant visqueux en sortie, régime établi -> Cs attendu = 3 N·m.
"""
import sys
from pathlib import Path

import numpy as np
import exudyn as exu
from exudyn.utilities import *  # noqa: F401,F403

sys.path.insert(0, str(Path(__file__).parent))
from commun import PIVOT, PIVOT_BLOQUE, R_AXE_Z, couplage_vitesse, lambda_couplage, reglages, utf8  # noqa: E402

Z1, Z2 = 20, 60
K = Z1 / Z2
MODULE = 0.002
R1, R2 = Z1 * MODULE / 2, Z2 * MODULE / 2   # rayons primitifs
EP = 0.010
RHO = 7800.0
ENTRAXE = R1 + R2
OMEGA_E = 30.0
T_MONTEE = 0.2


def th(t):
    if t < T_MONTEE:
        return OMEGA_E / 2 * (t - T_MONTEE / np.pi * np.sin(np.pi * t / T_MONTEE))
    return OMEGA_E / 2 * T_MONTEE + OMEGA_E * (t - T_MONTEE)


def th_t(t):
    return OMEGA_E / 2 * (1 - np.cos(np.pi * t / T_MONTEE)) if t < T_MONTEE else OMEGA_E


def corps_et_pivots(mbs, mode):
    """mode : 'position' (pivot motorisé par offsetUserFunction), 'vitesse' (pilotage par contrainte vitesse), 'libre'."""
    sol = mbs.AddObject(ObjectGround())
    b1 = mbs.CreateRigidBody(inertia=InertiaCylinder(density=RHO, length=EP, outerRadius=R1, axis=2),
                             referencePosition=[0, 0, 0])
    b2 = mbs.CreateRigidBody(inertia=InertiaCylinder(density=RHO, length=EP, outerRadius=R2, axis=2),
                             referencePosition=[ENTRAXE, 0, 0])
    if mode == "position":
        j1 = mbs.CreateGenericJoint(itemNumbers=[sol, b1], position=[0, 0, 0], rotationMatrixAxes=R_AXE_Z,
                                    constrainedAxes=PIVOT_BLOQUE,
                                    offsetUserFunction=lambda mbs_, t, i, p: [0, 0, 0, th(t), 0, 0],
                                    offsetUserFunction_t=lambda mbs_, t, i, p: [0, 0, 0, th_t(t), 0, 0],
                                    show=False)
    else:
        j1 = mbs.CreateGenericJoint(itemNumbers=[sol, b1], position=[0, 0, 0], rotationMatrixAxes=R_AXE_Z,
                                    constrainedAxes=PIVOT, show=False)
    j2 = mbs.CreateGenericJoint(itemNumbers=[sol, b2], position=[ENTRAXE, 0, 0], rotationMatrixAxes=R_AXE_Z,
                                constrainedAxes=PIVOT, show=False)
    return b1, b2, j1, j2


def angle_deroule(donnees):
    """Angle (rad, déroulé) à partir d'un capteur RotationMatrix stocké."""
    R = donnees[:, 1:10]
    return np.unwrap(np.arctan2(R[:, 3], R[:, 0]))


def cas_a(pas=1e-3, t_fin=1.0, mode="position"):
    SC = exu.SystemContainer()
    mbs = SC.AddSystem()
    b1, b2, j1, j2 = corps_et_pivots(mbs, mode)
    if mode == "vitesse":
        couplage_vitesse(mbs, b1, None, [0, 0, 0, 0, 0, 1], None, terme_t=th_t)
    cpl = couplage_vitesse(mbs, b1, b2, [0, 0, 0, 0, 0, K], [0, 0, 0, 0, 0, 1])   # w2 + k w1 = 0
    s1 = mbs.AddSensor(SensorBody(bodyNumber=b1, storeInternal=True,
                                  outputVariableType=exu.OutputVariableType.AngularVelocity))
    s2 = mbs.AddSensor(SensorBody(bodyNumber=b2, storeInternal=True,
                                  outputVariableType=exu.OutputVariableType.AngularVelocity))
    a2 = mbs.AddSensor(SensorBody(bodyNumber=b2, storeInternal=True,
                                  outputVariableType=exu.OutputVariableType.RotationMatrix))
    a1 = mbs.AddSensor(SensorBody(bodyNumber=b1, storeInternal=True,
                                  outputVariableType=exu.OutputVariableType.RotationMatrix))
    mbs.Assemble()
    mbs.SolveDynamic(reglages(t_fin, int(round(t_fin / pas))))
    w1 = mbs.GetSensorStoredData(s1)[-1, 3]
    w2 = mbs.GetSensorStoredData(s2)[-1, 3]
    ang1 = angle_deroule(mbs.GetSensorStoredData(a1))[-1]
    ang2 = angle_deroule(mbs.GetSensorStoredData(a2))[-1]
    return dict(w_e=w1, w_s=w2, ecart_w=abs(abs(w2) - 10.0), ecart_rapport=abs(w2 + K * w1),
                derive_angle=ang2 + K * ang1, lam=lambda_couplage(mbs, cpl))


def cas_b(pas=1e-3, t_fin=0.5, c=0.3, ce=1.0):
    SC = exu.SystemContainer()
    mbs = SC.AddSystem()
    b1, b2, j1, j2 = corps_et_pivots(mbs, 'libre')
    cpl = couplage_vitesse(mbs, b1, b2, [0, 0, 0, 0, 0, K], [0, 0, 0, 0, 0, 1])
    mbs.CreateTorque(itemNumber=b1, loadVector=[0, 0, ce], bodyFixed=False)

    def resistant(mbs_, t, load):
        wz = mbs_.GetObjectOutputBody(b2, exu.OutputVariableType.AngularVelocity)[2]
        return [0, 0, -c * wz]

    mbs.CreateTorque(itemNumber=b2, loadVector=[0, 0, 0], bodyFixed=False, loadVectorUserFunction=resistant)
    s1 = mbs.AddSensor(SensorBody(bodyNumber=b1, storeInternal=True,
                                  outputVariableType=exu.OutputVariableType.AngularVelocity))
    s2 = mbs.AddSensor(SensorBody(bodyNumber=b2, storeInternal=True,
                                  outputVariableType=exu.OutputVariableType.AngularVelocity))
    sa2 = mbs.AddSensor(SensorBody(bodyNumber=b2, storeInternal=True,
                                   outputVariableType=exu.OutputVariableType.AngularAcceleration))
    sf2 = mbs.AddSensor(SensorObject(objectNumber=j2, storeInternal=True,
                                     outputVariableType=exu.OutputVariableType.ForceLocal))
    mbs.Assemble()
    mbs.SolveDynamic(reglages(t_fin, int(round(t_fin / pas))))
    w1 = mbs.GetSensorStoredData(s1)[-1, 3]
    w2 = mbs.GetSensorStoredData(s2)[-1, 3]
    al2 = mbs.GetSensorStoredData(sa2)[-1, 3]
    f2 = mbs.GetSensorStoredData(sf2)[-1, 1:4]
    cs_charge = c * abs(w2)            # couple résistant appliqué = couple que l'engrenage fournit à la sortie
    return dict(w_e=w1, w_s=w2, acc_s=al2, cs_charge=cs_charge, lam=lambda_couplage(mbs, cpl), f_pivot_sortie=f2)


if __name__ == "__main__":
    utf8()
    print("=== Engrenage Z1=20, Z2=60 (k = 1/3), EX-14 ===")
    for mode in ("position", "vitesse"):
        a = cas_a(mode=mode)
        print("Cas A (%s) : omega_e mesuré = %.9f rad/s (imposé 30), omega_s = %.9f (attendu -10)"
              % (mode, a["w_e"], a["w_s"]))
        print("   |omega_s| - 10 = %.3e rad/s (critère 1e-6 -> %s) ; omega_s + k·omega_e = %.3e (rapport exact ?)"
              % (a["ecart_w"], "OK" if a["ecart_w"] < 1e-6 else "KO", a["ecart_rapport"]))
        print("   dérive angulaire phi2 + k·phi1 après 1 s = %.3e rad ; lambda = %.3e N·m"
              % (a["derive_angle"], a["lam"]))
        for pas in (2e-3, 5e-4):
            r = cas_a(pas=pas, mode=mode)
            print("   pas %.0e : |omega_s|-10 = %.3e ; |omega_s + k·omega_e| = %.3e ; dérive angle = %.3e"
                  % (pas, r["ecart_w"], r["ecart_rapport"], r["derive_angle"]))
    for tf in (5.0, 20.0):
        r = cas_a(t_fin=tf, mode="vitesse")
        print("   dérive angulaire à t = %.0f s (pilotage vitesse, h = 1e-3) : %.3e rad ; |omega_s|-10 = %.2e"
              % (tf, r["derive_angle"], r["ecart_w"]))
    b = cas_b()
    print("Cas B : Ce = 1 N·m moteur, charge visqueuse c = 0.3 N·m·s/rad en sortie")
    print("   omega_e = %.6f (attendu 30), omega_s = %.6f (attendu -10), acc_s = %.2e rad/s2"
          % (b["w_e"], b["w_s"], b["acc_s"]))
    print("   Cs (couple résistant appliqué en sortie) = %.6f N·m (attendu 3, tol 1e-3 -> %s)"
          % (b["cs_charge"], "OK" if abs(b["cs_charge"] - 3.0) < 3e-3 else "KO"))
    print("   multiplicateur de Lagrange lu dans le connecteur = %.6f N·m (|.| attendu 3)" % b["lam"])
    print("   réaction du pivot de sortie (ForceLocal) = %s N (attendu ~0 : pas de poussée radiale)"
          % np.array2string(b["f_pivot_sortie"], precision=4))
