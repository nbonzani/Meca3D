# SPDX-License-Identifier: GPL-3.0-or-later
"""Mode cinématique (EX-41), option « Hyperstatique autorisé » (EX-23) et garde-fou (EX-22).

Références : formule analytique de la bielle-manivelle, dérivée symbolique (sympy).
"""

import numpy as np
import pytest
from outils_cinematique import OMEGA, courbes_piston, etude_bielle_60

from meca3d.graphe.mobilite import Mode
from meca3d.modele.actions import ActionExterieure, NatureAction
from meca3d.moteur.base import ErreurGardeFou, ResultatsBruts
from meca3d.moteur.cinematique import MoteurCinematique
from meca3d.moteur.exudyn_dyn import MoteurExudynDyn
from meca3d.moteur.simulation import simuler_etude

TOLERANCE_POSITION = 1e-6  # m (EX-41)
TOLERANCE_ACCELERATION = 1e-3  # relative au maximum (EX-41)


@pytest.fixture(scope="module")
def resultats() -> ResultatsBruts:
    return MoteurCinematique().simuler(etude_bielle_60())


def test_ex41_grille_de_sortie(resultats: ResultatsBruts) -> None:
    assert len(resultats.t) == 501
    assert resultats.t[-1] == pytest.approx(0.25, abs=1e-12)


def test_ex41_position_du_piston(resultats: ResultatsBruts) -> None:
    x_b, _, _ = courbes_piston(resultats.t)
    assert np.abs(resultats.positions["Piston"][:, 0] - x_b).max() < TOLERANCE_POSITION


def test_ex41_vitesse_du_piston(resultats: ResultatsBruts) -> None:
    _, v_b, _ = courbes_piston(resultats.t)
    ecart = np.abs(resultats.vitesses["Piston"][:, 0] - v_b).max() / np.abs(v_b).max()
    assert ecart < TOLERANCE_ACCELERATION


def test_ex41_acceleration_du_piston_calculee_directement(resultats: ResultatsBruts) -> None:
    _, _, a_b = courbes_piston(resultats.t)
    calculee = resultats.accelerations["Piston"][:, 0]
    ecart = np.abs(calculee - a_b).max() / np.abs(a_b).max()
    assert ecart < TOLERANCE_ACCELERATION
    # « directement, pas par différence finie » : une différence finie sur 0,5 ms n'atteindrait
    # pas 1e-8 ; l'accélération directe est exacte à la précision du calcul
    assert ecart < 1e-8


def test_ex41_manivelle_a_vitesse_constante(resultats: ResultatsBruts) -> None:
    omega = resultats.vitesses_angulaires["Manivelle"]
    assert np.abs(omega[:, 2] - OMEGA).max() < 1e-8
    assert np.abs(omega[:, :2]).max() < 1e-8
    assert np.abs(resultats.accelerations_angulaires["Manivelle"]).max() < 1e-6
    # le piston reste sur l'axe x : y, z et rotations nuls
    assert np.abs(resultats.positions["Piston"][:, 1:]).max() < 1e-9
    assert np.abs(resultats.vitesses["Piston"][:, 1:]).max() < 1e-8


def test_ex41_aucun_effort_presente(resultats: ResultatsBruts) -> None:
    assert resultats.forces == {}
    assert resultats.moments == {}


def test_ex41_pesanteur_et_actions_sans_effet_en_cinematique() -> None:
    etude = etude_bielle_60()
    etude.pesanteur.actif = True
    etude.actions = [ActionExterieure("F1", "Piston", NatureAction.FORCE, (500.0, 0.0, 0.0))]
    res = MoteurCinematique().simuler(etude)
    x_b, _, _ = courbes_piston(res.t)
    assert np.abs(res.positions["Piston"][:, 0] - x_b).max() < TOLERANCE_POSITION


def test_ex41_simuler_etude_mode_cinematique() -> None:
    res = simuler_etude(etude_bielle_60(), Mode.CINEMATIQUE)
    x_b, _, _ = courbes_piston(res.t)
    assert np.abs(res.positions["Piston"][:, 0] - x_b).max() < TOLERANCE_POSITION
    assert res.ddl_liberes == []


