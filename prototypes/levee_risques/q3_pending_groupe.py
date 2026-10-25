"""Q3/Q6 : un déplacement en attente d'une occurrence de premier niveau emporte-t-il ses sous-occurrences ?"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from sc_client import Client, sauver
from sc_maquette import MAQ, etat, exe


def cdg(c: Client, occ: int, path: list[int]) -> list[float]:
    r = exe(c, "occurrence.properties", {"occurrence": occ, "path": path})
    return [round(x, 4) for x in r["total"]["center_of_mass"]]


def main() -> None:
    c = Client()
    n0 = c.appel("ui.inspect")["result"]["documents"]
    exe(c, "doc.open", {"path": str(MAQ / "sous_assemblage_propre.solidcraft")})
    out = {"documents_avant": n0, "documents_apres": c.appel("ui.inspect")["result"]["documents"],
           "document": etat(c)}
    out["avant"] = {"Barre dans G1": cdg(c, 12, [11, 12]), "Barre dans G2": cdg(c, 12, [14, 12])}
    exe(c, "occurrence.move", {"occurrence": 11, "space": "world", "translate": [0, 0, 30],
                               "axis": [0, 0, 1], "angle": "90 deg", "origin": [0, 0, 0], "capture": False})
    out["apres_move_G1"] = {"Barre dans G1": cdg(c, 12, [11, 12]), "Barre dans G2": cdg(c, 12, [14, 12]),
                            "etat": etat(c)}
    exe(c, "component.revert_position", {})
    out["apres_revert"] = {"Barre dans G1": cdg(c, 12, [11, 12]), "etat": etat(c)}
    sauver("q3_pending_groupe.json", out)
    for k, v in out.items():
        print(k, v)


if __name__ == "__main__":
    main()
