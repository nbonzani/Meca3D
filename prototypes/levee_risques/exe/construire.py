"""Construit l'exécutable de test (PyInstaller, mode dossier) et relève la taille de dist/.

À lancer avec le python du venv local : .venv/Scripts/python.exe construire.py
Options PyInstaller retenues :
  --hidden-import exudyn.exudynCPP   indispensable : Exudyn charge son module compilé par importlib
  --exclude-module tkinter           facultatif : tkinter est tiré par exudyn.utilities (tcl/tk = 8 Mo)
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ICI = Path(__file__).parent
OPTIONS = [
    "--noconfirm", "--clean", "--onedir", "--name", "mini_meca3d",
    "--hidden-import", "exudyn.exudynCPP",
    "--exclude-module", "tkinter",
]


def taille_mo(dossier: Path) -> float:
    return sum(f.stat().st_size for f in dossier.rglob("*") if f.is_file()) / 1e6


def main() -> None:
    cmd = [sys.executable, "-m", "PyInstaller", *OPTIONS, str(ICI / "mini_meca3d.py")]
    subprocess.run(cmd, cwd=ICI, check=True)
    dist = ICI / "dist" / "mini_meca3d"
    fichiers = [f for f in dist.rglob("*") if f.is_file()]
    bilan = {
        "commande": "pyinstaller " + " ".join(OPTIONS) + " mini_meca3d.py",
        "taille_dist_Mo": round(taille_mo(dist), 1),
        "nombre_de_fichiers": len(fichiers),
        "plus_gros": sorted(((f.name, round(f.stat().st_size / 1e6, 1)) for f in fichiers),
                            key=lambda x: -x[1])[:8],
    }
    (ICI / "sorties").mkdir(exist_ok=True)
    (ICI / "sorties" / "bilan_construction.json").write_text(
        json.dumps(bilan, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(bilan, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
