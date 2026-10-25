# SPDX-License-Identifier: GPL-3.0-or-later
"""Liaisons normalisées (EX-10), propositions (EX-11), base (EX-12), réorientation (EX-13)."""

import math
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
# Tx = p·Rx / 2π est ajouté par moteur/couplages.py (pas `Liaison.pas`). Linéaire rectiligne : le
# moteur la réalise par deux ponctuelles (moteur/exudyn_dyn.py).
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

# EX-12 : liaisons dont l'élève saisit une seconde direction (vecteur monde, projeté ⟂ à z).
# Elle devient x local : doigt de la rotule à doigt, ligne de contact de la linéaire rectiligne.
DIRECTION_REQUISE = frozenset({TypeLiaison.ROTULE_A_DOIGT, TypeLiaison.LINEAIRE_RECTILIGNE})

# Axes monde nommés (EX-13)
AXES_MONDE: dict[str, tuple[float, float, float]] = {
    "x": (1.0, 0.0, 0.0),
    "y": (0.0, 1.0, 0.0),
    "z": (0.0, 0.0, 1.0),
}

# EX-11
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


def proposer(type_sc: str, couplage_screw: bool = False) -> TypeLiaison | None:
    """Proposition par type SolidCraft ; None si aucune (pin_slot : choix imposé).

    `couplage_screw` : la liaison est couplée par `joint.screw` (détection au lot 7) ; un
    cylindrical ainsi couplé est proposé hélicoïdale (EX-11).
    """
    if couplage_screw and type_sc == "cylindrical":
        return TypeLiaison.HELICOIDALE
    return PROPOSITION_SOLIDCRAFT.get(type_sc)


def _vecteur(v: Sequence[float] | np.ndarray) -> np.ndarray:
    return np.array(v, dtype=float)


def _optionnel(valeur: object) -> float | None:
    return None if valeur is None else float(valeur)  # type: ignore[arg-type]


def _booleen(valeur: object) -> bool:
    if not isinstance(valeur, bool):
        raise ValueError(f"Booléen attendu, reçu {valeur!r}.")
    return valeur


