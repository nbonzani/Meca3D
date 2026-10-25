# SPDX-License-Identifier: GPL-3.0-or-later
"""Catalogue minimal : ddl bloqués (EX-10), propositions (EX-11), réorientation (EX-13)."""

import numpy as np
import pytest

from meca3d.modele.liaison import (
    DDL_BLOQUES,
    Liaison,
    Statut,
    TypeLiaison,
    proposer,
)

# Tableau d'EX-10 de la SPEC : [Tx Ty Tz Rx Ry Rz]
TABLEAU_EX10 = {
    "encastrement": [1, 1, 1, 1, 1, 1],
    "pivot": [1, 1, 1, 0, 1, 1],
    "glissiere": [0, 1, 1, 1, 1, 1],
    "pivot_glissant": [0, 1, 1, 0, 1, 1],
    "rotule_a_doigt": [1, 1, 1, 0, 0, 1],
    "rotule": [1, 1, 1, 0, 0, 0],
    "appui_plan": [0, 0, 1, 1, 1, 0],
    "lineaire_annulaire": [0, 1, 1, 0, 0, 0],
    "lineaire_rectiligne": [0, 0, 1, 0, 1, 0],
    "ponctuelle": [0, 0, 1, 0, 0, 0],
    "helicoidale": [0, 1, 1, 0, 1, 1],
}


def test_ex10_onze_liaisons_et_ddl_bloques() -> None:
    assert len(DDL_BLOQUES) == 11
    for nom, ddl in TABLEAU_EX10.items():
        assert list(DDL_BLOQUES[TypeLiaison(nom)]) == ddl


@pytest.mark.parametrize(
    ("type_sc", "attendu"),
    [
        ("revolute", TypeLiaison.PIVOT),
        ("slider", TypeLiaison.GLISSIERE),
        ("cylindrical", TypeLiaison.PIVOT_GLISSANT),
        ("planar", TypeLiaison.APPUI_PLAN),
        ("ball", TypeLiaison.ROTULE),
        ("rigid", TypeLiaison.ENCASTREMENT),
        ("pin_slot", None),
    ],
)
def test_ex11_proposition_par_type_solidcraft(type_sc: str, attendu: TypeLiaison | None) -> None:
    assert proposer(type_sc) == attendu


def _liaison(type_sc: str = "ball") -> Liaison:
    return Liaison(
        nom="L",
        type_sc=type_sc,
        solide_a="A",
        solide_b="B",
        centre=np.zeros(3),
        axe_sc=np.array([0.0, 0.0, 1.0]),
        valeur_pose=None,
    )


def test_ex11_statut_et_validation() -> None:
    liaison = _liaison()
    assert liaison.type == TypeLiaison.ROTULE
    assert liaison.statut is Statut.PROPOSEE
    liaison.valider()
    assert liaison.statut is Statut.VALIDEE


def test_ex11_pin_slot_ne_peut_pas_etre_validee_sans_choix() -> None:
    liaison = _liaison("pin_slot")
    assert liaison.type is None
    with pytest.raises(ValueError, match="choix"):
        liaison.valider()


def test_ex13_reorientation_de_l_axe() -> None:
    liaison = _liaison()
    liaison.type = TypeLiaison.LINEAIRE_ANNULAIRE
    liaison.reorienter_axe((0.0, 3.0, 0.0))
    assert liaison.axe == pytest.approx([0.0, 1.0, 0.0], abs=1e-15)
    base = liaison.base()
    assert base[:, 0] == pytest.approx([0.0, 1.0, 0.0], abs=1e-12)  # axe = x local
    with pytest.raises(ValueError):
        liaison.reorienter_axe((0.0, 0.0, 0.0))
