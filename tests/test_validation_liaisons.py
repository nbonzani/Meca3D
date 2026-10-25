# SPDX-License-Identifier: GPL-3.0-or-later
"""Proposition, choix et validation des liaisons (EX-11), règle avant simulation."""

from typing import Any

import numpy as np
import pytest

from meca3d.modele.etude import (
    ErreurValidation,
    Etude,
    liaisons_non_validees,
    simulation_possible,
)
from meca3d.modele.liaison import Liaison, Statut, TypeLiaison, proposer
from meca3d.modele.solide import Solide


def _liaison(nom: str, type_sc: str, **kw: Any) -> Liaison:
    return Liaison(
        nom=nom,
        type_sc=type_sc,
        solide_a="A",
        solide_b="B",
        centre=np.zeros(3),
        axe_sc=np.array([0.0, 0.0, 1.0]),
        valeur_pose=None,
        **kw,
    )


def _etude(*liaisons: Liaison) -> Etude:
    solides = [
        Solide("A", True, 1.0, np.zeros(3), np.eye(3)),
        Solide("B", False, 1.0, np.zeros(3), np.eye(3)),
    ]
    return Etude(solides=solides, liaisons=list(liaisons))


def test_ex11_cylindrical_couple_screw_propose_helicoidale() -> None:
    assert proposer("cylindrical", couplage_screw=True) == TypeLiaison.HELICOIDALE
    assert proposer("cylindrical", couplage_screw=False) == TypeLiaison.PIVOT_GLISSANT
    assert proposer("cylindrical") == TypeLiaison.PIVOT_GLISSANT
    assert proposer("revolute", couplage_screw=True) == TypeLiaison.PIVOT


def test_ex11_liaison_importee_avec_couplage_screw() -> None:
    liaison = _liaison("L", "cylindrical", couplage_screw=True)
    assert liaison.proposition == TypeLiaison.HELICOIDALE
    assert liaison.type == TypeLiaison.HELICOIDALE
    assert liaison.statut is Statut.PROPOSEE


def test_ex11_pin_slot_sans_proposition() -> None:
    liaison = _liaison("P", "pin_slot")
    assert liaison.proposition is None
    assert liaison.type is None
    assert proposer("pin_slot", couplage_screw=True) is None


@pytest.mark.parametrize("choix", list(TypeLiaison), ids=lambda t: t.value)
def test_ex11_choix_libre_parmi_les_onze(choix: TypeLiaison) -> None:
    liaison = _liaison("L", "revolute")
    liaison.choisir(choix)
    assert liaison.type == choix
    assert liaison.statut is Statut.PROPOSEE


def test_ex11_choix_pour_pin_slot_puis_validation() -> None:
    liaison = _liaison("P", "pin_slot")
    liaison.choisir(TypeLiaison.PIVOT_GLISSANT)
    liaison.valider()
    assert liaison.statut is Statut.VALIDEE


def test_ex11_changer_de_type_repasse_en_proposee() -> None:
    liaison = _liaison("L", "revolute")
    liaison.valider()
    liaison.choisir(TypeLiaison.ROTULE)
    assert liaison.statut is Statut.PROPOSEE


def test_ex11_simulation_impossible_tant_qu_une_liaison_n_est_pas_validee() -> None:
    a, b = _liaison("L1", "revolute"), _liaison("L2", "slider")
    etude = _etude(a, b)
    assert not simulation_possible(etude)
    assert liaisons_non_validees(etude) == ["L1", "L2"]
    a.valider()
    assert not simulation_possible(etude)
    assert liaisons_non_validees(etude) == ["L2"]
    b.valider()
    assert simulation_possible(etude)
    assert liaisons_non_validees(etude) == []


def test_ex11_validation_en_bloc_desactivee_par_defaut_et_refusee() -> None:
    etude = _etude(_liaison("L1", "revolute"), _liaison("L2", "slider"))
    assert etude.validation_en_bloc is False
    with pytest.raises(ErreurValidation, match="validation en bloc"):
        etude.valider_toutes()
    assert all(x.statut is Statut.PROPOSEE for x in etude.liaisons)


def test_ex11_validation_en_bloc_activee_valide_toutes() -> None:
    etude = _etude(_liaison("L1", "revolute"), _liaison("L2", "ball"))
    etude.validation_en_bloc = True
    assert etude.valider_toutes() == ["L1", "L2"]
    assert all(x.statut is Statut.VALIDEE for x in etude.liaisons)
    assert simulation_possible(etude)


def test_ex11_validation_en_bloc_laisse_les_liaisons_sans_type() -> None:
    etude = _etude(_liaison("L1", "revolute"), _liaison("P", "pin_slot"))
    etude.validation_en_bloc = True
    assert etude.valider_toutes() == ["L1"]
    assert liaisons_non_validees(etude) == ["P"]
    assert not simulation_possible(etude)
