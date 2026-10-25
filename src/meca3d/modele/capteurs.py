# SPDX-License-Identifier: GPL-3.0-or-later
"""Définitions de capteurs (EX-50, EX-51). Aucun calcul avant le lot 6.

- Capteur de liaison : torseur statique d'une liaison, dans le sens i→j ou j→i (i = solide_a,
  j = solide_b de la liaison), en base de liaison ou en base monde.
- Capteur de point : position, vitesse et accélération d'un point d'un solide relativement à un
  solide de référence, en base du solide de référence ou en base monde. Le point est donné en
  repère monde dans la configuration de référence (pose d'import), lié au solide.
"""

import math
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, ClassVar


class ErreurCapteur(ValueError):
    """Définition de capteur invalide ; le message est destiné à l'élève."""


class SensTorseur(StrEnum):
    I_VERS_J = "i_vers_j"
    J_VERS_I = "j_vers_i"


class BaseCapteur(StrEnum):
    LIAISON = "liaison"
    MONDE = "monde"
    REFERENCE = "reference"  # base du solide de référence (capteur de point)


def _nom_non_vide(valeur: object, libelle: str) -> None:
    if not isinstance(valeur, str) or not valeur.strip():
        raise ErreurCapteur(f"Capteur : {libelle} vide ou invalide.")


@dataclass(frozen=True)
class CapteurLiaison:
    GENRE: ClassVar[str] = "liaison"
    nom: str
    liaison: str
    sens: SensTorseur = SensTorseur.I_VERS_J
    base: BaseCapteur = BaseCapteur.LIAISON

    def __post_init__(self) -> None:
        _nom_non_vide(self.nom, "nom")
        _nom_non_vide(self.liaison, "liaison")
        if self.base not in (BaseCapteur.LIAISON, BaseCapteur.MONDE):
            raise ErreurCapteur(
                f"Capteur {self.nom} : la base d'un capteur de liaison est la liaison ou le monde."
            )

    def vers_dict(self) -> dict[str, Any]:
        return {
            "genre": self.GENRE,
            "nom": self.nom,
            "liaison": self.liaison,
            "sens": self.sens.value,
            "base": self.base.value,
        }


@dataclass(frozen=True)
class CapteurPoint:
    GENRE: ClassVar[str] = "point"
    nom: str
    solide: str
    point: tuple[float, float, float]
    solide_reference: str
    base: BaseCapteur = BaseCapteur.REFERENCE

    def __post_init__(self) -> None:
        _nom_non_vide(self.nom, "nom")
        _nom_non_vide(self.solide, "solide")
        _nom_non_vide(self.solide_reference, "solide de référence")
        try:
            coordonnees = tuple(float(x) for x in self.point)
        except (TypeError, ValueError) as e:
            raise ErreurCapteur(f"Capteur {self.nom} : point invalide ({e}).") from e
        if len(coordonnees) != 3 or not all(math.isfinite(x) for x in coordonnees):
            raise ErreurCapteur(
                f"Capteur {self.nom} : le point attendu a trois coordonnées finies (m)."
            )
        object.__setattr__(self, "point", coordonnees)
        if self.base not in (BaseCapteur.REFERENCE, BaseCapteur.MONDE):
            raise ErreurCapteur(
                f"Capteur {self.nom} : la base d'un capteur de point est celle du solide "
                "de référence ou le monde."
            )

    def vers_dict(self) -> dict[str, Any]:
        return {
            "genre": self.GENRE,
            "nom": self.nom,
            "solide": self.solide,
            "point": [float(x) for x in self.point],
            "solide_reference": self.solide_reference,
            "base": self.base.value,
        }


type Capteur = CapteurLiaison | CapteurPoint


def capteur_depuis_dict(d: dict[str, Any]) -> Capteur:
    """Reconstruit un capteur ; toute anomalie devient une ErreurCapteur."""
    genre = d.get("genre") if isinstance(d, dict) else None
    if genre not in (CapteurLiaison.GENRE, CapteurPoint.GENRE):
        raise ErreurCapteur(f"Capteur de genre inconnu ou absent : {genre!r}.")
    try:
        if genre == CapteurLiaison.GENRE:
            return CapteurLiaison(
                str(d["nom"]), str(d["liaison"]), SensTorseur(d["sens"]), BaseCapteur(d["base"])
            )
        if genre == CapteurPoint.GENRE:
            return CapteurPoint(
                str(d["nom"]),
                str(d["solide"]),
                tuple(d["point"]),  # type: ignore[arg-type]
                str(d["solide_reference"]),
                BaseCapteur(d["base"]),
            )
    except ErreurCapteur:
        raise
    except (KeyError, TypeError, ValueError) as e:
        raise ErreurCapteur(f"Capteur illisible ({type(e).__name__} : {e}).") from e
    raise AssertionError("genre de capteur non traité")  # pragma: no cover
