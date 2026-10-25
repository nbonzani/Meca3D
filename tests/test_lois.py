# SPDX-License-Identifier: GPL-3.0-or-later
"""Lois d'entrée (EX-30) et pesanteur (EX-31)."""

import numpy as np
import pytest
import reference_bielle as ref

from meca3d.modele.actions import ErreurLoi, LoiEntree, Pesanteur


def test_ex30_loi_lineaire() -> None:
    loi = LoiEntree("20*t")
    assert loi.valeur(0.5) == pytest.approx(10.0, abs=1e-12)
    assert loi.vitesse(0.5) == pytest.approx(20.0, abs=1e-12)
    assert loi.acceleration(0.5) == pytest.approx(0.0, abs=1e-12)


@pytest.mark.parametrize(
    "texte",
    ["__import__('os')", "", "   ", "open('x')", "t.real", "x + 1", "[1, 2]", "eval('1')", "t +"],
)
def test_ex30_expression_refusee(texte: str) -> None:
    with pytest.raises(ErreurLoi):
        LoiEntree(texte)


def test_ex30_pas_dexecution_de_code() -> None:
    with pytest.raises(ErreurLoi):
        LoiEntree("(lambda: 1)()")
    with pytest.raises(ErreurLoi):
        LoiEntree("sin(t).__class__")


def test_ex30_fonctions_et_constantes_nommees() -> None:
    loi = LoiEntree("A*sin(w*t) + min(t, 1) + abs(-2) + sqrt(4)", {"A": 2.0, "w": 3.0})
    t = 0.3
    attendu = 2.0 * np.sin(0.9) + 0.3 + 2.0 + 2.0
    assert loi.valeur(t) == pytest.approx(attendu, abs=1e-12)
    assert loi.vitesse(t) == pytest.approx(6.0 * np.cos(0.9) + 1.0, abs=1e-12)
    assert loi.acceleration(t) == pytest.approx(-18.0 * np.sin(0.9), abs=1e-12)


def test_ex30_puissance_gigantesque_sans_blocage() -> None:
    # Ne doit ni se figer ni exécuter quoi que ce soit : refus ou évaluation en virgule flottante
    try:
        loi = LoiEntree("9**9**9")
    except ErreurLoi:
        return
    assert loi.valeur(0.0) > 0


def test_ex30_loi_de_montee_du_prototype() -> None:
    loi = LoiEntree("Piecewise((10*(t - 0.2/pi*sin(pi*t/0.2)), t < 0.2), (2 + 20*(t - 0.2), True))")
    for t in np.linspace(0.0, 1.0, 201):
        t = float(t)
        assert loi.valeur(t) == pytest.approx(ref.theta(t), rel=1e-12, abs=1e-12)
        assert loi.vitesse(t) == pytest.approx(ref.theta_t(t), rel=1e-12, abs=1e-12)
        assert loi.acceleration(t) == pytest.approx(ref.theta_tt(t), rel=1e-12, abs=1e-12)


def test_ex31_pesanteur_par_defaut() -> None:
    assert Pesanteur().effectif() == pytest.approx([0.0, 0.0, -9.81], abs=0)


def test_ex31_pesanteur_desactivable() -> None:
    p = Pesanteur(vecteur=(0.0, -9.81, 0.0), actif=False)
    assert p.effectif() == pytest.approx([0.0, 0.0, 0.0], abs=0)
    assert Pesanteur(vecteur=(0.0, -9.81, 0.0)).effectif() == pytest.approx(
        [0.0, -9.81, 0.0], abs=0
    )
