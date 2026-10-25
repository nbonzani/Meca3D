# SPDX-License-Identifier: GPL-3.0-or-later
"""EX-52 : l'action « Exporter en CSV » devient active après une simulation lancée depuis l'IHM
(constat de la capture du lot 9 : le bouton y paraissait inactif parce que le script de capture
posait `fenetre.resultats` sans rafraîchir les actions, non à cause de la fenêtre)."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from collections.abc import Iterator  # noqa: E402

import pytest  # noqa: E402
from outils_bielle import etude_bielle  # noqa: E402
from pytestqt.qtbot import QtBot  # noqa: E402

from meca3d.ihm.fenetre import FenetrePrincipale  # noqa: E402


@pytest.fixture
def fenetre(qtbot: QtBot) -> Iterator[FenetrePrincipale]:
    f = FenetrePrincipale()
    qtbot.addWidget(f)
    yield f
    f.annuler()


@pytest.mark.slow
def test_ex52_export_csv_actif_apres_une_simulation_depuis_lihm(
    fenetre: FenetrePrincipale, qtbot: QtBot
) -> None:
    fenetre.charger_etude(etude_bielle("00"))
    assert not fenetre.action_exporter_csv.isEnabled()
    fenetre.action_simuler.trigger()
    qtbot.waitUntil(lambda: fenetre.resultats is not None, timeout=120_000)
    qtbot.waitUntil(lambda: fenetre.calcul is None, timeout=10_000)
    assert fenetre.action_exporter_csv.isEnabled()
