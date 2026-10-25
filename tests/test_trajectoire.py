# SPDX-License-Identifier: GPL-3.0-or-later
"""Trajectoire d'un point retracée dans SolidCraft par une spline 3D (EX-52, lot 10), contre le
faux serveur. Références : x_B(θ) = r cos θ + √(l² − r² sin² θ), θ = 60° + 20·t (SPEC EX-41)."""

import math
from collections.abc import Iterator

import numpy as np
import pytest
from faux_serveur import JETON_DE_TEST, FauxServeur
from meca3d.cao.animation import Animateur, ErreurAnimation
from outils_cinematique import etude_bielle_60

from meca3d.cao.canal import CanalSolidCraft
from meca3d.modele.etude import Etude
from meca3d.moteur.base import ResultatsBruts
from meca3d.moteur.cinematique import MoteurCinematique

R_MM, L_MM = 100.0, 300.0
THETA0, OMEGA = math.radians(60.0), 20.0
# point B du piston à l'import (θ = 60°), repère monde, en m
B_IMPORT = (0.1 * math.cos(THETA0) + math.sqrt(0.3**2 - (0.1 * math.sin(THETA0)) ** 2), 0.0, 0.0)


def x_b_mm(t: np.ndarray) -> np.ndarray:
    theta = THETA0 + OMEGA * t
    return R_MM * np.cos(theta) + np.sqrt(L_MM**2 - (R_MM * np.sin(theta)) ** 2)


@pytest.fixture(scope="module")
def etude() -> Etude:
    return etude_bielle_60(duree=0.5)


@pytest.fixture(scope="module")
def resultats(etude: Etude) -> ResultatsBruts:
    return MoteurCinematique().simuler(etude)


@pytest.fixture
def faux() -> Iterator[FauxServeur]:
    with FauxServeur(theta="60") as serveur:
        yield serveur


@pytest.fixture
def canal(faux: FauxServeur) -> Iterator[CanalSolidCraft]:
    with CanalSolidCraft(port=faux.port, jeton=JETON_DE_TEST) as c:
        yield c


def test_ex52_spline_passant_par_les_points_du_capteur_b(
    faux: FauxServeur, canal: CanalSolidCraft, etude: Etude, resultats: ResultatsBruts
) -> None:
    animateur = Animateur(canal, etude, resultats)
    nom = animateur.tracer_trajectoire(B_IMPORT, "Piston", nom="Trajectoire_B", max_points=None)
    assert len(faux.esquisses) == 1
    esquisse = faux.esquisses[0]
    assert esquisse.nom == nom == "Trajectoire_B"
    assert esquisse.sketch_3d and esquisse.termine
    points = np.array(esquisse.points)  # mm, repère monde
    assert points.shape == (len(resultats.t), 3)
    assert np.abs(points[:, 0] - x_b_mm(resultats.t)).max() <= 1e-3
    assert np.abs(points[:, 1:]).max() <= 1e-3


def test_ex52_sequence_de_commandes_de_la_trajectoire(
    faux: FauxServeur, canal: CanalSolidCraft, etude: Etude, resultats: ResultatsBruts
) -> None:
    Animateur(canal, etude, resultats).tracer_trajectoire(B_IMPORT, "Piston")
    attendu = ["sketch.create", "sketch.options", "sketch.spline3d", "sketch.finish"]
    assert faux.commandes_recues() == attendu
    options = next(
        r["params"]["params"]
        for r in faux.requetes
        if r["params"].get("command") == "sketch.options"
    )
    assert options == {"sketch_3d": True}


def test_ex52_nombre_de_points_borne_par_defaut_extremites_conservees(
    faux: FauxServeur, canal: CanalSolidCraft, etude: Etude, resultats: ResultatsBruts
) -> None:
    Animateur(canal, etude, resultats).tracer_trajectoire(B_IMPORT, "Piston")
    points = np.array(faux.esquisses[0].points)
    assert 2 <= len(points) <= 200 < len(resultats.t)
    assert points[0, 0] == pytest.approx(float(x_b_mm(resultats.t[:1])[0]), abs=1e-3)
    assert points[-1, 0] == pytest.approx(float(x_b_mm(resultats.t[-1:])[0]), abs=1e-3)


def test_ex52_trajectoire_par_rapport_a_la_manivelle(
    faux: FauxServeur, canal: CanalSolidCraft, etude: Etude, resultats: ResultatsBruts
) -> None:
    # B vu depuis la manivelle (tournant de ω·t autour de z, centre O), dessiné à la pose d'import
    Animateur(canal, etude, resultats).tracer_trajectoire(
        B_IMPORT, "Piston", reference="Manivelle", max_points=None
    )
    points = np.array(faux.esquisses[0].points)
    t = resultats.t
    attendu = np.column_stack(
        [x_b_mm(t) * np.cos(OMEGA * t), -x_b_mm(t) * np.sin(OMEGA * t), np.zeros_like(t)]
    )
    assert np.abs(points - attendu).max() <= 5e-3  # mm


def test_ex52_effacement_par_timeline_delete(
    faux: FauxServeur, canal: CanalSolidCraft, etude: Etude, resultats: ResultatsBruts
) -> None:
    animateur = Animateur(canal, etude, resultats)
    animateur.tracer_trajectoire(B_IMPORT, "Piston", nom="Trajectoire_B")
    animateur.tracer_trajectoire((0.0, 0.0, 0.0), "Manivelle", nom="Trajectoire_O")
    assert len(faux.esquisses) == 2
    assert animateur.effacer_trajectoires() == 2
    assert faux.esquisses == []
    suppression = [r for r in faux.requetes if r["params"].get("command") == "timeline.delete"]
    assert len(suppression) == 1
    assert sorted(suppression[0]["params"]["params"]["features"]) == [
        "Trajectoire_B",
        "Trajectoire_O",
    ]
    n = len(faux.requetes)
    assert animateur.effacer_trajectoires() == 0  # rien à effacer : aucune requête
    assert len(faux.requetes) == n


def test_ex52_le_nom_rendu_par_solidcraft_sert_a_l_effacement(
    faux: FauxServeur, canal: CanalSolidCraft, etude: Etude, resultats: ResultatsBruts
) -> None:
    animateur = Animateur(canal, etude, resultats)
    premier = animateur.tracer_trajectoire(B_IMPORT, "Piston", nom="Trace")
    second = animateur.tracer_trajectoire(B_IMPORT, "Piston", nom="Trace")  # SolidCraft renomme
    assert premier != second
    assert animateur.effacer_trajectoires() == 2
    assert faux.esquisses == []


def test_ex52_solide_inconnu_message_en_francais(
    faux: FauxServeur, canal: CanalSolidCraft, etude: Etude, resultats: ResultatsBruts
) -> None:
    animateur = Animateur(canal, etude, resultats)
    with pytest.raises(ErreurAnimation, match="Roue"):
        animateur.tracer_trajectoire(B_IMPORT, "Roue")
    assert faux.requetes == []  # rien n'a été envoyé


def test_ex52_la_trajectoire_n_enregistre_pas_la_maquette(
    faux: FauxServeur, canal: CanalSolidCraft, etude: Etude, resultats: ResultatsBruts
) -> None:
    animateur = Animateur(canal, etude, resultats)
    animateur.tracer_trajectoire(B_IMPORT, "Piston")
    animateur.effacer_trajectoires()
    assert not [n for n in faux.commandes_recues() if "save" in n.lower()]
