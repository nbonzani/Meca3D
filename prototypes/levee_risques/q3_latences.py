"""Q3 : latence par type de requête sur une connexion persistante (médiane et p95, en ms)."""

from __future__ import annotations

import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from sc_client import Client, sauver


def mesurer(f, n: int = 40) -> dict:
    t = []
    for _ in range(n):
        t0 = time.perf_counter()
        f()
        t.append(1000 * (time.perf_counter() - t0))
    t.sort()
    return {"n": n, "mediane_ms": statistics.median(t), "p95_ms": t[int(0.95 * n) - 1],
            "max_ms": t[-1]}


def main() -> None:
    c = Client()
    out = {}
    out["document.inspect"] = mesurer(lambda: c.appel("document.inspect"))
    out["joint.list"] = mesurer(lambda: c.cmd("joint.list"))
    out["component.list"] = mesurer(lambda: c.cmd("component.list"))
    out["engine.commands"] = mesurer(lambda: c.appel("engine.commands"), 5)
    k = [0]

    def drive():
        k[0] += 1
        c.cmd("joint.drive", {"joint": "L01_pivot", "value": 60 + (k[0] % 2) * 0.5, "quiet": True})

    out["joint.drive"] = mesurer(drive)
    c.cmd("joint.drive", {"joint": "L01_pivot", "value": 59.99999999999999, "quiet": True})
    j = [0]

    def move():
        j[0] += 1
        s = 1 if j[0] % 2 else -1
        c.cmd("occurrence.move", {"occurrence": 11, "space": "world", "translate": [s * 1.0, 0, 0],
                                  "capture": False})

    out["occurrence.move(capture=false)"] = mesurer(move)
    c.cmd("component.revert_position", {})
    sauver("q3_latences.json", out)
    for k_, v in out.items():
        print(k_, {a: round(b, 1) for a, b in v.items()})


if __name__ == "__main__":
    main()
