# SPDX-License-Identifier: GPL-3.0-or-later
"""Capteurs de point (EX-51) et branchement des capteurs de l'étude sur l'export CSV (EX-52)."""

import numpy as np
import pytest
from meca3d.moteur.cinematique import MoteurCinematique
from meca3d.resultats.capteurs import mesurer_point
from outils_bielle import etude_bielle
from outils_cinematique import OMEGA, courbes_piston, courbes_piston_dans_manivelle, etude_bielle_60

from meca3d.modele.capteurs import (
    BaseCapteur,
    CapteurLiaison,
    CapteurPoint,
    SensTorseur,
)
from meca3d.modele.etude import Etude, Reglages
from meca3d.moteur.base import ResultatsBruts
from meca3d.moteur.exudyn_dyn import MoteurExudynDyn
from meca3d.resultats.export import colonnes_resultats

# Points de la configuration d'import (θ = 60°), repère monde, en m
A_IMPORT = (0.1 * np.cos(np.radians(60.0)), 0.1 * np.sin(np.radians(60.0)), 0.0)
B_IMPORT = (0.1 * np.cos(np.radians(60.0)) + np.sqrt(0.3**2 - A_IMPORT[1] ** 2), 0.0, 0.0)


@pytest.fixture(scope="module")
def etude() -> Etude:
    return etude_bielle_60()


@pytest.fixture(scope="module")
def resultats(etude: Etude) -> ResultatsBruts:
    return MoteurCinematique().simuler(etude)


def test_ex51_point_b_du_piston_par_rapport_au_bati(
    etude: Etude, resultats: ResultatsBruts
) -> None:
    # conforme à EX-41 : x_B à 1e-6 m, accélération à 1e-3 relatif
    capteur = CapteurPoint("P_B", "Piston", B_IMPORT, "Bati", BaseCapteur.MONDE)
    mesure = mesurer_point(etude, resultats, capteur)
    x_b, v_b, a_b = courbes_piston(resultats.t)
    assert np.abs(mesure.position[:, 0] - x_b).max() < 1e-6
    assert np.abs(mesure.position[:, 1:]).max() < 1e-6
    assert np.abs(mesure.vitesse[:, 0] - v_b).max() / np.abs(v_b).max() < 1e-3
    assert np.abs(mesure.acceleration[:, 0] - a_b).max() / np.abs(a_b).max() < 1e-3
    assert np.abs(mesure.vitesse[:, 1:]).max() < 1e-8


def test_ex51_base_du_solide_de_reference_confondue_avec_le_monde_pour_le_bati(
    etude: Etude, resultats: ResultatsBruts
) -> None:
    monde = mesurer_point(
        etude, resultats, CapteurPoint("P", "Piston", B_IMPORT, "Bati", BaseCapteur.MONDE)
    )
    base_ref = mesurer_point(
        etude, resultats, CapteurPoint("P", "Piston", B_IMPORT, "Bati", BaseCapteur.REFERENCE)
    )
    assert np.abs(monde.position - base_ref.position).max() < 1e-12
    assert np.abs(monde.vitesse - base_ref.vitesse).max() < 1e-12
    assert np.abs(monde.acceleration - base_ref.acceleration).max() < 1e-12


def test_ex51_point_a_de_la_bielle_par_rapport_a_la_manivelle_vitesse_nulle(
    etude: Etude, resultats: ResultatsBruts
) -> None:
    # A est au centre de la pivot L12 : vitesse relative nulle à 1e-9 près
    for base in (BaseCapteur.REFERENCE, BaseCapteur.MONDE):
        mesure = mesurer_point(
            etude, resultats, CapteurPoint("P_A", "Bielle", A_IMPORT, "Manivelle", base)
        )
        assert np.abs(mesure.vitesse).max() < 1e-9
        assert np.abs(mesure.acceleration).max() < 1e-6


def test_ex51_point_b_par_rapport_a_la_manivelle_en_base_de_la_manivelle(
    etude: Etude, resultats: ResultatsBruts
) -> None:
    # référence tournante : position, vitesse relative et accélération relative (Coriolis,
    # centrifuge) calculées symboliquement dans le repère de la manivelle (origine en O)
    p, v, a = courbes_piston_dans_manivelle(resultats.t)
    mesure = mesurer_point(
        etude,
        resultats,
        CapteurPoint("P", "Piston", B_IMPORT, "Manivelle", BaseCapteur.REFERENCE),
    )
    assert np.abs(mesure.position - p).max() < 1e-6
    assert np.abs(mesure.vitesse - v).max() / np.abs(v).max() < 1e-3
    assert np.abs(mesure.acceleration - a).max() / np.abs(a).max() < 1e-3


