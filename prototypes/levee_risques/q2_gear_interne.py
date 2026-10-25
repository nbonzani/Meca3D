"""Q2 (complément) : forme de joint.list pour un engrenage intérieur et un engrenage inversé."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from sc_client import Client, sauver
from sc_maquette import MAQ, exe


def main() -> None:
    c = Client()
    exe(c, "doc.open", {"path": str(MAQ / "reducteur.solidcraft")})
    out = {}
    for nom, params in (("exterieur", {}), ("interieur", {"internal": True}),
                        ("exterieur_reverse", {"reverse": True}),
                        ("depuis_dents_texte", {"ra": "20", "rb": "60"})):
        p = {"a": "L1_pivot", "b": "L2_pivot", "ra": 20, "rb": 60, "link": 0, **params}
        r = c.cmd("joint.gear", p)
        out[nom] = {"params": p, "reponse": r["result"] if r["ok"] else r["error"],
                    "links": exe(c, "joint.list")["links"]}
        print(nom, json.dumps(out[nom]["links"]))
    sauver("q2_gear_variantes.json", out)
    # ne rien enregistrer : fermeture sans sauvegarde du document de travail
    docs = c.appel("ui.documents")["result"]
    actif = docs["active"]
    assert docs["documents"][actif]["name"] == "reducteur", docs
    c.appel("ui.documents", {"action": "close", "index": actif, "force": True})


if __name__ == "__main__":
    main()
