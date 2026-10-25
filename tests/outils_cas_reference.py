# SPDX-License-Identifier: GPL-3.0-or-later
"""Outils de test du lot 11 : cas de référence construits dans SolidCraft (EX-14, EX-16, EX-21,
EX-31, EX-44).

Les études viennent des réponses RÉELLES du canal de contrôle enregistrées sous
`tests/fixtures/<cas>/solidcraft/` (`etude_depuis_reponses`) ou, pour les tests `solidcraft`, de
l'import en direct. Toutes les références (périodes, énergie, intégration de Lagrange) sont
calculées ici, indépendamment du code testé.
"""

import json
import math
from pathlib import Path
from typing import Any

import numpy as np
from outils_couplages import couple

from meca3d.cao.solidcraft import etude_depuis_reponses
from meca3d.modele.etude import Etude, Reglages
from meca3d.moteur.base import ResultatsBruts

FIXTURES = Path(__file__).parent / "fixtures"
MAQUETTES = FIXTURES / "maquettes"

G = 9.81
RHO_ACIER = 7800.0  # SPEC : barre d'acier
LONGUEUR = 0.4  # barre 400 × 20 × 20 mm
COTE = 0.02
MASSE_BARRE = RHO_ACIER * LONGUEUR * COTE * COTE  # 1,248 kg
I_CDG_BARRE = MASSE_BARRE * (LONGUEUR**2 + COTE**2) / 12.0  # axe horizontal, perpendiculaire


def etude_enregistree(cas: str, etiquette: str) -> Etude:
    """Étude lue depuis les réponses enregistrées du canal (liaisons proposées, non validées)."""
    dossier = FIXTURES / cas / "solidcraft"

    def lire(nom: str) -> Any:
        return json.loads((dossier / f"{nom}_{etiquette}.json").read_text(encoding="utf-8"))

    urdf = (dossier / f"export_{etiquette}" / f"{cas}.urdf").read_text(encoding="utf-8")
    return etude_depuis_reponses(
        lire("joint_list"),
        lire("component_list"),
        lire("component_properties"),
        urdf,
        lire("document_inspect")["revision"],
    )


def valider_tout(etude: Etude) -> Etude:
    for liaison in etude.liaisons:
        liaison.valider()
    return etude


def preparer(etude: Etude, duree: float, nb_pas: int, periode: float | None = None) -> Etude:
    valider_tout(etude)
    etude.reglages = Reglages(
        duree=duree, nb_pas=nb_pas, periode_ecriture=periode or duree / nb_pas
    )
    return etude


# ------------------------------------------------------------------------- pendule simple
def inertie_pivot_barre() -> float:
    """Théorème de Huygens : I_O = I_G + m·(L/2)²."""
    return I_CDG_BARRE + MASSE_BARRE * (LONGUEUR / 2.0) ** 2


def periode_petites_oscillations() -> float:
    return 2.0 * math.pi * math.sqrt(inertie_pivot_barre() / (MASSE_BARRE * G * LONGUEUR / 2.0))


def periode_amplitude(amplitude: float) -> float:
    """T(θ₀) = T₀ · (2/π)·K(sin(θ₀/2)), K calculée par la moyenne arithmético-géométrique."""
    a, b = 1.0, math.sqrt(1.0 - math.sin(amplitude / 2.0) ** 2)
    for _ in range(40):
        a, b = (a + b) / 2.0, math.sqrt(a * b)
    return periode_petites_oscillations() / a


def omega_point_bas(amplitude: float) -> float:
    """Conservation de l'énergie entre le lâcher à θ₀ et le point bas."""
    return math.sqrt(
        2.0
        * MASSE_BARRE
        * G
        * (LONGUEUR / 2.0)
        * (1.0 - math.cos(amplitude))
        / inertie_pivot_barre()
    )


def periode_mesuree(t: np.ndarray, x: np.ndarray) -> float:
    """Période : écart moyen entre deux passages montants (ou descendants) par la verticale,
    passages interpolés linéairement (le signal est quasi linéaire au passage par zéro)."""
    indices = np.flatnonzero(x[:-1] * x[1:] < 0.0)
    passages = np.array([t[i] - x[i] * (t[i + 1] - t[i]) / (x[i + 1] - x[i]) for i in indices])
    assert len(passages) >= 5, "moins de deux périodes simulées"
    return float(np.mean(passages[2:] - passages[:-2]))


