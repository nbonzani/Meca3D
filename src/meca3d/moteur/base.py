# SPDX-License-Identifier: GPL-3.0-or-later
"""Interface du moteur de simulation, résultats bruts et erreurs typées (D1)."""

from dataclasses import dataclass, field
from typing import Protocol

import numpy as np

from meca3d.modele.etude import Etude
from meca3d.modele.etude import Reglages as Reglages

__all__ = [
    "ErreurModele",
    "ErreurMoteur",
    "ErreurSolveur",
    "Moteur",
    "Reglages",
    "ResultatsBruts",
]


class ErreurMoteur(Exception):
    """Erreur du moteur ; `args[0]` est un message pédagogique en français."""


class ErreurModele(ErreurMoteur):
    """Le modèle transmis ne peut pas être simulé (liaison non validée, solide inconnu...)."""


class ErreurSolveur(ErreurMoteur):
    """Échec du solveur (Jacobien singulier, non-convergence) ; `t_echec` si connu."""

    def __init__(self, message: str, t_echec: float | None = None) -> None:
        super().__init__(message)
        self.t_echec = t_echec


@dataclass
class ResultatsBruts:
    """Sorties du moteur (tableaux numpy, sérialisables).

    - `t` : (n,) ; `positions[solide]` : (n, 3) CdG en m ; `rotations[solide]` : (n, 3, 3).
      Le solide fixe n'y figure pas (repère monde).
    - `forces[liaison]`, `moments[liaison]` : (n, 3), action du solide b sur le solide a,
      réduite au centre, en base de liaison liée au solide a (convention Exudyn brute).
    """

    t: np.ndarray
    positions: dict[str, np.ndarray] = field(default_factory=dict)
    rotations: dict[str, np.ndarray] = field(default_factory=dict)
    forces: dict[str, np.ndarray] = field(default_factory=dict)
    moments: dict[str, np.ndarray] = field(default_factory=dict)


class Moteur(Protocol):
    def simuler(self, etude: Etude, reglages: Reglages | None = None) -> ResultatsBruts: ...
