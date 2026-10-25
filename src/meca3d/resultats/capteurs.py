# SPDX-License-Identifier: GPL-3.0-or-later
"""Capteurs de point (EX-51) : position, vitesse et accélération d'un point d'un solide relativement
à un solide de référence quelconque, en base du solide de référence ou en base monde.

Conventions. Le repère d'un solide est celui de son composant CAO (`Solide.repere_rotation`,
`Solide.repere_origine`, repère monde à la pose d'import), lié au solide ensuite. Le point du
capteur est donné en repère monde à la pose d'import (`Solide.vers_monde` convertit une saisie en
coordonnées pièce). La position est celle du point par rapport à l'origine du repère de référence ;
la vitesse et l'accélération sont celles
du point DANS le repère du solide de référence (dérivées relatives, termes de Coriolis et
d'entraînement compris), puis exprimées dans la base demandée.
"""

from dataclasses import dataclass

import numpy as np

from meca3d.modele.capteurs import BaseCapteur, CapteurPoint
from meca3d.modele.etude import Etude
from meca3d.moteur.base import ResultatsBruts


@dataclass(frozen=True, eq=False)
class EtatSolide:
    """Cinématique d'un solide dans le repère monde, (n, ...) : x, v, a (CdG), R, ω, α."""

    cdg_import: np.ndarray
    repere_rotation: np.ndarray
    repere_origine: np.ndarray
    x: np.ndarray
    rotation: np.ndarray
    v: np.ndarray
    omega: np.ndarray
    a: np.ndarray
    alpha: np.ndarray

    def point(self, p_import: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Position, vitesse, accélération (n, 3) du point matériel situé en p_import à l'import."""
        s = np.einsum("nij,j->ni", self.rotation, p_import - self.cdg_import)
        position = self.x + s
        vitesse = self.v + np.cross(self.omega, s)
        acceleration = (
            self.a + np.cross(self.alpha, s) + np.cross(self.omega, np.cross(self.omega, s))
        )
        return position, vitesse, acceleration


def etat_solide(etude: Etude, resultats: ResultatsBruts, nom: str) -> EtatSolide:
    """État d'un solide ; le solide fixe est immobile à sa pose d'import. KeyError si inconnu."""
    solide = etude.solide(nom)
    n = len(resultats.t)
    zeros = np.zeros((n, 3))
    if solide.fixe or nom not in resultats.positions:
        return EtatSolide(
            solide.cdg,
            solide.repere_rotation,
            solide.repere_origine,
            np.broadcast_to(solide.cdg, (n, 3)),
            np.broadcast_to(np.eye(3), (n, 3, 3)),
            zeros,
            zeros,
            zeros,
            zeros,
        )

    def lire(champ: dict[str, np.ndarray]) -> np.ndarray:
        return champ.get(nom, zeros)

    return EtatSolide(
        solide.cdg,
        solide.repere_rotation,
        solide.repere_origine,
        resultats.positions[nom],
        resultats.rotations[nom],
        lire(resultats.vitesses),
        lire(resultats.vitesses_angulaires),
        lire(resultats.accelerations),
        lire(resultats.accelerations_angulaires),
    )


@dataclass(frozen=True, eq=False)
class MesurePoint:
    position: np.ndarray  # (n, 3) m
    vitesse: np.ndarray  # (n, 3) m/s
    acceleration: np.ndarray  # (n, 3) m/s²


def mesurer_point(etude: Etude, resultats: ResultatsBruts, capteur: CapteurPoint) -> MesurePoint:
    """EX-51 : mesure du capteur de point, dans la base demandée (référence ou monde)."""
    solide = etat_solide(etude, resultats, capteur.solide)
    reference = etat_solide(etude, resultats, capteur.solide_reference)
    p, v_p, a_p = solide.point(np.array(capteur.point))
    o, v_o, a_o = reference.point(reference.repere_origine)
    w, alpha = reference.omega, reference.alpha
    r = p - o
    v_rel = v_p - v_o - np.cross(w, r)
    a_rel = a_p - a_o - np.cross(alpha, r) - np.cross(w, np.cross(w, r)) - 2.0 * np.cross(w, v_rel)
    if capteur.base is BaseCapteur.REFERENCE:
        rt = np.swapaxes(reference.rotation @ reference.repere_rotation, 1, 2)
        r, v_rel, a_rel = (np.einsum("nij,nj->ni", rt, vec) for vec in (r, v_rel, a_rel))
    return MesurePoint(np.array(r), np.array(v_rel), np.array(a_rel))
