# SPDX-License-Identifier: GPL-3.0-or-later
"""Lot 11 : les quatre cas de référence importés depuis le VRAI SolidCraft (manuel).

SolidCraft est lancé avec `--control 7878`, fenêtre visible. Chaque test ouvre sa maquette
(`tests/fixtures/maquettes/<cas>.solidcraft`) par la commande `doc.open`, l'importe par le canal,
fait les choix de l'élève, simule et compare aux références. À la fin du module, la maquette qui
était ouverte au départ (par exemple la bielle) est rouverte ; aucune maquette n'est enregistrée.
"""

import math
import tempfile
from collections.abc import Iterator
from pathlib import Path

import numpy as np
import pytest
from outils_cas_reference import (
    LONGUEUR,
    MAQUETTES,
    MASSE_BARRE,
    G,
    angle_barre2_au_pas,
    angles_depuis_etude,
    energie_double,
    lagrange_rk4,
    periode_mesuree,
    preparer,
    valider_tout,
    x_relatif_au_pivot,
)
from outils_couplages import PAS, action, couple, pilote, reglages

from meca3d.cao.canal import CanalSolidCraft
from meca3d.cao.solidcraft import EtudeImportee, importer
from meca3d.graphe.mobilite import Mode
from meca3d.modele.actions import NatureAction
from meca3d.modele.couplage import Engrenage, SensEngrenage, VisEcrou
from meca3d.moteur.exudyn_dyn import MoteurExudynDyn
from meca3d.moteur.simulation import analyser_etude, simuler_etude

pytestmark = pytest.mark.solidcraft

TOL = 1e-3


@pytest.fixture(scope="module")
def canal() -> Iterator[CanalSolidCraft]:
    c = CanalSolidCraft(port=7878)
    depart = c.requete("document.inspect").get("path")
    yield c
    if depart:
        c.executer("doc.open", {"path": depart})
    c.fermer()


def _importer(canal: CanalSolidCraft, cas: str) -> EtudeImportee:
    """Ouvre la maquette du cas dans SolidCraft, puis l'importe (pose enregistrée)."""
    canal.executer("doc.open", {"path": str(MAQUETTES / f"{cas}.solidcraft")})
    with tempfile.TemporaryDirectory(prefix="meca3d_test_") as dossier:
        etude = importer(canal, Path(dossier))
    assert etude.avertissements == []
    assert etude.maquette == cas
    return etude


def test_cas_reel_pendule_simple(canal: CanalSolidCraft) -> None:
    """Lâcher à 30° (pose enregistrée) : T(30°), ω_bas ; sans pesanteur, immobile."""
    etude = preparer(_importer(canal, "pendule_simple"), 3.4, 3400, 3.4 / 6400)
    res = simuler_etude(etude, Mode.DYNAMIQUE)
    x = x_relatif_au_pivot(etude, res, "Barre", "L01_pivot")
    assert periode_mesuree(res.t, x) == pytest.approx(1.05429, rel=TOL)
    omega = np.linalg.norm(res.vitesses_angulaires["Barre"], axis=1)
    assert float(omega.max()) == pytest.approx(3.13863, rel=TOL)
    # EX-31
    etude.pesanteur.actif = False
    etude.reglages = reglages(1.0, 500)
    res = simuler_etude(etude, Mode.DYNAMIQUE)
    assert np.abs(res.rotations["Barre"] - res.rotations["Barre"][0]).max() < 1e-9


