# SPDX-License-Identifier: GPL-3.0-or-later
"""Outils de test du lot 6 : bielle-manivelle à 60° en cinématique, solutions analytiques.

Les références analytiques sont calculées par dérivation symbolique (sympy), indépendamment du
code testé : x_B(θ) = r cos θ + √(L² − r² sin² θ) avec θ = θ₀ + ω t (SPEC EX-41).
"""

import math
from collections.abc import Callable

import numpy as np
import sympy
from outils_bielle import etude_proposee

from meca3d.modele.actions import LoiEntree, Pesanteur, Pilote
from meca3d.modele.etude import Etude, Reglages
from meca3d.modele.liaison import TypeLiaison

R_MANIVELLE = 0.10  # m (SPEC EX-40)
L_BIELLE = 0.30  # m
THETA0 = math.radians(60.0)
OMEGA = 20.0  # rad/s (SPEC EX-41)

_T = sympy.Symbol("t", real=True)


def etude_bielle_60(
    liaison_b: str = "annulaire_z", pilote: bool = True, duree: float = 0.25
) -> Etude:
    """Bielle-manivelle importée à θ = 60° (réponses enregistrées), prête à simuler.

    `liaison_b` : « annulaire_z » (isostatique), « rotule » (h = 1, proposition de l'import) ou
    « pivot » (trois pivots et une glissière, h = 3). Pilote L01 : θ = 60° + 20·t. Pesanteur
    désactivée. 501 points de sortie (période 0,5 ms).
    """
    etude = etude_proposee("60")
    etude.maquette = "bielle_manivelle.solidcraft"
    liaison = etude.liaison("L23_rotule")
    if liaison_b == "annulaire_z":
        liaison.type = TypeLiaison.LINEAIRE_ANNULAIRE
        liaison.reorienter_axe((0.0, 0.0, 1.0))
    elif liaison_b == "pivot":
        liaison.type = TypeLiaison.PIVOT
    elif liaison_b != "rotule":
        raise ValueError(liaison_b)
    for x in etude.liaisons:
        x.valider()
    if pilote:
        etude.pilotes = [Pilote("L01_pivot", LoiEntree(f"{THETA0!r} + {OMEGA!r}*t"))]
    etude.pesanteur = Pesanteur(actif=False)
    etude.reglages = Reglages(duree=duree, nb_pas=round(duree / 2.5e-4), periode_ecriture=5e-4)
    return etude


def _fonctions(expressions: list[sympy.Expr]) -> Callable[[np.ndarray], np.ndarray]:
    f = sympy.lambdify(_T, expressions, modules="numpy")

    def evaluer(t: np.ndarray) -> np.ndarray:
        valeurs = f(t)
        return np.array([np.broadcast_to(v, t.shape) for v in valeurs], dtype=float).T

    return evaluer


def _abscisse_piston() -> sympy.Expr:
    theta = THETA0 + OMEGA * _T
    r, lg = R_MANIVELLE, L_BIELLE
    return r * sympy.cos(theta) + sympy.sqrt(lg**2 - (r * sympy.sin(theta)) ** 2)


def courbes_piston(t: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(x_B, ẋ_B, ẍ_B) du piston dans le repère monde, exactes (dérivation symbolique)."""
    x = _abscisse_piston()
    evaluer = _fonctions([x, sympy.diff(x, _T), sympy.diff(x, _T, 2)])
    v = evaluer(t)
    return v[:, 0], v[:, 1], v[:, 2]


def courbes_piston_dans_manivelle(t: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Position, vitesse et accélération (n, 3) du point B du piston par rapport à la manivelle,
    exprimées dans la base de la manivelle (repère tournant d'angle θ autour de z, origine en O).
    """
    theta = THETA0 + OMEGA * _T
    x = _abscisse_piston()
    p = [sympy.cos(theta) * x, -sympy.sin(theta) * x, sympy.Integer(0)]
    evaluer = _fonctions([*p, *[sympy.diff(c, _T) for c in p], *[sympy.diff(c, _T, 2) for c in p]])
    v = evaluer(t)
    return v[:, 0:3], v[:, 3:6], v[:, 6:9]
