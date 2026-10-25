# SPDX-License-Identifier: GPL-3.0-or-later
"""Outils de test du lot 4 : mécanismes décrits à la main (bielle-manivelle, pendule double...)."""

import math

import numpy as np
from meca3d.graphe.graphe import DescriptionMecanisme, LiaisonGraphe, SolideGraphe

from meca3d import unites

R = 0.10  # m, manivelle
LONGUEUR = 0.30  # m, bielle
THETA = unites.deg_vers_rad(60.0)

PIVOT = (1, 1, 1, 0, 1, 1)
GLISSIERE = (0, 1, 1, 1, 1, 1)
ROTULE = (1, 1, 1, 0, 0, 0)
LINEAIRE_ANNULAIRE = (0, 1, 1, 0, 0, 0)

X = np.array([1.0, 0.0, 0.0])
Z = np.array([0.0, 0.0, 1.0])


def base_axe_x(axe: np.ndarray) -> np.ndarray:
    """Base orthonormée directe dont la première colonne (x local) est `axe`."""
    x = axe / np.linalg.norm(axe)
    aide = np.array([0.0, 0.0, 1.0]) if abs(x[2]) < 0.9 else np.array([1.0, 0.0, 0.0])
    y = np.cross(aide, x)
    y /= np.linalg.norm(y)
    z = np.cross(x, y)
    return np.column_stack([x, y, z])


def liaison(
    nom: str,
    a: str,
    b: str,
    ddl: tuple[int, ...],
    centre: tuple[float, ...] | np.ndarray,
    axe: np.ndarray = Z,
) -> LiaisonGraphe:
    return LiaisonGraphe(
        nom=nom,
        solide_a=a,
        solide_b=b,
        ddl_bloques=ddl,
        centre=np.asarray(centre, dtype=float),
        base=base_axe_x(np.asarray(axe, dtype=float)),
    )


def points_bielle() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    o = np.zeros(3)
    a = np.array([R * math.cos(THETA), R * math.sin(THETA), 0.0])
    x_b = R * math.cos(THETA) + math.sqrt(LONGUEUR**2 - R**2 * math.sin(THETA) ** 2)
    return o, a, np.array([x_b, 0.0, 0.0])


def bielle(
    ddl_b: tuple[int, ...] = ROTULE, axe_b: np.ndarray = Z, ddl_a: tuple[int, ...] = PIVOT
) -> DescriptionMecanisme:
    """Bielle-manivelle à 60° : pivot en O, `ddl_a` en A (axe z), `ddl_b` en B, glissière x."""
    o, a, b = points_bielle()
    return DescriptionMecanisme(
        solides=(
            SolideGraphe("Bati", "Bâti", True),
            SolideGraphe("Manivelle", "Manivelle", False),
            SolideGraphe("Bielle", "Bielle", False),
            SolideGraphe("Piston", "Piston", False),
        ),
        liaisons=(
            liaison("L01", "Bati", "Manivelle", PIVOT, o),
            liaison("L12", "Manivelle", "Bielle", ddl_a, a),
            liaison("L23", "Bielle", "Piston", ddl_b, b, axe_b),
            liaison("L30", "Bati", "Piston", GLISSIERE, b, X),
        ),
    )


def trois_pivots_glissiere() -> DescriptionMecanisme:
    return bielle(ddl_b=PIVOT, axe_b=Z)


def pendule_double() -> DescriptionMecanisme:
    return DescriptionMecanisme(
        solides=(
            SolideGraphe("Bati", "Bâti", True),
            SolideGraphe("S1", "Bras 1", False),
            SolideGraphe("S2", "Bras 2", False),
        ),
        liaisons=(
            liaison("P1", "Bati", "S1", PIVOT, (0.0, 0.0, 0.0)),
            liaison("P2", "S1", "S2", PIVOT, (0.2, 0.0, 0.0)),
        ),
    )
