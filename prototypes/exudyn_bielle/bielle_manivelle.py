"""Bielle-manivelle : simulation Exudyn (GenericJoint) comparée à une solution de référence indépendante.

Plan du mécanisme : (x, y) ; z sort du plan. Gravité -g·y.
Solides : 0 bâti, 1 manivelle OA (r), 2 bielle AB (L), 3 piston (centre B, glisse selon x).
Liaisons (architecture isostatique, h = 0) :
  L01 pivot d'axe (O, z), motorisée : θ(t) imposé
  L12 pivot d'axe (A, z)
  L23 linéaire annulaire d'axe (B, z)
  L30 glissière de direction x
Référence : équations de Newton-Euler planes, cinématique exacte en fermeture de boucle,
système linéaire 9×9 résolu à chaque instant.
"""
import numpy as np
import exudyn as exu
from exudyn.utilities import *  # noqa: F401,F403

from liaisons import LIAISONS

# --- Données -------------------------------------------------------------
r, L = 0.10, 0.30                 # m
e = 0.02                          # section carrée des barres (m)
rho = 7800.0                      # kg/m3
m3 = 0.5                          # masse du piston (kg)
g = 9.81
OMEGA, T_MONTEE = 20.0, 0.2       # rad/s, s
T_FIN, N_PAS = 1.0, 4000

m1 = rho * r * e * e
m2 = rho * L * e * e
I1 = m1 * (r**2 + e**2) / 12      # inertie en G autour de z
I2 = m2 * (L**2 + e**2) / 12
I3_cote = 0.03                    # cube de 3 cm pour le piston (inertie sans effet sur le plan)

# Repère de liaison « axe = x local » orienté selon z global (pivots, linéaire annulaire)
R_AXE_Z = RotationMatrixY(-np.pi / 2)   # x_local -> z_global


# --- Loi de mouvement d'entrée (régulière, au repos à t = 0) --------------
def theta(t):
    if t < T_MONTEE:
        return OMEGA / 2 * (t - T_MONTEE / np.pi * np.sin(np.pi * t / T_MONTEE))
    return OMEGA / 2 * T_MONTEE + OMEGA * (t - T_MONTEE)


def theta_t(t):
    return OMEGA / 2 * (1 - np.cos(np.pi * t / T_MONTEE)) if t < T_MONTEE else OMEGA


def theta_tt(t):
    return OMEGA * np.pi / (2 * T_MONTEE) * np.sin(np.pi * t / T_MONTEE) if t < T_MONTEE else 0.0


# --- Solution de référence (Newton-Euler plan) -----------------------------
def cross2(a, b):
    return a[0] * b[1] - a[1] * b[0]


def reference(t):
    th, w, al = theta(t), theta_t(t), theta_tt(t)
    sb = -r * np.sin(th) / L
    b = np.arcsin(sb)
    cb = np.cos(b)
    b_t = -r * w * np.cos(th) / (L * cb)
    b_tt = (-r * al * np.cos(th) + r * w**2 * np.sin(th) + L * np.sin(b) * b_t**2) / (L * cb)

    A = r * np.array([np.cos(th), np.sin(th)])
    B = A + L * np.array([cb, np.sin(b)])
    G1, G2 = A / 2, (A + B) / 2
    u, n = np.array([np.cos(th), np.sin(th)]), np.array([-np.sin(th), np.cos(th)])
    v, m = np.array([cb, np.sin(b)]), np.array([-np.sin(b), cb])
    aA = r * (al * n - w**2 * u)
    aG1 = aA / 2
    aB = aA + L * (b_tt * m - b_t**2 * v)
    aG2 = (aA + aB) / 2

    # inconnues : Ox Oy C | Ax Ay | Bx By | Ny Mp
    # O = ground->1 ; A = 1->2 ; B = 2->3 ; N, Mp = ground->3 ; C = couple moteur ground->1
    K = np.zeros((9, 9))
    s = np.zeros(9)
    # manivelle : m1 aG1 = O - A + m1 g ; moments en G1
    K[0, [0, 3]] = [1, -1]; s[0] = m1 * aG1[0]
    K[1, [1, 4]] = [1, -1]; s[1] = m1 * aG1[1] + m1 * g
    dO, dA = -G1, A - G1
    K[2, 0], K[2, 1], K[2, 2] = -dO[1], dO[0], 1
    K[2, 3], K[2, 4] = dA[1], -dA[0]                  # (A-G1) × (-A)
    s[2] = I1 * al
    # bielle : m2 aG2 = A - B + m2 g
    K[3, [3, 5]] = [1, -1]; s[3] = m2 * aG2[0]
    K[4, [4, 6]] = [1, -1]; s[4] = m2 * aG2[1] + m2 * g
    dA2, dB2 = A - G2, B - G2
    K[5, 3], K[5, 4] = -dA2[1], dA2[0]
    K[5, 5], K[5, 6] = dB2[1], -dB2[0]
    s[5] = I2 * b_tt
    # piston : m3 aB = B + N + m3 g ; pas de rotation
    K[6, 5] = 1; s[6] = m3 * aB[0]
    K[7, [6, 7]] = [1, 1]; s[7] = m3 * g
    K[8, 8] = 1; s[8] = 0.0
    x = np.linalg.solve(K, s)
    return dict(theta=th, xB=B[0], vB=None, O=x[0:2], C=x[2], A=x[3:5], B=x[5:7], N=x[7])


