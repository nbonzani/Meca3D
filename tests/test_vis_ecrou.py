# SPDX-License-Identifier: GPL-3.0-or-later
"""Vis-écrou, hélicoïdale et pignon-crémaillère (EX-14, EX-32), mode dynamique d'Exudyn."""

import math

import numpy as np
import pytest
from outils_couplages import (
    PAS,
    X,
    action,
    couple,
    cylindre,
    etude_helicoidale,
    etude_vis_ecrou,
    liaison,
    pilote,
    reglages,
)

from meca3d.modele.actions import NatureAction
from meca3d.modele.couplage import PignonCremaillere, VisEcrou
from meca3d.modele.etude import Etude
from meca3d.modele.liaison import TypeLiaison
from meca3d.modele.solide import Solide
from meca3d.moteur.base import ErreurModele
from meca3d.moteur.exudyn_dyn import MoteurExudynDyn

OMEGA = 10.0  # rad/s (SPEC EX-14)
V_ATTENDUE = 7.9577e-3  # m/s (SPEC : p = 5 mm, ω = 10 rad/s)
COUPLE = 2.0  # N·m (SPEC)
EFFORT = 2513.27  # N (SPEC : 2π·C/p)


def _vis_ecrou():
    etude = etude_vis_ecrou()
    etude.couplages = [VisEcrou("VE", "L_vis", "L_ecrou", PAS)]
    return etude


def _effort_axial(f: float):
    return action("Fr", "Ecrou", NatureAction.FORCE, (-f, 0.0, 0.0))


def test_ex14_vis_ecrou_vitesse() -> None:
    """p = 5 mm, ω = 10 rad/s : v = 7,9577 mm/s."""
    etude = _vis_ecrou()
    etude.pilotes = [pilote("L_vis", OMEGA)]
    etude.reglages = reglages(1.0, 1000, 0.001)
    res = MoteurExudynDyn().simuler(etude)
    assert res.vitesses_angulaires["Vis"][-1, 0] == pytest.approx(OMEGA, rel=1e-3)
    assert res.vitesses["Ecrou"][-1, 0] == pytest.approx(V_ATTENDUE, rel=1e-4)
    # position : x = p·θ/2π avec θ(1 s) = ω/2·0,2 + ω·0,8 (montée en cosinus relevé sur 0,2 s)
    theta = OMEGA / 2 * 0.2 + OMEGA * 0.8
    assert res.positions["Ecrou"][-1, 0] == pytest.approx(PAS * theta / (2 * math.pi), rel=1e-4)


def test_ex14_vis_ecrou_couple_et_effort_axial() -> None:
    """Couple moteur 2 N·m en équilibre -> effort axial 2 513,27 N à 1e-3 près."""
    etude = _vis_ecrou()
    etude.actions = [
        action("C", "Vis", NatureAction.COUPLE, (COUPLE, 0.0, 0.0)),
        _effort_axial(EFFORT),
    ]
    etude.reglages = reglages(0.5, 500, 0.001)
    res = MoteurExudynDyn().simuler(etude)
    assert np.abs(res.positions["Ecrou"][:, 0]).max() < 1e-9
    assert np.abs(res.accelerations["Ecrou"][:, 0]).max() < 1e-3
    efforts = res.efforts_couplages["VE"]  # [couple sur la vis, effort sur l'écrou]
    assert abs(efforts[-1, 1]) == pytest.approx(EFFORT, rel=1e-3)
    assert abs(efforts[-1, 0]) == pytest.approx(COUPLE, rel=1e-3)


def test_ex14_vis_ecrou_equilibre_discrimine_a_1e3() -> None:
    etude = _vis_ecrou()
    etude.actions = [
        action("C", "Vis", NatureAction.COUPLE, (COUPLE, 0.0, 0.0)),
        _effort_axial(EFFORT * 1.001),
    ]
    etude.reglages = reglages(0.1, 100, 0.001)
    res = MoteurExudynDyn().simuler(etude)
    assert np.abs(res.accelerations["Ecrou"][:, 0]).max() > 1.0


