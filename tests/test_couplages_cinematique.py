# SPDX-License-Identifier: GPL-3.0-or-later
"""Couplages en mode cinématique (EX-14, EX-41) : vitesses et accélérations par dérivation exacte
des équations de couplage (comme pour les liaisons, `moteur/cinematique.py`)."""

import math

import numpy as np
import pytest
from outils_couplages import (
    PAS,
    Z1,
    Z2,
    etude_epicycloidal,
    etude_helicoidale,
    etude_reducteur,
    etude_vis_ecrou,
    pilote,
    reglages,
)

from meca3d.modele.couplage import Engrenage, VisEcrou
from meca3d.moteur.cinematique import MoteurCinematique

K = Z1 / Z2


def test_ex14_cinematique_reducteur() -> None:
    etude = etude_reducteur()
    etude.couplages = [Engrenage.depuis_dents("R", "L1", "L2", Z1, Z2)]
    etude.pilotes = [pilote("L1", 30.0)]
    etude.reglages = reglages(1.0, 1000, 0.001)
    res = MoteurCinematique().simuler(etude)
    w_e = res.vitesses_angulaires["Roue1"][:, 2]
    w_s = res.vitesses_angulaires["Roue2"][:, 2]
    a_e = res.accelerations_angulaires["Roue1"][:, 2]
    a_s = res.accelerations_angulaires["Roue2"][:, 2]
    assert w_e[-1] == pytest.approx(30.0, abs=1e-9)
    assert w_s[-1] == pytest.approx(-10.0, abs=1e-9)
    assert np.abs(w_s + K * w_e).max() < 1e-9
    assert np.abs(a_s + K * a_e).max() < 1e-9
    assert np.abs(a_e).max() > 100.0  # la montée en vitesse existe bien (ω̇ jusqu'à 235 rad/s²)
    assert res.forces == {} and res.moments == {}
    assert res.efforts_couplages == {}


def test_ex14_cinematique_vis_ecrou() -> None:
    etude = etude_vis_ecrou()
    etude.couplages = [VisEcrou("VE", "L_vis", "L_ecrou", PAS)]
    etude.pilotes = [pilote("L_vis", 10.0)]
    etude.reglages = reglages(1.0, 1000, 0.001)
    res = MoteurCinematique().simuler(etude)
    v = res.vitesses["Ecrou"][:, 0]
    w = res.vitesses_angulaires["Vis"][:, 0]
    assert np.abs(v - PAS * w / (2 * math.pi)).max() < 1e-9
    assert v[-1] == pytest.approx(7.9577e-3, rel=1e-4)
    theta = 10.0 / 2 * 0.2 + 10.0 * 0.8
    assert res.positions["Ecrou"][-1, 0] == pytest.approx(PAS * theta / (2 * math.pi), rel=1e-4)


def test_ex14_cinematique_helicoidale() -> None:
    etude = etude_helicoidale()
    etude.pilotes = [pilote("L_hel", 10.0)]
    etude.reglages = reglages(1.0, 1000, 0.001)
    res = MoteurCinematique().simuler(etude)
    v = res.vitesses["Vis"][:, 0]
    w = res.vitesses_angulaires["Vis"][:, 0]
    assert np.abs(v - PAS * w / (2 * math.pi)).max() < 1e-9
    assert v[-1] == pytest.approx(7.9577e-3, rel=1e-4)


def test_q7_cinematique_train_epicycloidal() -> None:
    etude = etude_epicycloidal()
    etude.couplages = [Engrenage.depuis_dents("Willis", "Ls", "Lp", 20, 40)]
    etude.pilotes = [pilote("Lc", 6.0), pilote("Ls", 24.0)]
    etude.reglages = reglages(1.0, 1000, 0.001)
    res = MoteurCinematique().simuler(etude)
    w_c = res.vitesses_angulaires["Porte"][:, 2]
    w_s = res.vitesses_angulaires["Planetaire"][:, 2]
    w_p = res.vitesses_angulaires["Satellite"][:, 2]
    assert w_p[-1] == pytest.approx(-6.0, abs=1e-9)
    assert np.abs((w_p - w_c) + 0.5 * (w_s - w_c)).max() < 1e-9
    a_c = res.accelerations_angulaires["Porte"][:, 2]
    a_s = res.accelerations_angulaires["Planetaire"][:, 2]
    a_p = res.accelerations_angulaires["Satellite"][:, 2]
    assert np.abs((a_p - a_c) + 0.5 * (a_s - a_c)).max() < 1e-9
