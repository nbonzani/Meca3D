# SPDX-License-Identifier: GPL-3.0-or-later
"""Branche « Animation » de la fenêtre (EX-53) et trajectoire d'un capteur de point (EX-52),
contre le faux serveur : lecture, pause, vitesse, curseur, arrêt (restauration), trajectoire."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import math  # noqa: E402
from collections.abc import Iterator  # noqa: E402

import pytest  # noqa: E402
from faux_serveur import JETON_DE_TEST, FauxServeur  # noqa: E402
from outils_cinematique import etude_bielle_60  # noqa: E402
from pytestqt.qtbot import QtBot  # noqa: E402
from test_animation import ecart_angle_deg, pose_analytique  # noqa: E402

from meca3d.cao.canal import CanalSolidCraft  # noqa: E402
from meca3d.ihm import textes  # noqa: E402
from meca3d.ihm.arbre import GENRE_RUBRIQUE  # noqa: E402
from meca3d.ihm.fenetre import FenetrePrincipale  # noqa: E402
from meca3d.modele.capteurs import BaseCapteur, CapteurPoint  # noqa: E402

pytestmark = pytest.mark.slow  # une simulation en processus séparé par test (≈ 12 s chacun)

DELAI = 120_000
DUREE = 0.4
B_IMPORT = (0.1 * math.cos(math.radians(60.0)) + math.sqrt(0.09 - 0.0075), 0.0, 0.0)


@pytest.fixture
def faux() -> Iterator[FauxServeur]:
    with FauxServeur(theta="60") as serveur:
        yield serveur


@pytest.fixture
def fenetre(qtbot: QtBot, faux: FauxServeur) -> Iterator[FenetrePrincipale]:
    f = FenetrePrincipale()
    qtbot.addWidget(f)
    f.confirmer = lambda titre, texte: True
    f.fabrique_canal = lambda: CanalSolidCraft(
        port=faux.port, jeton=JETON_DE_TEST, intervalle_pending=0.01
    )
    yield f
    f.close()


def _preparer(fenetre: FenetrePrincipale, qtbot: QtBot, avec_resultats: bool = True) -> None:
    fenetre.action_connecter.trigger()
    qtbot.waitUntil(lambda: fenetre.action_importer.isEnabled(), timeout=10_000)
    etude = etude_bielle_60(duree=DUREE)
    etude.capteurs.append(CapteurPoint("P_B", "Piston", B_IMPORT, "Bati", BaseCapteur.MONDE))
    fenetre.charger_etude(etude)
    if avec_resultats:
        fenetre.action_simuler_cinematique.trigger()
        qtbot.waitUntil(lambda: fenetre.resultats is not None, timeout=DELAI)
    fenetre.arbre.selection_changee.emit(GENRE_RUBRIQUE, textes.RUBRIQUE_ANIMATION)


def test_ex53_la_rubrique_animation_ouvre_l_onglet_commandes_inactives_sans_resultat(
    fenetre: FenetrePrincipale, qtbot: QtBot
) -> None:
    _preparer(fenetre, qtbot, avec_resultats=False)
    vue = fenetre.vue_animation
    assert fenetre.onglets.currentWidget() is vue
    assert not vue.bouton_lecture.isEnabled()
    assert not vue.curseur.isEnabled()
    assert not vue.bouton_trajectoire.isEnabled()


def test_ex53_commandes_actives_apres_la_simulation(
    fenetre: FenetrePrincipale, qtbot: QtBot
) -> None:
    _preparer(fenetre, qtbot)
    vue = fenetre.vue_animation
    assert vue.bouton_lecture.isEnabled()
    assert vue.curseur.isEnabled()
    assert vue.selecteur_vitesse.count() >= 4
    textes_vitesse = [
        vue.selecteur_vitesse.itemText(i) for i in range(vue.selecteur_vitesse.count())
    ]
    assert "×0,1" in textes_vitesse[0] and "×2" in textes_vitesse[-1]


def test_ex53_lecture_puis_pause_puis_arret_restaure_la_pose(
    fenetre: FenetrePrincipale, faux: FauxServeur, qtbot: QtBot
) -> None:
    _preparer(fenetre, qtbot)
    vue = fenetre.vue_animation
    vue.selecteur_vitesse.setCurrentIndex(0)  # ×0,1 : la lecture dure plus longtemps que le test
    vue.bouton_lecture.click()
    qtbot.waitUntil(lambda: len(faux.sequences_batch) >= 3, timeout=10_000)
    vue.bouton_lecture.click()  # pause
    assert not vue.en_lecture
    figees = len(faux.sequences_batch)
    qtbot.wait(150)
    assert len(faux.sequences_batch) == figees
    assert faux.poses_en_attente  # la pose reste affichée en pause
    vue.bouton_arret.click()
    assert faux.poses_en_attente == {}
    assert vue.curseur.value() == 0


def test_ex53_curseur_affiche_la_pose_au_temps_choisi(
    fenetre: FenetrePrincipale, faux: FauxServeur, qtbot: QtBot
) -> None:
    _preparer(fenetre, qtbot)
    vue = fenetre.vue_animation
    vue.curseur.setValue((vue.curseur.maximum() * 3) // 4)
    qtbot.waitUntil(lambda: bool(faux.poses_en_attente), timeout=10_000)
    t = DUREE * vue.curseur.value() / vue.curseur.maximum()
    angle, _ = pose_analytique(t)["Manivelle"]
    pose = faux.pose("Manivelle")
    assert ecart_angle_deg(math.atan2(pose[1, 0], pose[0, 0]), angle) <= 0.1


def test_ex53_vitesse_choisie_transmise_a_l_animateur(
    fenetre: FenetrePrincipale, qtbot: QtBot
) -> None:
    _preparer(fenetre, qtbot)
    vue = fenetre.vue_animation
    vue.selecteur_vitesse.setCurrentIndex(vue.selecteur_vitesse.count() - 1)
    assert vue.vitesse == 2.0
    vue.selecteur_vitesse.setCurrentIndex(0)
    assert vue.vitesse == pytest.approx(0.1)


def test_ex53_fin_de_lecture_restaure_la_pose(
    fenetre: FenetrePrincipale, faux: FauxServeur, qtbot: QtBot
) -> None:
    _preparer(fenetre, qtbot)
    vue = fenetre.vue_animation
    vue.selecteur_vitesse.setCurrentIndex(vue.selecteur_vitesse.count() - 1)  # ×2
    vue.bouton_lecture.click()
    qtbot.waitUntil(lambda: not vue.en_lecture and bool(faux.sequences_batch), timeout=20_000)
    assert faux.poses_en_attente == {}
    assert faux.commandes_recues()[-1] == "component.revert_position"


def test_ex53_fermer_la_fenetre_restaure_la_pose(
    fenetre: FenetrePrincipale, faux: FauxServeur, qtbot: QtBot
) -> None:
    _preparer(fenetre, qtbot)
    fenetre.vue_animation.curseur.setValue(500)
    qtbot.waitUntil(lambda: bool(faux.poses_en_attente), timeout=10_000)
    fenetre.close()
    assert faux.poses_en_attente == {}
    assert not [n for n in faux.commandes_recues() if "save" in n.lower()]


def test_ex52_tracer_puis_effacer_la_trajectoire_d_un_capteur_de_point(
    fenetre: FenetrePrincipale, faux: FauxServeur, qtbot: QtBot
) -> None:
    _preparer(fenetre, qtbot)
    vue = fenetre.vue_animation
    assert vue.choix_capteur.count() == 1
    assert vue.choix_capteur.itemText(0) == "P_B"
    vue.bouton_trajectoire.click()
    qtbot.waitUntil(lambda: len(faux.esquisses) == 1 and faux.esquisses[0].termine, timeout=10_000)
    assert faux.esquisses[0].points[0][0] == pytest.approx(B_IMPORT[0] * 1000.0, abs=1e-3)
    vue.bouton_effacer.click()
    qtbot.waitUntil(lambda: faux.esquisses == [], timeout=10_000)
