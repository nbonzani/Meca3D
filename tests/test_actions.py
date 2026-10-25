# SPDX-License-Identifier: GPL-3.0-or-later
"""Actions extérieures (EX-32) : force ou couple, constant ou fonction de t, point d'application,
repère monde ou solide. Références : mécanique analytique et intégration RK4 indépendante."""

import math
from pathlib import Path

import numpy as np
import pytest

from meca3d.modele.actions import (
    ActionExterieure,
    ErreurAction,
    ErreurLoi,
    NatureAction,
    Pesanteur,
    RepereAction,
    RessortAmortisseur,
)
from meca3d.modele.etude import ErreurEtude, Etude, Reglages, ecrire_etude, lire_etude
from meca3d.modele.liaison import Liaison
from meca3d.modele.solide import Solide
from meca3d.moteur.base import ErreurModele
from meca3d.moteur.exudyn_dyn import MoteurExudynDyn

MASSE = 2.0  # kg
IZZ = 0.05  # kg·m², au centre de gravité
BRAS_CDG = 0.5  # m, distance pivot - centre de gravité
BRAS_POINT = 0.8  # m, point d'application de la force
J_PIVOT = IZZ + MASSE * BRAS_CDG**2  # moment d'inertie par rapport à l'axe du pivot
F = 3.0  # N


def _solide(nom: str, fixe: bool, masse: float, cdg: tuple[float, float, float], izz: float):
    return Solide(nom, fixe, masse, np.array(cdg), np.diag([1e-3, 1e-3, izz]))


def etude_glissiere_x() -> Etude:
    """Masse de 2 kg sur glissière d'axe x, sans pesanteur."""
    liaison = Liaison("L01", "slider", "Bati", "Masse", np.zeros(3), np.array([1.0, 0, 0]), 0.0)
    liaison.valider()
    etude = Etude(
        solides=[
            _solide("Bati", True, 1.0, (0, 0, 0), 1e-3),
            _solide("Masse", False, MASSE, (0, 0, 0), 1e-3),
        ],
        liaisons=[liaison],
        pesanteur=Pesanteur(actif=False),
        reglages=Reglages(duree=1.0, nb_pas=1000, periode_ecriture=1e-3),
    )
    return etude


def etude_pivot(cdg_x: float, izz: float, duree: float = 0.5) -> Etude:
    """Corps sur un pivot d'axe z en O, centre de gravité en (cdg_x, 0, 0), sans pesanteur."""
    liaison = Liaison("L01", "revolute", "Bati", "Barre", np.zeros(3), np.array([0, 0, 1.0]), 0.0)
    liaison.valider()
    return Etude(
        solides=[
            _solide("Bati", True, 1.0, (0, 0, 0), 1e-3),
            _solide("Barre", False, MASSE, (cdg_x, 0, 0), izz),
        ],
        liaisons=[liaison],
        pesanteur=Pesanteur(actif=False),
        reglages=Reglages(duree=duree, nb_pas=1000, periode_ecriture=1e-3),
    )


def _angle(rotations: np.ndarray) -> np.ndarray:
    return np.unwrap(np.arctan2(rotations[:, 1, 0], rotations[:, 0, 0]))


def test_ex32_force_constante_a_egale_f_sur_m() -> None:
    etude = etude_glissiere_x()
    etude.actions = [ActionExterieure("F1", "Masse", NatureAction.FORCE, (F, 0.0, 0.0))]
    res = MoteurExudynDyn().simuler(etude)
    # x(t) = ½ (F/m) t² : exact pour une accélération constante
    attendu = 0.5 * F / MASSE * res.t**2
    assert np.abs(res.positions["Masse"][:, 0] - attendu).max() < 1e-6
    assert res.positions["Masse"][-1, 0] == pytest.approx(0.75, abs=1e-6)


def test_ex32_force_fonction_de_t() -> None:
    etude = etude_glissiere_x()
    etude.actions = [ActionExterieure("F1", "Masse", NatureAction.FORCE, ("3*t", "0", "0"))]
    res = MoteurExudynDyn().simuler(etude)
    # m x'' = 3 t  =>  x = t³ / 4
    assert np.abs(res.positions["Masse"][:, 0] - res.t**3 / 4.0).max() < 1e-5


