"""Briques communes des prototypes du lot 1a (jetables, pas de code produit).

Contient :
- `couplage_vitesse` : contrainte linéaire au niveau vitesse entre deux corps (ObjectConnectorCoordinateVector
  + constraintUserFunction + jacobianUserFunction), pour engrenage, vis-écrou, crémaillère ;
- `lambda_couplage` : lecture du multiplicateur de Lagrange du couplage (effort transmis) ;
- quelques constantes de repère identiques à prototypes/exudyn_bielle.
"""
import numpy as np
import exudyn as exu
from exudyn.utilities import *  # noqa: F401,F403

# Repère de liaison « axe = x local » orienté selon z global (cf. prototypes/exudyn_bielle/bielle_manivelle.py)
R_AXE_Z = RotationMatrixY(-np.pi / 2)
R_AXE_X = np.eye(3)

PIVOT = [1, 1, 1, 0, 1, 1]            # constrainedAxes [Tx,Ty,Tz,Rx,Ry,Rz]
PIVOT_BLOQUE = [1, 1, 1, 1, 1, 1]
PIVOT_GLISSANT = [0, 1, 1, 0, 1, 1]


def _g_ep(e):
    """Matrice 3x4 telle que omega_local = 2 G(e) e_dot (paramètres d'Euler, e = [e0,e1,e2,e3])."""
    e0, e1, e2, e3 = e
    return 2.0 * np.array([[-e1, e0, e3, -e2],
                           [-e2, -e3, e0, e1],
                           [-e3, e2, -e1, e0]])


def utf8():
    """Sortie console en UTF-8 (Windows)."""
    import sys
    sys.stdout.reconfigure(encoding="utf-8")


def couplage_vitesse(mbs, corps_a, corps_b, coef_a, coef_b, terme_t=None):
    """Contrainte g = coef_a . s_a + coef_b . s_b = 0 au niveau vitesse.

    corps_a, corps_b : numéros d'objets CreateRigidBody (nœuds RigidBodyEP : [x,y,z,e0,e1,e2,e3]).
    coef_x : vecteur de 6 réels [vx, vy, vz, wx, wy, wz] : combinaison des vitesses de translation
             (repère monde, coordonnées nodales) et de la vitesse de rotation (repère LOCAL du corps).
    corps_b = None : contrainte sur un seul corps (les deux marqueurs sont sur le même nœud, coef_b ignoré).
    terme_t : fonction t -> réel soustrait à g (g = ... - terme_t(t)) pour un pilotage au niveau vitesse.
    Retourne le numéro de l'objet connecteur.
    """
    if corps_b is None:
        corps_b, coef_b = corps_a, np.zeros(6)
    coef_a = np.asarray(coef_a, float)
    coef_b = np.asarray(coef_b, float)
    na = mbs.GetObject(corps_a)["nodeNumber"]
    nb = mbs.GetObject(corps_b)["nodeNumber"]
    ma = mbs.AddMarker(MarkerNodeCoordinates(nodeNumber=na))
    mb = mbs.AddMarker(MarkerNodeCoordinates(nodeNumber=nb))

    def ligne_t(q, coef):
        """d(s)/d(q_t) sur 7 coordonnées : s = coef_v . v + coef_w . (2 G(e) e_t)."""
        row = np.zeros(7)
        row[0:3] = coef[0:3]
        row[3:7] = coef[3:6] @ _g_ep(q[3:7])
        return row

    def contrainte(mbs_, t, itemNumber, q, qt, velocityLevel):
        q = np.asarray(q)
        qt = np.asarray(qt)
        g = ligne_t(q[:7], coef_a) @ qt[:7] + ligne_t(q[7:], coef_b) @ qt[7:]
        return np.array([g - (terme_t(t) if terme_t else 0.0)])

    def jacobien(mbs_, t, itemNumber, q, qt, velocityLevel):
        q = np.asarray(q)
        qt = np.asarray(qt)
        J = np.zeros((1, 14))
        J[0, :7] = ligne_t(q[:7], coef_a)
        J[0, 7:] = ligne_t(q[7:], coef_b)
        return J

    return mbs.AddObject(ObjectConnectorCoordinateVector(
        markerNumbers=[ma, mb], scalingMarker0=np.zeros((1, 7)), scalingMarker1=np.zeros((1, 7)),
        velocityLevel=True, constraintUserFunction=contrainte, jacobianUserFunction=jacobien))


def lambda_couplage(mbs, objet):
    """Multiplicateur de Lagrange du couplage dans l'état courant (N·m pour un couplage rotation/rotation)."""
    ltg = mbs.systemData.GetObjectLTGAE(objet)
    ae = mbs.systemData.GetAECoordinates()
    return float(ae[ltg[0]])


def reglages(t_fin, n_pas, ecriture=0.002):
    ss = exu.SimulationSettings()
    ss.timeIntegration.endTime = t_fin
    ss.timeIntegration.numberOfSteps = n_pas
    ss.timeIntegration.verboseMode = 0
    ss.timeIntegration.generalizedAlpha.spectralRadius = 0.9
    ss.solution.file.write = False
    ss.solution.sensors.writePeriod = ecriture
    return ss