def test_ex51_expression_en_base_monde_d_un_mouvement_relatif(
    etude: Etude, resultats: ResultatsBruts
) -> None:
    # même mouvement relatif, exprimé en base monde : le vecteur est tourné de θ(t) autour de z
    ref = mesurer_point(
        etude,
        resultats,
        CapteurPoint("P", "Piston", B_IMPORT, "Manivelle", BaseCapteur.REFERENCE),
    )
    monde = mesurer_point(
        etude, resultats, CapteurPoint("P", "Piston", B_IMPORT, "Manivelle", BaseCapteur.MONDE)
    )
    theta = np.radians(60.0) + OMEGA * resultats.t
    c, s = np.cos(theta), np.sin(theta)
    for local, global_ in ((ref.position, monde.position), (ref.vitesse, monde.vitesse)):
        tourne = np.column_stack(
            [c * local[:, 0] - s * local[:, 1], s * local[:, 0] + c * local[:, 1]]
        )
        assert np.abs(tourne - global_[:, :2]).max() < 1e-6


def test_ex51_vitesse_du_point_a_de_la_manivelle_par_rapport_au_bati(
    etude: Etude, resultats: ResultatsBruts
) -> None:
    # A tourne à 0,1 m du centre à 20 rad/s : |v| = 2 m/s, |a| = r ω² = 40 m/s²
    mesure = mesurer_point(
        etude, resultats, CapteurPoint("P", "Manivelle", A_IMPORT, "Bati", BaseCapteur.MONDE)
    )
    assert np.abs(np.linalg.norm(mesure.vitesse, axis=1) - 2.0).max() < 1e-6
    assert np.abs(np.linalg.norm(mesure.acceleration, axis=1) - 40.0).max() < 1e-4


def test_ex51_solide_inconnu_refuse(etude: Etude, resultats: ResultatsBruts) -> None:
    with pytest.raises(KeyError, match="Fantome"):
        mesurer_point(etude, resultats, CapteurPoint("P", "Fantome", B_IMPORT, "Bati"))


# --- EX-52 : les capteurs définis dans l'étude alimentent le CSV ---


def test_ex52_capteurs_de_l_etude_dans_les_colonnes_csv() -> None:
    etude = etude_bielle_60()
    etude.capteurs = [
        CapteurPoint("P_B", "Piston", B_IMPORT, "Bati", BaseCapteur.MONDE),
        CapteurLiaison("C_L01", "L01_pivot", SensTorseur.I_VERS_J, BaseCapteur.MONDE),
    ]
    res = MoteurCinematique().simuler(etude)
    colonnes = colonnes_resultats(etude, res)
    assert colonnes["t (s)"] is res.t or np.array_equal(colonnes["t (s)"], res.t)
    mesure = mesurer_point(etude, res, etude.capteurs[0])  # type: ignore[arg-type]
    for i, axe in enumerate("xyz"):
        assert np.array_equal(colonnes[f"P_B {axe} (m)"], mesure.position[:, i])
        assert np.array_equal(colonnes[f"P_B v{axe} (m/s)"], mesure.vitesse[:, i])
        assert np.array_equal(colonnes[f"P_B a{axe} (m/s²)"], mesure.acceleration[:, i])
    # capteur de liaison : torseur cinématique {V j/i} en cinématique (aucun effort)
    assert "C_L01 Ωz (rad/s)" in colonnes
    assert np.abs(colonnes["C_L01 Ωz (rad/s)"] - OMEGA).max() < 1e-8
    assert not any("(N)" in nom for nom in colonnes)  # aucun effort en mode cinématique


def test_ex52_capteur_de_liaison_en_dynamique_ajoute_le_torseur_statique() -> None:
    etude = etude_bielle("00")
    etude.reglages = Reglages(duree=0.1, nb_pas=400, periode_ecriture=0.002)
    etude.capteurs = [CapteurLiaison("C_L12", "L12_pivot", SensTorseur.J_VERS_I, BaseCapteur.MONDE)]
    res = MoteurExudynDyn().simuler(etude)
    colonnes = colonnes_resultats(etude, res)
    for composante in ("Fx (N)", "Fy (N)", "Fz (N)", "Mx (N·m)", "My (N·m)", "Mz (N·m)"):
        assert f"C_L12 {composante}" in colonnes
    # sens j→i : opposé du sens i→j par défaut (colonnes de liaison déjà exportées)
    assert (
        np.abs(colonnes["C_L12 Fx (N)"] + colonnes["L12_pivot Manivelle→Bielle Fx (N)"]).max()
        < 1e-12
    )