def test_ex32_force_en_repere_solide_sur_pivot() -> None:
    etude = etude_pivot(BRAS_CDG, IZZ)
    etude.actions = [
        ActionExterieure(
            "F1",
            "Barre",
            NatureAction.FORCE,
            (0.0, F, 0.0),
            RepereAction.SOLIDE,
            point=(BRAS_POINT, 0.0, 0.0),
        )
    ]
    res = MoteurExudynDyn().simuler(etude)
    # force toujours perpendiculaire à la barre : couple constant F·0,8, θ = ½ (0,8 F / J) t²
    attendu = 0.5 * BRAS_POINT * F / J_PIVOT * res.t**2
    assert np.abs(_angle(res.rotations["Barre"]) - attendu).max() < 1e-5


def _theta_rk4(t: np.ndarray, pas: float = 1e-4) -> np.ndarray:
    """θ'' = (0,8 F cos θ) / J : force fixe (0, F) en repère monde, appliquée en (0,8 cos θ,
    0,8 sin θ) ; intégration RK4 indépendante."""

    def derivee(y: np.ndarray) -> np.ndarray:
        return np.array([y[1], BRAS_POINT * F * math.cos(y[0]) / J_PIVOT])

    y = np.zeros(2)
    sortie = [0.0]
    temps = 0.0
    for cible in t[1:]:
        while temps < cible - 1e-12:
            h = min(pas, cible - temps)
            k1 = derivee(y)
            k2 = derivee(y + h / 2 * k1)
            k3 = derivee(y + h / 2 * k2)
            k4 = derivee(y + h * k3)
            y = y + h / 6 * (k1 + 2 * k2 + 2 * k3 + k4)
            temps += h
        sortie.append(float(y[0]))
    return np.array(sortie)


def test_ex32_force_en_repere_monde_sur_pivot() -> None:
    etude = etude_pivot(BRAS_CDG, IZZ)
    etude.actions = [
        ActionExterieure(
            "F1",
            "Barre",
            NatureAction.FORCE,
            (0.0, F, 0.0),
            RepereAction.MONDE,
            point=(BRAS_POINT, 0.0, 0.0),
        )
    ]
    res = MoteurExudynDyn().simuler(etude)
    theta = _angle(res.rotations["Barre"])
    assert np.abs(theta - _theta_rk4(res.t)).max() < 1e-5
    # le repère compte : la même force en repère solide donne un autre mouvement
    assert theta[-1] != pytest.approx(0.5 * BRAS_POINT * F / J_PIVOT * res.t[-1] ** 2, abs=1e-3)


def test_ex32_couple_fonction_de_t() -> None:
    izz = 0.01
    etude = etude_pivot(0.0, izz)
    etude.actions = [ActionExterieure("C1", "Barre", NatureAction.COUPLE, ("0", "0", "2*t"))]
    res = MoteurExudynDyn().simuler(etude)
    # J θ'' = 2 t  =>  θ = t³ / (3 J) ; à t = 0,5 s : 4,16667 rad
    theta = _angle(res.rotations["Barre"])
    assert theta[-1] == pytest.approx(0.5**3 / (3 * izz), rel=1e-4)
    assert np.abs(theta - res.t**3 / (3 * izz)).max() < 1e-3


def test_ex32_couple_constant_en_repere_solide() -> None:
    izz = 0.01
    etude = etude_pivot(0.0, izz)
    etude.actions = [
        ActionExterieure("C1", "Barre", NatureAction.COUPLE, (0.0, 0.0, 0.2), RepereAction.SOLIDE)
    ]
    res = MoteurExudynDyn().simuler(etude)
    attendu = 0.5 * 0.2 / izz * res.t**2
    assert np.abs(_angle(res.rotations["Barre"]) - attendu).max() < 1e-5


def test_ex32_action_sur_solide_fixe_refusee() -> None:
    etude = etude_glissiere_x()
    etude.actions = [ActionExterieure("F1", "Bati", NatureAction.FORCE, (1.0, 0.0, 0.0))]
    with pytest.raises(ErreurModele, match="fixe"):
        MoteurExudynDyn().simuler(etude)


def test_ex32_action_solide_inconnu_refusee() -> None:
    etude = etude_glissiere_x()
    etude.actions = [ActionExterieure("F1", "Fantome", NatureAction.FORCE, (1.0, 0.0, 0.0))]
    with pytest.raises(ErreurModele, match="Fantome"):
        MoteurExudynDyn().simuler(etude)
    with pytest.raises(ErreurEtude, match="Fantome"):
        etude.verifier_coherence()