# --- Modèle Exudyn --------------------------------------------------------
def construire(hyperstatique=False):
    SC = exu.SystemContainer()
    mbs = SC.AddSystem()
    sol = mbs.AddObject(ObjectGround())
    grav = [0, -g, 0]
    b1 = mbs.CreateRigidBody(inertia=InertiaCuboid(density=rho, sideLengths=[r, e, e]),
                             referencePosition=[r / 2, 0, 0], gravity=grav)
    b2 = mbs.CreateRigidBody(inertia=InertiaCuboid(density=rho, sideLengths=[L, e, e]),
                             referencePosition=[r + L / 2, 0, 0], gravity=grav)
    rho3 = m3 / I3_cote**3
    b3 = mbs.CreateRigidBody(inertia=InertiaCuboid(density=rho3, sideLengths=[I3_cote] * 3),
                             referencePosition=[r + L, 0, 0], gravity=grav)

    # Pivot motorisé : la rotation autour de l'axe (x local) est bloquée et pilotée par l'offset
    def offset(mbs, t, itemNumber, p):
        return [0, 0, 0, theta(t), 0, 0]

    def offset_t(mbs, t, itemNumber, p):
        return [0, 0, 0, theta_t(t), 0, 0]

    axes_moteur = LIAISONS["pivot"].copy()
    axes_moteur[3] = 1
    j01 = mbs.CreateGenericJoint(itemNumbers=[sol, b1], position=[0, 0, 0], rotationMatrixAxes=R_AXE_Z,
                                 constrainedAxes=axes_moteur, offsetUserFunction=offset,
                                 offsetUserFunction_t=offset_t, show=False)
    j12 = mbs.CreateGenericJoint(itemNumbers=[b1, b2], position=[r, 0, 0], rotationMatrixAxes=R_AXE_Z,
                                 constrainedAxes=LIAISONS["pivot"], show=False)
    lb = "pivot" if hyperstatique else "lineaire_annulaire"
    j23 = mbs.CreateGenericJoint(itemNumbers=[b2, b3], position=[r + L, 0, 0], rotationMatrixAxes=R_AXE_Z,
                                 constrainedAxes=LIAISONS[lb], show=False)
    j30 = mbs.CreateGenericJoint(itemNumbers=[sol, b3], position=[r + L, 0, 0], rotationMatrixAxes=np.eye(3),
                                 constrainedAxes=LIAISONS["glissiere"], show=False)
    mbs.Assemble()
    return mbs, dict(b1=b1, b2=b2, b3=b3, j01=j01, j12=j12, j23=j23, j30=j30)


def simuler(hyperstatique=False):
    mbs, it = construire(hyperstatique)
    cap = {}
    for k in ["j01", "j12", "j23", "j30"]:
        cap[k + "F"] = mbs.AddSensor(SensorObject(objectNumber=it[k], storeInternal=True,
                                                  outputVariableType=exu.OutputVariableType.ForceLocal))
        cap[k + "M"] = mbs.AddSensor(SensorObject(objectNumber=it[k], storeInternal=True,
                                                  outputVariableType=exu.OutputVariableType.TorqueLocal))
    cap["rot1"] = mbs.AddSensor(SensorBody(bodyNumber=it["b1"], storeInternal=True,
                                           outputVariableType=exu.OutputVariableType.RotationMatrix))
    cap["rot2"] = mbs.AddSensor(SensorBody(bodyNumber=it["b2"], storeInternal=True,
                                           outputVariableType=exu.OutputVariableType.RotationMatrix))
    cap["xB"] = mbs.AddSensor(SensorBody(bodyNumber=it["b3"], storeInternal=True,
                                         outputVariableType=exu.OutputVariableType.Position))
    ss = exu.SimulationSettings()
    ss.timeIntegration.endTime = T_FIN
    ss.timeIntegration.numberOfSteps = N_PAS
    ss.timeIntegration.verboseMode = 0
    # ρ∞ < 1 indispensable : sans amortissement numérique, les efforts de liaison divergent (index 3)
    ss.timeIntegration.generalizedAlpha.spectralRadius = 0.9
    ss.solution.file.write = False
    ss.solution.sensors.writePeriod = 0.002
    mbs.Assemble()
    mbs.SolveDynamic(ss)
    return {k: mbs.GetSensorStoredData(s) for k, s in cap.items()}
