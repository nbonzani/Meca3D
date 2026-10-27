# SPDX-License-Identifier: GPL-3.0-or-later
"""Présentation de la fenêtre (EX-61, R12) : thème clair et sombre, pastilles d'état m et h,
étapes numérotées Modèle → Données → Simulation → Résultats, barre de commandes à icônes."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from collections.abc import Iterator  # noqa: E402

import pytest  # noqa: E402
from meca3d.ihm.etapes import EtatEtape  # noqa: E402
from outils_bielle import etude_bielle, etude_proposee  # noqa: E402
from pytestqt.qtbot import QtBot  # noqa: E402

from meca3d.ihm import theme  # noqa: E402
from meca3d.ihm.fenetre import FenetrePrincipale  # noqa: E402
from meca3d.modele.etude import Reglages  # noqa: E402

DELAI = 120_000  # ms, attente maximale d'un calcul
ETAPES = ["1  Modèle", "2  Données", "3  Simulation", "4  Résultats"]
CUIVRE = "#E07A2C"  # charte méca ia : Orange Cuivre, réservé aux états (R12)
CYAN = "#00B4D8"  # charte méca ia : Cyan Signal, réservé aux états (R12)


@pytest.fixture
def fenetre(qtbot: QtBot) -> Iterator[FenetrePrincipale]:
    f = FenetrePrincipale()
    qtbot.addWidget(f)
    f.confirmer = lambda titre, texte: True
    yield f
    f.annuler()


def _luminance(couleur: tuple[float, ...]) -> float:
    """Luminance relative approchée d'une couleur RVB(A) en [0, 1]."""
    r, v, b = couleur[:3]
    return 0.2126 * r + 0.7152 * v + 0.0722 * b


def _luminance_fond(fenetre: FenetrePrincipale) -> float:
    c = fenetre.palette().color(fenetre.backgroundRole())
    return _luminance((c.redF(), c.greenF(), c.blueF()))


# --- thème clair / sombre -----------------------------------------------------------------
def test_ex61_theme_clair_par_defaut(fenetre: FenetrePrincipale) -> None:
    assert fenetre.theme is theme.Theme.CLAIR
    assert not fenetre.action_theme_sombre.isChecked()
    assert _luminance_fond(fenetre) > 0.8
    assert _luminance(fenetre.vue_courbes.figure.get_facecolor()) > 0.8
    assert _luminance(fenetre.vue_graphe.figure.get_facecolor()) > 0.8


def test_ex61_bascule_clair_sombre_et_retour(fenetre: FenetrePrincipale) -> None:
    fenetre.charger_etude(etude_bielle("60", 60.0))
    feuille_claire = fenetre.styleSheet()
    assert feuille_claire != ""
    fenetre.action_theme_sombre.trigger()
    assert fenetre.theme is theme.Theme.SOMBRE
    assert fenetre.styleSheet() != feuille_claire
    assert _luminance_fond(fenetre) < 0.25
    assert _luminance(fenetre.vue_courbes.figure.get_facecolor()) < 0.25
    assert _luminance(fenetre.vue_graphe.figure.get_facecolor()) < 0.25
    fenetre.action_theme_sombre.trigger()
    assert fenetre.theme is theme.Theme.CLAIR
    assert fenetre.styleSheet() == feuille_claire
    assert _luminance_fond(fenetre) > 0.8


def test_ex61_bascule_de_theme_sans_changement_de_comportement(
    fenetre: FenetrePrincipale,
) -> None:
    etude = etude_bielle("60", 60.0)
    fenetre.charger_etude(etude)
    avant = (fenetre.action_simuler.isEnabled(), fenetre.arbre.elements("Liaisons"))
    fenetre.action_theme_sombre.trigger()
    assert fenetre.etude is etude
    assert not fenetre.modifiee
    assert (fenetre.action_simuler.isEnabled(), fenetre.arbre.elements("Liaisons")) == avant


# --- pastilles de la barre d'état ---------------------------------------------------------
def test_ex61_pastilles_neutres_sans_etude(fenetre: FenetrePrincipale) -> None:
    assert fenetre.etiquette_m.property("etat") == theme.ETAT_NEUTRE
    assert fenetre.etiquette_h.property("etat") == theme.ETAT_NEUTRE
    assert fenetre.etiquette_connexion.property("etat") == theme.ETAT_NEUTRE


