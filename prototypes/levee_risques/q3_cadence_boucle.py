"""Q3 (suite) : cadence « une requête par image » et restauration sur le mécanisme à boucle fermée.

Travaille sur la copie `maquettes/bielle_trace.solidcraft` (jamais sur l'original).
  - A : une requête engine.batch([joint.drive]) par image, 200 images ;
  - B : une requête engine.batch([3 x occurrence.move en attente]) par image, 200 images ;
  - restauration par edit.checkpoint / edit.restore_checkpoint, comparée bit à bit,
    et par retour joint.drive (dérive due à la fermeture de boucle).
"""

from __future__ import annotations

import math
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from q3_animation import ID, delta_deplacement, poses_analytiques, transform_vers_matrice
from sc_client import Client, sauver
from sc_maquette import etat, exe

N = 200


def instantane(c: Client) -> dict:
    jl = exe(c, "joint.list")
    cl = exe(c, "component.list")
    return {
        "valeurs": {j["name"]: [v["value"] for v in j["values"]] for j in jl["joints"]},
        "poses": {ch["name"]: ch["transform"] for ch in cl["components"][0]["children"]},
        "pending": cl["pending_moves"],
    }


def ecart(a: dict, b: dict) -> dict:
    ev = max(abs(x - y) for k in a["valeurs"] for x, y in zip(a["valeurs"][k], b["valeurs"][k], strict=True))
    ep = max(
        abs(x - y)
        for k in a["poses"]
        for ra, rb in zip(a["poses"][k], b["poses"][k], strict=True)
        for x, y in zip(ra, rb, strict=True)
    )
    return {"valeurs_max": ev, "poses_max": ep, "pending_apres": b["pending"]}


def main() -> None:
    c = Client()
    d = c.appel("document.inspect")["result"]
    assert d["path"].replace("\\", "/").endswith("maquettes/bielle_trace.solidcraft"), d["path"]
    s0 = instantane(c)
    th0 = s0["valeurs"]["L01_pivot"][0]
    out: dict = {"etat_initial": etat(c), "theta0": th0}
    thetas = [1.8 * k for k in range(N)]

    # A : une requête par image (engine.batch d'un seul joint.drive)
    cp = exe(c, "edit.checkpoint")
    t0 = time.perf_counter()
    lat = []
    for th in thetas:
        t1 = time.perf_counter()
        c.appel("engine.batch", {"commands": [
            {"command": "joint.drive", "params": {"joint": "L01_pivot", "value": th, "quiet": True}}]})
        lat.append(1000 * (time.perf_counter() - t1))
    dt = time.perf_counter() - t0
    out["A_batch_1_drive_par_image"] = {"images_par_s": N / dt, "latence_mediane_ms": float(np.median(lat)),
                                        "latence_max_ms": max(lat)}
    out["A_etat_apres"] = etat(c)
    # retour par joint.drive : dérive de la boucle fermée
    exe(c, "joint.drive", {"joint": "L01_pivot", "value": th0, "quiet": True})
    out["A_retour_drive_ecart"] = ecart(s0, instantane(c))
    # restauration par checkpoint
    exe(c, "edit.restore_checkpoint", {"checkpoint": cp["checkpoint"]})
    out["A_restore_checkpoint_ecart"] = ecart(s0, instantane(c))
    out["A_etat_apres_restore"] = etat(c)

    # B : 3 occurrence.move en attente par requête
    courant = {k: transform_vers_matrice(s0["poses"][f"{k}:1"]) for k in ID}
    t0 = time.perf_counter()
    lat = []
    for th in thetas:
        cibles = poses_analytiques(math.radians(th))
        cmds = []
        for k in ID:
            p_ = delta_deplacement(cibles[k], courant[k])
            cmds.append({"command": "occurrence.move", "params": {"occurrence": ID[k], **p_}})
            courant[k] = cibles[k]
        t1 = time.perf_counter()
        c.appel("engine.batch", {"commands": cmds})
        lat.append(1000 * (time.perf_counter() - t1))
    dt = time.perf_counter() - t0
    out["B_batch_3_moves_par_image"] = {"images_par_s": N / dt, "latence_mediane_ms": float(np.median(lat)),
                                        "latence_max_ms": max(lat)}
    out["B_etat_apres"] = etat(c)
    exe(c, "component.revert_position", {})
    out["B_revert_ecart"] = ecart(s0, instantane(c))
    out["B_etat_apres_revert"] = etat(c)
    exe(c, "edit.restore_checkpoint", {"checkpoint": cp["checkpoint"], "forget": True})
    sauver("q3_cadence_boucle.json", out)
    for k, v in out.items():
        print(k, v)


if __name__ == "__main__":
    main()
