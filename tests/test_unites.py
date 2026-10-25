# SPDX-License-Identifier: GPL-3.0-or-later
"""Conversions d'unités, matrices par colonnes, base de liaison (EX-12)."""

import math

import numpy as np
import pytest

from meca3d import unites


def test_conversions_scalaires() -> None:
    assert unites.mm_vers_m(400.0) == pytest.approx(0.4, rel=1e-15)
    assert unites.m_vers_mm(0.4) == pytest.approx(400.0, rel=1e-15)
    assert unites.g_vers_kg(936.0) == pytest.approx(0.936, rel=1e-15)
    assert unites.kg_vers_g(0.5) == pytest.approx(500.0, rel=1e-15)
    assert unites.deg_vers_rad(180.0) == pytest.approx(math.pi, rel=1e-15)
    assert unites.rad_vers_deg(math.pi / 2) == pytest.approx(90.0, rel=1e-15)


def test_conversions_vecteurs() -> None:
    v = unites.mm_vers_m(np.array([100.0, 0.0, -30.0]))
    assert v == pytest.approx([0.1, 0.0, -0.03], abs=1e-15)


def test_transformation_stockee_par_colonnes() -> None:
    # Manivelle à 60° (component_list_theta60) : la ligne 0 stockée est l'image de x
    stockee = [
        [0.5000000000000001, 0.8660254037844386, 0.0, 0.0],
        [-0.8660254037844386, 0.5000000000000001, 0.0, 0.0],
        [0.0, 0.0, 1.0, 0.0],
        [0.0, 0.0, 0.0, 1.0],
    ]
    rotation, translation = unites.rotation_translation(stockee)
    assert rotation[:, 0] == pytest.approx([0.5, math.sqrt(3) / 2, 0.0], abs=1e-12)
    assert rotation[:, 1] == pytest.approx([-math.sqrt(3) / 2, 0.5, 0.0], abs=1e-12)
    assert translation == pytest.approx([0.0, 0.0, 0.0], abs=1e-15)


def test_transformation_translation_en_metres() -> None:
    stockee = [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [10.0, 20.0, 30.0, 1]]
    rotation, translation = unites.rotation_translation(stockee)
    assert rotation == pytest.approx(np.eye(3), abs=1e-15)
    assert translation == pytest.approx([0.01, 0.02, 0.03], abs=1e-15)


AXES = [
    (0.0, 0.0, 1.0),
    (1.0, 0.0, 0.0),
    (0.0, -1.0, 0.0),
    (1.0, 2.0, 3.0),
    (0.95, 0.1, 0.1),
]


@pytest.mark.parametrize("axe_en_x", [True, False])
@pytest.mark.parametrize("z", AXES)
def test_ex12_base_orthonormee_directe(z: tuple[float, float, float], axe_en_x: bool) -> None:
    base = unites.base_liaison(z, axe_en_x=axe_en_x)
    assert base.T @ base == pytest.approx(np.eye(3), abs=1e-12)
    assert np.linalg.det(base) == pytest.approx(1.0, abs=1e-12)
    zu = np.array(z) / np.linalg.norm(z)
    colonne = 0 if axe_en_x else 2
    assert base[:, colonne] == pytest.approx(zu, abs=1e-12)


def test_ex12_axe_z_monde_devient_x_local_comme_le_prototype() -> None:
    # Prototype exudyn_bielle : RotationMatrixY(-pi/2) pour un axe selon z
    attendu = np.array([[0.0, 0.0, -1.0], [0.0, 1.0, 0.0], [1.0, 0.0, 0.0]])
    base = unites.base_liaison((0.0, 0.0, 1.0), axe_en_x=True)
    assert base == pytest.approx(attendu, abs=1e-12)


@pytest.mark.parametrize("axe_en_x", [True, False])
def test_ex12_seconde_direction_projetee(axe_en_x: bool) -> None:
    base = unites.base_liaison((0.0, 0.0, 1.0), axe_en_x=axe_en_x, direction=(1.0, 1.0, 0.0))
    assert base.T @ base == pytest.approx(np.eye(3), abs=1e-12)
    assert np.linalg.det(base) == pytest.approx(1.0, abs=1e-12)
    direction = np.array([1.0, 1.0, 0.0]) / math.sqrt(2)
    colonne_direction = 1 if axe_en_x else 0
    assert base[:, colonne_direction] == pytest.approx(direction, abs=1e-12)


def test_ex12_direction_colineaire_refusee() -> None:
    with pytest.raises(unites.ErreurDirection, match="colinéaire"):
        unites.base_liaison((0.0, 0.0, 1.0), axe_en_x=True, direction=(0.01, 0.0, 1.0))
    with pytest.raises(unites.ErreurDirection):
        unites.base_liaison((0.0, 0.0, 1.0), axe_en_x=False, direction=(0.0, 0.0, -2.0))
    # 5,7° : acceptée
    unites.base_liaison((0.0, 0.0, 1.0), axe_en_x=True, direction=(0.1, 0.0, 1.0))
