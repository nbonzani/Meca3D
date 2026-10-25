# SPDX-License-Identifier: GPL-3.0-or-later
"""Capture de la fenêtre peuplée avec la bielle (rendu offscreen) : docs/captures/lot8_fenetre.png.

Usage : `uv run python tests/outils_capture.py`.
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", "C:/Windows/Fonts")

from pathlib import Path  # noqa: E402

from outils_bielle import etude_bielle  # noqa: E402
from PyQt6.QtGui import QFont  # noqa: E402
from PyQt6.QtWidgets import QApplication, QSplitter  # noqa: E402

from meca3d.ihm.fenetre import FenetrePrincipale  # noqa: E402
from meca3d.modele.liaison import Statut  # noqa: E402

SORTIE = Path(__file__).parent.parent / "docs" / "captures" / "lot8_fenetre.png"


def main() -> None:
    application = QApplication.instance() or QApplication([])
    QApplication.setFont(QFont("Segoe UI", 9))
    etude = etude_bielle("60", 60.0)
    etude.liaison("L30_glissiere").statut = Statut.PROPOSEE  # une liaison restée à valider
    fenetre = FenetrePrincipale()
    fenetre.resize(1280, 760)
    fenetre.show()
    separateur = fenetre.centralWidget()
    assert isinstance(separateur, QSplitter)
    separateur.setSizes([300, 560, 420])
    fenetre.centralWidget().setSizes([300, 560, 420])  # type: ignore[union-attr]
    fenetre.charger_etude(etude)
    fenetre.arbre.selectionner_liaison("L23_rotule")
    application.processEvents()
    SORTIE.parent.mkdir(parents=True, exist_ok=True)
    fenetre.grab().save(str(SORTIE))
    fenetre.close()


if __name__ == "__main__":
    main()
