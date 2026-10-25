"""Lot 1a, risque 4 : rendement des couplages (EX-16).

Réducteur Z1 = 20, Z2 = 60 (couplage vitesse, cf. moteur_engrenage.py) + couples de perte appliqués par
deux LoadTorqueVector à loadVectorUserFunction, calculés à partir du multiplicateur λ du couplage :
  couple exercé par la contrainte sur la sortie  T_s = -λ ;  sur l'entrée  T_e = -k·λ  (g = ω2 + k·ω1)
  puissance entrante  P_e = -T_e·ω_e = k·λ·ω_e
  sens direct  (P_e > 0) : couple de perte sur la SORTIE  = -(1-η)·T_s   -> P_s = η·P_e
  sens inverse (P_e < 0) : couple de perte sur l'ENTRÉE   = -(1-η)·T_e   -> |P_e| = η·|P_s|
Les deux sont pondérés par w = ½(1 + tanh(P_e/P_eps)) et (1-w) pour que le changement de sens soit continu.
Variante 'avant_seul' (contre-exemple) : perte toujours sur la sortie, sans distinction de sens.

Cas 1 : Ce = 1 N·m moteur, charge visqueuse sur la sortie, régime établi : Cs = 3·η = 2,85 N·m.
Cas 2 : deux phases, entrée à vitesse imposée (moteur puis frein) ; phase 1 : charge résistante sur la sortie
        (moteur) ; phase 2 : couple entraînant sur la sortie (la charge entraîne, l'entrée freine).
"""
import sys
from pathlib import Path

import numpy as np
import exudyn as exu
from exudyn.utilities import *  # noqa: F401,F403

sys.path.insert(0, str(Path(__file__).parent))
from commun import PIVOT, PIVOT_BLOQUE, R_AXE_Z, couplage_vitesse, lambda_couplage, reglages, utf8  # noqa: E402

K = 20 / 60
MODULE = 0.002
R1, R2 = 20 * MODULE / 2, 60 * MODULE / 2
ENTRAXE = R1 + R2
EP, RHO = 0.010, 7800.0
P_EPS = 0.5          # W, largeur de la transition de sens de puissance
OMEGA_E = 30.0
T_MONTEE = 0.2


def th_t(t):
    return OMEGA_E / 2 * (1 - np.cos(np.pi * t / T_MONTEE)) if t < T_MONTEE else OMEGA_E


def reducteur(mbs, eta, mode_perte="deux_sens", imposer_entree=False, lecture="courant"):
    sol = mbs.AddObject(ObjectGround())
    b1 = mbs.CreateRigidBody(inertia=InertiaCylinder(density=RHO, length=EP, outerRadius=R1, axis=2),
                             referencePosition=[0, 0, 0])
    b2 = mbs.CreateRigidBody(inertia=InertiaCylinder(density=RHO, length=EP, outerRadius=R2, axis=2),
                             referencePosition=[ENTRAXE, 0, 0])
    j1 = mbs.CreateGenericJoint(itemNumbers=[sol, b1], position=[0, 0, 0], rotationMatrixAxes=R_AXE_Z,
                                constrainedAxes=PIVOT, show=False)
    j2 = mbs.CreateGenericJoint(itemNumbers=[sol, b2], position=[ENTRAXE, 0, 0], rotationMatrixAxes=R_AXE_Z,
                                constrainedAxes=PIVOT, show=False)
    cpl = couplage_vitesse(mbs, b1, b2, [0, 0, 0, 0, 0, K], [0, 0, 0, 0, 0, 1])
    pil = couplage_vitesse(mbs, b1, None, [0, 0, 0, 0, 0, 1], None, terme_t=th_t) if imposer_entree else None
    memo = dict(lam=0.0)

    def lam():
        return lambda_couplage(mbs, cpl) if lecture == "courant" else memo["lam"]

    def w_e():
        return mbs.GetObjectOutputBody(b1, exu.OutputVariableType.AngularVelocity)[2]

    def poids_direct():
        if mode_perte == "avant_seul":
            return 1.0
        pe = K * lam() * w_e()
        return 0.5 * (1 + np.tanh(pe / P_EPS))

    def perte_sortie(mbs_, t, load):
        return [0, 0, (1 - eta) * poids_direct() * lam()]            # -(1-η)·w·T_s,  T_s = -λ

    def perte_entree(mbs_, t, load):
        return [0, 0, (1 - eta) * (1 - poids_direct()) * K * lam()]  # -(1-η)(1-w)·T_e, T_e = -k·λ

    mbs.CreateTorque(itemNumber=b2, loadVector=[0, 0, 0], bodyFixed=False, loadVectorUserFunction=perte_sortie)
    mbs.CreateTorque(itemNumber=b1, loadVector=[0, 0, 0], bodyFixed=False, loadVectorUserFunction=perte_entree)
    if lecture != "courant":
        def prestep(mbs_, t):
            memo["lam"] = lambda_couplage(mbs_, cpl)
            return True
        mbs.SetPreStepUserFunction(prestep)
    return b1, b2, cpl, pil