def x_relatif_au_pivot(etude: Etude, res: ResultatsBruts, solide: str, liaison: str) -> np.ndarray:
    return res.positions[solide][:, 0] - etude.liaison(liaison).centre[0]


# ------------------------------------------------------------------------- pendule double
def angles_depuis_etude(etude: Etude) -> tuple[float, float]:
    """Angles absolus (depuis la verticale descendante, positifs vers +x) des deux barres,
    déduits des CdG importés et des centres des pivots."""
    angles = []
    for barre, pivot in (("Barre1", "L01_pivot"), ("Barre2", "L12_pivot")):
        c = etude.solide(barre).cdg - etude.liaison(pivot).centre
        angles.append(math.atan2(c[0], -c[2]))
    return angles[0], angles[1]


def energie_double(res: ResultatsBruts) -> np.ndarray:
    """E = Σ ½·m·v² + ½·I_y·ω_y² + m·g·z des deux barres (mouvement dans le plan xz)."""
    e = 0.0
    for barre in ("Barre1", "Barre2"):
        v = res.vitesses[barre]
        w = res.vitesses_angulaires[barre][:, 1]
        e = (
            e
            + 0.5 * MASSE_BARRE * np.sum(v**2, axis=1)
            + 0.5 * I_CDG_BARRE * w**2
            + MASSE_BARRE * G * res.positions[barre][:, 2]
        )
    return np.asarray(e)


def _derivees_lagrange(y: np.ndarray) -> np.ndarray:
    """Équations de Lagrange de deux barres identiques en série (angles absolus φ₁, φ₂)."""
    p1, p2, w1, w2 = y
    m, el = MASSE_BARRE, LONGUEUR
    d = p1 - p2
    m11 = I_CDG_BARRE + m * el**2 / 4.0 + m * el**2
    m12 = 0.5 * m * el**2 * math.cos(d)
    m22 = I_CDG_BARRE + m * el**2 / 4.0
    f1 = -0.5 * m * el**2 * math.sin(d) * w2**2 - 1.5 * m * G * el * math.sin(p1)
    f2 = 0.5 * m * el**2 * math.sin(d) * w1**2 - 0.5 * m * G * el * math.sin(p2)
    det = m11 * m22 - m12 * m12
    a1 = (f1 * m22 - m12 * f2) / det
    a2 = (m11 * f2 - m12 * f1) / det
    return np.array([w1, w2, a1, a2])


def lagrange_rk4(phi1: float, phi2: float, duree: float, pas: float = 1e-4) -> tuple[float, float]:
    """Angles (φ₁, φ₂) à `duree`, lâchés au repos, par Runge-Kutta d'ordre 4."""
    y = np.array([phi1, phi2, 0.0, 0.0])
    for _ in range(round(duree / pas)):
        k1 = _derivees_lagrange(y)
        k2 = _derivees_lagrange(y + 0.5 * pas * k1)
        k3 = _derivees_lagrange(y + 0.5 * pas * k2)
        k4 = _derivees_lagrange(y + pas * k3)
        y = y + pas / 6.0 * (k1 + 2.0 * k2 + 2.0 * k3 + k4)
    return float(y[0]), float(y[1])


def angle_barre2_au_pas(etude: Etude, res: ResultatsBruts, indice: int) -> float:
    """Angle absolu de la barre 2 à l'instant `indice`, depuis les positions des CdG."""
    p1 = etude.liaison("L01_pivot").centre
    cdg1 = res.positions["Barre1"][indice]
    pivot2 = p1 + 2.0 * (cdg1 - p1)
    c = res.positions["Barre2"][indice] - pivot2
    return math.atan2(c[0], -c[2])


# ------------------------------------------------------------------------- réducteur, vis-écrou
def couple_entree_sortie(etude: Etude, ce: float, cs: float) -> None:
    etude.actions = [couple("Ce", "Roue1", ce), couple("Cs", "Roue2", cs)]
