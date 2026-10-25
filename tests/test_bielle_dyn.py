# SPDX-License-Identifier: GPL-3.0-or-later
"""Bielle-manivelle en dynamique contre la solution Newton-Euler indépendante (EX-40, EX-05)."""

import math
from dataclasses import replace

import numpy as np
import pytest
import reference_bielle as ref
from outils_bielle import etude_bielle

from meca3d.modele.etude import Etude
from meca3d.modele.liaison import Statut
from meca3d.moteur.base import ErreurModele, ResultatsBruts
from meca3d.moteur.exudyn_dyn import RHO_INFINI, MoteurExudynDyn
from meca3d.resultats.torseurs import torseur_statique

TOLERANCE_EX40 = 5e-3


@pytest.fixture(scope="module")
def etude() -> Etude:
    return etude_bielle("00")


@pytest.fixture(scope="module")
def resultats(etude: Etude) -> ResultatsBruts:
    return MoteurExudynDyn().simuler(etude)


def test_ex40_rho_infini_constant_nommee() -> None:
    assert RHO_INFINI == 0.9


def test_ex40_grille_de_sortie(resultats: ResultatsBruts) -> None:
    assert len(resultats.t) == 501
    assert resultats.t[0] == pytest.approx(0.0, abs=1e-15)
    assert resultats.t[-1] == pytest.approx(1.0, abs=1e-12)


def _ecart(calcule: np.ndarray, reference: np.ndarray) -> float:
    return float(np.abs(calcule - reference).max() / np.abs(reference).max())


@pytest.mark.parametrize(
    ("grandeur", "liaison", "de"),
    [
        ("O", "L01_pivot", "Bati"),
        ("A", "L12_pivot", "Manivelle"),
        ("B", "L23_rotule", "Bielle"),
    ],
)
def test_ex40_reactions_de_liaison(
    etude: Etude, resultats: ResultatsBruts, grandeur: str, liaison: str, de: str
) -> None:
    tors = torseur_statique(etude, resultats, liaison, de=de, base="monde")
    refs = np.array([ref.reference(float(t))[grandeur] for t in resultats.t])
    assert _ecart(tors[:, :2], refs) <= TOLERANCE_EX40


def test_ex40_couple_moteur(etude: Etude, resultats: ResultatsBruts) -> None:
    tors = torseur_statique(etude, resultats, "L01_pivot", de="Bati", base="monde")
    refs = np.array([ref.reference(float(t))["C"] for t in resultats.t])
    assert _ecart(tors[:, 5], refs) <= TOLERANCE_EX40


def test_ex40_normale_du_piston(etude: Etude, resultats: ResultatsBruts) -> None:
    tors = torseur_statique(etude, resultats, "L30_glissiere", de="Bati", base="monde")
    refs = np.array([ref.reference(float(t))["N"] for t in resultats.t])
    assert _ecart(tors[:, 1], refs) <= TOLERANCE_EX40


def test_ex50_moment_sur_l_axe_libre_nul_hors_pilote(etude: Etude, resultats: ResultatsBruts) -> None:
    # pivot L12 : moment d'axe z nul (liaison parfaite)
    tors = torseur_statique(etude, resultats, "L12_pivot", de="Manivelle", base="monde")
    assert np.abs(tors[:, 5]).max() < 1e-9


def test_ex40_position_du_piston(etude: Etude, resultats: ResultatsBruts) -> None:
    x_b = resultats.positions["Piston"][:, 0]
    refs = np.array([ref.reference(float(t))["xB"] for t in resultats.t])
    assert np.abs(x_b - refs).max() < 1e-6


def test_ex05_configuration_a_60_degres() -> None:
    etude60 = etude_bielle("60", theta0_deg=60.0)
    etude60.reglages = replace(etude60.reglages, duree=0.01, nb_pas=10, periode_ecriture=0.001)
    res = MoteurExudynDyn().simuler(etude60)
    assert res.positions["Piston"][0, 0] == pytest.approx(0.3372281, abs=1e-6)
    # formule analytique : r cosθ + sqrt(L² − r² sin²θ)
    th = math.radians(60.0)
    analytique = 0.1 * math.cos(th) + math.sqrt(0.3**2 - (0.1 * math.sin(th)) ** 2)
    assert res.positions["Piston"][0, 0] == pytest.approx(analytique, abs=1e-6)


def test_ex22_liaison_non_validee_refusee_par_le_moteur() -> None:
    etude = etude_bielle("00")
    etude.liaison("L12_pivot").statut = Statut.PROPOSEE
    with pytest.raises(ErreurModele, match="L12_pivot"):
        MoteurExudynDyn().simuler(etude)