# --- EX-23 : option « Hyperstatique autorisé » ---


def test_ex23_trois_pivots_et_glissiere_option_cochee() -> None:
    etude = etude_bielle_60("pivot")
    etude.hyperstatique_autorise = True
    res = simuler_etude(etude, Mode.CINEMATIQUE)
    # trois ddl libérés, listés (liaison, indice du ddl dans [Tx Ty Tz Rx Ry Rz])
    assert len(res.ddl_liberes) == 3
    assert len(set(res.ddl_liberes)) == 3
    noms = {x.nom for x in etude.liaisons}
    for liaison, ddl in res.ddl_liberes:
        assert liaison in noms
        assert 0 <= ddl <= 5
    # x_B(t) identique au cas isostatique à 1e-6 m, et conforme à la formule analytique
    isostatique = MoteurCinematique().simuler(etude_bielle_60())
    x_b, _, a_b = courbes_piston(res.t)
    assert (
        np.abs(res.positions["Piston"][:, 0] - isostatique.positions["Piston"][:, 0]).max() < 1e-6
    )
    assert np.abs(res.positions["Piston"][:, 0] - x_b).max() < TOLERANCE_POSITION
    ecart = np.abs(res.accelerations["Piston"][:, 0] - a_b).max() / np.abs(a_b).max()
    assert ecart < TOLERANCE_ACCELERATION
    # mouvement plan : les ddl libérés restent nuls (aucun mouvement hors du plan)
    assert np.abs(res.positions["Bielle"][:, 2]).max() < 1e-9


def test_ex23_option_decochee_refus() -> None:
    etude = etude_bielle_60("pivot")
    assert etude.hyperstatique_autorise is False
    with pytest.raises(ErreurGardeFou, match=r"h = 3"):
        simuler_etude(etude, Mode.CINEMATIQUE)


def test_ex23_option_cochee_mode_dynamique_refus() -> None:
    etude = etude_bielle_60("pivot")
    etude.hyperstatique_autorise = True
    with pytest.raises(ErreurGardeFou, match="indéterminé"):
        simuler_etude(etude, Mode.DYNAMIQUE)


# --- EX-22 : garde-fou avant tout appel au moteur ---


@pytest.fixture
def moteurs_interdits(monkeypatch: pytest.MonkeyPatch) -> None:
    def interdit(*args: object, **kwargs: object) -> None:
        raise AssertionError("le moteur ne doit pas être appelé")

    monkeypatch.setattr(MoteurExudynDyn, "simuler", interdit)
    monkeypatch.setattr(MoteurCinematique, "simuler", interdit)


@pytest.mark.parametrize("mode", [Mode.DYNAMIQUE, Mode.CINEMATIQUE])
def test_ex22_hyperstatique_refuse_sans_appel_au_moteur(
    moteurs_interdits: None, mode: Mode
) -> None:
    etude = etude_bielle_60("rotule")  # h = 1
    with pytest.raises(ErreurGardeFou) as info:
        simuler_etude(etude, mode)
    message = str(info.value)
    assert "h = 1" in message
    for nom in ("L01_pivot", "L12_pivot", "L23_rotule", "L30_glissiere"):
        assert nom in message


def test_ex22_option_cochee_dynamique_refus_sans_appel_au_moteur(moteurs_interdits: None) -> None:
    etude = etude_bielle_60("pivot")
    etude.hyperstatique_autorise = True
    with pytest.raises(ErreurGardeFou, match="indéterminé"):
        simuler_etude(etude, Mode.DYNAMIQUE)


def test_ex22_cinematique_exige_une_loi_par_mobilite(moteurs_interdits: None) -> None:
    etude = etude_bielle_60(pilote=False)
    with pytest.raises(ErreurGardeFou, match="loi"):
        simuler_etude(etude, Mode.CINEMATIQUE)


def test_ex22_dynamique_sans_loi_avertit_sans_refuser() -> None:
    etude = etude_bielle_60(pilote=False, duree=0.05)
    res = simuler_etude(etude, Mode.DYNAMIQUE)
    assert any("loi" in message for message in res.avertissements)
