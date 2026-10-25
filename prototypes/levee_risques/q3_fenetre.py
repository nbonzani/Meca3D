"""Q3 (complément) : une fenêtre SolidCraft réduite ralentit le canal ; ui.window la ramène.

Travaille sur la bielle d'origine, rouverte depuis le disque au début (état propre), jamais
enregistrée ; le checkpoint ramène la pose exactement à la fin.
"""

from __future__ import annotations

import json
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from sc_client import Client, sauver
from sc_maquette import exe

BIELLE = "D:/CLAUDE/dev/Solidcraft/meca3d_sonde/bielle_manivelle.solidcraft"


def lat(c: Client, n: int = 30) -> float:
    t = []
    for _ in range(n):
        t0 = time.perf_counter()
        c.appel("document.inspect")
        t.append(1000 * (time.perf_counter() - t0))
    return round(statistics.median(t), 1)


def main() -> None:
    c = Client()
    out: dict = {}
    docs = c.appel("ui.documents")["result"]
    c.appel("ui.documents", {"action": "close", "index": docs["active"], "force": True})
    exe(c, "doc.open", {"path": BIELLE})
    d = c.appel("document.inspect")["result"]
    out["document"] = {k: d[k] for k in ("name", "dirty", "undo")}
    out["latence_document_inspect_ms_fenetre_normale"] = lat(c)
    out["minimize"] = c.appel("ui.window", {"action": "minimize"})["result"]
    time.sleep(1.0)
    out["latence_fenetre_reduite_ms"] = lat(c)
    out["screenshot_fenetre_reduite"] = c.appel("ui.screenshot", {"path": str(Path(__file__).parent / "x.png")})
    out["maximize_depuis_reduite"] = c.appel("ui.window", {"action": "maximize"})["result"]
    time.sleep(1.0)
    out["latence_apres_maximize_ms"] = lat(c)
    (Path(__file__).parent / "x.png").unlink(missing_ok=True)
    d = c.appel("document.inspect")["result"]
    out["etat_apres"] = {k: d[k] for k in ("name", "dirty", "undo")}
    sauver("q3_fenetre.json", out)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
