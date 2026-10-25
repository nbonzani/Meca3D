"""Q6 (suite) : poses des sous-occurrences, propriétés, exports JSON et URDF."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from sc_client import Client, sauver
from sc_maquette import enregistrer, etat, exe, exporter


def cdg(c: Client, occ: int, path: list[int] | None = None) -> object:
    p: dict = {"occurrence": occ}
    if path:
        p["path"] = path
    r = c.cmd("occurrence.properties", p)
    if not r["ok"]:
        return r["error"][:300]
    return [round(x, 3) for x in r["result"]["total"]["center_of_mass"]], r["result"].get("path")


def lister(c: Client, titre: str) -> dict:
    out = {}
    cl = exe(c, "component.list")
    out["occurrences"] = {
        o["id"]: {"nom": o["name"], "composant": o["component"], "parent": o["parent"],
                  "grounded": o["grounded"], "transform_translation": [round(v, 3) for v in o["transform"][3]],
                  "transform_col0": [round(v, 4) for v in o["transform"][0]]}
        for x in cl["components"] for o in x["occurrences"]
    }
    out["groupe_children"] = [
        {k: ch[k] for k in ("id", "name", "parent", "component")} for x in cl["components"]
        if x["name"] == "Groupe" for ch in x["children"]
    ]
    out["cdg"] = {
        "Barre:1 (5)": cdg(c, 5), "Barre:2 (12) sans path": cdg(c, 12),
        "Barre:2 chemin [11,12]": cdg(c, 12, [11, 12]), "Barre:2 chemin [14,12]": cdg(c, 12, [14, 12]),
        "Axe:2 chemin [11,13]": cdg(c, 13, [11, 13]), "Axe:2 chemin [14,13]": cdg(c, 13, [14, 13]),
        "Groupe:1 (11)": cdg(c, 11), "Groupe:2 (14)": cdg(c, 14),
    }
    out["valeurs"] = {j["name"]: [v["value"] for v in j["values"]] for j in exe(c, "joint.list")["joints"]}
    print("\n==", titre)
    print(json.dumps(out, indent=None)[:3000])
    return out


def main() -> None:
    c = Client()
    res = {}
    res["repos"] = lister(c, "repos")
    exe(c, "joint.drive", {"joint": "LA_bati_groupe1", "value": 30})
    res["drive LA 30"] = lister(c, "drive LA (Bati/Groupe:1) = 30 deg")
    exe(c, "joint.drive", {"joint": "LA_bati_groupe1", "value": 0})
    exe(c, "joint.drive", {"joint": "LD_bati_axe2", "value": 40})
    res["drive LD 40"] = lister(c, "drive LD (Bati/Axe:2) = 40 deg")
    exe(c, "joint.drive", {"joint": "LD_bati_axe2", "value": 0})
    exe(c, "joint.drive", {"joint": "LC_sous", "value": 25})
    res["drive LC 25"] = lister(c, "drive LC (Barre:2/Axe:2) = 25 deg")
    exe(c, "joint.drive", {"joint": "LC_sous", "value": 0})
    sauver("q6_poses.json", res)
    sauver("q6_component_properties_groupe.json", c.cmd("component.properties", {"component": "Groupe"}))
    sauver("q6_component_properties_racine.json", c.cmd("component.properties", {"component": "root"}))
    sauver("q6_occurrence_properties_12.json", c.cmd("occurrence.properties", {"occurrence": 12}))
    exporter(c, "sous_assemblage")
    enregistrer(c, "sous_assemblage")
    print(etat(c))


if __name__ == "__main__":
    main()
