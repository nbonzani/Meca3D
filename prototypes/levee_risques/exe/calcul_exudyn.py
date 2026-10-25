"""Calcul Exudyn exécuté dans un processus fils (démarrage spawn) : pendule à liaison pivot.

Une barre de 1 m (section 2 cm x 2 cm, acier) articulée en O par une GenericJoint (pivot,
axe z), lâchée à l'horizontale sans vitesse, 1 s, pas de 1 ms. Mêmes réglages que le
prototype de la bielle-manivelle (generalized-alpha, spectralRadius = 0.9).
"""

from __future__ import annotations

import os
import time

LONGUEUR = 1.0
SECTION = 0.02
RHO = 7800.0
G = 9.81
T_FIN = 1.0
N_PAS = 1000


def simuler_pendule() -> dict:
    import exudyn as exu
    import numpy as np
    from exudyn.utilities import (  # noqa: F401  (charge aussi les dépendances d'exudyn.utilities)
        InertiaCuboid,
        ObjectGround,
        RotationMatrixY,
        SensorBody,
        SensorObject,
    )

    SC = exu.SystemContainer()
    mbs = SC.AddSystem()
    sol = mbs.AddObject(ObjectGround())
    barre = mbs.CreateRigidBody(
        inertia=InertiaCuboid(density=RHO, sideLengths=[LONGUEUR, SECTION, SECTION]),
        referencePosition=[LONGUEUR / 2, 0, 0],
        gravity=[0, -G, 0],
    )
    # repère de liaison : axe x local orienté selon z global (convention de Meca3D)
    r_axe_z = RotationMatrixY(-np.pi / 2)
    pivot = mbs.CreateGenericJoint(
        itemNumbers=[sol, barre],
        position=[0, 0, 0],
        rotationMatrixAxes=r_axe_z,
        constrainedAxes=[1, 1, 1, 0, 1, 1],
        show=False,
    )
    s_rot = mbs.AddSensor(SensorBody(bodyNumber=barre, storeInternal=True,
                                     outputVariableType=exu.OutputVariableType.RotationMatrix))
    s_f = mbs.AddSensor(SensorObject(objectNumber=pivot, storeInternal=True,
                                     outputVariableType=exu.OutputVariableType.ForceLocal))
    ss = exu.SimulationSettings()
    ss.timeIntegration.endTime = T_FIN
    ss.timeIntegration.numberOfSteps = N_PAS
    ss.timeIntegration.verboseMode = 0
    ss.timeIntegration.generalizedAlpha.spectralRadius = 0.9
    ss.solution.file.write = False
    ss.solution.sensors.writePeriod = 0.001
    mbs.Assemble()
    t0 = time.perf_counter()
    mbs.SolveDynamic(ss)
    duree = time.perf_counter() - t0
    rot = np.asarray(mbs.GetSensorStoredData(s_rot))   # colonnes : t, R(0,0)...R(2,2)
    f = np.asarray(mbs.GetSensorStoredData(s_f))       # colonnes : t, Fx, Fy, Fz (base locale)
    theta = np.arctan2(rot[:, 4], rot[:, 1])           # R[1,0] / R[0,0]
    return {
        "n_points": int(rot.shape[0]),
        "theta_fin_rad": float(theta[-1]),
        "force_locale_fin_N": [float(x) for x in f[-1, 1:4]],
        "somme_theta": float(theta.sum()),
        "norme_force_max_N": float(np.linalg.norm(f[:, 1:4], axis=1).max()),
        "duree_calcul_s": duree,
        "exudyn": exu.GetVersionString(),
        "pid_calcul": os.getpid(),
    }


def fils(file_attente) -> None:
    """Point d'entrée du processus fils : calcule et renvoie le résultat par la file."""
    try:
        file_attente.put({"ok": True, **simuler_pendule()})
    except Exception as e:  # noqa: BLE001
        file_attente.put({"ok": False, "erreur": repr(e)})
