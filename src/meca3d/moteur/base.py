# SPDX-License-Identifier: GPL-3.0-or-later
"""Interface du moteur de simulation, résultats bruts et erreurs typées (D1)."""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol

import numpy as np

from meca3d.modele.etude import Etude
from meca3d.modele.etude import Reglages as Reglages

__all__ = [
    "CalculAnnule",
    "ErreurGardeFou",
    "ErreurLiaisonNonPriseEnCharge",
    "ErreurModele",
    "ErreurMoteur",
    "ErreurSolveur",
    "Fluage",
    "Moteur",
    "Reglages",
    "ResultatsBruts",
]


class ErreurMoteur(Exception):
    """Erreur du moteur ; `args[0]` est un message pédagogique en français."""


class ErreurModele(ErreurMoteur):
    """Le modèle transmis ne peut pas être simulé (liaison non validée, solide inconnu...)."""


class ErreurLiaisonNonPriseEnCharge(ErreurModele):
    """Liaison ou couplage dont la traduction n'existe pas dans le moteur (ex. : train
    épicycloïdal hors des cas traités)."""


class CalculAnnule(ErreurMoteur):
    """Calcul arrêté proprement à la demande de l'appelant (drapeau d'arrêt, R5, EX-42) ; aucun
    résultat partiel n'est renvoyé."""


class ErreurGardeFou(ErreurMoteur):
    """Simulation refusée par le garde-fou EX-22 (hyperstatisme, nombre de lois) avant tout appel
    au moteur ; le message nomme h, les liaisons des cycles concernés et la correction."""


class ErreurSolveur(ErreurMoteur):
    """Échec du solveur (Jacobien singulier, non-convergence) ; `t_echec` si connu."""

    def __init__(self, message: str, t_echec: float | None = None) -> None:
        super().__init__(message)
        self.t_echec = t_echec


@dataclass(frozen=True)
class Fluage:
    """Fluage de la loi de Coulomb régularisée (EX-15) pour une liaison frottante.

    Dans la zone d'adhérence apparente (|v| ≤ 3·ε, où l'effort tangent est inférieur à 99,5 % de
    f·|N|), le solide glisse à la vitesse v = ε·atanh(F_t / (f·|N|)) au lieu de rester immobile.
    `vitesse_max` (m/s ou rad/s) et `deplacement` (m ou rad, ∫|v|dt) sont relevés dans cette
    zone ; `duree` (s) est le temps passé dedans ; `epsilon` est le ε utilisé.
    """

    vitesse_max: float
    deplacement: float
    duree: float
    epsilon: float


@dataclass
class ResultatsBruts:
    """Sorties du moteur (tableaux numpy, sérialisables).

    - `t` : (n,) ; `positions[solide]` : (n, 3) CdG en m ; `rotations[solide]` : (n, 3, 3).
      Le solide fixe n'y figure pas (repère monde).
    - `forces[liaison]`, `moments[liaison]` : (n, 3), action du solide b sur le solide a,
      réduite au centre, en base de liaison liée au solide a (convention Exudyn brute). Vides en
      mode cinématique : aucun effort n'est présenté (EX-41).
    - `vitesses`, `vitesses_angulaires`, `accelerations`, `accelerations_angulaires` : (n, 3) par
      solide mobile, repère monde, du centre de gravité (vitesse et accélération) et du solide.
      Dynamique : capteurs d'Exudyn (erreur en O(h) pour les accélérations). Cinématique :
      dérivation exacte des liaisons à partir des poses (voir `moteur/cinematique.py`).
    - `efforts_couplages[nom]` : (n, 2) effort exercé par le couplage `nom` (ou par l'hélicoïdale
      du même nom que sa liaison) sur la coordonnée relative de la liaison 1 (entrée) et de la
      liaison 2 (sortie) : couple en N·m pour une rotation, force en N pour une translation, selon
      l'axe de la liaison ; pertes du rendement (EX-16) comprises. Vides en mode cinématique.
    - `fluage[liaison]` : fluage des liaisons frottantes (EX-15).
    - `ddl_liberes` : (liaison, indice du ddl dans [Tx Ty Tz Rx Ry Rz]) libérés par l'option
      « Hyperstatique autorisé » (EX-23). `avertissements` : messages à montrer à l'élève.
    """

    t: np.ndarray
    positions: dict[str, np.ndarray] = field(default_factory=dict)
    rotations: dict[str, np.ndarray] = field(default_factory=dict)
    forces: dict[str, np.ndarray] = field(default_factory=dict)
    moments: dict[str, np.ndarray] = field(default_factory=dict)
    vitesses: dict[str, np.ndarray] = field(default_factory=dict)
    vitesses_angulaires: dict[str, np.ndarray] = field(default_factory=dict)
    accelerations: dict[str, np.ndarray] = field(default_factory=dict)
    accelerations_angulaires: dict[str, np.ndarray] = field(default_factory=dict)
    efforts_couplages: dict[str, np.ndarray] = field(default_factory=dict)
    fluage: dict[str, Fluage] = field(default_factory=dict)
    ddl_liberes: list[tuple[str, int]] = field(default_factory=list)
    avertissements: list[str] = field(default_factory=list)


class Moteur(Protocol):
    """`progression(fraction)` et `arret()` sont facultatifs (R5) ; `arret() == True` interrompt
    le calcul par `CalculAnnule`."""

    def simuler(
        self,
        etude: Etude,
        reglages: Reglages | None = None,
        *,
        progression: Callable[[float], None] | None = None,
        arret: Callable[[], bool] | None = None,
    ) -> ResultatsBruts: ...
