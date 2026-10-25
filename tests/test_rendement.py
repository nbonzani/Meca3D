# SPDX-License-Identifier: GPL-3.0-or-later
"""Rendement des couplages (EX-16) : η = 0,95, sens de la puissance déterminé à chaque instant."""

import numpy as np
import pytest
from outils_couplages import (
    PAS,
    Z1,
    Z2,
    action,
    couple,
    etude_reducteur,
    etude_vis_ecrou,
    pilote,
    reglages,
)

from meca3d.modele.actions import NatureAction
from meca3d.modele.couplage import Engrenage, VisEcrou
from meca3d.moteur.exudyn_dyn import MoteurExudynDyn

ETA = 0.95
K = Z1 / Z2
OMEGA_E = 30.0


def _reducteur(eta: float):
    etude = etude_reducteur()
    etude.couplages = [Engrenage.depuis_dents("R", "L1", "L2", Z1, Z2, rendement=eta)]
    return etude


def test_ex16_rendement_couple_de_sortie() -> None:
    """Réducteur Z1 = 20, Z2 = 60, η = 0,95, Ce = 1 N·m en régime établi : Cs = 2,85 N·m.

    Un couple de charge de 2,85 N·m équilibre exactement le réducteur en marche (ω_e = 30 rad/s) ;
    le couple de sortie exposé par le moteur vaut 2,85 N·m à 1e-3 près.
    """
    etude = _reducteur(ETA)
    etude.actions = [couple("Ce", "Roue1", 1.0), couple("Cs", "Roue2", 2.85)]
    etude.reglages = reglages(0.5, 500, 0.001)
    vitesses = {
        "Roue1": ((0.0, 0.0, 0.0), (0.0, 0.0, OMEGA_E)),
        "Roue2": ((0.0, 0.0, 0.0), (0.0, 0.0, -K * OMEGA_E)),
    }
    res = MoteurExudynDyn().simuler(etude, vitesses_initiales=vitesses)
    assert np.abs(res.accelerations_angulaires["Roue2"][:, 2]).max() < 1.0
    assert res.vitesses_angulaires["Roue1"][-1, 2] == pytest.approx(OMEGA_E, abs=0.05)
    assert abs(res.efforts_couplages["R"][-1, 1]) == pytest.approx(2.85, rel=1e-3)
    # le même chargement sans perte (3 N·m attendus) n'est pas en équilibre à η = 0,95
    etude.actions = [couple("Ce", "Roue1", 1.0), couple("Cs", "Roue2", 3.0)]
    res = MoteurExudynDyn().simuler(etude, vitesses_initiales=vitesses)
    assert np.abs(res.accelerations_angulaires["Roue2"][:, 2]).max() > 10.0


def test_ex16_deux_phases_moteur_puis_frein() -> None:
    """Entrée imposée à 30 rad/s. Phase 1 (moteur) : charge résistante de 3 N·m sur la sortie,
    couple d'entrée 3/(3·η) = 1,05263 N·m. Phase 2 (frein) : couple entraînant de 3 N·m sur la
    sortie, couple absorbé à l'entrée η·3/3 = 0,95 N·m, de signe opposé."""
    etude = _reducteur(ETA)
    etude.pilotes = [pilote("L1", OMEGA_E)]
    # ω_s = −10 rad/s : +3 N·m s'oppose au mouvement (phase 1), −3 N·m l'entraîne (phase 2)
    etude.actions = [couple("Cs", "Roue2", "Piecewise((3.0, t < 1.0), (-3.0, True))")]
    etude.reglages = reglages(2.0, 2000, 0.001)
    res = MoteurExudynDyn().simuler(etude)
    c_entree = res.moments["L1"][:, 0]  # couple du pilote sur l'axe de la liaison d'entrée
    phase1 = (res.t > 0.85) & (res.t <= 1.0)
    phase2 = (res.t > 1.85) & (res.t <= 2.0)
    c1 = float(np.mean(c_entree[phase1]))
    c2 = float(np.mean(c_entree[phase2]))
    assert abs(c1) == pytest.approx(3.0 / (3.0 * ETA), rel=1e-3)
    assert abs(c2) == pytest.approx(ETA * 3.0 / 3.0, rel=1e-3)
    assert c1 * c2 < 0.0  # le pilote passe de moteur à frein


def test_ex16_rendement_vis_ecrou() -> None:
    """Vis-écrou η = 0,9, en marche (ω = 10 rad/s, v = p·ω/2π) : un effort résistant η·2π·C/p
    équilibre un couple de 2 N·m (P_s = η·P_e)."""
    eta = 0.9
    etude = etude_vis_ecrou()
    etude.couplages = [VisEcrou("VE", "L_vis", "L_ecrou", PAS, rendement=eta)]
    f0 = eta * 2 * np.pi * 2.0 / PAS
    etude.actions = [
        action("C", "Vis", NatureAction.COUPLE, (2.0, 0.0, 0.0)),
        action("Fr", "Ecrou", NatureAction.FORCE, (-f0, 0.0, 0.0)),
    ]
    etude.reglages = reglages(0.3, 300, 0.001)
    vitesses = {
        "Vis": ((0.0, 0.0, 0.0), (10.0, 0.0, 0.0)),
        "Ecrou": ((PAS * 10.0 / (2 * np.pi), 0.0, 0.0), (0.0, 0.0, 0.0)),
    }
    res = MoteurExudynDyn().simuler(etude, vitesses_initiales=vitesses)
    assert np.abs(res.accelerations["Ecrou"][:, 0]).max() < 1.0
    assert abs(res.efforts_couplages["VE"][-1, 1]) == pytest.approx(f0, rel=1e-3)