def test_ex32_loi_dangereuse_refusee() -> None:
    with pytest.raises(ErreurLoi):
        ActionExterieure("F1", "Masse", NatureAction.FORCE, ("__import__('os')", "0", "0"))
    with pytest.raises(ErreurLoi):
        ActionExterieure("F1", "Masse", NatureAction.FORCE, ("", "0", "0"))


def test_ex32_definition_invalide() -> None:
    with pytest.raises(ErreurAction, match="nature"):
        ActionExterieure("F1", "Masse", "torsion", (0.0, 0.0, 0.0))  # type: ignore[arg-type]
    with pytest.raises(ErreurAction, match="trois"):
        ActionExterieure("F1", "Masse", NatureAction.FORCE, (1.0, 0.0))  # type: ignore[arg-type]
    with pytest.raises(ErreurAction, match="point"):
        ActionExterieure("F1", "Masse", NatureAction.FORCE, (1, 0, 0), point=(0.0, float("nan"), 0))
    with pytest.raises(ErreurAction, match="nom"):
        ActionExterieure("", "Masse", NatureAction.FORCE, (1, 0, 0))


def test_ex32_valeur_en_fonction_du_temps() -> None:
    action = ActionExterieure("F1", "Masse", NatureAction.FORCE, ("2*t", "5", "-t"))
    assert action.valeur(0.5).tolist() == [1.0, 5.0, -0.5]


def _etude_complete() -> Etude:
    etude = etude_glissiere_x()
    etude.actions = [
        ActionExterieure(
            "F1", "Masse", NatureAction.FORCE, ("3*t", "0", "0"), RepereAction.SOLIDE, (0.1, 0, 0)
        ),
        ActionExterieure("C1", "Masse", NatureAction.COUPLE, (0.0, 0.0, 0.5)),
    ]
    etude.ressorts = [
        RessortAmortisseur(
            "R1", "Bati", (0.0, 0.0, 1.0), "Masse", (0.0, 0.0, 0.0), 1000.0, 0.9, 2.5
        )
    ]
    etude.hyperstatique_autorise = True
    return etude


def test_ex32_ex33_aller_retour_du_fichier_etude(tmp_path: Path) -> None:
    etude = _etude_complete()
    premier, second = tmp_path / "a.meca3d", tmp_path / "b.meca3d"
    ecrire_etude(etude, premier)
    relue = lire_etude(premier)
    assert relue.vers_dict() == etude.vers_dict()
    ecrire_etude(relue, second)
    assert second.read_bytes() == premier.read_bytes()
    assert [a.nom for a in relue.actions] == ["F1", "C1"]
    assert relue.actions[0].repere is RepereAction.SOLIDE
    assert relue.actions[0].composantes == ("3*t", "0", "0")
    assert relue.ressorts[0].amortissement == 2.5
    assert relue.hyperstatique_autorise is True


def test_ex32_etude_sans_actions_ni_ressorts_inchangee(tmp_path: Path) -> None:
    # une étude sans action ni ressort s'écrit comme avant le lot 6 (fixtures lisibles et stables)
    fixture = Path(__file__).parent / "fixtures" / "bielle" / "bielle.meca3d"
    etude = lire_etude(fixture)
    assert etude.actions == [] and etude.ressorts == []
    assert etude.hyperstatique_autorise is False
    sortie = tmp_path / "copie.meca3d"
    ecrire_etude(etude, sortie)
    assert sortie.read_bytes() == fixture.read_bytes()


def test_ex32_reference_croisee_actions_corrompues(tmp_path: Path) -> None:
    donnees = _etude_complete().vers_dict()
    donnees["actions"][0]["solide"] = "Fantome"
    with pytest.raises(ErreurEtude):
        Etude.depuis_dict(donnees)
    donnees = _etude_complete().vers_dict()
    donnees["ressorts"][0]["solide_2"] = "Fantome"
    with pytest.raises(ErreurEtude):
        Etude.depuis_dict(donnees)
    donnees = _etude_complete().vers_dict()
    donnees["actions"].append(dict(donnees["actions"][0]))
    with pytest.raises(ErreurEtude, match="double"):
        Etude.depuis_dict(donnees)
    donnees = _etude_complete().vers_dict()
    donnees["actions"][0]["composantes"][0] = "__import__('os')"
    with pytest.raises(ErreurEtude):
        Etude.depuis_dict(donnees)
