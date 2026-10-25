# SPDX-License-Identifier: GPL-3.0-or-later
"""Conversions d'unités et conventions de repères (D8). Seul endroit où l'on convertit.

SolidCraft : mm, g, deg dans l'API ; transformations 4×4 stockées par colonnes. Interne : SI.
"""

import math
from collections.abc import Sequence

import numpy as np

MM_PAR_M = 1000.0
G_PAR_KG = 1000.0
ANGLE_COLINEAIRE_MIN_DEG = 1.0  # EX-12 : en dessous, la seconde direction est refusée


class ErreurDirection(ValueError):
    """Seconde direction de liaison colinéaire à l'axe z (EX-12)."""


def mm_vers_m[T: (float, np.ndarray)](x: T) -> T:
    return x / MM_PAR_M


def m_vers_mm[T: (float, np.ndarray)](x: T) -> T:
    return x * MM_PAR_M


def g_vers_kg[T: (float, np.ndarray)](x: T) -> T:
    return x / G_PAR_KG


def kg_vers_g[T: (float, np.ndarray)](x: T) -> T:
    return x * G_PAR_KG


def deg_vers_rad[T: (float, np.ndarray)](x: T) -> T:
    return x * (math.pi / 180.0)


def rad_vers_deg[T: (float, np.ndarray)](x: T) -> T:
    return x * (180.0 / math.pi)


def rotation_translation(
    transform_colonnes: Sequence[Sequence[float]],
) -> tuple[np.ndarray, np.ndarray]:
    """Transformation SolidCraft (stockée par colonnes, translation en mm) -> (R, t en m)."""
    m = np.array(transform_colonnes, dtype=float).T
    return m[:3, :3].copy(), mm_vers_m(m[:3, 3].copy())


def unitaire(v: Sequence[float] | np.ndarray) -> np.ndarray:
    v = np.asarray(v, dtype=float)
    if v.shape != (3,) or not np.all(np.isfinite(v)):
        raise ValueError("Vecteur invalide : trois composantes finies sont attendues.")
    n = float(np.linalg.norm(v))
    if n == 0.0:
        raise ValueError("Vecteur nul : une direction est attendue.")
    return v / n


def verifier_direction(
    axe_z: Sequence[float] | np.ndarray, direction: Sequence[float] | np.ndarray
) -> None:
    """EX-12 : refuse une seconde direction colinéaire à z (angle < 1°, dans les deux sens)."""
    z, d = unitaire(axe_z), unitaire(direction)
    sinus = float(np.linalg.norm(np.cross(z, d)))
    if math.degrees(math.asin(min(1.0, sinus))) < ANGLE_COLINEAIRE_MIN_DEG:
        raise ErreurDirection(
            "La seconde direction est colinéaire à l'axe de la liaison "
            f"(angle inférieur à {ANGLE_COLINEAIRE_MIN_DEG:g}°) : choisir une autre direction."
        )


def base_liaison(
    axe_z: Sequence[float] | np.ndarray,
    axe_en_x: bool,
    direction: Sequence[float] | np.ndarray | None = None,
) -> np.ndarray:
    """Base de liaison (colonnes = x, y, z locaux exprimés en repère monde), orthonormée directe.

    L'axe z de SolidCraft devient x local (axe_en_x) ou reste z local (normale). Sans seconde
    direction, la base est complétée arbitrairement (symétrie de révolution) ; avec une
    direction, elle est projetée orthogonalement à z et devient y local (axe_en_x) ou x local.
    """
    z = unitaire(axe_z)
    if direction is None:
        aux = np.array([1.0, 0.0, 0.0]) if abs(z[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
        u = unitaire(np.cross(z, aux))
    else:
        verifier_direction(z, direction)
        d = unitaire(direction)
        u = unitaire(d - float(np.dot(d, z)) * z)
    v = np.cross(z, u)
    if axe_en_x:
        return np.column_stack([z, u, v])
    return np.column_stack([u, v, z])