def test_ex14_helicoidale_vitesse() -> None:
    """Pivot glissant + couplage interne Tx = p·Rx / 2π : v = 7,9577 mm/s à ω = 10 rad/s."""
    etude = etude_helicoidale()
    etude.pilotes = [pilote("L_hel", OMEGA)]
    etude.reglages = reglages(1.0, 1000, 0.001)
    res = MoteurExudynDyn().simuler(etude)
    assert res.vitesses["Vis"][-1, 0] == pytest.approx(V_ATTENDUE, rel=1e-4)
    assert res.vitesses_angulaires["Vis"][-1, 0] == pytest.approx(OMEGA, rel=1e-3)


def test_ex14_helicoidale_couple_et_effort_axial() -> None:
    etude = etude_helicoidale()
    etude.actions = [
        action("C", "Vis", NatureAction.COUPLE, (COUPLE, 0.0, 0.0)),
        action("Fr", "Vis", NatureAction.FORCE, (-EFFORT, 0.0, 0.0)),
    ]
    etude.reglages = reglages(0.5, 500, 0.001)
    res = MoteurExudynDyn().simuler(etude)
    assert np.abs(res.positions["Vis"][:, 0]).max() < 1e-9
    assert abs(res.efforts_couplages["L_hel"][-1, 1]) == pytest.approx(EFFORT, rel=1e-3)


def test_ex14_helicoidale_sans_pas_refusee_avec_message() -> None:
    etude = etude_helicoidale(pas=None)
    with pytest.raises(ErreurModele, match="pas"):
        MoteurExudynDyn().simuler(etude)


def _pignon_cremaillere():
    r = 0.02
    pignon = cylindre("Pignon", r, 0.01, np.zeros(3))
    cremaillere = Solide("Cremaillere", False, 0.2, np.array([0.0, -r, 0.0]), np.eye(3) * 1e-4)
    etude = Etude(
        solides=[
            etude_vis_ecrou().solides[0],
            pignon,
            cremaillere,
        ],
        liaisons=[
            liaison(
                "L_pignon",
                TypeLiaison.PIVOT,
                "Bati",
                "Pignon",
                np.zeros(3),
                np.array([0.0, 0.0, 1.0]),
                valeur_pose=0.0,
            ),
            liaison(
                "L_cremaillere",
                TypeLiaison.GLISSIERE,
                "Bati",
                "Cremaillere",
                np.array([0.0, -r, 0.0]),
                X,
                valeur_pose=0.0,
            ),
        ],
    )
    etude.pesanteur.actif = False
    etude.couplages = [PignonCremaillere("PC", "L_pignon", "L_cremaillere", r)]
    return etude, r


def test_ex14_pignon_cremaillere_vitesse() -> None:
    """v = r·ω : r = 20 mm, ω = 10 rad/s -> 0,2 m/s."""
    etude, r = _pignon_cremaillere()
    etude.pilotes = [pilote("L_pignon", OMEGA)]
    etude.reglages = reglages(1.0, 1000, 0.001)
    res = MoteurExudynDyn().simuler(etude)
    assert res.vitesses["Cremaillere"][-1, 0] == pytest.approx(0.2, rel=1e-4)


def test_ex14_pignon_cremaillere_effort() -> None:
    """Couple 1 N·m sur le pignon en équilibre avec un effort de 1/r = 50 N sur la crémaillère."""
    etude, r = _pignon_cremaillere()
    etude.actions = [
        couple("C", "Pignon", 1.0),
        action("Fr", "Cremaillere", NatureAction.FORCE, (-1.0 / r, 0.0, 0.0)),
    ]
    etude.reglages = reglages(0.3, 300, 0.001)
    res = MoteurExudynDyn().simuler(etude)
    assert np.abs(res.accelerations["Cremaillere"][:, 0]).max() < 1e-3
    assert abs(res.efforts_couplages["PC"][-1, 1]) == pytest.approx(50.0, rel=1e-3)
