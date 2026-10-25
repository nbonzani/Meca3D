# SPDX-License-Identifier: GPL-3.0-or-later
"""Captures de la fenêtre peuplée avec la bielle (rendu offscreen), dans docs/captures/ :
lot8_fenetre.png, lot9_saisie.png, lot9_resultats.png.

Usage : `uv run python tests/outils_capture.py`.
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", "C:/Windows/Fonts")

from pathlib import Path  # noqa: E402

from outils_bielle import etude_bielle  # noqa: E402
from PyQt6.QtCore import Qt  # noqa: E402
from PyQt6.QtGui import QFont, QImage, QPainter  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from meca3d.ihm.fenetre import FenetrePrincipale  # noqa: E402
from meca3d.modele.actions import ActionExterieure, NatureAction  # noqa: E402
from meca3d.modele.capteurs import BaseCapteur, CapteurPoint  # noqa: E402
from meca3d.modele.liaison import Statut  # noqa: E402
from meca3d.moteur.simulation import simuler_etude  # noqa: E402

DOSSIER = Path(__file__).parent.parent / "docs" / "captures"


def _fenetre() -> FenetrePrincipale:
    fenetre = FenetrePrincipale()
    fenetre.resize(1280, 760)
    fenetre.show()
    fenetre.separateur.setSizes([300, 560, 420])
    return fenetre


def capture_lot8(application: QApplication) -> None:
    etude = etude_bielle("60", 60.0)
    etude.liaison("L30_glissiere").statut = Statut.PROPOSEE  # une liaison restée à valider
    fenetre = _fenetre()
    fenetre.charger_etude(etude)
    fenetre.arbre.selectionner_liaison("L23_rotule")
    application.processEvents()
    fenetre.grab().save(str(DOSSIER / "lot8_fenetre.png"))
    fenetre.close()


def capture_lot9_saisie(application: QApplication) -> None:
    etude = etude_bielle("60", 60.0)
    manivelle = etude.solide("Manivelle")
    etude.actions = [
        ActionExterieure(
            "F1",
            "Manivelle",
            NatureAction.FORCE,
            ("0", "-5", "0"),
            point=tuple(float(x) for x in manivelle.vers_monde([0.1, 0.0, 0.0])),  # type: ignore[arg-type]
        )
    ]
    etude.capteurs = [  # type: ignore[assignment]
        CapteurPoint(
            "B",
            "Piston",
            tuple(float(x) for x in etude.solide("Piston").vers_monde([0.0, 0.0, 0.0])),  # type: ignore[arg-type]
            "Bati",
            BaseCapteur.MONDE,
        )
    ]
    fenetre = _fenetre()
    fenetre.charger_etude(etude)
    fenetre.arbre.selectionner_liaison("L01_pivot")
    editeur = fenetre.proprietes.editeur_pilote
    editeur.champ.setText("2*pi*t")
    application.processEvents()
    fenetre.grab().save(str(DOSSIER / "lot9_saisie.png"))
    fenetre.close()


def capture_lot9_resultats(application: QApplication) -> None:
    etude = etude_bielle("00")
    etude.capteurs = [
        CapteurPoint("B", "Piston", (0.0, 0.0, 0.0), "Bati", BaseCapteur.MONDE),
    ]
    fenetre = _fenetre()
    fenetre.charger_etude(etude)
    fenetre.resultats = simuler_etude(etude)
    fenetre._afficher_resultats(basculer=True)  # noqa: SLF001
    fenetre.vue_courbes.choix_y.setCurrentIndex(fenetre.vue_courbes.choix_y.findText("C (N·m)"))
    fenetre.vue_torseurs.curseur.setValue(250)
    fenetre.vue_torseurs.choix_base.setCurrentIndex(
        fenetre.vue_torseurs.choix_base.findData("monde")
    )
    fenetre.arbre.selectionner_rubrique("Courbes")
    application.processEvents()
    courbes = fenetre.grab().toImage()
    fenetre.onglets.setCurrentWidget(fenetre.vue_torseurs)
    application.processEvents()
    torseurs = fenetre.grab().toImage()
    image = QImage(
        courbes.width(), courbes.height() + torseurs.height(), QImage.Format.Format_ARGB32
    )
    image.fill(Qt.GlobalColor.white)
    peintre = QPainter(image)
    peintre.drawImage(0, 0, courbes)
    peintre.drawImage(0, courbes.height(), torseurs)
    peintre.end()
    image.save(str(DOSSIER / "lot9_resultats.png"))
    fenetre.close()


def main() -> None:
    application = QApplication.instance() or QApplication([])
    assert isinstance(application, QApplication)
    QApplication.setFont(QFont("Segoe UI", 9))
    DOSSIER.mkdir(parents=True, exist_ok=True)
    capture_lot8(application)
    capture_lot9_saisie(application)
    capture_lot9_resultats(application)


if __name__ == "__main__":
    main()
