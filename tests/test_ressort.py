# SPDX-License-Identifier: GPL-3.0-or-later
"""Ressorts-amortisseurs (EX-33) : valeurs de la SPEC et solutions analytiques indépendantes."""

import math

import numpy as np
import pytest

from meca3d.modele.actions import ErreurAction, Pesanteur, RessortAmortisseur
from meca3d.modele.etude import Etude, Reglages
from meca3d.modele.liaison import Liaison
from meca3d.modele.solide import Solide
from meca3d.moteur.base import ErreurModele
from meca3d.moteur.exudyn_dyn import MoteurExudynDyn

MASSE = 1.0  # kg (SPEC EX-33)
RAIDEUR = 1000.0  # N/m
PERIODE_SPEC = 0.19869  # s = 2π√(m/k)
G = 9.81


def _solide(nom: str, fixe: bool, masse: float, cdg: tuple[float, float, float]) -> Solide:
    return Solide(nom, fixe, masse, np.array(cdg), np.eye(3) * 1e-3)


def _glissiere(nom: str, a: str, b: str, centre: tuple[float, float, float]) -> Liaison:
    liaison = Liaison(nom, "slider", a, b, np.array(centre), np.array([0.0, 0.0, 1.0]), 0.0)
    liaison.valider()
    return liaison


def etude_masse_ressort(
    z0: float, point_bati_z: float, l0: float, c: float, gravite: bool = False
) -> Etude:
    """Masse de 1 kg sur glissière verticale, ressort entre le bâti (0, 0, point_bati_z) et le
    centre de gravité de la masse (0, 0, z0)."""
    etude = Etude(
        solides=[_solide("Bati", True, 1.0, (0, 0, 0)), _solide("Masse", False, MASSE, (0, 0, z0))],
        liaisons=[_glissiere("L01", "Bati", "Masse", (0.0, 0.0, z0))],
    )
    etude.ressorts = [
        RessortAmortisseur(
            "R1", "Bati", (0.0, 0.0, point_bati_z), "Masse", (0.0, 0.0, z0), RAIDEUR, l0, c
        )
    ]
    etude.pesanteur = Pesanteur(actif=gravite)
    etude.reglages = Reglages(duree=1.0, nb_pas=2000, periode_ecriture=5e-4)
    return etude


