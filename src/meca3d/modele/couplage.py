# SPDX-License-Identifier: GPL-3.0-or-later
"""Données de couplage (EX-14) et rendement (EX-16). Aucune traduction moteur avant le lot 7.

Chaque couplage relie deux liaisons par leur nom :
- engrenage : ω₂ = −k·ω₁ (extérieur) ou +k·ω₁ (intérieur), k = Z₁/Z₂ ;
- pignon-crémaillère : v = r·ω (liaison_1 : pivot du pignon, liaison_2 : glissière) ;
- vis-écrou : v = p·ω / 2π (liaison_1 : rotation de la vis, liaison_2 : translation de l'écrou).
Le rendement η ∈ ]0 ; 1] vaut 1 par défaut.
"""

import math
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, ClassVar


class ErreurCouplage(ValueError):
    """Données de couplage invalides ; le message est destiné à l'élève."""


class SensEngrenage(StrEnum):
    EXTERIEUR = "exterieur"
    INTERIEUR = "interieur"


def _positif_fini(valeur: float, nom: str) -> float:
    if isinstance(valeur, bool) or not isinstance(valeur, int | float):
        raise ErreurCouplage(f"{nom} : un nombre est attendu.")
    if not (math.isfinite(valeur) and valeur > 0.0):
        raise ErreurCouplage(f"{nom} doit être un nombre fini strictement positif.")
    return float(valeur)


def _verifier_commun(nom: str, liaison_1: str, liaison_2: str, rendement: float) -> None:
    if not isinstance(nom, str) or not nom.strip():
        raise ErreurCouplage("Le nom du couplage ne peut pas être vide.")
    if not liaison_1 or not liaison_2:
        raise ErreurCouplage(f"Couplage {nom} : une liaison couplée n'est pas nommée.")
    if liaison_1 == liaison_2:
        raise ErreurCouplage(
            f"Couplage {nom} : les deux liaisons couplées doivent être distinctes."
        )
    if isinstance(rendement, bool) or not isinstance(rendement, int | float):
        raise ErreurCouplage(f"Couplage {nom} : le rendement doit être un nombre.")
    if not (0.0 < rendement <= 1.0):
        raise ErreurCouplage(f"Couplage {nom} : le rendement doit appartenir à ]0 ; 1].")


@dataclass(frozen=True)
class Engrenage:
    """ω₂ = signe·k·ω₁, avec signe = −1 (extérieur) ou +1 (intérieur)."""

    GENRE: ClassVar[str] = "engrenage"
    nom: str
    liaison_1: str
    liaison_2: str
    k: float
    sens: SensEngrenage = SensEngrenage.EXTERIEUR
    rendement: float = 1.0

    def __post_init__(self) -> None:
        _verifier_commun(self.nom, self.liaison_1, self.liaison_2, self.rendement)
        _positif_fini(self.k, f"Couplage {self.nom} : le rapport k")

    @classmethod
    def depuis_dents(
        cls,
        nom: str,
        liaison_1: str,
        liaison_2: str,
        z1: int,
        z2: int,
        sens: SensEngrenage = SensEngrenage.EXTERIEUR,
        rendement: float = 1.0,
    ) -> "Engrenage":
        """k = Z₁/Z₂ (ω₂ = −k·ω₁ : Z₁ = 20, Z₂ = 60 donne k = 1/3)."""
        for z in (z1, z2):
            if isinstance(z, bool) or not isinstance(z, int) or z <= 0:
                raise ErreurCouplage(
                    f"Couplage {nom} : les nombres de dents sont des entiers strictement positifs."
                )
        return cls(nom, liaison_1, liaison_2, z1 / z2, sens, rendement)

    @property
    def signe(self) -> float:
        return -1.0 if self.sens is SensEngrenage.EXTERIEUR else 1.0

    def vers_dict(self) -> dict[str, Any]:
        return {
            "genre": self.GENRE,
            "nom": self.nom,
            "liaison_1": self.liaison_1,
            "liaison_2": self.liaison_2,
            "k": self.k,
            "sens": self.sens.value,
            "rendement": self.rendement,
        }


@dataclass(frozen=True)
class PignonCremaillere:
    """v = r·ω ; r : rayon primitif du pignon (m)."""

    GENRE: ClassVar[str] = "pignon_cremaillere"
    nom: str
    liaison_1: str
    liaison_2: str
    r: float
    rendement: float = 1.0

    def __post_init__(self) -> None:
        _verifier_commun(self.nom, self.liaison_1, self.liaison_2, self.rendement)
        _positif_fini(self.r, f"Couplage {self.nom} : le rayon r")

    def vers_dict(self) -> dict[str, Any]:
        return {
            "genre": self.GENRE,
            "nom": self.nom,
            "liaison_1": self.liaison_1,
            "liaison_2": self.liaison_2,
            "r": self.r,
            "rendement": self.rendement,
        }


@dataclass(frozen=True)
class VisEcrou:
    """v = p·ω / 2π ; p : pas (m par tour)."""

    GENRE: ClassVar[str] = "vis_ecrou"
    nom: str
    liaison_1: str
    liaison_2: str
    p: float
    rendement: float = 1.0

    def __post_init__(self) -> None:
        _verifier_commun(self.nom, self.liaison_1, self.liaison_2, self.rendement)
        _positif_fini(self.p, f"Couplage {self.nom} : le pas p")

    def vers_dict(self) -> dict[str, Any]:
        return {
            "genre": self.GENRE,
            "nom": self.nom,
            "liaison_1": self.liaison_1,
            "liaison_2": self.liaison_2,
            "p": self.p,
            "rendement": self.rendement,
        }


type Couplage = Engrenage | PignonCremaillere | VisEcrou


def couplage_depuis_dict(d: dict[str, Any]) -> Couplage:
    """Reconstruit un couplage ; toute anomalie devient une ErreurCouplage."""
    genre = d.get("genre") if isinstance(d, dict) else None
    if genre not in (Engrenage.GENRE, PignonCremaillere.GENRE, VisEcrou.GENRE):
        raise ErreurCouplage(f"Couplage de genre inconnu ou absent : {genre!r}.")
    try:
        commun = (str(d["nom"]), str(d["liaison_1"]), str(d["liaison_2"]))
        rendement = d["rendement"]
        if genre == Engrenage.GENRE:
            return Engrenage(*commun, d["k"], SensEngrenage(d["sens"]), rendement)
        if genre == PignonCremaillere.GENRE:
            return PignonCremaillere(*commun, d["r"], rendement)
        if genre == VisEcrou.GENRE:
            return VisEcrou(*commun, d["p"], rendement)
    except ErreurCouplage:
        raise
    except (KeyError, TypeError, ValueError) as e:
        raise ErreurCouplage(f"Couplage illisible ({type(e).__name__} : {e}).") from e
    raise AssertionError("genre de couplage non traité")  # pragma: no cover
