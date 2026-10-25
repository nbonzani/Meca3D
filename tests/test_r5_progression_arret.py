# SPDX-License-Identifier: GPL-3.0-or-later
"""R5 : progression et arrêt passent par des paramètres explicites du moteur, pas par une
enveloppe posée sur `exudyn_dyn.exu` dans le processus fils."""

import re
from dataclasses import replace
from pathlib import Path

import pytest
from outils_bielle import etude_bielle

from meca3d.graphe.mobilite import Mode
from meca3d.modele.etude import Reglages
from meca3d.moteur import processus
from meca3d.moteur.base import CalculAnnule
from meca3d.moteur.simulation import simuler_etude

REGLAGES = Reglages(duree=0.2, nb_pas=400, periode_ecriture=0.002)


@pytest.mark.parametrize("mode", [Mode.DYNAMIQUE, Mode.CINEMATIQUE])
def test_r5_simuler_etude_rend_la_progression_croissante_jusqua_1(mode: Mode) -> None:
    etude = replace(etude_bielle("00"), reglages=REGLAGES)
    fractions: list[float] = []
    simuler_etude(etude, mode, progression=fractions.append)
    assert len(fractions) > 10
    assert fractions == sorted(fractions)
    assert fractions[-1] == 1.0
    assert all(0.0 <= f <= 1.0 for f in fractions)


@pytest.mark.parametrize("mode", [Mode.DYNAMIQUE, Mode.CINEMATIQUE])
def test_r5_simuler_etude_sarrete_par_calcul_annule(mode: Mode) -> None:
    etude = replace(etude_bielle("00"), reglages=REGLAGES)
    fractions: list[float] = []

    def arret() -> bool:
        return len(fractions) >= 5

    with pytest.raises(CalculAnnule):
        simuler_etude(etude, mode, progression=fractions.append, arret=arret)
    assert fractions[-1] < 1.0  # arrêt avant la fin, aucun résultat renvoyé


def test_r5_processus_ne_remplace_plus_le_module_exudyn_du_moteur() -> None:
    source = Path(processus.__file__).read_text(encoding="utf-8")
    assert not re.search(r"exudyn_dyn\.exu\s*=", source)
    assert not hasattr(processus, "_ExudynSuivi")
