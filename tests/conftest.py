# SPDX-License-Identifier: GPL-3.0-or-later
"""Fixtures communes.

Aucun processus de calcul ne doit survivre à un test : un processus préchauffé oublié (fenêtre
non fermée, calcul non terminé) occupe un cœur et plusieurs centaines de Mo pendant les tests
suivants et fausse les mesures de durée (lot 9b).
"""

import multiprocessing
from collections.abc import Iterator

import pytest

from meca3d.moteur.processus import arreter_tous_les_prechauffes

DELAI_ARRET = 5.0  # s


@pytest.fixture(autouse=True)
def _aucun_processus_de_calcul_survivant() -> Iterator[None]:
    yield
    arreter_tous_les_prechauffes()
    survivants = multiprocessing.active_children()
    for enfant in survivants:
        enfant.terminate()
    for enfant in survivants:
        enfant.join(timeout=DELAI_ARRET)
    assert not survivants, (
        f"{len(survivants)} processus de calcul laissés vivants par le test "
        "(fenêtre non fermée ou calcul non terminé)."
    )