def _passages_montants(t: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Instants des passages par zéro croissants, par interpolation linéaire."""
    i = np.nonzero((y[:-1] < 0.0) & (y[1:] >= 0.0))[0]
    return t[i] - y[i] * (t[i + 1] - t[i]) / (y[i + 1] - y[i])


def test_ex33_periode_masse_ressort() -> None:
    # longueur libre 0,9 m : équilibre en z = 0,9 m, lâcher à 1,0 m, sans pesanteur ni amortissement
    res = MoteurExudynDyn().simuler(etude_masse_ressort(1.0, 0.0, 0.9, 0.0))
    y = res.positions["Masse"][:, 2] - 0.9
    passages = _passages_montants(res.t, y)
    assert len(passages) >= 4
    periode = float(np.mean(np.diff(passages)))
    assert periode == pytest.approx(PERIODE_SPEC, rel=1e-3)
    assert periode == pytest.approx(2 * math.pi * math.sqrt(MASSE / RAIDEUR), rel=1e-3)


def test_ex33_amortissement_decroissance() -> None:
    c = 5.0
    res = MoteurExudynDyn().simuler(etude_masse_ressort(1.0, 0.0, 0.9, c))
    y = res.positions["Masse"][:, 2] - 0.9
    sommets = [y[i] for i in range(1, len(y) - 1) if y[i - 1] < y[i] >= y[i + 1] and y[i] > 0]
    assert len(sommets) >= 4
    assert all(b < a for a, b in zip(sommets, sommets[1:], strict=False))
    # décrément logarithmique analytique : exp(−ζ ω T_d) = exp(−2π ζ / √(1 − ζ²))
    zeta = c / (2 * math.sqrt(RAIDEUR * MASSE))
    rapport = math.exp(-2 * math.pi * zeta / math.sqrt(1 - zeta**2))
    for a, b in zip(sommets, sommets[1:], strict=False):
        assert b / a == pytest.approx(rapport, rel=0.03)


def test_ex33_equilibre_statique_signe_de_l_effort() -> None:
    # ressort au-dessus de la masse (point fixe en z = 2 m), longueur libre 1 m, pesanteur :
    # équilibre quand k (l − l0) = m g, soit l = l0 + m g / k
    z_eq = 2.0 - (1.0 + MASSE * G / RAIDEUR)
    etude = etude_masse_ressort(z_eq, 2.0, 1.0, 0.0, gravite=True)
    etude.pesanteur = Pesanteur(vecteur=(0.0, 0.0, -G), actif=True)
    etude.reglages = Reglages(duree=0.5, nb_pas=500, periode_ecriture=1e-3)
    res = MoteurExudynDyn().simuler(etude)
    assert np.abs(res.positions["Masse"][:, 2] - z_eq).max() < 1e-6


def test_ex33_deux_solides_mobiles() -> None:
    # deux masses (1 kg et 3 kg) sur deux glissières verticales, reliées par un ressort :
    # la coordonnée relative oscille à la période 2π√(μ/k), μ = m1 m2 / (m1 + m2)
    m1, m2 = 1.0, 3.0
    etude = Etude(
        solides=[
            _solide("Bati", True, 1.0, (0, 0, 0)),
            _solide("M1", False, m1, (0, 0, 0.0)),
            _solide("M2", False, m2, (0, 0, 1.0)),
        ],
        liaisons=[
            _glissiere("L1", "Bati", "M1", (0.0, 0.0, 0.0)),
            _glissiere("L2", "Bati", "M2", (0.0, 0.0, 1.0)),
        ],
    )
    etude.ressorts = [
        RessortAmortisseur("R", "M1", (0, 0, 0.0), "M2", (0, 0, 1.0), RAIDEUR, 0.9, 0.0)
    ]
    etude.pesanteur = Pesanteur(actif=False)
    etude.reglages = Reglages(duree=1.0, nb_pas=2000, periode_ecriture=5e-4)
    res = MoteurExudynDyn().simuler(etude)
    d = res.positions["M2"][:, 2] - res.positions["M1"][:, 2] - 0.9
    periode = float(np.mean(np.diff(_passages_montants(res.t, d))))
    assert periode == pytest.approx(
        2 * math.pi * math.sqrt(m1 * m2 / (m1 + m2) / RAIDEUR), rel=1e-3
    )
    # quantité de mouvement conservée (aucune force extérieure verticale hors glissières libres)
    assert np.abs(m1 * res.positions["M1"][:, 2] + m2 * res.positions["M2"][:, 2] - m2).max() < 1e-6


@pytest.mark.parametrize(
    "parametres",
    [
        {"raideur": -1.0},
        {"raideur": float("nan")},
        {"longueur_libre": -0.1},
        {"amortissement": -1.0},
    ],
    ids=["k_negative", "k_nan", "l0_negative", "c_negatif"],
)
def test_ex33_parametres_invalides(parametres: dict[str, float]) -> None:
    base = {"raideur": 1.0, "longueur_libre": 0.1, "amortissement": 0.0}
    base.update(parametres)
    with pytest.raises(ErreurAction):
        RessortAmortisseur("R", "A", (0, 0, 0), "B", (0, 0, 1), **base)


def test_ex33_meme_solide_refuse() -> None:
    with pytest.raises(ErreurAction, match="deux solides"):
        RessortAmortisseur("R", "A", (0, 0, 0), "A", (0, 0, 1), 1.0, 0.1)


def test_ex33_solide_inconnu_refuse_par_le_moteur() -> None:
    etude = etude_masse_ressort(1.0, 0.0, 0.9, 0.0)
    etude.ressorts = [RessortAmortisseur("R", "Bati", (0, 0, 0), "Fantome", (0, 0, 1), 1.0, 0.1)]
    with pytest.raises(ErreurModele, match="Fantome"):
        MoteurExudynDyn().simuler(etude)
