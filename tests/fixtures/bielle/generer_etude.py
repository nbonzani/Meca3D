# SPDX-License-Identifier: GPL-3.0-or-later
"""Génère UNE fois tests/fixtures/bielle/bielle.meca3d depuis les réponses enregistrées.

Usage : uv run python tests/fixtures/bielle/generer_etude.py
"""

import sys
from pathlib import Path

RACINE_TESTS = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE_TESTS))

from meca3d.modele.etude import ecrire_etude  # noqa: E402
from outils_bielle import etude_bielle  # noqa: E402


def main() -> None:
    sortie = Path(__file__).resolve().parent / "bielle.meca3d"
    ecrire_etude(etude_bielle("00"), sortie)
    print(f"Étude écrite : {sortie}")


if __name__ == "__main__":
    main()