@dataclass
class Liaison:
    """Liaison SolidCraft importée et choix de l'élève.

    `axe_sc` : axe z SolidCraft (monde). `axe` : axe retenu (EX-13), égal à `axe_sc` par défaut.
    `valeur_pose` : coordonnée articulaire à l'import (rad ou m), None si sans objet.
    `direction` : seconde direction (vecteur monde) de la rotule à doigt et de la linéaire
    rectiligne. `couplage_screw` : la liaison SolidCraft est couplée par `joint.screw`.

    Données optionnelles du lot 7 (écrites dans le `.meca3d` seulement si renseignées) :
    `frottement` : coefficient de Coulomb f (EX-15, 0 = liaison parfaite) ; `rayon_axe` : rayon r
    de l'axe d'un pivot frottant (m) ; `epsilon` : vitesse de régularisation v_ε (m/s) ou ω_ε
    (rad/s), None = défaut de la SPEC ; `pas` : pas p de l'hélicoïdale (m par tour).
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
    couplage_screw: bool = False
    frottement: float = 0.0
    rayon_axe: float | None = None
    epsilon: float | None = None
    pas: float | None = None
    _initialisee: bool = False

    def __post_init__(self) -> None:
        self.centre = _vecteur(self.centre)
        if self.centre.shape != (3,) or not np.all(np.isfinite(self.centre)):
            raise ValueError(f"Liaison {self.nom} : centre invalide (trois coordonnées finies).")
        self.axe_sc = unites.unitaire(self.axe_sc)
        if self.axe is None:
            self.axe = self.axe_sc.copy()
        else:
            self.axe = unites.unitaire(self.axe)
        if self.direction is not None:
            self.direction = _vecteur(self.direction)
            if self.type in DIRECTION_REQUISE:
                unites.verifier_direction(self.axe, self.direction)
        self._verifier_frottement()
        if self.type is None and not self._initialisee:
            self.type = self.proposition
        self._initialisee = True

    def _verifier_frottement(self) -> None:
        """Valeurs de frottement et de pas : finies, f ≥ 0, les autres strictement positives."""
        if not (math.isfinite(self.frottement) and self.frottement >= 0.0):
            raise ValueError(
                f"Liaison {self.nom} : le coefficient de frottement doit être un nombre fini ≥ 0."
            )
        for valeur, libelle in (
            (self.rayon_axe, "le rayon de l'axe"),
            (self.epsilon, "la vitesse de régularisation"),
            (self.pas, "le pas"),
        ):
            if valeur is not None and not (math.isfinite(valeur) and valeur > 0.0):
                raise ValueError(
                    f"Liaison {self.nom} : {libelle} doit être un nombre fini strictement positif."
                )

    @property
    def proposition(self) -> TypeLiaison | None:
        return proposer(self.type_sc, self.couplage_screw)

    def ddl_bloques(self) -> list[int]:
        if self.type is None:
            raise ValueError(f"Liaison {self.nom} : aucun type de liaison choisi.")
        return list(DDL_BLOQUES[self.type])

    def _exiger_direction(self) -> None:
        if self.type in DIRECTION_REQUISE and self.direction is None:
            raise unites.ErreurDirection(
                f"Liaison {self.nom} : la seconde direction est à saisir pour cette liaison."
            )

    def base(self) -> np.ndarray:
        """Base de liaison (colonnes x, y, z locaux en repère monde, configuration de référence)."""
        if self.type is None:
            raise ValueError(f"Liaison {self.nom} : aucun type de liaison choisi.")
        assert self.axe is not None
        self._exiger_direction()
        return unites.base_liaison(
            self.axe, axe_en_x=self.type in AXE_EN_X, direction=self.direction
        )

    def choisir(self, type_liaison: TypeLiaison) -> None:
        """EX-11 : choix libre parmi les 11 liaisons ; le nouveau choix est à valider."""
        self.type = TypeLiaison(type_liaison)
        self.statut = Statut.PROPOSEE

    def definir_direction(self, vecteur: Sequence[float] | np.ndarray) -> None:
        """EX-12 : seconde direction (monde) ; refusée si l'angle avec l'axe z est < 1°."""
        assert self.axe is not None
        v = _vecteur(vecteur)
        unites.verifier_direction(self.axe, v)
        self.direction = v

    def reorienter_axe(self, vecteur: Sequence[float] | np.ndarray | str) -> None:
        """EX-13 : l'axe devient x, y ou z du repère monde (« x », « y », « z ») ou un vecteur.

        Refusé, sans modification, si la seconde direction saisie deviendrait colinéaire.
        """
        if isinstance(vecteur, str):
            if vecteur not in AXES_MONDE:
                raise ValueError(f"Axe monde inconnu « {vecteur} » : x, y ou z attendu.")
            vecteur = AXES_MONDE[vecteur]
        nouvel_axe = unites.unitaire(vecteur)
        if self.direction is not None and self.type in DIRECTION_REQUISE:
            unites.verifier_direction(nouvel_axe, self.direction)
        self.axe = nouvel_axe

    def deplacer_centre(self, point: Sequence[float] | np.ndarray) -> None:
        """EX-13 : le centre de la liaison devient le point saisi (m, repère monde)."""
        p = _vecteur(point)
        if p.shape != (3,) or not np.all(np.isfinite(p)):
            raise ValueError("Centre invalide : trois coordonnées finies sont attendues.")
        self.centre = p

    def valider(self) -> None:
        if self.type is None:
            raise ValueError(f"Liaison {self.nom} : un choix de type est imposé avant validation.")
        self._exiger_direction()
        self._verifier_frottement()
        self.statut = Statut.VALIDEE

    def vers_dict(self) -> dict[str, Any]:
        d = self._vers_dict_base()
        if self.frottement != 0.0:
            d["frottement"] = self.frottement
        if self.rayon_axe is not None:
            d["rayon_axe"] = self.rayon_axe
        if self.epsilon is not None:
            d["epsilon"] = self.epsilon
        if self.pas is not None:
            d["pas"] = self.pas
        return d

    def _vers_dict_base(self) -> dict[str, Any]:
        assert self.axe is not None
        return {
            "nom": self.nom,
            "type_sc": self.type_sc,
            "couplage_screw": self.couplage_screw,
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
            couplage_screw=_booleen(d["couplage_screw"]),
            solide_a=str(d["solide_a"]),
            solide_b=str(d["solide_b"]),
            centre=_vecteur(d["centre"]),
            axe_sc=_vecteur(d["axe_sc"]),
            valeur_pose=None if valeur is None else float(valeur),
            type=None if d["type"] is None else TypeLiaison(d["type"]),
            axe=_vecteur(d["axe"]),
            direction=None if d["direction"] is None else _vecteur(d["direction"]),
            statut=Statut(d["statut"]),
            frottement=float(d.get("frottement", 0.0)),
            rayon_axe=_optionnel(d.get("rayon_axe")),
            epsilon=_optionnel(d.get("epsilon")),
            pas=_optionnel(d.get("pas")),
            _initialisee=True,
        )
