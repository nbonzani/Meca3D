# SPDX-License-Identifier: GPL-3.0-or-later
"""Torseurs de liaison (EX-50) : statique {i→j}, base de liaison ou monde, cinématique {V j/i}."""

import numpy as np
import pytest
import reference_bielle as ref
from meca3d.moteur.cinematique import MoteurCinematique
from outils_bielle import etude_bielle
from outils_cinematique import OMEGA, courbes_piston, etude_bielle_60

from meca3d.modele.etude import Etude
from meca3d.moteur.base import ResultatsBruts
from meca3d.moteur.exudyn_dyn import MoteurExudynDyn
from meca3d.resultats.torseurs import torseur_cinematique, torseur_statique

TOLERANCE_EX40 = 5e-3


@pytest.fixture(scope="module")
def etude() -> Etude:
    return etude_bielle("00")


@pytest.fixture(scope="module")
def resultats(etude: Etude) -> ResultatsBruts:
    return MoteurExudynDyn().simuler(etude)


@pytest.fixture(scope="module")
def etude_cinematique() -> Etude:
    return etude_bielle_60()


@pytest.fixture(scope="module")
def resultats_cinematique(etude_cinematique: Etude) -> ResultatsBruts:
    return MoteurCinematique().simuler(etude_cinematique)


def _ecart(calcule: np.ndarray, reference: np.ndarray) -> float:
    return float(np.abs(calcule - reference).max() / np.abs(reference).max())


# --- torseur statique ---


def test_ex50_pivot_l01_reaction_conforme_a_la_reference(
    etude: Etude, resultats: ResultatsBruts
) -> None:
    # R(0→1) : action du bâti sur la manivelle, en base monde
    tors = torseur_statique(etude, resultats, "L01_pivot", de="Bati", base="monde")
    refs = np.array([ref.reference(float(t))["O"] for t in resultats.t])
    assert _ecart(tors[:, :2], refs) <= TOLERANCE_EX40


def test_ex50_pivot_l01_couple_moteur(etude: Etude, resultats: ResultatsBruts) -> None:
    tors = torseur_statique(etude, resultats, "L01_pivot", de="Bati", base="monde")
    refs = np.array([ref.reference(float(t))["C"] for t in resultats.t])
    assert _ecart(tors[:, 5], refs) <= TOLERANCE_EX40


def test_ex50_moment_sur_l_axe_libre_nul_hors_pilote(
    etude: Etude, resultats: ResultatsBruts
) -> None:
    # pivot L12 (axe z) : moment d'axe z nul ; hors pilote
    tors = torseur_statique(etude, resultats, "L12_pivot", de="Manivelle", base="monde")
    assert np.abs(tors[:, 5]).max() < 1e-9
    # L30, glissière d'axe x : effort selon l'axe libre nul
    tors = torseur_statique(etude, resultats, "L30_glissiere", de="Bati", base="monde")
    assert np.abs(tors[:, 0]).max() < 1e-9


def test_ex50_composantes_nulles_par_construction_affichees_nulles(
    etude: Etude, resultats: ResultatsBruts
) -> None:
    # base de liaison [Fx Fy Fz Mx My Mz], x local = axe libre. Les composantes sur les ddl libres
    # (hors pilote) sont exactement nulles, pas seulement petites.
    attendu_nulles = {
        "L12_pivot": [3],  # pivot : Mx
        "L23_rotule": [0, 3, 4, 5],  # linéaire annulaire d'axe z : Fx, Mx, My, Mz
        "L30_glissiere": [0],  # glissière : Fx
    }
    for liaison, indices in attendu_nulles.items():
        de = etude.liaison(liaison).solide_a
        tors = torseur_statique(etude, resultats, liaison, de=de, base="liaison")
        for i in indices:
            assert np.all(tors[:, i] == 0.0), (liaison, i)
    # le pilote L01 porte le couple moteur sur son axe libre : il n'est pas annulé
    tors = torseur_statique(etude, resultats, "L01_pivot", de="Bati", base="liaison")
    assert np.abs(tors[:, 3]).max() > 0.1


@pytest.mark.parametrize("base", ["monde", "liaison"])
@pytest.mark.parametrize("liaison", ["L01_pivot", "L12_pivot", "L23_rotule", "L30_glissiere"])
def test_ex50_i_vers_j_oppose_de_j_vers_i(
    etude: Etude, resultats: ResultatsBruts, liaison: str, base: str
) -> None:
    lia = etude.liaison(liaison)
    ij = torseur_statique(etude, resultats, liaison, de=lia.solide_a, base=base)
    ji = torseur_statique(etude, resultats, liaison, de=lia.solide_b, base=base)
    assert np.abs(ij + ji).max() < 1e-12
    assert np.abs(ij).max() > 0.0


