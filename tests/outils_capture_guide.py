# SPDX-License-Identifier: GPL-3.0-or-later
"""Captures du guide utilisateur (rendu offscreen), dans docs/guide/captures/, à partir des
études d'exemple livrées (`exemples/`).

Usage : `uv run python tests/outils_capture_guide.py`.
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", "C:/Windows/Fonts")

from pathlib import Path  # noqa: E402

from PyQt6.QtGui import QFont  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from meca3d.ihm.fenetre import FenetrePrincipale  # noqa: E402
from meca3d.modele.liaison import TypeLiaison  # noqa: E402
from meca3d.moteur.simulation import simuler_etude  # noqa: E402

RACINE = Path(__file__).resolve().parents[1]
EXEMPLES = RACINE / "exemples"
DOSSIER = RACINE / "docs" / "guide" / "captures"


def _fenetre(exemple: str) -> FenetrePrincipale:
    fenetre = FenetrePrincipale()
    fenetre.confirmer = lambda titre, texte: True
    fenetre.resize(1280, 760)
    fenetre.show()
    fenetre.separateur.setSizes([300, 560, 420])
    assert fenetre.ouvrir_etude(EXEMPLES / f"{exemple}.meca3d")
    return fenetre


def _selectionner(fenetre: FenetrePrincipale, debut: str) -> None:
    """Sélectionne dans l'arbre le premier élément dont le texte commence par `debut`."""
    for item in fenetre.arbre._tous():  # noqa: SLF001
        if item.text(0).removeprefix("⚠ ").startswith(debut):
            fenetre.arbre.setCurrentItem(item)
            return
    raise KeyError(debut)


def _simuler(fenetre: FenetrePrincipale) -> None:
    etude = fenetre.etude
    assert etude is not None
    fenetre.resultats = simuler_etude(etude)
    fenetre._afficher_resultats(basculer=True)  # noqa: SLF001
    fenetre._maj_actions()  # noqa: SLF001


def _courbe(fenetre: FenetrePrincipale, x: str, y: str) -> None:
    vue = fenetre.vue_courbes
    vue.choix_x.setCurrentIndex(vue.choix_x.findText(x))
    vue.choix_y.setCurrentIndex(vue.choix_y.findText(y))


def _enregistrer(application: QApplication, fenetre: FenetrePrincipale, nom: str) -> None:
    application.processEvents()
    fenetre.grab().save(str(DOSSIER / f"{nom}.png"))
    print(nom)


def main() -> None:
    application = QApplication.instance() or QApplication([])
    assert isinstance(application, QApplication)
    QApplication.setFont(QFont("Segoe UI", 9))
    DOSSIER.mkdir(parents=True, exist_ok=True)

    f = _fenetre("bielle_manivelle")
    _selectionner(f, "Graphe")
    _enregistrer(application, f, "g01_ouverture_graphe")
    f.arbre.selectionner_liaison("L23_rotule")
    _enregistrer(application, f, "g02_liaison")
    _selectionner(f, "L01_pivot :")
    _enregistrer(application, f, "g04_loi_entree")
    _selectionner(f, "B_piston")
    _enregistrer(application, f, "g05_capteur")
    _simuler(f)
    _selectionner(f, "Courbes")
    _courbe(f, "t (s)", "B_piston x (m)")
    _enregistrer(application, f, "g06_courbes")
    f.vue_torseurs.curseur.setValue(250)
    f.onglets.setCurrentWidget(f.vue_torseurs)
    _enregistrer(application, f, "g07_torseurs")
    f.onglets.setCurrentWidget(f.journal)
    _enregistrer(application, f, "g08_journal")
    f.close()

    # Choix initial proposé (rotule en B) : h = 1, la simulation est refusée
    f = _fenetre("bielle_manivelle")
    etude = f.etude
    assert etude is not None
    etude.liaison("L23_rotule").type = TypeLiaison.ROTULE
    etude.liaison("L23_rotule").valider()
    f.charger_etude(etude)
    _selectionner(f, "Graphe")
    _enregistrer(application, f, "g03_hyperstatique")
    f.close()

    f = _fenetre("reducteur")
    _selectionner(f, "Graphe")
    _enregistrer(application, f, "g09_reducteur")
    f.close()

    f = _fenetre("pendule_double")
    _simuler(f)
    _selectionner(f, "Courbes")
    _courbe(f, "Bout_barre2 x (m)", "Bout_barre2 z (m)")
    _enregistrer(application, f, "g10_pendule_double")
    f.close()


if __name__ == "__main__":
    main()
