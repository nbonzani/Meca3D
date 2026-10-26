# SPDX-License-Identifier: GPL-3.0-or-later
"""R10 : avant d'animer, la fenêtre SolidCraft réduite est ramenée au premier plan par la méthode
de connexion `ui.window` (RESULTATS_1b § Q3, EX-53). Une fenêtre visible n'est jamais touchée.
Faux serveur : fenêtre réduite = 120 ms par requête (115 ms mesurés sur le vrai SolidCraft)."""

from collections.abc import Iterator

import pytest
from faux_serveur import JETON_DE_TEST, FauxServeur, Scenario
from outils_cinematique import etude_bielle_60

from meca3d.cao.animation import Animateur
from meca3d.cao.canal import CanalSolidCraft
from meca3d.cao.fenetre import SEUIL_LATENCE, ramener_au_premier_plan
from meca3d.moteur.cinematique import MoteurCinematique


@pytest.fixture
def faux_reduit() -> Iterator[FauxServeur]:
    with FauxServeur(theta="60", scenario=Scenario(fenetre_reduite=True)) as s:
        yield s


@pytest.fixture
def faux_visible() -> Iterator[FauxServeur]:
    with FauxServeur(theta="60") as s:
        yield s


def test_r10_fenetre_reduite_est_ramenee_par_ui_window_maximize(faux_reduit: FauxServeur) -> None:
    with CanalSolidCraft(port=faux_reduit.port, jeton=JETON_DE_TEST) as canal:
        assert ramener_au_premier_plan(canal) is True
    appels = [r for r in faux_reduit.requetes if r.get("method") == "ui.window"]
    assert len(appels) == 1  # méthode de premier niveau, pas une commande d'engine.execute
    assert appels[0]["params"] == {"action": "maximize"}
    assert faux_reduit.scenario.fenetre_reduite is False


def test_r10_fenetre_visible_n_est_pas_touchee(faux_visible: FauxServeur) -> None:
    with CanalSolidCraft(port=faux_visible.port, jeton=JETON_DE_TEST) as canal:
        assert ramener_au_premier_plan(canal) is False
    assert "ui.window" not in faux_visible.methodes_recues()


def test_r10_seuil_entre_fenetre_visible_et_reduite() -> None:
    # 34 ms visible, 115-130 ms réduite (RESULTATS_1b § Q3 et mesures du lot 12)
    assert 0.040 < SEUIL_LATENCE < 0.115


def test_r10_animation_ramene_la_fenetre_avant_la_premiere_image(
    faux_reduit: FauxServeur,
) -> None:
    etude = etude_bielle_60(duree=0.6)
    resultats = MoteurCinematique().simuler(etude)
    with CanalSolidCraft(port=faux_reduit.port, jeton=JETON_DE_TEST) as canal:
        animateur = Animateur(canal, etude, resultats)
        animateur.aller_a(0.3)
        animateur.terminer()
    noms = faux_reduit.commandes_recues()
    assert "ui.window" in noms
    assert noms.index("ui.window") < noms.index("occurrence.move")
    assert noms.count("ui.window") == 1  # une seule fois par animation


def test_r10_animation_sur_fenetre_visible_n_envoie_pas_ui_window(
    faux_visible: FauxServeur,
) -> None:
    etude = etude_bielle_60(duree=0.6)
    resultats = MoteurCinematique().simuler(etude)
    with CanalSolidCraft(port=faux_visible.port, jeton=JETON_DE_TEST) as canal:
        animateur = Animateur(canal, etude, resultats)
        animateur.aller_a(0.3)
        animateur.terminer()
    assert "ui.window" not in faux_visible.methodes_recues()