def test_cas_reel_pendule_double(canal: CanalSolidCraft) -> None:
    etude = preparer(_importer(canal, "pendule_double"), 2.0, 2000)
    r = analyser_etude(etude).resultat
    assert (r.ic, r.rc, r.m, r.h, r.mu) == (2, 0, 2, 0, 0)
    res = simuler_etude(etude, Mode.DYNAMIQUE)
    e = energie_double(res)
    e_repos = -MASSE_BARRE * G * (LONGUEUR / 2.0 + 3.0 * LONGUEUR / 2.0)
    assert float(np.abs(e - e[0]).max() / abs(e[0] - e_repos)) < 1e-3
    phi1, phi2 = angles_depuis_etude(etude)
    indice = int(np.argmin(np.abs(res.t - 1.0)))
    _, phi2_ref = lagrange_rk4(phi1, phi2, 1.0)
    assert angle_barre2_au_pas(etude, res, indice) == pytest.approx(phi2_ref, abs=5e-4)


def test_cas_reel_reducteur(canal: CanalSolidCraft) -> None:
    etude = _importer(canal, "reducteur")
    valider_tout(etude)
    etude.pesanteur.actif = False
    assert len(etude.couplages) == 1
    gear = etude.couplages[0]
    assert isinstance(gear, Engrenage)
    assert gear.k == pytest.approx(20.0 / 60.0, rel=1e-12)
    # EX-14
    etude.pilotes = [pilote("L1_pivot", 30.0)]
    etude.reglages = reglages(1.0, 1000, 0.001)
    res = simuler_etude(etude, Mode.DYNAMIQUE)
    w_e = res.vitesses_angulaires["Roue1"][:, 2]
    w_s = res.vitesses_angulaires["Roue2"][:, 2]
    assert abs(w_s[-1]) == pytest.approx(10.0, rel=TOL)
    assert np.abs(w_s + gear.k * w_e).max() < 1e-6
    # EX-14 (couple) et EX-16 (rendement)
    etude.pilotes = []
    etude.reglages = reglages(0.5, 500, 0.001)
    vitesses = {
        "Roue1": ((0.0, 0.0, 0.0), (0.0, 0.0, 30.0)),
        "Roue2": ((0.0, 0.0, 0.0), (0.0, 0.0, -10.0)),
    }
    for eta, cs in ((1.0, 3.0), (0.95, 2.85)):
        etude.couplages = [
            Engrenage(gear.nom, "L1_pivot", "L2_pivot", gear.k, SensEngrenage.EXTERIEUR, eta)
        ]
        etude.actions = [couple("Ce", "Roue1", 1.0), couple("Cs", "Roue2", cs)]
        res = MoteurExudynDyn().simuler(etude, vitesses_initiales=vitesses)
        assert np.abs(res.vitesses_angulaires["Roue2"][:, 2] + 10.0).max() < 1e-4
        assert abs(res.efforts_couplages[gear.nom][-1, 1]) == pytest.approx(cs, rel=TOL)


def test_cas_reel_vis_ecrou(canal: CanalSolidCraft) -> None:
    etude = _importer(canal, "vis_ecrou")
    valider_tout(etude)
    etude.pesanteur.actif = False
    vis = etude.couplages[0]
    assert isinstance(vis, VisEcrou)
    assert vis.p == pytest.approx(PAS, rel=1e-12)
    etude.pilotes = [pilote("L_vis_pivot", 10.0)]
    etude.reglages = reglages(1.0, 1000, 0.001)
    res = simuler_etude(etude, Mode.DYNAMIQUE)
    assert res.vitesses["Ecrou"][-1, 2] == pytest.approx(7.9577e-3, rel=1e-4)
    effort = 2.0 * math.pi * 2.0 / PAS
    etude.pilotes = []
    etude.actions = [
        action("C", "Vis", NatureAction.COUPLE, (0.0, 0.0, 2.0)),
        action("Fr", "Ecrou", NatureAction.FORCE, (0.0, 0.0, -effort)),
    ]
    etude.reglages = reglages(0.5, 500, 0.001)
    res = MoteurExudynDyn().simuler(etude)
    assert np.abs(res.positions["Ecrou"][:, 2] - res.positions["Ecrou"][0, 2]).max() < 1e-4
    assert abs(res.efforts_couplages[vis.nom][-1, 1]) == pytest.approx(2513.27, rel=TOL)
