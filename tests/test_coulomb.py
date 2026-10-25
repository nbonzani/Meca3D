# SPDX-License-Identifier: GPL-3.0-or-later
"""Frottement de Coulomb (EX-15) : glissière, appui plan, pivot ; fluage signalé."""

import math

import numpy as np
import pytest
from outils_couplages import G, bati, cylindre, liaison, reglages

from meca3d.modele.etude import Etude
from meca3d.modele.liaison import TypeLiaison
from meca3d.modele.solide import Solide
from meca3d.moteur.base import ErreurModele
from meca3d.moteur.exudyn_dyn import MoteurExudynDyn

ALPHA = math.radians(30.0)
PENTE = np.array([math.cos(ALPHA), -math.sin(ALPHA), 0.0])  # sens de la plus grande pente
NORMALE = np.array([math.sin(ALPHA), math.cos(ALPHA), 0.0])
A_GLISSEMENT = 3.20586  # m/s², SPEC : g·(sin 30° − 0,2·cos 30°)
X_GLISSEMENT = 1.60293  # m, SPEC : x(1 s)


def _bloc(type_liaison: TypeLiaison, axe: np.ndarray, f: float, **options: float) -> Etude:
    bloc = Solide("Bloc", False, 1.0, np.zeros(3), np.eye(3) * 1e-3)
    x = liaison(
        "L",
        type_liaison,
        "Bati",
        "Bloc",
        np.zeros(3),
        axe,
        frottement=f,
        valeur_pose=0.0,
        **options,
    )
    etude = Etude(solides=[bati(), bloc], liaisons=[x])
    etude.pesanteur.vecteur = (0.0, -G, 0.0)
    etude.reglages = reglages(1.0, 1000, 0.001)
    return etude


def test_ex15_glissement() -> None:
    """Bloc de 1 kg, glissière inclinée de 30°, f = 0,2, départ au repos."""
    res = MoteurExudynDyn().simuler(_bloc(TypeLiaison.GLISSIERE, PENTE, 0.2))
    x = res.positions["Bloc"] @ PENTE
    accel = res.accelerations["Bloc"] @ PENTE
    assert accel[len(accel) // 2] == pytest.approx(A_GLISSEMENT, rel=1e-2)
    assert x[-1] == pytest.approx(X_GLISSEMENT, rel=1e-2)


def test_ex15_adherence() -> None:
    """f = 0,7 > tan 30° = 0,577 : déplacement sur 1 s inférieur à 1e-3 m ; fluage signalé."""
    res = MoteurExudynDyn().simuler(_bloc(TypeLiaison.GLISSIERE, PENTE, 0.7))
    x = res.positions["Bloc"] @ PENTE
    assert np.abs(x).max() < 1e-3
    fluage = res.fluage["L"]
    # fluage v = v_ε·atanh(tan 30°/0,7) = 1,17·v_ε avec v_ε = 1e-4 m/s (RESULTATS_1a § 2.3)
    assert fluage.vitesse_max == pytest.approx(1e-4 * math.atanh(math.tan(ALPHA) / 0.7), rel=0.2)
    assert any("fluage" in message.lower() for message in res.avertissements)


def test_ex15_pas_de_frottement_par_defaut() -> None:
    """f = 0 (liaison parfaite) : accélération g·sin 30°, aucun fluage."""
    res = MoteurExudynDyn().simuler(_bloc(TypeLiaison.GLISSIERE, PENTE, 0.0))
    accel = res.accelerations["Bloc"] @ PENTE
    assert accel[len(accel) // 2] == pytest.approx(G * math.sin(ALPHA), rel=1e-6)
    assert res.fluage == {}


def test_ex15_disque_sur_pivot() -> None:
    """Disque d'acier R = 0,1 m, e = 0,02 m, axe horizontal, r = 5 mm, f = 0,1, ω0 = 10 rad/s :
    arrêt à t = ω0·R² / (2·f·r·g) = 10,194 s à 2 % près."""
    rayon, f, r_axe, w0 = 0.1, 0.1, 0.005, 10.0
    disque = cylindre("Disque", rayon, 0.02, np.zeros(3))
    x = liaison(
        "L",
        TypeLiaison.PIVOT,
        "Bati",
        "Disque",
        np.zeros(3),
        np.array([0.0, 0.0, 1.0]),
        frottement=f,
        rayon_axe=r_axe,
        valeur_pose=0.0,
    )
    etude = Etude(solides=[bati(), disque], liaisons=[x])
    etude.pesanteur.vecteur = (0.0, -G, 0.0)
    etude.reglages = reglages(12.0, 2400, 0.005)
    res = MoteurExudynDyn().simuler(
        etude, vitesses_initiales={"Disque": ((0.0, 0.0, 0.0), (0.0, 0.0, w0))}
    )
    w = res.vitesses_angulaires["Disque"][:, 2]
    arret = res.t[np.argmax(np.abs(w) < 0.01)]
    attendu = w0 * rayon**2 / (2 * f * r_axe * G)
    assert attendu == pytest.approx(10.194, abs=1e-3)
    assert arret == pytest.approx(attendu, rel=0.02)


def test_ex15_appui_plan_descente() -> None:
    """Appui plan incliné de 30°, f = 0,2 : même accélération qu'en glissière, pas de dérive
    latérale (le frottement s'oppose à la vitesse de glissement dans le plan)."""
    res = MoteurExudynDyn().simuler(_bloc(TypeLiaison.APPUI_PLAN, NORMALE, 0.2))
    x = res.positions["Bloc"]
    assert x[-1] @ PENTE == pytest.approx(X_GLISSEMENT, rel=1e-2)
    assert abs(x[-1, 2]) < 1e-9
    assert abs(x[-1] @ NORMALE) < 1e-9


def test_ex15_appui_plan_montee_le_frottement_s_oppose_a_la_vitesse() -> None:
    """Bloc lancé à 2 m/s vers le haut de la pente : décélération g·(sin 30° + f·cos 30°)."""
    etude = _bloc(TypeLiaison.APPUI_PLAN, NORMALE, 0.2)
    v0 = tuple(float(c) for c in -2.0 * PENTE)
    res = MoteurExudynDyn().simuler(etude, vitesses_initiales={"Bloc": (v0, (0.0, 0.0, 0.0))})
    a = G * (math.sin(ALPHA) + 0.2 * math.cos(ALPHA))
    t = 0.2
    attendu = -(2.0 * t - 0.5 * a * t**2)  # abscisse selon PENTE (la montée est négative)
    mesure = np.interp(t, res.t, res.positions["Bloc"] @ PENTE)
    assert mesure == pytest.approx(attendu, rel=5e-3)


def test_ex15_frottement_sur_pivot_exige_un_rayon() -> None:
    etude = _bloc(TypeLiaison.PIVOT, np.array([0.0, 0.0, 1.0]), 0.1)
    with pytest.raises(ErreurModele, match="rayon"):
        MoteurExudynDyn().simuler(etude)


def test_ex15_frottement_non_pris_en_charge_pour_une_rotule() -> None:
    etude = _bloc(TypeLiaison.ROTULE, np.array([0.0, 0.0, 1.0]), 0.1)
    with pytest.raises(ErreurModele, match="frottement"):
        MoteurExudynDyn().simuler(etude)
