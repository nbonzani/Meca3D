# SPDX-License-Identifier: GPL-3.0-or-later
"""EX-50 : le tableau des torseurs de l'IHM n'affiche plus de bruit numérique (capture du lot 9)."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import re  # noqa: E402

import pytest  # noqa: E402
from outils_bielle import etude_bielle  # noqa: E402
from pytestqt.qtbot import QtBot  # noqa: E402

from meca3d.ihm.vue_torseurs import VueTorseurs  # noqa: E402
from meca3d.moteur.simulation import simuler_etude  # noqa: E402

BRUIT = re.compile(r"e-(0[89]|[1-9]\d)")  # exposants inférieurs ou égaux à -8 : bruit


@pytest.mark.parametrize("base", ["monde", "liaison"])
@pytest.mark.parametrize("torseur", ["statique", "cinematique"])
def test_ex50_aucun_bruit_numerique_affiche(qtbot: QtBot, base: str, torseur: str) -> None:
    etude = etude_bielle("00")
    resultats = simuler_etude(etude)
    vue = VueTorseurs()
    qtbot.addWidget(vue)
    vue.choix_base.setCurrentIndex(vue.choix_base.findData(base))
    vue.choix_torseur.setCurrentIndex(vue.choix_torseur.findData(torseur))
    vue.afficher(etude, resultats)
    for k in (0, 250, 500):
        vue.curseur.setValue(k)
        for liaison in vue.liaisons():
            for c in range(6):
                texte = vue.table.item(vue.liaisons().index(liaison), c).text()  # type: ignore[union-attr]
                assert not BRUIT.search(texte), (k, liaison, c, texte)
                assert len(re.sub(r"[^0-9]", "", texte.split("e")[0]).lstrip("0")) <= 4


def test_ex50_en_base_de_liaison_les_composantes_nulles_par_construction_sont_zero(
    qtbot: QtBot,
) -> None:
    etude = etude_bielle("00")
    vue = VueTorseurs()
    qtbot.addWidget(vue)
    vue.choix_base.setCurrentIndex(vue.choix_base.findData("liaison"))
    vue.afficher(etude, simuler_etude(etude))
    vue.curseur.setValue(250)
    assert vue.cellule("L12_pivot", "Mx (N·m)") == "0"