def test_ex61_pastille_h_en_alerte_si_hyperstatique(fenetre: FenetrePrincipale) -> None:
    fenetre.charger_etude(etude_proposee("60"))  # bielle, rotule en B : h = 1
    assert fenetre.etiquette_h.text() == "h = 1"
    assert fenetre.etiquette_h.property("etat") == theme.ETAT_ALERTE


def test_ex61_pastille_h_valide_si_isostatique(fenetre: FenetrePrincipale) -> None:
    fenetre.charger_etude(etude_bielle("60", 60.0))  # linéaire annulaire d'axe z : h = 0
    assert fenetre.etiquette_h.text() == "h = 0"
    assert fenetre.etiquette_h.property("etat") == theme.ETAT_OK
    assert fenetre.etiquette_m.property("etat") == theme.ETAT_OK


@pytest.mark.parametrize("choix", list(theme.Theme))
def test_ex61_couleurs_des_pastilles_cyan_et_cuivre(choix: theme.Theme) -> None:
    feuille = theme.feuille_de_style(choix)
    assert f'[etat="{theme.ETAT_ALERTE}"]' in feuille
    assert f'[etat="{theme.ETAT_OK}"]' in feuille
    assert CUIVRE.lower() in feuille.lower()
    assert CYAN.lower() in feuille.lower()


# --- étapes numérotées ----------------------------------------------------------------------
def test_ex61_etapes_numerotees_a_faire_sans_etude(fenetre: FenetrePrincipale) -> None:
    assert fenetre.etapes.libelles() == ETAPES
    assert fenetre.etapes.etats() == [EtatEtape.A_FAIRE] * 4


def test_ex61_etape_modele_incomplete_si_liaison_proposee(fenetre: FenetrePrincipale) -> None:
    fenetre.charger_etude(etude_proposee("60"))
    etats = fenetre.etapes.etats()
    assert etats[0] is EtatEtape.INCOMPLET
    assert etats[2] is EtatEtape.A_FAIRE  # simulation impossible
    assert etats[3] is EtatEtape.A_FAIRE


def test_ex61_etapes_pret_a_simuler(fenetre: FenetrePrincipale) -> None:
    fenetre.charger_etude(etude_bielle("60", 60.0))
    assert fenetre.etapes.etats() == [
        EtatEtape.FAIT,
        EtatEtape.FAIT,
        EtatEtape.PRET,
        EtatEtape.A_FAIRE,
    ]


def test_ex61_etapes_toutes_faites_apres_simulation(
    fenetre: FenetrePrincipale, qtbot: QtBot
) -> None:
    etude = etude_bielle("60", 60.0)
    etude.reglages = Reglages(duree=0.05, nb_pas=200, periode_ecriture=0.002)
    fenetre.charger_etude(etude)
    fenetre.action_simuler.trigger()
    qtbot.waitUntil(lambda: fenetre.resultats is not None, timeout=DELAI)
    assert fenetre.etapes.etats() == [EtatEtape.FAIT] * 4


def test_ex61_clic_sur_une_etape_selectionne_sa_branche(fenetre: FenetrePrincipale) -> None:
    fenetre.charger_etude(etude_bielle("60", 60.0))
    fenetre.etapes.bouton(1).click()
    courant = fenetre.arbre.currentItem()
    assert courant is fenetre.arbre.item_branche("Données d'entrée")
    fenetre.etapes.bouton(3).click()
    assert fenetre.arbre.currentItem() is fenetre.arbre.item_branche("Résultats")
    assert fenetre.onglets.currentWidget() is fenetre.vue_courbes


# --- barre de commandes ---------------------------------------------------------------------
def test_ex61_barre_de_commandes_a_icones(fenetre: FenetrePrincipale) -> None:
    actions = fenetre.barre_commandes.actions()
    visibles = [a for a in actions if not a.isSeparator() and a.isVisible()]
    assert visibles
    assert all(not a.icon().isNull() for a in visibles)