def cas1(eta=0.95, ce=1.0, c=0.3, pas=1e-3, t_fin=0.5, lecture="courant"):
    SC = exu.SystemContainer()
    mbs = SC.AddSystem()
    b1, b2, cpl, _ = reducteur(mbs, eta, lecture=lecture)
    mbs.CreateTorque(itemNumber=b1, loadVector=[0, 0, ce], bodyFixed=False)
    mbs.CreateTorque(itemNumber=b2, loadVector=[0, 0, 0], bodyFixed=False,
                     loadVectorUserFunction=lambda mbs_, t, load: [0, 0, -c * mbs_.GetObjectOutputBody(
                         b2, exu.OutputVariableType.AngularVelocity)[2]])
    s1 = mbs.AddSensor(SensorBody(bodyNumber=b1, storeInternal=True, outputVariableType=exu.OutputVariableType.AngularVelocity))
    s2 = mbs.AddSensor(SensorBody(bodyNumber=b2, storeInternal=True, outputVariableType=exu.OutputVariableType.AngularVelocity))
    mbs.Assemble()
    mbs.SolveDynamic(reglages(t_fin, int(round(t_fin / pas))))
    w1 = mbs.GetSensorStoredData(s1)[-1, 3]
    w2 = mbs.GetSensorStoredData(s2)[-1, 3]
    return dict(w_e=w1, w_s=w2, cs=c * abs(w2), puiss_e=ce * w1, puiss_s=c * w2 * w2)


def cas2(eta=0.95, c=0.3, td=3.0, mode_perte="deux_sens", pas=1e-3, lecture="courant", p_eps=None):
    """Deux phases à entrée imposée (30 rad/s) : 0-1 s charge visqueuse c (moteur), 1-2 s couple entraînant td."""
    SC = exu.SystemContainer()
    mbs = SC.AddSystem()
    b1, b2, cpl, pil = reducteur(mbs, eta, mode_perte, imposer_entree=True, lecture=lecture)

    def charge(mbs_, t, load):
        wz = mbs_.GetObjectOutputBody(b2, exu.OutputVariableType.AngularVelocity)[2]
        if t < 1.0:
            return [0, 0, -c * wz]          # résistant
        return [0, 0, -td]                  # ω_s < 0 : couple dans le sens du mouvement (entraînant)

    mbs.CreateTorque(itemNumber=b2, loadVector=[0, 0, 0], bodyFixed=False, loadVectorUserFunction=charge)
    ts, lp, le = [], [], []

    def poststep(mbs_, t):
        ts.append(t)
        lp.append(lambda_couplage(mbs_, pil))
        le.append(mbs_.GetObjectOutputBody(b1, exu.OutputVariableType.AngularVelocity)[2])
        return True

    mbs.SetPostStepUserFunction(poststep)
    mbs.Assemble()
    mbs.SolveDynamic(reglages(2.0, int(round(2.0 / pas))))
    ts, lp, le = map(np.array, (ts, lp, le))
    res = {}
    for nom, (a, b) in dict(phase1=(0.85, 1.0), phase2=(1.85, 2.0)).items():
        m = (ts > a) & (ts <= b)
        # couple exercé par la commande d'entrée sur l'arbre = -λ_pilotage ; puissance = couple·ω_e
        res[nom] = dict(ce=float(np.mean(np.abs(lp[m]))), signe=float(np.sign(np.mean(lp[m]))), we=float(np.mean(le[m])))
    return res


if __name__ == "__main__":
    utf8()
    print("=== Rendement du réducteur, EX-16 ===")
    for lecture in ("courant", "pas_prec"):
        r = cas1(lecture=lecture)
        print("Cas 1 (%s) : Ce = 1 N·m, η = 0,95 : ω_e = %.4f, ω_s = %.4f rad/s ; Cs = %.6f N·m (attendu 2,85 ; écart abs %.2e)"
              % (lecture, r["w_e"], r["w_s"], r["cs"], abs(r["cs"] - 2.85)))
        print("   puissance entrée = %.4f W, sortie = %.4f W, rapport = %.6f (attendu 0,95)"
              % (r["puiss_e"], r["puiss_s"], r["puiss_s"] / r["puiss_e"]))
    for eta in (1.0, 0.5):
        r = cas1(eta=eta)
        print("Cas 1 bis : η = %.2f : Cs = %.6f N·m (attendu %.4f)" % (eta, r["cs"], 3 * eta))
    print("Cas 2 : entrée imposée 30 rad/s ; phase 1 (moteur) charge visqueuse c = 0,3 (Cs = 3 N·m) ; "
          "phase 2 (frein) couple entraînant de 3 N·m sur la sortie")
    eta = 0.95
    att1 = 3.0 / (3 * eta)       # moteur : Ce = Cs/(η·3)
    att2 = eta * 3.0 / 3          # frein : couple absorbé à l'entrée = η·Td/3
    for mode in ("deux_sens", "avant_seul"):
        for lecture in ("courant", "pas_prec"):
            if mode == "avant_seul" and lecture == "pas_prec":
                continue
            r = cas2(eta=eta, mode_perte=mode, lecture=lecture)
            print("   [%s, %s]" % (mode, lecture))
            print("   phase 1 : couple d'entrée = %.5f N·m (attendu %.5f), signe %+d, ω_e = %.3f"
                  % (r["phase1"]["ce"], att1, r["phase1"]["signe"], r["phase1"]["we"]))
            print("   phase 2 : couple d'entrée = %.5f N·m (attendu %.5f), signe %+d, ω_e = %.3f"
                  % (r["phase2"]["ce"], att2, r["phase2"]["signe"], r["phase2"]["we"]))
