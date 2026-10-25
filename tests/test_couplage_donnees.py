# SPDX-License-Identifier: GPL-3.0-or-later
"""Données de couplage (EX-14, EX-16) : structure et validation des valeurs, sans moteur."""

import math

import pytest
from meca3d.modele.couplage import (
    Couplage,
    Engrenage,
    ErreurCouplage,
    PignonCremaillere,
    SensEngrenage,
    VisEcrou,
    couplage_depuis_dict,
)


def test_ex14_engrenage_exterieur_rapport_et_signe() -> None:
    # Z1 = 20, Z2 = 60 : omega_2 = -(Z1/Z2) omega_1, donc omega_e = 30 -> |omega_s| = 10
    e = Engrenage.depuis_dents("R", "L1", "L2", z1=20, z2=60)
    assert e.k == pytest.approx(1.0 / 3.0, rel=1e-15)
    assert 30.0 * e.k == pytest.approx(10.0, rel=1e-6)
    assert e.sens is SensEngrenage.EXTERIEUR
    assert e.signe == -1.0
    assert e.rendement == 1.0


def test_ex14_engrenage_interieur_signe_positif() -> None:
    e = Engrenage("R", "L1", "L2", k=0.5, sens=SensEngrenage.INTERIEUR)
    assert e.signe == 1.0


def test_ex14_pignon_cremaillere_et_vis_ecrou() -> None:
    pc = PignonCremaillere("PC", "L1", "L2", r=0.02)
    assert pc.r == 0.02
    ve = VisEcrou("VE", "L1", "L2", p=0.005)
    assert ve.p == 0.005
    # v = p w / 2pi : p = 5 mm, w = 10 rad/s -> 7,9577 mm/s (SPEC EX-14)
    assert ve.p * 10.0 / (2.0 * math.pi) == pytest.approx(7.9577e-3, rel=1e-4)


@pytest.mark.parametrize("eta", [0.0, -0.1, 1.0000001, 2.0, float("nan"), float("inf")])
def test_ex16_rendement_hors_de_0_1_refuse(eta: float) -> None:
    with pytest.raises(ErreurCouplage, match="rendement"):
        Engrenage("R", "L1", "L2", k=0.5, rendement=eta)


@pytest.mark.parametrize("eta", [1e-6, 0.95, 1.0])
def test_ex16_rendement_valide(eta: float) -> None:
    assert Engrenage("R", "L1", "L2", k=0.5, rendement=eta).rendement == eta


@pytest.mark.parametrize("k", [0.0, -1.0, float("nan"), float("inf")])
def test_ex14_rapport_invalide(k: float) -> None:
    with pytest.raises(ErreurCouplage, match="rapport"):
        Engrenage("R", "L1", "L2", k=k)


@pytest.mark.parametrize(("z1", "z2"), [(0, 60), (20, 0), (-20, 60), (20.5, 60)])
def test_ex14_dents_invalides(z1: float, z2: float) -> None:
    with pytest.raises(ErreurCouplage, match="dents"):
        Engrenage.depuis_dents("R", "L1", "L2", z1=z1, z2=z2)  # type: ignore[arg-type]


@pytest.mark.parametrize("r", [0.0, -0.02, float("nan")])
def test_ex14_rayon_invalide(r: float) -> None:
    with pytest.raises(ErreurCouplage, match="rayon"):
        PignonCremaillere("PC", "L1", "L2", r=r)


@pytest.mark.parametrize("p", [0.0, -0.005, float("inf")])
def test_ex14_pas_invalide(p: float) -> None:
    with pytest.raises(ErreurCouplage, match="pas"):
        VisEcrou("VE", "L1", "L2", p=p)


def test_ex14_liaisons_couplees_distinctes_et_nom_non_vide() -> None:
    with pytest.raises(ErreurCouplage, match="distinctes"):
        Engrenage("R", "L1", "L1", k=0.5)
    with pytest.raises(ErreurCouplage, match="nom"):
        Engrenage("", "L1", "L2", k=0.5)
    with pytest.raises(ErreurCouplage, match="liaison"):
        VisEcrou("VE", "L1", "", p=0.005)


def test_ex14_sens_engrenage_inconnu() -> None:
    with pytest.raises(ValueError):
        SensEngrenage("diagonal")


@pytest.mark.parametrize(
    "couplage",
    [
        Engrenage("R", "L1", "L2", k=1 / 3, sens=SensEngrenage.INTERIEUR, rendement=0.95),
        PignonCremaillere("PC", "L1", "L2", r=0.02, rendement=0.9),
        VisEcrou("VE", "L1", "L2", p=0.005),
    ],
    ids=lambda c: c.nom,
)
def test_ex14_aller_retour_dict(couplage: Couplage) -> None:
    d = couplage.vers_dict()
    relu = couplage_depuis_dict(d)
    assert relu == couplage
    assert relu.vers_dict() == d


def test_ex14_dict_invalide() -> None:
    with pytest.raises(ErreurCouplage, match="genre"):
        couplage_depuis_dict({"genre": "courroie", "nom": "C"})
    with pytest.raises(ErreurCouplage, match="genre"):
        couplage_depuis_dict({"nom": "C"})
    d = VisEcrou("VE", "L1", "L2", p=0.005).vers_dict()
    d["rendement"] = 3.0
    with pytest.raises(ErreurCouplage, match="rendement"):
        couplage_depuis_dict(d)
    d["rendement"] = 1.0
    del d["p"]
    with pytest.raises(ErreurCouplage):
        couplage_depuis_dict(d)
