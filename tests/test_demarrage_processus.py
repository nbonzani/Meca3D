# SPDX-License-Identifier: GPL-3.0-or-later
"""Démarrage du processus de calcul (R6) : processus préchauffé à l'ouverture de la fenêtre.

Avant le lot 9, le premier calcul de la bielle coûtait environ 5 s de plus qu'en direct (import de
sympy, numpy et exudyn dans le processus fils, démarrage spawn).
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import time  # noqa: E402
from collections.abc import (
    Callable,  # noqa: E402
    Iterator,  # noqa: E402
)

import numpy as np  # noqa: E402
import pytest  # noqa: E402
from outils_bielle import etude_bielle  # noqa: E402
from pytestqt.qtbot import QtBot  # noqa: E402

from meca3d.ihm.fenetre import FenetrePrincipale  # noqa: E402
from meca3d.moteur.processus import CalculEnCours, EtatCalcul, ProcessusPrechauffe  # noqa: E402
from meca3d.moteur.simulation import simuler_etude  # noqa: E402

CONSIGNE_PREMIER_CALCUL = 3.0  # s (consigne du lot 9)
DELAI_PRECHAUFFAGE = 90_000  # ms


@pytest.fixture
def fenetre(qtbot: QtBot) -> Iterator[FenetrePrincipale]:
    f = FenetrePrincipale()
    qtbot.addWidget(f)
    yield f
    f.annuler()


def test_r6_premier_calcul_depuis_lihm_prechauffee(
    fenetre: FenetrePrincipale, qtbot: QtBot, record_property: Callable[[str, object], None]
) -> None:
    fenetre.charger_etude(etude_bielle("60", 60.0))
    fenetre.show()  # l'ouverture de la fenêtre lance le préchauffage
    qtbot.waitUntil(fenetre.prechauffe_pret, timeout=DELAI_PRECHAUFFAGE)
    debut = time.perf_counter()
    fenetre.action_simuler.trigger()
    qtbot.waitUntil(lambda: fenetre.resultats is not None, timeout=60_000)
    duree = time.perf_counter() - debut
    record_property("duree_premier_calcul_s", round(duree, 3))
    print(f"\nR6 : premier calcul de la bielle depuis l'IHM préchauffée : {duree:.2f} s")
    assert duree < CONSIGNE_PREMIER_CALCUL


def test_r6_deuxieme_calcul_aussi_prechauffe(fenetre: FenetrePrincipale, qtbot: QtBot) -> None:
    fenetre.charger_etude(etude_bielle("60", 60.0))
    fenetre.show()
    qtbot.waitUntil(fenetre.prechauffe_pret, timeout=DELAI_PRECHAUFFAGE)
    fenetre.action_simuler.trigger()
    qtbot.waitUntil(lambda: fenetre.resultats is not None, timeout=60_000)
    qtbot.waitUntil(fenetre.prechauffe_pret, timeout=DELAI_PRECHAUFFAGE)  # processus suivant


def test_r6_processus_prechauffe_resultats_identiques_au_calcul_direct() -> None:
    etude = etude_bielle("60", 60.0)
    chaud = ProcessusPrechauffe()
    chaud.demarrer()
    try:
        deadline = time.perf_counter() + DELAI_PRECHAUFFAGE / 1000
        while not chaud.pret and time.perf_counter() < deadline:
            time.sleep(0.05)  # test hors Qt : attente passive du processus
        assert chaud.pret
        assert chaud.disponible
        calcul = CalculEnCours(etude)
        calcul.demarrer(chaud)
        assert not chaud.disponible  # consommé
        assert calcul.attendre(timeout=60.0) is EtatCalcul.TERMINE
        direct = simuler_etude(etude)
        assert calcul.resultats is not None
        assert np.array_equal(calcul.resultats.t, direct.t)
        assert np.array_equal(calcul.resultats.positions["Piston"], direct.positions["Piston"])
    finally:
        chaud.arreter()


def test_r6_arret_dun_processus_prechauffe_inutilise_est_rapide() -> None:
    chaud = ProcessusPrechauffe()
    chaud.demarrer()
    debut = time.perf_counter()
    chaud.arreter()
    assert time.perf_counter() - debut < 2.0
    assert not chaud.vivant
    assert not chaud.disponible
