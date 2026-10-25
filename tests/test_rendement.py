# SPDX-License-Identifier: GPL-3.0-or-later
"""Rendement des couplages (EX-16) : η = 0,95, sens de la puissance déterminé à chaque instant."""

import numpy as np
import pytest
from outils_couplages import (
    Z1,
    Z2,
    couple,
    etude_reducteur,
    pilote,
    reglages,
)

from meca3d.modele.couplage import Engrenage
from meca3d.moteur.exudyn_dyn import MoteurExudynDyn

ETA = 0.95
K = Z1 / Z2
OMEGA_E = 30.0


def _reducteur(eta: float):
    etude = etude_reducteur()
    etude.couplages = [Engrenage.depuis_dents("R", "L1", "L2", Z1, Z2, rendement=eta)]
    return etude


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
