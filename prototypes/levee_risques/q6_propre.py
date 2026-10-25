"""Q6 (cas géré) : sous-assemblage rigide instancié deux fois, liaisons au premier niveau seulement."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from sc_client import Client, sauver
from sc_maquette import composant, enregistrer, etat, exe, exporter, liaison


def main() -> None:
    c = Client()
    exe(c, "file.new", {"name": "sous_assemblage_propre"})
    rb = exe(c, "component.create", {"name": "Bati"})
    exe(c, "solid.box", {"length": 400, "width": 300, "height": 10, "corner": [-100, -100, -10],
                         "body_name": "Bati_corps"})
    exe(c, "component.activate", {"component": "root"})
    exe(c, "occurrence.ground", {"occurrence": rb["occurrence"], "grounded": True})
    composant(c, "Barre", "solid.box", {"length": 100, "width": 10, "height": 10, "corner": [0, -5, 0]})
    composant(c, "Axe", "solid.cylinder", {"radius": 6, "height": 14, "base": [100, 0, -2]})
    exe(c, "component.create", {"name": "Groupe"})
    exe(c, "component.activate", {"component": "root"})
    exe(c, "occurrence.copy", {"component": "Barre", "parent": "Groupe"})
    exe(c, "occurrence.copy", {"component": "Axe", "parent": "Groupe"})
    g2 = exe(c, "occurrence.copy", {"component": "Groupe", "translate": [0, 150, 0]})
    # Barre:1 et Axe:1 (premier niveau) sont écartés de la zone de travail
    exe(c, "occurrence.move", {"occurrence": 5, "space": "world", "translate": [0, -150, 0]})
    exe(c, "occurrence.move", {"occurrence": 8, "space": "world", "translate": [0, -150, 0]})
    ob = 2
    liaison(c, "L_g1", "revolute", ob, [0, 0, 0], 11, [0, 0, 0])
    liaison(c, "L_g2", "revolute", ob, [0, 150, 0], g2["occurrence"], [0, 150, 0])
    liaison(c, "L_barre1", "revolute", ob, [0, -150, 0], 5, [0, -150, 0])
    jl = exe(c, "joint.list", {}, "q6_propre_joint_list.json")
    print("dof", jl["dof"])
    # pose : les deux exemplaires du sous-assemblage tournent indépendamment
    exe(c, "joint.drive", {"joint": "L_g1", "value": 30})
    exe(c, "joint.drive", {"joint": "L_g2", "value": -50})
    res = {}
    for nom, occ, path in (("Groupe:1", 11, None), ("Groupe:2", g2["occurrence"], None),
                           ("Barre:2 dans Groupe:1", 12, [11, 12]), ("Barre:2 dans Groupe:2", 12, [g2["occurrence"], 12]),
                           ("Axe:2 dans Groupe:1", 13, [11, 13]), ("Axe:2 dans Groupe:2", 13, [g2["occurrence"], 13])):
        p = {"occurrence": occ}
        if path:
            p["path"] = path
        r = c.cmd("occurrence.properties", p)
        res[nom] = r["result"]["total"] if r["ok"] else r["error"]
    sauver("q6_propre_properties.json", res)
    for k, v in res.items():
        print(k, json.dumps({a: v[a] for a in ("mass_g", "center_of_mass")}) if isinstance(v, dict) else v)
    sauver("q6_propre_component_list_pose.json", c.cmd("component.list"))
    print({o["id"]: [round(x, 3) for x in sum(o["transform"], [])] for x in exe(c, "component.list")["components"] for o in x["occurrences"]})
    sauver("q6_propre_component_properties_groupe.json", c.cmd("component.properties", {"component": "Groupe"}))
    exporter(c, "sous_assemblage_propre")
    exe(c, "joint.drive", {"joint": "L_g1", "value": 0})
    exe(c, "joint.drive", {"joint": "L_g2", "value": 0})
    enregistrer(c, "sous_assemblage_propre")
    print(etat(c))


if __name__ == "__main__":
    main()
