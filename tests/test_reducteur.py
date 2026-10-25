# SPDX-License-Identifier: GPL-3.0-or-later
"""Couplage par engrenage (EX-14) : rapport, couple transmis, engrenage intérieur, train
épicycloïdal (Q7, formule de Willis). Mode dynamique d'Exudyn."""

import numpy as np
import pytest
from outils_couplages import (
    Z1,
    Z2,
    etude_epicycloidal,
    etude_reducteur,
    pilote,
    reglages,
)

from meca3d.modele.couplage import Engrenage, SensEngrenage
from meca3d.moteur.exudyn_dyn import MoteurExudynDyn

K = Z1 / Z2  # 1/3 (SPEC EX-14 : Z1 = 20, Z2 = 60)
OMEGA_E = 30.0  # rad/s (SPEC EX-14)


def _reducteur(sens: SensEngrenage = SensEngrenage.EXTERIEUR):
    etude = etude_reducteur()
    etude.couplages = [Engrenage.depuis_dents("R", "L1", "L2", Z1, Z2, sens)]
    return etude


def test_ex14_reducteur_rapport() -> None:
    """Z1 = 20, Z2 = 60, ω_e = 30 rad/s : |ω_s| = 10 rad/s et |ω_s + k·ω_e| < 1e-6 rad/s."""
    etude = _reducteur()
    etude.pilotes = [pilote("L1", OMEGA_E)]
    etude.reglages = reglages(1.0, 1000, 0.001)
    res = MoteurExudynDyn().simuler(etude)
    w_e = res.vitesses_angulaires["Roue1"][:, 2]
    w_s = res.vitesses_angulaires["Roue2"][:, 2]
    assert w_e[-1] == pytest.approx(30.0, rel=1e-3)
    assert abs(w_s[-1]) == pytest.approx(10.0, rel=1e-3)
    assert np.abs(w_s + K * w_e).max() < 1e-6


def test_ex14_engrenage_interieur_signe_positif() -> None:
    etude = _reducteur(SensEngrenage.INTERIEUR)
    etude.pilotes = [pilote("L1", OMEGA_E)]
    etude.reglages = reglages(0.6, 600, 0.001)
    res = MoteurExudynDyn().simuler(etude)
    w_e = res.vitesses_angulaires["Roue1"][:, 2]
    w_s = res.vitesses_angulaires["Roue2"][:, 2]
    assert w_s[-1] == pytest.approx(+10.0, rel=1e-3)
    assert np.abs(w_s - K * w_e).max() < 1e-6


def test_q7_train_epicycloidal_formule_de_willis() -> None:
    """Q7 : (ω_p − ω_c) = −k·(ω_s − ω_c), k = Zs/Zp = 1/2, couplage porté par le porte-satellites
    mobile. Valeurs posées : ω_c = 6 rad/s, ω_s = 30 rad/s -> ω_p = 6 − 0,5·(30 − 6) = −6 rad/s."""
    etude = etude_epicycloidal()
    etude.couplages = [Engrenage.depuis_dents("Willis", "Ls", "Lp", 20, 40)]
    # pilotes relatifs au porte-satellites : Lc = 6 rad/s, Ls = ω_s − ω_c = 24 rad/s
    etude.pilotes = [pilote("Lc", 6.0), pilote("Ls", 24.0)]
    etude.reglages = reglages(1.0, 1000, 0.001)
    res = MoteurExudynDyn().simuler(etude)
    w_c = res.vitesses_angulaires["Porte"][:, 2]
    w_s = res.vitesses_angulaires["Planetaire"][:, 2]
    w_p = res.vitesses_angulaires["Satellite"][:, 2]
    assert np.abs((w_p - w_c) + 0.5 * (w_s - w_c)).max() < 1e-6
    assert w_c[-1] == pytest.approx(6.0, rel=1e-3)
    assert w_s[-1] == pytest.approx(30.0, rel=1e-3)
    assert w_p[-1] == pytest.approx(-6.0, rel=1e-3)


def test_ex14_engrenage_necessite_liaisons_a_axe() -> None:
    from meca3d.modele.liaison import TypeLiaison
    from meca3d.moteur.base import ErreurModele

    etude = _reducteur()
    etude.liaison("L2").choisir(TypeLiaison.ROTULE)
    etude.liaison("L2").valider()
    with pytest.raises(ErreurModele, match="couplage"):
        MoteurExudynDyn().simuler(etude)
