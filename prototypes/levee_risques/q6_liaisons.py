"""Q6 (suite) : liaisons visant des sous-occurrences, relevé brut des réponses et des erreurs."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from sc_client import Client, sauver
from sc_maquette import enregistrer, etat, exe


def essai(c: Client, journal: list, nom: str, cmd: str, params: dict) -> dict:
    r = c.cmd(cmd, params)
    journal.append({"essai": nom, "commande": cmd, "params": params, "reponse": r})
    print(nom, "->", json.dumps(r)[:350])
    return r


def main() -> None:
    c = Client()
    j: list = []
    # le document actif est la maquette créée par q6_sous_assemblages.py
    print(etat(c))
    # déplacements pour que les trois exemplaires de Barre ne se superposent pas
    exe(c, "occurrence.move", {"occurrence": 5, "space": "world", "translate": [0, -150, 0]})
    # Axe racine aussi
    exe(c, "occurrence.move", {"occurrence": 8, "space": "world", "translate": [0, -150, 0]})

    # 1. liaison de premier niveau : bâti / Groupe:1 (l'ensemble Groupe tourne)
    essai(c, j, "origin bati", "joint.origin", {"name": "OA_bati", "occurrence": 2, "point": [0, 0, 0]})
    essai(c, j, "origin groupe1", "joint.origin", {"name": "OA_g1", "occurrence": 11, "point": [0, 0, 0]})
    essai(c, j, "create A (bati/Groupe:1)", "joint.create",
          {"type": "revolute", "a": "OA_bati", "b": "OA_g1", "flip": True, "name": "LA_bati_groupe1"})
    # 2. racine : bâti / Barre:1 (second exemplaire de Barre, au premier niveau)
    essai(c, j, "origin bati2", "joint.origin", {"name": "OB_bati", "occurrence": 2, "point": [0, -150, 0]})
    essai(c, j, "origin barre1", "joint.origin", {"name": "OB_b1", "occurrence": 5, "point": [0, -150, 0]})
    essai(c, j, "create B (bati/Barre:1)", "joint.create",
          {"type": "revolute", "a": "OB_bati", "b": "OB_b1", "flip": True, "name": "LB_bati_barre1"})
    # 3. liaison interne au sous-assemblage : Barre:2 / Axe:2 (sous-occurrences)
    essai(c, j, "origin barre2 ambigu", "joint.origin", {"name": "OC_barre", "occurrence": 12, "point": [100, 0, 0]})
    essai(c, j, "origin barre2 par path", "joint.origin",
          {"name": "OC_barre_p", "occurrence": 12, "path": [11, 12], "point": [100, 0, 0]})
    essai(c, j, "origin barre2 par nom", "joint.origin", {"name": "OC_barre_n", "occurrence": "Barre:2", "point": [100, 0, 0]})
    essai(c, j, "origin axe2", "joint.origin", {"name": "OC_axe", "occurrence": 13, "point": [100, 0, 0]})
    r = essai(c, j, "create C (Barre:2/Axe:2)", "joint.create",
              {"type": "revolute", "a": "OC_barre", "b": "OC_axe", "flip": True, "name": "LC_sous"})
    # 4. liaison bâti / sous-occurrence (Axe:2 dans Groupe)
    essai(c, j, "origin bati3", "joint.origin", {"name": "OD_bati", "occurrence": 2, "point": [100, 0, 0]})
    essai(c, j, "create D (bati/Axe:2)", "joint.create",
          {"type": "revolute", "a": "OD_bati", "b": "OC_axe", "flip": True, "name": "LD_bati_axe2"})
    sauver("q6_essais_joints.json", j)
    sauver("q6_joint_list.json", c.cmd("joint.list"))
    sauver("q6_joint_inspect.json", c.cmd("joint.inspect"))
    sauver("q6_component_list.json", c.cmd("component.list"))
    print(json.dumps(exe(c, "joint.list"), indent=None)[:3000])


if __name__ == "__main__":
    main()
