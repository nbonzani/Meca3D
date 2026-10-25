# SPDX-License-Identifier: GPL-3.0-or-later
"""Import réel de la bielle ouverte dans SolidCraft lancé avec `--control 7878` (manuel)."""

import tempfile
from pathlib import Path

import pytest
from outils_bielle import etude_proposee

from meca3d.cao.canal import CanalSolidCraft
from meca3d.cao.solidcraft import importer

pytestmark = pytest.mark.solidcraft


def test_ex04_import_reel_de_la_bielle_compare_aux_fixtures() -> None:
    canal = CanalSolidCraft(port=7878)
    with tempfile.TemporaryDirectory(prefix="meca3d_test_") as dossier:
        etude = importer(canal, Path(dossier))
    canal.fermer()
    angle = etude.liaison("L01_pivot").valeur_pose
    assert angle is not None
    theta = "00" if abs(angle) < 1e-6 else "60"
    reference = etude_proposee(theta)
    assert {s.nom for s in etude.solides} == {s.nom for s in reference.solides}
    for solide in reference.solides:
        lu = etude.solide(solide.nom)
        assert lu.fixe == solide.fixe
        assert lu.masse == pytest.approx(solide.masse, rel=1e-9)
        assert lu.inertie[2, 2] == pytest.approx(solide.inertie[2, 2], rel=1e-9)
        assert lu.cdg == pytest.approx(solide.cdg, abs=1e-9)
    assert [(x.nom, x.type_sc, x.solide_a, x.solide_b) for x in etude.liaisons] == [
        (x.nom, x.type_sc, x.solide_a, x.solide_b) for x in reference.liaisons
    ]
