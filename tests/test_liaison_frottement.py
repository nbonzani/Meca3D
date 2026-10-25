# SPDX-License-Identifier: GPL-3.0-or-later
"""Données de frottement (EX-15) et de pas (hélicoïdale, EX-10) portées par la liaison."""

import numpy as np
import pytest

from meca3d.modele.liaison import Liaison, TypeLiaison


def _liaison(**options: object) -> Liaison:
    return Liaison(
        nom="L",
        type_sc="revolute",
        solide_a="A",
        solide_b="B",
        centre=np.zeros(3),
        axe_sc=np.array([0.0, 0.0, 1.0]),
        valeur_pose=0.0,
        type=TypeLiaison.PIVOT,
        **options,  # type: ignore[arg-type]
    )


def test_ex15_valeurs_par_defaut_liaison_parfaite() -> None:
    x = _liaison()
    assert x.frottement == 0.0
    assert x.rayon_axe is None
    assert x.pas is None
    assert x.epsilon is None


def test_ex15_fichier_inchange_sans_frottement() -> None:
    """Les clés de frottement et de pas ne sont écrites que si elles sont renseignées : les
    fichiers .meca3d existants restent identiques."""
    d = _liaison().vers_dict()
    assert not {"frottement", "rayon_axe", "pas", "epsilon"} & d.keys()


def test_ex15_aller_retour_dict() -> None:
    x = _liaison(frottement=0.1, rayon_axe=0.005, pas=0.005, epsilon=2e-4)
    d = x.vers_dict()
    y = Liaison.depuis_dict(d)
    assert (y.frottement, y.rayon_axe, y.pas, y.epsilon) == (0.1, 0.005, 0.005, 2e-4)
    assert y.vers_dict() == d


@pytest.mark.parametrize(
    "options",
    [
        {"frottement": -0.1},
        {"frottement": float("nan")},
        {"rayon_axe": 0.0},
        {"rayon_axe": -1.0},
        {"pas": 0.0},
        {"epsilon": -1e-4},
    ],
)
def test_ex15_valeurs_invalides_refusees(options: dict[str, float]) -> None:
    with pytest.raises(ValueError, match="Liaison L"):
        _liaison(**options)


def test_ex15_validation_apres_saisie() -> None:
    x = _liaison()
    x.frottement = -1.0
    with pytest.raises(ValueError, match="frottement"):
        x.valider()
