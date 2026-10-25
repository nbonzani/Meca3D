# SPDX-License-Identifier: GPL-3.0-or-later
"""Import de la bielle-manivelle depuis les réponses enregistrées (EX-04, EX-05, EX-11)."""

import math

import pytest
from outils_bielle import etude_proposee

from meca3d.modele.etude import Etude
from meca3d.modele.liaison import Statut, TypeLiaison


@pytest.fixture(scope="module")
def etude00() -> Etude:
    return etude_proposee("00")


@pytest.fixture(scope="module")
def etude60() -> Etude:
    return etude_proposee("60")


def test_ex04_solides_masses_et_inerties(etude00: Etude) -> None:
    solides = {s.nom: s for s in etude00.solides}
    assert set(solides) == {"Bati", "Manivelle", "Bielle", "Piston"}
    assert solides["Bati"].fixe
    assert not any(solides[n].fixe for n in ("Manivelle", "Bielle", "Piston"))
    assert solides["Manivelle"].masse == pytest.approx(0.312, rel=1e-9)
    assert solides["Bielle"].masse == pytest.approx(0.936, rel=1e-9)
    assert solides["Piston"].masse == pytest.approx(0.5, rel=1e-9)
    assert solides["Manivelle"].inertie[2, 2] == pytest.approx(2.704e-4, rel=1e-9)
    assert solides["Bielle"].inertie[2, 2] == pytest.approx(7.0512e-3, rel=1e-9)


def test_ex04_centres_de_gravite_en_metres(etude00: Etude) -> None:
    solides = {s.nom: s for s in etude00.solides}
    assert solides["Manivelle"].cdg == pytest.approx([0.05, 0.0, 0.0], abs=1e-9)
    assert solides["Bielle"].cdg == pytest.approx([0.25, 0.0, 0.0], abs=1e-9)
    assert solides["Piston"].cdg == pytest.approx([0.4, 0.0, 0.0], abs=1e-9)


def test_ex04_quatre_liaisons(etude00: Etude) -> None:
    assert [(x.nom, x.type_sc, x.solide_a, x.solide_b) for x in etude00.liaisons] == [
        ("L01_pivot", "revolute", "Bati", "Manivelle"),
        ("L12_pivot", "revolute", "Manivelle", "Bielle"),
        ("L23_rotule", "ball", "Bielle", "Piston"),
        ("L30_glissiere", "slider", "Bati", "Piston"),
    ]
    centres = {x.nom: x.centre for x in etude00.liaisons}
    assert centres["L12_pivot"] == pytest.approx([0.1, 0.0, 0.0], abs=1e-9)
    assert centres["L23_rotule"] == pytest.approx([0.4, 0.0, 0.0], abs=1e-9)
    axes = {x.nom: x.axe_sc for x in etude00.liaisons}
    assert axes["L01_pivot"] == pytest.approx([0.0, 0.0, 1.0], abs=1e-12)
    assert axes["L30_glissiere"] == pytest.approx([1.0, 0.0, 0.0], abs=1e-12)


def test_ex11_propositions_non_validees(etude00: Etude) -> None:
    attendu = {
        "L01_pivot": TypeLiaison.PIVOT,
        "L12_pivot": TypeLiaison.PIVOT,
        "L23_rotule": TypeLiaison.ROTULE,
        "L30_glissiere": TypeLiaison.GLISSIERE,
    }
    assert {x.nom: x.proposition for x in etude00.liaisons} == attendu
    assert all(x.statut is Statut.PROPOSEE for x in etude00.liaisons)


def test_ex04_revision_memorisee(etude00: Etude, etude60: Etude) -> None:
    assert etude00.revision == 47
    assert etude60.revision == 49


def test_ex05_pose_courante_a_60_degres(etude60: Etude) -> None:
    solides = {s.nom: s for s in etude60.solides}
    man = solides["Manivelle"]
    assert man.cdg == pytest.approx([0.025, 0.05 * math.sqrt(3) / 2, 0.0], abs=1e-9)
    # barre inclinée de 60° : Ixx = I_axe·cos²60° + I_transv·sin²60° (valeurs de l'URDF)
    assert man.inertie[2, 2] == pytest.approx(2.704e-4, rel=1e-9)
    assert man.inertie[0, 0] == pytest.approx(2.08e-5 * 0.25 + 2.704e-4 * 0.75, rel=1e-9)
    piston = solides["Piston"]
    assert piston.cdg[0] == pytest.approx(0.3372281323, abs=1e-9)
    pivot = next(x for x in etude60.liaisons if x.nom == "L01_pivot")
    assert pivot.valeur_pose == pytest.approx(math.radians(60.0), abs=1e-12)
