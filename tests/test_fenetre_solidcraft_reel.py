# SPDX-License-Identifier: GPL-3.0-or-later
"""R10 contre le vrai SolidCraft (`--control 7878`, bielle ouverte, jamais enregistrée) : la fenêtre
est réduite volontairement, ramenée, puis la cadence de l'animation est mesurée (manuel)."""

import time

import pytest
from outils_cinematique import etude_bielle_60

from meca3d.cao.animation import Animateur
from meca3d.cao.canal import CanalSolidCraft
from meca3d.cao.fenetre import SEUIL_LATENCE, ramener_au_premier_plan
from meca3d.moteur.cinematique import MoteurCinematique

pytestmark = pytest.mark.solidcraft

CADENCE_MIN = 20.0  # images/s (SPEC EX-53)


def _latence(canal: CanalSolidCraft, n: int = 5) -> float:
    debut = time.perf_counter()
    for _ in range(n):
        canal.requete("document.inspect")
    return (time.perf_counter() - debut) / n


def test_r10_reel_fenetre_reduite_ramenee() -> None:
    with CanalSolidCraft(port=7878) as canal:
        canal.requete("ui.window", {"action": "minimize"})
        time.sleep(1.0)
        assert _latence(canal) > SEUIL_LATENCE
        try:
            assert ramener_au_premier_plan(canal) is True
            time.sleep(0.5)
            assert _latence(canal) < SEUIL_LATENCE
        finally:
            canal.requete("ui.window", {"action": "maximize"})


def test_r10_reel_cadence_apres_reduction() -> None:
    etude = etude_bielle_60(duree=1.0)
    resultats = MoteurCinematique().simuler(etude)
    with CanalSolidCraft(port=7878) as canal:
        canal.requete("ui.window", {"action": "minimize"})
        time.sleep(1.0)
        animateur = Animateur(canal, etude, resultats)
        debut = time.perf_counter()
        images = animateur.jouer()
        cadence = images / (time.perf_counter() - debut)
        print(f"cadence après réduction : {cadence:.1f} images/s")
        assert cadence >= CADENCE_MIN
