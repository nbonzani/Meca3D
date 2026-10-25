# SPDX-License-Identifier: GPL-3.0-or-later
"""Raccord R5 côté moteur : rappel de progression et drapeau d'arrêt explicites (EX-42)."""

import time

import pytest
from outils_bielle import etude_bielle

from meca3d.modele.etude import Reglages
from meca3d.moteur.base import CalculAnnule, ErreurMoteur
from meca3d.moteur.cinematique import MoteurCinematique
from meca3d.moteur.exudyn_dyn import MoteurExudynDyn


def test_r5_progression_monotone_de_0_a_1() -> None:
    etude = etude_bielle()
    etude.reglages = Reglages(duree=0.2, nb_pas=400, periode_ecriture=0.002)
    valeurs: list[float] = []
    MoteurExudynDyn().simuler(etude, progression=valeurs.append)
    assert len(valeurs) >= 10
    assert all(0.0 <= v <= 1.0 for v in valeurs)
    assert all(b >= a for a, b in zip(valeurs, valeurs[1:], strict=False))
    assert valeurs[-1] == pytest.approx(1.0, abs=1e-9)


def test_r5_sans_rappel_le_resultat_est_inchange() -> None:
    etude = etude_bielle()
    etude.reglages = Reglages(duree=0.1, nb_pas=200, periode_ecriture=0.002)
    seul = MoteurExudynDyn().simuler(etude)
    avec = MoteurExudynDyn().simuler(etude, progression=lambda f: None, arret=lambda: False)
    assert (seul.positions["Piston"] == avec.positions["Piston"]).all()


def test_r5_arret_leve_calcul_annule_rapidement() -> None:
    """Un calcul d'une dizaine de secondes, arrêté à 5 % : retour en moins de 1 s après l'ordre."""
    etude = etude_bielle()
    etude.reglages = Reglages(duree=1.0, nb_pas=40000, periode_ecriture=0.002)
    etat: dict[str, float] = {}

    def progression(fraction: float) -> None:
        if fraction >= 0.05 and "ordre" not in etat:
            etat["ordre"] = time.perf_counter()

    t0 = time.perf_counter()
    with pytest.raises(CalculAnnule):
        MoteurExudynDyn().simuler(etude, progression=progression, arret=lambda: "ordre" in etat)
    fin = time.perf_counter()
    assert "ordre" in etat
    assert fin - etat["ordre"] < 1.0
    assert fin - t0 < 8.0  # le calcul complet durerait plus de 10 s


def test_r5_calcul_annule_est_une_erreur_du_moteur() -> None:
    assert issubclass(CalculAnnule, ErreurMoteur)


def test_r5_mode_cinematique_progression_et_arret() -> None:
    etude = etude_bielle()
    etude.reglages = Reglages(duree=0.2, nb_pas=400, periode_ecriture=0.002)
    valeurs: list[float] = []
    MoteurCinematique().simuler(etude, progression=valeurs.append)
    assert valeurs and valeurs[-1] == pytest.approx(1.0, abs=1e-9)
    assert all(b >= a for a, b in zip(valeurs, valeurs[1:], strict=False))
    with pytest.raises(CalculAnnule):
        MoteurCinematique().simuler(etude, arret=lambda: True)
