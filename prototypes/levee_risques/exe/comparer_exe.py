"""Compare les résultats numériques du mode source et de l'exécutable (écart attendu < 1e-12)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

CLES = ("theta_fin_rad", "somme_theta", "norme_force_max_N")


def aplatir(d: dict) -> dict[str, float]:
    out = {k: float(d[k]) for k in CLES}
    for i, v in enumerate(d["force_locale_fin_N"]):
        out[f"force_locale_fin_N[{i}]"] = float(v)
    out["n_points"] = float(d["n_points"])
    return out


def main(a: Path, b: Path) -> int:
    ra = json.loads(a.read_text(encoding="utf-8"))
    rb = json.loads(b.read_text(encoding="utf-8"))
    fa, fb = aplatir(ra), aplatir(rb)
    pire = 0.0
    for k in fa:
        e = abs(fa[k] - fb[k])
        pire = max(pire, e)
        print(f"{k:28s} source={fa[k]!r:26} exe={fb[k]!r:26} ecart={e:.3e}")
    print(f"mode {ra['mode']} / {rb['mode']} ; pid parent {ra['pid_parent']} / calcul {ra['pid_calcul']}"
          f" ; pid parent {rb['pid_parent']} / calcul {rb['pid_calcul']}")
    print(f"écart absolu maximal = {pire:.3e}  ->  {'OK' if pire < 1e-12 else 'ECHEC'}")
    return 0 if pire < 1e-12 else 1


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1]), Path(sys.argv[2])))
