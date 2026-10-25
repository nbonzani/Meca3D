"""Relève dans SolidCraft (engine.commands) la documentation des commandes utilisées par le lot 1b.

Le registre complet (173 Ko) n'est pas conservé : seules les commandes utiles sont enregistrées
dans reponses/commandes_utilisees.json.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from sc_client import Client, sauver

UTILISEES = [
    "component.create", "component.list", "component.properties", "occurrence.properties",
    "occurrence.copy", "occurrence.move", "occurrence.ground", "component.revert_position",
    "component.capture_position", "joint.origin", "joint.create", "joint.drive", "joint.list",
    "joint.motion_link", "joint.gear", "joint.rack_pinion", "joint.screw", "joint.edit",
    "motion.study", "motion.trace", "motion.trace.keep", "motion.plot", "motion.list", "motion.delete",
    "sketch.create", "sketch.options", "sketch.spline3d", "sketch.line3d", "sketch.finish",
    "timeline.delete", "edit.checkpoint", "edit.restore_checkpoint", "edit.undo",
    "file.export", "file.new", "doc.open", "file.save_as", "document.inspect",
]


def main() -> None:
    c = Client()
    tout = c.appel("engine.commands")["result"]
    par_id = {x["id"]: x for x in tout}
    sel = {i: {"label": par_id[i]["label"], "params": par_id[i]["params"]} for i in UTILISEES if i in par_id}
    manquantes = [i for i in UTILISEES if i not in par_id]
    sauver("commandes_utilisees.json", {"total_commandes_registre": len(tout),
                                        "absentes_du_registre": manquantes, "commandes": sel})
    print(len(sel), "commandes ; absentes du registre :", manquantes)
    print(json.dumps(sorted(par_id)[:3]))


if __name__ == "__main__":
    main()
