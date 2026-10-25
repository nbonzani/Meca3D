# SPDX-License-Identifier: GPL-3.0-or-later
"""Liaisons normalisées (EX-10), propositions (EX-11), base (EX-12), réorientation (EX-13)."""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

import numpy as np

from meca3d import unites


class TypeLiaison(StrEnum):
    ENCASTREMENT = "encastrement"
    PIVOT = "pivot"
    GLISSIERE = "glissiere"
    PIVOT_GLISSANT = "pivot_glissant"
    ROTULE_A_DOIGT = "rotule_a_doigt"
    ROTULE = "rotule"
    APPUI_PLAN = "appui_plan"
    LINEAIRE_ANNULAIRE = "lineaire_annulaire"
    LINEAIRE_RECTILIGNE = "lineaire_rectiligne"
    PONCTUELLE = "ponctuelle"
    HELICOIDALE = "helicoidale"


# ddl bloqués [Tx Ty Tz Rx Ry Rz] dans la base de liaison (SPEC EX-10). Hélicoïdale : le couplage
# Tx = p·Rx / 2π est ajouté par moteur/couplages.py (lot 7). Linéaire rectiligne : deux
# ponctuelles (lot 3).
DDL_BLOQUES: dict[TypeLiaison, tuple[int, ...]] = {
    TypeLiaison.ENCASTREMENT: (1, 1, 1, 1, 1, 1),
    TypeLiaison.PIVOT: (1, 1, 1, 0, 1, 1),
    TypeLiaison.GLISSIERE: (0, 1, 1, 1, 1, 1),
    TypeLiaison.PIVOT_GLISSANT: (0, 1, 1, 0, 1, 1),
    TypeLiaison.ROTULE_A_DOIGT: (1, 1, 1, 0, 0, 1),
    TypeLiaison.ROTULE: (1, 1, 1, 0, 0, 0),
    TypeLiaison.APPUI_PLAN: (0, 0, 1, 1, 1, 0),
    TypeLiaison.LINEAIRE_ANNULAIRE: (0, 1, 1, 0, 0, 0),
    TypeLiaison.LINEAIRE_RECTILIGNE: (0, 0, 1, 0, 1, 0),
    TypeLiaison.PONCTUELLE: (0, 0, 1, 0, 0, 0),
    TypeLiaison.HELICOIDALE: (0, 1, 1, 0, 1, 1),
}

# Liaisons dont l'axe z SolidCraft devient x local ; les autres : z -> z local (EX-12)
AXE_EN_X = frozenset(
    {
        TypeLiaison.PIVOT,
        TypeLiaison.GLISSIERE,
        TypeLiaison.PIVOT_GLISSANT,
        TypeLiaison.LINEAIRE_ANNULAIRE,
        TypeLiaison.HELICOIDALE,
    }
)

# EX-11 (la proposition hélicoïdale, pour un cylindrical couplé, relève du lot 7)
PROPOSITION_SOLIDCRAFT: dict[str, TypeLiaison] = {
    "revolute": TypeLiaison.PIVOT,
    "slider": TypeLiaison.GLISSIERE,
    "cylindrical": TypeLiaison.PIVOT_GLISSANT,
    "planar": TypeLiaison.APPUI_PLAN,
    "ball": TypeLiaison.ROTULE,
    "rigid": TypeLiaison.ENCASTREMENT,
}


class Statut(StrEnum):
    PROPOSEE = "proposee"
    VALIDEE = "validee"


def proposer(type_sc: str) -> TypeLiaison | None:
    """Proposition par type SolidCraft ; None si aucune (pin_slot : choix imposé)."""
    return PROPOSITION_SOLIDCRAFT.get(type_sc)


def _vecteur(v: Sequence[float] | np.ndarray) -> np.ndarray:
    return np.array(v, dtype=float)


@dataclass
class Liaison:
    """Liaison SolidCraft importée et choix de l'élève.

    `axe_sc` : axe z SolidCraft (monde). `axe` : axe retenu (EX-13), égal à `axe_sc` par défaut.
    `valeur_pose` : coordonnée articulaire à l'import (rad ou m), None si sans objet.
    """

    nom: str
    type_sc: str
    solide_a: str
    solide_b: str
    centre: np.ndarray
    axe_sc: np.ndarray
    valeur_pose: float | None
    type: TypeLiaison | None = None
    axe: np.ndarray | None = None
    direction: np.ndarray | None = None
    statut: Statut = Statut.PROPOSEE
    _initialisee: bool = False

    def __post_init__(self) -> None:
        self.centre = _vecteur(self.centre)
        self.axe_sc = unites.unitaire(self.axe_sc)
        if self.axe is None:
            self.axe = self.axe_sc.copy()
        else:
            self.axe = unites.unitaire(self.axe)
        if self.direction is not None:
            self.direction = _vecteur(self.direction)
        if self.type is None and not self._initialisee:
            self.type = self.proposition
        self._initialisee = True

    @property
    def proposition(self) -> TypeLiaison | None:
        return proposer(self.type_sc)

    def ddl_bloques(self) -> list[int]:
        if self.type is None:
            raise ValueError(f"Liaison {self.nom} : aucun type de liaison choisi.")
        return list(DDL_BLOQUES[self.type])

    def base(self) -> np.ndarray:
        """Base de liaison (colonnes x, y, z locaux en repère monde, configuration de référence)."""
        if self.type is None:
            raise ValueError(f"Liaison {self.nom} : aucun type de liaison choisi.")
        assert self.axe is not None
        return unites.base_liaison(
            self.axe, axe_en_x=self.type in AXE_EN_X, direction=self.direction
        )

    def reorienter_axe(self, vecteur: Sequence[float] | np.ndarray) -> None:
        """EX-13 (minimal) : l'axe devient le vecteur saisi (repère monde)."""
        self.axe = unites.unitaire(vecteur)

    def valider(self) -> None:
        if self.type is None:
            raise ValueError(f"Liaison {self.nom} : un choix de type est imposé avant validation.")
        self.statut = Statut.VALIDEE

    def vers_dict(self) -> dict[str, Any]:
        assert self.axe is not None
        return {
            "nom": self.nom,
            "type_sc": self.type_sc,
            "solide_a": self.solide_a,
            "solide_b": self.solide_b,
            "centre": [float(x) for x in self.centre],
            "axe_sc": [float(x) for x in self.axe_sc],
            "valeur_pose": self.valeur_pose,
            "type": None if self.type is None else self.type.value,
            "axe": [float(x) for x in self.axe],
            "direction": None if self.direction is None else [float(x) for x in self.direction],
            "statut": self.statut.value,
        }

    @classmethod
    def depuis_dict(cls, d: dict[str, Any]) -> "Liaison":
        valeur = d["valeur_pose"]
        return cls(
            nom=str(d["nom"]),
            type_sc=str(d["type_sc"]),
            solide_a=str(d["solide_a"]),
            solide_b=str(d["solide_b"]),
            centre=_vecteur(d["centre"]),
            axe_sc=_vecteur(d["axe_sc"]),
            valeur_pose=None if valeur is None else float(valeur),
            type=None if d["type"] is None else TypeLiaison(d["type"]),
            axe=_vecteur(d["axe"]),
            direction=None if d["direction"] is None else _vecteur(d["direction"]),
            statut=Statut(d["statut"]),
            _initialisee=True,
        )
