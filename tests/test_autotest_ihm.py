# SPDX-License-Identifier: GPL-3.0-or-later
"""EX-63 : le mode d'auto-test de l'IHM (variable MECA3D_AUTOTEST_DELAI_S) sert à vérifier
l'exécutable : la fenêtre s'ouvre, attend que le processus de calcul préchauffé soit prêt, se
ferme seule. Code 0 si prêt dans le délai, 3 sinon."""

import pytest

from meca3d.ihm import fenetre

pytestmark = pytest.mark.slow

CODE_DELAI_DEPASSE = 3


def test_ex63_autotest_ihm_ferme_la_fenetre_quand_le_calcul_est_pret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MECA3D_AUTOTEST_DELAI_S", "90")
    assert fenetre.lancer() == 0


def test_ex63_autotest_ihm_delai_trop_court_donne_le_code_3(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MECA3D_AUTOTEST_DELAI_S", "0.3")
    assert fenetre.lancer() == CODE_DELAI_DEPASSE
