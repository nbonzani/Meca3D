# SPDX-License-Identifier: GPL-3.0-or-later
"""Lisibilité de la loi d'entrée pour un élève (EX-30, lot 9b) : texte saisi mis en forme
mathématique, Piecewise en « si … : … ; sinon : … », unité affichée."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from outils_bielle import LOI_MONTEE, etude_bielle  # noqa: E402
from pytestqt.qtbot import QtBot  # noqa: E402

from meca3d.ihm import textes  # noqa: E402
from meca3d.ihm.fenetre import FenetrePrincipale  # noqa: E402
from meca3d.modele.loi_affichage import loi_lisible  # noqa: E402


@pytest.mark.parametrize(
    ("saisie", "attendu"),
    [
        ("20*t", "20·t"),
        ("2*pi*t**2", "2·π·t^2"),
        ("0.5*sin(2*pi*t)", "0,5·sin(2·π·t)"),
        ("sqrt(t)", "√(t)"),
        ("(t+1)**2", "(t + 1)^2"),
        ("-t", "-t"),
        ("t - (1 - t)", "t - (1 - t)"),
        ("1/(2*t+1)", "1/(2·t + 1)"),
        ("min(t, 2)", "min(t, 2)"),
        ("10.0*t", "10·t"),
    ],
)
def test_ex30_expression_mise_en_forme_mathematique(saisie: str, attendu: str) -> None:
    assert loi_lisible(saisie) == attendu


def test_ex30_piecewise_rendu_en_si_sinon() -> None:
    assert loi_lisible(LOI_MONTEE) == (
        "si t < 0,2 : 10·(t - 0,2/π·sin(π·t/0,2)) ; sinon : 2 + 20·(t - 0,2)"
    )


def test_ex30_piecewise_sans_condition_vraie_finale() -> None:
    assert loi_lisible("Piecewise((t, t < 1), (1, t >= 1))") == "si t < 1 : t ; si t ≥ 1 : 1"


def test_ex30_texte_illisible_replie_sur_la_substitution_simple() -> None:
    assert loi_lisible("2*(") == "2·("


def test_ex30_loi_pilote_avec_unite() -> None:
    texte = textes.loi_pilote("20*t", "angle")
    assert texte == "θ(t) = 20·t  (rad)"
    assert textes.loi_pilote("0.1*t", "position") == "x(t) = 0,1·t  (m)"


def test_ex30_arbre_et_proprietes_sans_piecewise_brut(qtbot: QtBot) -> None:
    fenetre = FenetrePrincipale()
    qtbot.addWidget(fenetre)
    fenetre.charger_etude(etude_bielle("00"))
    element = fenetre.arbre.elements("Pilotes")[0]
    assert "Piecewise" not in element
    assert "si t < 0,2" in element
    assert "sinon" in element
    assert "(rad)" in element
    fenetre.arbre.selectionner_liaison("L01_pivot")
    etiquette = fenetre.proprietes.etiquette_loi.text()
    assert "Piecewise" not in etiquette
    assert "si t < 0,2" in etiquette
