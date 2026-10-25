# SPDX-License-Identifier: GPL-3.0-or-later
"""Étude : agrégat du modèle neutre et fichier `.meca3d` (JSON UTF-8 versionné, D10, EX-60)."""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from meca3d.modele.actions import ErreurLoi, Pesanteur, Pilote
from meca3d.modele.liaison import Liaison
from meca3d.modele.solide import Solide

VERSION_ETUDE = 1


class ErreurEtude(Exception):
    """Fichier d'étude illisible ou incohérent ; aucune étude partielle n'est produite."""


@dataclass(frozen=True)
class Reglages:
    """Réglages de simulation : durée (s), nombre de pas, période d'écriture des capteurs (s)."""

    duree: float = 1.0
    nb_pas: int = 1000
    periode_ecriture: float = 0.001

    def vers_dict(self) -> dict[str, Any]:
        return {
            "duree": self.duree,
            "nb_pas": self.nb_pas,
            "periode_ecriture": self.periode_ecriture,
        }

    @classmethod
    def depuis_dict(cls, d: dict[str, Any]) -> "Reglages":
        return cls(
            duree=float(d["duree"]),
            nb_pas=int(d["nb_pas"]),
            periode_ecriture=float(d["periode_ecriture"]),
        )


@dataclass
class Etude:
    solides: list[Solide]
    liaisons: list[Liaison]
    maquette: str = ""
    revision: int | None = None
    pilotes: list[Pilote] = field(default_factory=list)
    pesanteur: Pesanteur = field(default_factory=Pesanteur)
    reglages: Reglages = field(default_factory=Reglages)

    def solide(self, nom: str) -> Solide:
        for s in self.solides:
            if s.nom == nom:
                return s
        raise KeyError(f"Solide inconnu : {nom}")

    def liaison(self, nom: str) -> Liaison:
        for liaison in self.liaisons:
            if liaison.nom == nom:
                return liaison
        raise KeyError(f"Liaison inconnue : {nom}")

    def vers_dict(self) -> dict[str, Any]:
        return {
            "version_etude": VERSION_ETUDE,
            "maquette": self.maquette,
            "revision": self.revision,
            "solides": [s.vers_dict() for s in self.solides],
            "liaisons": [x.vers_dict() for x in self.liaisons],
            "pilotes": [p.vers_dict() for p in self.pilotes],
            "pesanteur": self.pesanteur.vers_dict(),
            "reglages": self.reglages.vers_dict(),
        }

    @classmethod
    def depuis_dict(cls, d: dict[str, Any]) -> "Etude":
        version = d.get("version_etude")
        if version != VERSION_ETUDE:
            raise ErreurEtude(
                f"Étude en version {version!r} non prise en charge "
                f"(version attendue : {VERSION_ETUDE})."
            )
        try:
            revision = d["revision"]
            return cls(
                maquette=str(d["maquette"]),
                revision=None if revision is None else int(revision),
                solides=[Solide.depuis_dict(s) for s in d["solides"]],
                liaisons=[Liaison.depuis_dict(x) for x in d["liaisons"]],
                pilotes=[Pilote.depuis_dict(p) for p in d["pilotes"]],
                pesanteur=Pesanteur.depuis_dict(d["pesanteur"]),
                reglages=Reglages.depuis_dict(d["reglages"]),
            )
        except (KeyError, TypeError, ValueError, ErreurLoi) as e:
            raise ErreurEtude(f"Fichier d'étude incohérent ({type(e).__name__} : {e}).") from e


def ecrire_etude(etude: Etude, chemin: Path | str) -> None:
    texte = json.dumps(etude.vers_dict(), indent=2, ensure_ascii=False) + "\n"
    Path(chemin).write_text(texte, encoding="utf-8", newline="\n")


def lire_etude(chemin: Path | str) -> Etude:
    try:
        texte = Path(chemin).read_text(encoding="utf-8")
    except OSError as e:
        raise ErreurEtude(f"Impossible de lire le fichier d'étude : {e}") from e
    try:
        donnees = json.loads(texte)
    except json.JSONDecodeError as e:
        raise ErreurEtude(f"Fichier d'étude corrompu (JSON invalide) : {e}") from e
    if not isinstance(donnees, dict):
        raise ErreurEtude("Fichier d'étude corrompu : objet JSON attendu.")
    return Etude.depuis_dict(donnees)
