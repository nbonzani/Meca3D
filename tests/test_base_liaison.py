# SPDX-License-Identifier: GPL-3.0-or-later
"""Base de liaison (EX-12) et changement d'orientation (EX-13)."""

import numpy as np
import pytest

from meca3d.modele.liaison import Liaison, TypeLiaison
from meca3d.unites import ErreurDirection

Z = (0.0, 0.0, 1.0)
TYPES_A_DIRECTION = [TypeLiaison.ROTULE_A_DOIGT, TypeLiaison.LINEAIRE_RECTILIGNE]


def _liaison(type_liaison: TypeLiaison, axe: tuple[float, ...] = Z) -> Liaison:
    return Liaison(
        nom="L",
        type_sc="ball",
        solide_a="A",
        solide_b="B",
        centre=np.zeros(3),
        axe_sc=np.array(axe),
        valeur_pose=None,
        type=type_liaison,
    )


@pytest.mark.parametrize(
    "type_liaison",
    [
        TypeLiaison.PIVOT,
        TypeLiaison.GLISSIERE,
        TypeLiaison.PIVOT_GLISSANT,
        TypeLiaison.LINEAIRE_ANNULAIRE,
        TypeLiaison.HELICOIDALE,
    ],
)
def test_ex12_axe_devient_x_local(type_liaison: TypeLiaison) -> None:
    base = _liaison(type_liaison, (0.0, 1.0, 0.0)).base()
    assert base[:, 0] == pytest.approx([0.0, 1.0, 0.0], abs=1e-12)


@pytest.mark.parametrize("type_liaison", [TypeLiaison.APPUI_PLAN, TypeLiaison.PONCTUELLE])
def test_ex12_axe_devient_normale_z_local(type_liaison: TypeLiaison) -> None:
    base = _liaison(type_liaison, (0.0, 1.0, 0.0)).base()
    assert base[:, 2] == pytest.approx([0.0, 1.0, 0.0], abs=1e-12)


@pytest.mark.parametrize("type_liaison", TYPES_A_DIRECTION)
def test_ex12_direction_1_1_0_base_orthonormee_directe(type_liaison: TypeLiaison) -> None:
    liaison = _liaison(type_liaison)
    liaison.definir_direction((1.0, 1.0, 0.0))
    base = liaison.base()
    assert base.T @ base == pytest.approx(np.eye(3), abs=1e-12)
    assert np.linalg.det(base) == pytest.approx(1.0, abs=1e-12)
    assert base[:, 2] == pytest.approx(Z, abs=1e-12)  # z local = z SolidCraft
    # la direction saisie, déjà orthogonale à z, devient x local
    assert base[:, 0] == pytest.approx(np.array([1.0, 1.0, 0.0]) / np.sqrt(2.0), abs=1e-12)


def test_ex12_direction_projetee_orthogonalement() -> None:
    liaison = _liaison(TypeLiaison.LINEAIRE_RECTILIGNE)
    liaison.definir_direction((1.0, 0.0, 1.0))  # composante sur z retirée
    base = liaison.base()
    assert base[:, 0] == pytest.approx([1.0, 0.0, 0.0], abs=1e-12)
    assert np.linalg.det(base) == pytest.approx(1.0, abs=1e-12)


@pytest.mark.parametrize("direction", [(0.0, 0.0, 1.0), (0.0, 0.0, -2.0), (0.01, 0.0, 1.0)])
def test_ex12_direction_colineaire_refusee(direction: tuple[float, ...]) -> None:
    liaison = _liaison(TypeLiaison.ROTULE_A_DOIGT)
    with pytest.raises(ErreurDirection, match="colinéaire"):
        liaison.definir_direction(direction)
    assert liaison.direction is None


def test_ex12_seuil_d_un_degre() -> None:
    liaison = _liaison(TypeLiaison.ROTULE_A_DOIGT)
    ok, ko = np.radians(1.01), np.radians(0.99)
    liaison.definir_direction((np.sin(ok), 0.0, np.cos(ok)))
    with pytest.raises(ErreurDirection):
        liaison.definir_direction((np.sin(ko), 0.0, np.cos(ko)))


@pytest.mark.parametrize("type_liaison", TYPES_A_DIRECTION)
def test_ex12_seconde_direction_obligatoire(type_liaison: TypeLiaison) -> None:
    liaison = _liaison(type_liaison)
    with pytest.raises(ErreurDirection, match="seconde direction"):
        liaison.base()
    with pytest.raises(ErreurDirection, match="seconde direction"):
        liaison.valider()


def test_ex13_reorientation_vers_axes_monde() -> None:
    liaison = _liaison(TypeLiaison.LINEAIRE_ANNULAIRE, (0.0, 1.0, 0.0))
    for nom, attendu in (("x", (1, 0, 0)), ("y", (0, 1, 0)), ("z", (0, 0, 1))):
        liaison.reorienter_axe(nom)
        assert liaison.axe == pytest.approx(attendu, abs=1e-15)
        assert liaison.base()[:, 0] == pytest.approx(attendu, abs=1e-12)


def test_ex13_reorientation_vecteur_et_valeurs_refusees() -> None:
    liaison = _liaison(TypeLiaison.PIVOT)
    liaison.reorienter_axe((1.0, 1.0, 0.0))
    attendu = np.array([1.0, 1.0, 0.0]) / np.sqrt(2.0)
    assert liaison.axe == pytest.approx(attendu, abs=1e-15)
    with pytest.raises(ValueError):
        liaison.reorienter_axe("w")
    with pytest.raises(ValueError):
        liaison.reorienter_axe((0.0, 0.0, 0.0))
    assert liaison.axe == pytest.approx(attendu, abs=1e-15)


def test_ex13_reorientation_conserve_l_axe_solidcraft() -> None:
    liaison = _liaison(TypeLiaison.PIVOT)
    liaison.reorienter_axe("x")
    assert liaison.axe_sc == pytest.approx(Z, abs=1e-15)


def test_ex13_reorientation_refusee_si_direction_devient_colineaire() -> None:
    liaison = _liaison(TypeLiaison.LINEAIRE_RECTILIGNE)
    liaison.definir_direction((1.0, 0.0, 0.0))
    with pytest.raises(ErreurDirection):
        liaison.reorienter_axe("x")
    assert liaison.axe == pytest.approx(Z, abs=1e-15)


def test_ex13_deplacement_du_centre() -> None:
    liaison = _liaison(TypeLiaison.PIVOT)
    liaison.deplacer_centre((0.1, -0.2, 0.3))
    assert liaison.centre == pytest.approx([0.1, -0.2, 0.3], abs=1e-15)
    with pytest.raises(ValueError):
        liaison.deplacer_centre((0.0, float("nan"), 0.0))
    with pytest.raises(ValueError):
        liaison.deplacer_centre((0.0, 0.0))
    assert liaison.centre == pytest.approx([0.1, -0.2, 0.3], abs=1e-15)
