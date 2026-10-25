# SPDX-License-Identifier: GPL-3.0-or-later
"""Couplage par engrenage (EX-14) : rapport, couple transmis, engrenage intérieur, train
épicycloïdal (Q7, formule de Willis). Mode dynamique d'Exudyn."""

import numpy as np
import pytest
from outils_couplages import (
    Z1,
    Z2,
    couple,
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


def _equilibre(couple_charge: float):
    """Ce = 1 N·m sur Roue1, couple de charge sur Roue2, en régime établi (ω_e = 30, ω_s = −10)."""
    etude = _reducteur()
    etude.actions = [couple("Ce", "Roue1", 1.0), couple("Cs", "Roue2", couple_charge)]
    etude.reglages = reglages(0.5, 500, 0.001)
    vitesses = {
        "Roue1": ((0.0, 0.0, 0.0), (0.0, 0.0, OMEGA_E)),
        "Roue2": ((0.0, 0.0, 0.0), (0.0, 0.0, -K * OMEGA_E)),
    }
    return MoteurExudynDyn().simuler(etude, vitesses_initiales=vitesses)


def test_ex14_reducteur_couple_transmis() -> None:
    """Sans perte, en régime établi : Ce = 1 N·m -> Cs = 3 N·m à 1e-3 près.

    Le couple de charge de 3 N·m (= Ce·Z2/Z1, calcul de la SPEC) équilibre exactement le
    réducteur : accélérations nulles, vitesses constantes ; le couple transmis exposé par le
    moteur vaut 3 N·m.
    """
    res = _equilibre(3.0)
    assert np.abs(res.accelerations_angulaires["Roue2"][:, 2]).max() < 1e-3
    assert res.vitesses_angulaires["Roue1"][-1, 2] == pytest.approx(30.0, abs=1e-3)
    efforts = res.efforts_couplages["R"]  # colonnes : [entrée, sortie]
    assert abs(efforts[-1, 1]) == pytest.approx(3.0, rel=1e-3)
    assert abs(efforts[-1, 0]) == pytest.approx(1.0, rel=1e-3)


def test_ex14_reducteur_couple_transmis_discrimine_a_1e3() -> None:
    """Un couple de charge écarté de 1e-3 relatif de 3 N·m n'est plus en équilibre."""
    res = _equilibre(3.0 * 1.001)
    assert np.abs(res.accelerations_angulaires["Roue2"][:, 2]).max() > 0.3


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


def test_q7_train_epicycloidal_couple_transmis() -> None:
    """Statique du train (k = 1/2) : relation ω_p + k·ω_s − (1+k)·ω_c = 0, donc couples du
    couplage idéal C_p = λ, C_s = k·λ, C_c = −(1+k)·λ (le couplage ne transmet aucune puissance).
    Pour λ = 2 N·m : (C_p, C_s, C_c) = (2, 1, −3) N·m, puissance 6·(−3) + 30·1 + (−6)·2 = 0 W.
    Appliqués en vitesses établies (ω_c, ω_s, ω_p) = (6, 30, −6) rad/s, ces couples équilibrent
    le train : les vitesses restent constantes et le couple transmis exposé vaut 2 N·m."""
    etude = etude_epicycloidal()
    etude.couplages = [Engrenage.depuis_dents("Willis", "Ls", "Lp", 20, 40)]
    etude.actions = [
        couple("Cs", "Planetaire", 1.0),
        couple("Cp", "Satellite", 2.0),
        couple("Cc", "Porte", -3.0),
    ]
    etude.reglages = reglages(0.3, 300, 0.001)
    vitesses = {
        "Porte": ((0.0, 0.0, 0.0), (0.0, 0.0, 6.0)),
        "Planetaire": ((0.0, 0.0, 0.0), (0.0, 0.0, 30.0)),
        # le centre du satellite tourne autour de l'axe du porte-satellites : v = ω_c × r
        "Satellite": ((0.0, 6.0 * 0.06, 0.0), (0.0, 0.0, -6.0)),
    }
    res = MoteurExudynDyn().simuler(etude, vitesses_initiales=vitesses)
    assert np.abs(res.accelerations_angulaires["Planetaire"][:, 2]).max() < 1e-2
    assert res.vitesses_angulaires["Planetaire"][-1, 2] == pytest.approx(30.0, abs=1e-2)
    assert abs(res.efforts_couplages["Willis"][-1, 1]) == pytest.approx(2.0, rel=1e-3)
    assert abs(res.efforts_couplages["Willis"][-1, 0]) == pytest.approx(1.0, rel=1e-3)


def test_ex14_engrenage_necessite_liaisons_a_axe() -> None:
    from meca3d.modele.liaison import TypeLiaison
    from meca3d.moteur.base import ErreurModele

    etude = _reducteur()
    etude.liaison("L2").choisir(TypeLiaison.ROTULE)
    etude.liaison("L2").valider()
    with pytest.raises(ErreurModele, match="couplage"):
        MoteurExudynDyn().simuler(etude)
