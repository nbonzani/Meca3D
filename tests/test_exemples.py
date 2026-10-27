# SPDX-License-Identifier: GPL-3.0-or-later
"""Études d'exemple livrées (`exemples/`) : chacune s'ouvre complète et se simule.

À l'ouverture : liaisons toutes validées, h = 0, aucun élément de l'arbre signalé incomplet,
bouton Simuler actif, maquette SolidCraft présente à côté. Simulation (slow) : le calcul aboutit
et les grandeurs caractéristiques sont celles de la SPEC (EX-14) ou de la conception de l'exemple.
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from collections.abc import Iterator  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402
import pytest  # noqa: E402
from pytestqt.qtbot import QtBot  # noqa: E402

from meca3d.graphe.mobilite import Mode  # noqa: E402
from meca3d.ihm.fenetre import FenetrePrincipale  # noqa: E402
from meca3d.modele.etude import lire_etude  # noqa: E402
from meca3d.modele.liaison import Statut  # noqa: E402
from meca3d.moteur.simulation import analyser_etude, simuler_etude  # noqa: E402
from meca3d.resultats.export import colonnes_resultats  # noqa: E402

EXEMPLES = Path(__file__).resolve().parents[1] / "exemples"
NOMS = ["bielle_manivelle", "pendule_simple", "pendule_double", "reducteur", "vis_ecrou"]
# (m, nombre de lois d'entrée) attendus : les pendules sont en mouvement libre
MOBILITES = {
    "bielle_manivelle": (1, 1),
    "pendule_simple": (1, 0),
    "pendule_double": (2, 0),
    "reducteur": (1, 1),
    "vis_ecrou": (1, 1),
}


@pytest.fixture
def fenetre(qtbot: QtBot) -> Iterator[FenetrePrincipale]:
    f = FenetrePrincipale()
    qtbot.addWidget(f)
    f.confirmer = lambda titre, texte: True
    yield f
    f.annuler()


def test_exemples_presents() -> None:
    assert sorted(p.stem for p in EXEMPLES.glob("*.meca3d")) == sorted(NOMS)


@pytest.mark.parametrize("nom", NOMS)
def test_exemple_complet(nom: str) -> None:
    etude = lire_etude(EXEMPLES / f"{nom}.meca3d")
    assert (EXEMPLES / etude.maquette).is_file()
    assert all(x.statut is Statut.VALIDEE for x in etude.liaisons)
    assert len(etude.capteurs) >= 2
    r = analyser_etude(etude).resultat
    assert r.h == 0
    assert (r.m, len(etude.pilotes)) == MOBILITES[nom]


@pytest.mark.parametrize("nom", NOMS)
def test_exemple_ouvert_sans_element_incomplet(fenetre: FenetrePrincipale, nom: str) -> None:
    assert fenetre.ouvrir_etude(EXEMPLES / f"{nom}.meca3d")
    arbre = fenetre.arbre
    for branche in arbre.branches():
        assert not arbre.est_incomplet(arbre.item_branche(branche)), branche
    assert fenetre.action_simuler.isEnabled()


@pytest.mark.slow
@pytest.mark.parametrize("nom", NOMS)
def test_exemple_simule(nom: str) -> None:
    etude = lire_etude(EXEMPLES / f"{nom}.meca3d")
    res = simuler_etude(etude, Mode.DYNAMIQUE)
    colonnes = colonnes_resultats(etude, res)
    assert all(np.isfinite(v).all() for v in colonnes.values())
    if nom == "reducteur":  # EX-14 : |ω_s| = 10 rad/s pour ω_e = 30 rad/s
        assert abs(res.vitesses_angulaires["Roue2"][-1, 2]) == pytest.approx(10.0, rel=1e-3)
    if nom == "vis_ecrou":  # EX-14 : v = 7,9577 mm/s pour ω = 10 rad/s
        assert res.vitesses["Ecrou"][-1, 2] == pytest.approx(7.9577e-3, rel=1e-4)
    if MOBILITES[nom][0] == MOBILITES[nom][1]:
        cinematique = simuler_etude(etude, Mode.CINEMATIQUE)
        assert np.isfinite(cinematique.positions[etude.solides[-1].nom]).all()


@pytest.mark.parametrize(
    ("nom", "attendu"), [("reducteur", "engrenage k = 0.3333"), ("vis_ecrou", "vis-écrou p = 5 mm")]
)
def test_ex14_couplage_visible_sur_le_graphe(
    fenetre: FenetrePrincipale, nom: str, attendu: str
) -> None:
    """Le couplage lu dans SolidCraft est tracé sur le graphe des liaisons, avec son rapport."""
    assert fenetre.ouvrir_etude(EXEMPLES / f"{nom}.meca3d")
    textes = [t.get_text() for ax in fenetre.vue_graphe.figure.axes for t in ax.texts]
    assert attendu in textes


def test_dialogue_ouvrir_part_du_dossier_exemples() -> None:
    from meca3d.ihm.fenetre import dossier_exemples

    assert dossier_exemples() == EXEMPLES