def test_ex50_base_monde_et_base_de_liaison_coherentes(
    etude: Etude, resultats: ResultatsBruts
) -> None:
    # L01 : bâti fixe, base de liaison constante : F_monde = B · F_liaison (B = base de la liaison)
    lia = etude.liaison("L01_pivot")
    monde = torseur_statique(etude, resultats, "L01_pivot", de="Bati", base="monde")
    local = torseur_statique(etude, resultats, "L01_pivot", de="Bati", base="liaison")
    assert np.abs(monde[:, :3] - local[:, :3] @ lia.base().T).max() < 1e-9
    assert np.abs(monde[:, 3:] - local[:, 3:] @ lia.base().T).max() < 1e-9


def test_ex50_solide_etranger_refuse(etude: Etude, resultats: ResultatsBruts) -> None:
    with pytest.raises(ValueError, match="Piston"):
        torseur_statique(etude, resultats, "L01_pivot", de="Piston")


# --- torseur cinématique {V j/i} : [Ωx Ωy Ωz Vx Vy Vz], réduit au centre de la liaison ---


def test_ex50_cinematique_pivot_pilote(
    etude_cinematique: Etude, resultats_cinematique: ResultatsBruts
) -> None:
    # {V Manivelle/Bâti} en base de liaison (x local = axe z du monde) : Ωx = 20 rad/s, V(O) = 0
    tors = torseur_cinematique(
        etude_cinematique, resultats_cinematique, "L01_pivot", i="Bati", base="liaison"
    )
    assert np.abs(tors[:, 0] - OMEGA).max() < 1e-8
    assert np.abs(tors[:, 1:]).max() < 1e-8


def test_ex50_cinematique_composantes_bloquees_exactement_nulles(
    etude_cinematique: Etude, resultats_cinematique: ResultatsBruts
) -> None:
    # pivot : Ωy, Ωz, Vx, Vy, Vz bloqués ; glissière : Vy, Vz, Ωx, Ωy, Ωz bloqués
    pivot = torseur_cinematique(
        etude_cinematique, resultats_cinematique, "L12_pivot", i="Manivelle", base="liaison"
    )
    for i in (1, 2, 3, 4, 5):
        assert np.all(pivot[:, i] == 0.0)
    glissiere = torseur_cinematique(
        etude_cinematique, resultats_cinematique, "L30_glissiere", i="Bati", base="liaison"
    )
    for i in (0, 1, 2, 4, 5):
        assert np.all(glissiere[:, i] == 0.0)


def test_ex50_cinematique_glissiere_vitesse_du_piston(
    etude_cinematique: Etude, resultats_cinematique: ResultatsBruts
) -> None:
    _, v_b, _ = courbes_piston(resultats_cinematique.t)
    tors = torseur_cinematique(
        etude_cinematique, resultats_cinematique, "L30_glissiere", i="Bati", base="monde"
    )
    assert np.abs(tors[:, 3] - v_b).max() / np.abs(v_b).max() < 1e-3


def test_ex50_cinematique_j_par_rapport_a_i_oppose(
    etude_cinematique: Etude, resultats_cinematique: ResultatsBruts
) -> None:
    for base in ("monde", "liaison"):
        ij = torseur_cinematique(
            etude_cinematique, resultats_cinematique, "L12_pivot", i="Manivelle", base=base
        )
        ji = torseur_cinematique(
            etude_cinematique, resultats_cinematique, "L12_pivot", i="Bielle", base=base
        )
        assert np.abs(ij + ji).max() < 1e-8
        assert np.abs(ij).max() > 1.0


def test_ex50_cinematique_pivot_l12_vitesse_relative_bielle_manivelle(
    etude_cinematique: Etude, resultats_cinematique: ResultatsBruts
) -> None:
    # Ω(Bielle/Manivelle) en z = β' − θ' avec β' = −r θ' cos θ / (L cos β) (fermeture de boucle)
    t = resultats_cinematique.t
    theta = np.radians(60.0) + OMEGA * t
    r, lg = 0.1, 0.3
    beta = np.arcsin(-r * np.sin(theta) / lg)
    beta_t = -r * OMEGA * np.cos(theta) / (lg * np.cos(beta))
    tors = torseur_cinematique(
        etude_cinematique, resultats_cinematique, "L12_pivot", i="Manivelle", base="monde"
    )
    attendu = beta_t - OMEGA
    assert np.abs(tors[:, 2] - attendu).max() / np.abs(attendu).max() < 1e-6
    assert np.abs(tors[:, 3:]).max() < 1e-8  # pivot : pas de translation relative au centre
