"""Q6 : maquette à sous-assemblage imbriqué et à occurrences multiples d'un même composant."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from sc_client import Client, sauver
from sc_maquette import composant, enregistrer, exe


def pose(c: Client) -> None:
    cl = exe(c, "component.list")
    print("composants :", [(x["id"], x["name"], x["parent"]) for x in cl["components"]])
    for x in cl["components"]:
        for o in x["occurrences"]:
            print("  occurrence", o["id"], o["name"], "composant", o["component"], "parent", o["parent"],
                  "gr", o["grounded"], [round(v, 3) for v in o["transform"][3]])


def main() -> None:
    c = Client()
    exe(c, "file.new", {"name": "sous_assemblage"})
    rb = exe(c, "component.create", {"name": "Bati"})
    exe(c, "solid.box", {"length": 400, "width": 300, "height": 10, "corner": [-100, -100, -10],
                         "body_name": "Bati_corps"})
    exe(c, "component.activate", {"component": "root"})
    exe(c, "occurrence.ground", {"occurrence": rb["occurrence"], "grounded": True})
    composant(c, "Barre", "solid.box", {"length": 100, "width": 10, "height": 10, "corner": [0, -5, 0]})
    composant(c, "Axe", "solid.cylinder", {"radius": 6, "height": 14, "base": [100, 0, -2]})
    rg = exe(c, "component.create", {"name": "Groupe"}, "q6_component_create_groupe.json")
    exe(c, "component.activate", {"component": "root"})
    print("Groupe ->", rg)
    pose(c)
    # nombrer l'imbrication : copie de Barre et d'Axe dans Groupe
    r1 = exe(c, "occurrence.copy", {"component": "Barre", "parent": "Groupe"}, "q6_copy_barre_dans_groupe.json")
    r2 = exe(c, "occurrence.copy", {"component": "Axe", "parent": "Groupe"}, "q6_copy_axe_dans_groupe.json")
    print("copy Barre ->", json.dumps(r1))
    print("copy Axe   ->", json.dumps(r2))
    pose(c)
    r3 = exe(c, "occurrence.copy", {"component": "Groupe", "translate": [0, 150, 0]},
             "q6_copy_groupe.json")
    print("copy Groupe ->", json.dumps(r3))
    pose(c)
    sauver("q6_component_list_brut.json", c.cmd("component.list"))
    sauver("q6_joint_list_vide.json", c.cmd("joint.list"))
    enregistrer(c, "sous_assemblage_sans_liaison")


if __name__ == "__main__":
    main()
