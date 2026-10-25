"""Q3 : restauration exacte de la pose et effet sur dirty / revision / undo.

Document de travail : maquette `cremaillere` (enregistrée, donc propre au départ), pignon à 0°.
Trois scénarios, chacun comparé à l'état initial bit à bit :
  1. 200 joint.drive puis retour par joint.drive à la valeur initiale ;
  2. 200 occurrence.move « en attente » puis component.revert_position ;
  3. 200 joint.drive encadrés par edit.checkpoint / edit.restore_checkpoint.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from sc_client import Client, sauver
from sc_maquette import enregistrer, etat, exe


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
    return {"valeurs_max": ev, "poses_max": ep, "pending_avant": a["pending"], "pending_apres": b["pending"]}


def main() -> None:
    c = Client()
    out: dict = {"document": c.appel("document.inspect")["result"]["name"]}
    enregistrer(c, "cremaillere")  # état propre de référence
    exe(c, "joint.drive", {"joint": "L_pignon", "value": 17.0})  # pose initiale non triviale
    enregistrer(c, "cremaillere")
    s0 = instantane(c)
    out["etat_initial"] = etat(c)
    out["s0"] = s0["valeurs"]
    angles = [1.8 * k for k in range(200)]

    # 1. drive puis retour
    cmds = [{"command": "joint.drive", "params": {"joint": "L_pignon", "value": a, "quiet": True}}
            for a in angles]
    c.appel("engine.batch", {"commands": cmds})
    out["1_apres_animation"] = etat(c)
    exe(c, "joint.drive", {"joint": "L_pignon", "value": s0["valeurs"]["L_pignon"][0], "quiet": True})
    out["1_apres_retour"] = etat(c)
    out["1_ecart"] = ecart(s0, instantane(c))
    enregistrer(c, "cremaillere")  # remet propre

    # 2. déplacements en attente
    out["2_etat_avant"] = etat(c)
    cmds = [{"command": "occurrence.move",
             "params": {"occurrence": 5, "space": "world", "capture": False, "axis": [0, 0, 1],
                        "angle": math.radians(1.8), "origin": [0, 0, 0]}} for _ in range(200)]
    c.appel("engine.batch", {"commands": cmds})
    out["2_apres_animation"] = etat(c)
    out["2_pose_pendant"] = instantane(c)["pending"]
    exe(c, "component.revert_position", {})
    out["2_apres_revert"] = etat(c)
    out["2_ecart"] = ecart(s0, instantane(c))

    # 3. checkpoint / restore
    cp = exe(c, "edit.checkpoint", {}, "q3_checkpoint_reponse.json")
    out["3_checkpoint"] = cp
    out["3_etat_apres_checkpoint"] = etat(c)
    cmds = [{"command": "joint.drive", "params": {"joint": "L_pignon", "value": a, "quiet": True}}
            for a in angles]
    c.appel("engine.batch", {"commands": cmds})
    out["3_apres_animation"] = etat(c)
    r = exe(c, "edit.restore_checkpoint", {"checkpoint": cp["checkpoint"]}, "q3_restore_checkpoint_reponse.json")
    out["3_restore_reponse"] = r
    out["3_apres_restore"] = etat(c)
    out["3_ecart"] = ecart(s0, instantane(c))
    try:
        r2 = c.cmd("edit.restore_checkpoint", {"checkpoint": cp["checkpoint"], "forget": True})
        out["3_forget"] = r2
    except Exception as e:  # noqa: BLE001
        out["3_forget"] = str(e)
    sauver("q3_restauration.json", out)
    print(json.dumps({k: v for k, v in out.items() if k != "s0"}, indent=1)[:6000])


if __name__ == "__main__":
    main()
