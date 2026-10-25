# SPDX-License-Identifier: GPL-3.0-or-later
"""Résultats dans l'IHM : courbes, min/max/moyenne, tableau des torseurs, export CSV (EX-50,
EX-52). La bielle est simulée depuis la fenêtre (processus de calcul séparé)."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from collections.abc import Iterator  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402
import pytest  # noqa: E402
import reference_bielle as ref  # noqa: E402
from outils_bielle import etude_bielle  # noqa: E402
from pytestqt.qtbot import QtBot  # noqa: E402

from meca3d import cli  # noqa: E402
from meca3d.ihm.fenetre import FenetrePrincipale  # noqa: E402
from meca3d.modele.capteurs import BaseCapteur, CapteurPoint  # noqa: E402
from meca3d.modele.etude import Etude, ecrire_etude  # noqa: E402

DELAI = 120_000
COUPLE = "C (N·m)"
TEMPS = "t (s)"
TOLERANCE_EX40 = 5e-3


@pytest.fixture
def fenetre(qtbot: QtBot) -> Iterator[FenetrePrincipale]:
    f = FenetrePrincipale()
    qtbot.addWidget(f)
    f.confirmer = lambda titre, texte: True
    yield f
    f.annuler()


def _simuler(fenetre: FenetrePrincipale, qtbot: QtBot, etude: Etude) -> None:
    fenetre.charger_etude(etude)
    fenetre.action_simuler.trigger()
    qtbot.waitUntil(lambda: fenetre.resultats is not None, timeout=DELAI)


def _lire_csv(chemin: Path) -> dict[str, np.ndarray]:
    lignes = chemin.read_bytes().decode("utf-8-sig").splitlines()
    entetes = lignes[0].split(";")
    valeurs = np.array(
        [[float(c.replace(",", ".")) for c in ligne.split(";")] for ligne in lignes[1:]]
    )
    return {nom: valeurs[:, i] for i, nom in enumerate(entetes)}


@pytest.mark.slow
def test_ex52_courbe_du_couple_moteur_min_max_moyenne_coherents_avec_le_csv(
    fenetre: FenetrePrincipale, qtbot: QtBot, tmp_path: Path
) -> None:
    _simuler(fenetre, qtbot, etude_bielle("00"))
    vue = fenetre.vue_courbes
    assert COUPLE in vue.grandeurs()
    assert TEMPS in vue.grandeurs()
    vue.choix_x.setCurrentIndex(vue.choix_x.findText(TEMPS))
    vue.choix_y.setCurrentIndex(vue.choix_y.findText(COUPLE))
    x, y = vue.donnees_courbe()
    assert len(x) == len(y) == 501
    chemin = tmp_path / "bielle.csv"
    assert fenetre.exporter_csv(chemin)
    csv = _lire_csv(chemin)
    assert y == pytest.approx(csv[COUPLE], abs=1e-12, rel=1e-12)
    mini, maxi, moyenne = vue.statistiques()
    assert mini == pytest.approx(csv[COUPLE].min(), abs=1e-12, rel=1e-12)
    assert maxi == pytest.approx(csv[COUPLE].max(), abs=1e-12, rel=1e-12)
    assert moyenne == pytest.approx(csv[COUPLE].mean(), abs=1e-12, rel=1e-12)
    texte = vue.etiquette_stats.text()
    for valeur in (mini, maxi, moyenne):
        assert format(valeur, ".6g") in texte
    assert "N·m" in texte
    # le couple moteur est conforme à la référence Newton-Euler (EX-40)
    t = np.array(x)
    refs = np.array([ref.reference(float(ti))["C"] for ti in t])
    assert np.abs(y - refs).max() / np.abs(refs).max() <= TOLERANCE_EX40


@pytest.mark.slow
def test_ex52_toute_grandeur_en_fonction_dune_autre(
    fenetre: FenetrePrincipale, qtbot: QtBot
) -> None:
    _simuler(fenetre, qtbot, etude_bielle("00"))
    vue = fenetre.vue_courbes
    autres = [g for g in vue.grandeurs() if g not in (TEMPS, COUPLE)]
    assert len(autres) > 5
    vue.choix_x.setCurrentIndex(vue.choix_x.findText(autres[0]))
    vue.choix_y.setCurrentIndex(vue.choix_y.findText(COUPLE))
    x, y = vue.donnees_courbe()
    assert len(x) == len(y) == 501
    assert not np.array_equal(x, fenetre.vue_courbes.donnees_courbe()[1])


@pytest.mark.slow
def test_ex51_un_capteur_ajoute_apres_la_simulation_apparait_dans_les_courbes(
    fenetre: FenetrePrincipale, qtbot: QtBot
) -> None:
    etude = etude_bielle("00")
    _simuler(fenetre, qtbot, etude)
    assert not any(g.startswith("B ") for g in fenetre.vue_courbes.grandeurs())
    fenetre.arbre.selectionner_rubrique("Capteurs")
    e = fenetre.proprietes.editeur_capteur
    e.choix_genre.setCurrentIndex(e.choix_genre.findData("point"))
    e.champ_nom.setText("B")
    e.choix_solide.setCurrentIndex(e.choix_solide.findText("Piston"))
    e.choix_reference.setCurrentIndex(e.choix_reference.findText("Bati"))
    e.choix_base_point.setCurrentIndex(e.choix_base_point.findData(BaseCapteur.MONDE))
    e.bouton_ajouter.click()
    assert isinstance(etude.capteurs[0], CapteurPoint)
    assert fenetre.resultats is not None  # les résultats ne sont pas invalidés
    assert "B x (m)" in fenetre.vue_courbes.grandeurs()


@pytest.mark.slow
def test_ex50_tableau_des_torseurs_a_linstant_choisi(
    fenetre: FenetrePrincipale, qtbot: QtBot
) -> None:
    _simuler(fenetre, qtbot, etude_bielle("00"))
    vue = fenetre.vue_torseurs
    assert vue.curseur.maximum() == 500
    vue.curseur.setValue(250)
    assert vue.instant() == pytest.approx(0.5, abs=1e-9)
    # R(0→1) = {bâti → manivelle}, base monde, conforme à la référence Newton-Euler (EX-40)
    vue.choix_sens.setCurrentIndex(vue.choix_sens.findData("i_vers_j"))
    vue.choix_base.setCurrentIndex(vue.choix_base.findData("monde"))
    t = np.arange(501) * 0.002
    o = np.array([ref.reference(float(ti))["O"] for ti in t])
    echelle = np.abs(o).max()
    assert vue.valeur("L01_pivot", "Fx (N)") == pytest.approx(
        o[250][0], abs=TOLERANCE_EX40 * echelle
    )
    assert vue.valeur("L01_pivot", "Fy (N)") == pytest.approx(
        o[250][1], abs=TOLERANCE_EX40 * echelle
    )
    # composante nulle par construction (axe libre de la pivot L12, base de liaison) : 0 exact
    vue.choix_base.setCurrentIndex(vue.choix_base.findData("liaison"))
    assert vue.cellule("L12_pivot", "Mx (N·m)") == "0"
    assert vue.valeur("L12_pivot", "Mx (N·m)") == 0.0
    # une ligne par liaison
    assert vue.liaisons() == ["L01_pivot", "L12_pivot", "L23_rotule", "L30_glissiere"]


@pytest.mark.slow
def test_ex50_torseur_cinematique_disponible_dans_le_tableau(
    fenetre: FenetrePrincipale, qtbot: QtBot
) -> None:
    _simuler(fenetre, qtbot, etude_bielle("00"))
    vue = fenetre.vue_torseurs
    vue.choix_torseur.setCurrentIndex(vue.choix_torseur.findData("cinematique"))
    vue.choix_base.setCurrentIndex(vue.choix_base.findData("liaison"))
    vue.curseur.setValue(400)
    # pivot L01 : seule la rotation d'axe x local est libre, à ω = 20 rad/s après la montée
    assert abs(vue.valeur("L01_pivot", "Ωx (rad/s)")) == pytest.approx(20.0, rel=1e-2)
    assert vue.valeur("L01_pivot", "Vx (m/s)") == 0.0


@pytest.mark.slow
def test_ex52_export_csv_depuis_lihm_identique_a_meca3d_simuler(
    fenetre: FenetrePrincipale, qtbot: QtBot, tmp_path: Path
) -> None:
    etude = etude_bielle("00")
    _simuler(fenetre, qtbot, etude)
    depuis_ihm = tmp_path / "ihm.csv"
    assert fenetre.exporter_csv(depuis_ihm)
    fichier = tmp_path / "etude.meca3d"
    ecrire_etude(etude, fichier)
    depuis_cli = tmp_path / "cli.csv"
    assert cli.main(["simuler", str(fichier), "--csv", str(depuis_cli)]) == 0
    assert depuis_ihm.read_bytes() == depuis_cli.read_bytes()


def test_ex52_export_csv_sans_resultat_refuse(fenetre: FenetrePrincipale, tmp_path: Path) -> None:
    fenetre.charger_etude(etude_bielle("00"))
    chemin = tmp_path / "vide.csv"
    assert not fenetre.exporter_csv(chemin)
    assert not chemin.exists()
    assert "résultat" in fenetre.dernier_message.lower()
