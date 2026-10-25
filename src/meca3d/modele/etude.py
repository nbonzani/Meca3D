# SPDX-License-Identifier: GPL-3.0-or-later
"""Étude : agrégat du modèle neutre et fichier `.meca3d` (JSON UTF-8 versionné, D10, EX-60)."""

import copy
import json
import math
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from meca3d.modele.actions import (
    ActionExterieure,
    ErreurAction,
    ErreurLoi,
    Pesanteur,
    Pilote,
    RessortAmortisseur,
)
from meca3d.modele.capteurs import Capteur, CapteurLiaison, CapteurPoint, capteur_depuis_dict
from meca3d.modele.couplage import Couplage, couplage_depuis_dict
from meca3d.modele.liaison import Liaison, Statut
from meca3d.modele.solide import Solide

# Version 2 (lot 3) : couplages, capteurs, validation_en_bloc et couplage_screw des liaisons.
# Lot 6 : `actions`, `ressorts` et `hyperstatique_autorise` sont des clés OPTIONNELLES de la
# version 2, écrites seulement si elles diffèrent de la valeur par défaut (les fichiers v2
# existants restent identiques et relisibles ; pas de nouvelle version, donc pas de migration).
VERSION_ETUDE = 2


class ErreurEtude(Exception):
    """Fichier d'étude illisible ou incohérent ; aucune étude partielle n'est produite."""


class ErreurValidation(Exception):
    """Opération de validation des liaisons refusée (EX-11)."""


def _migrer_v1_vers_v2(d: dict[str, Any]) -> dict[str, Any]:
    """Version 1 (lot 2) : ni couplages, ni capteurs, ni validation en bloc, ni couplage_screw."""
    d["version_etude"] = 2
    d.setdefault("validation_en_bloc", False)
    d.setdefault("couplages", [])
    d.setdefault("capteurs", [])
    for liaison in d["liaisons"]:
        liaison.setdefault("couplage_screw", False)
    return d


# Migration de la version n vers n+1, appliquées en chaîne sur une copie des données lues.
_MIGRATIONS: dict[int, Callable[[dict[str, Any]], dict[str, Any]]] = {1: _migrer_v1_vers_v2}


def _verifier_finis(valeur: Any) -> None:
    if isinstance(valeur, float) and not math.isfinite(valeur):
        raise ErreurEtude("Fichier d'étude incohérent : valeur numérique non finie.")
    if isinstance(valeur, dict):
        for v in valeur.values():
            _verifier_finis(v)
    elif isinstance(valeur, list):
        for v in valeur:
            _verifier_finis(v)


def _booleen(valeur: object) -> bool:
    if not isinstance(valeur, bool):
        raise ValueError(f"Booléen attendu, reçu {valeur!r}.")
    return valeur


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
    couplages: list[Couplage] = field(default_factory=list)
    capteurs: list[Capteur] = field(default_factory=list)
    validation_en_bloc: bool = False
    actions: list[ActionExterieure] = field(default_factory=list)
    ressorts: list[RessortAmortisseur] = field(default_factory=list)
    hyperstatique_autorise: bool = False  # EX-23

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

    def valider_toutes(self) -> list[str]:
        """EX-11 : « Valider toutes les propositions », refusé si la validation en bloc est
        désactivée. Valide les liaisons non validées qui ont un type ; celles sans type
        (pin_slot sans choix) restent à choisir. Renvoie les noms des liaisons validées."""
        if not self.validation_en_bloc:
            raise ErreurValidation(
                "La validation en bloc est désactivée : valider les liaisons une par une "
                "(réglage de l'étude, menu Enseignant)."
            )
        validees = []
        for liaison in self.liaisons:
            if liaison.statut is Statut.PROPOSEE and liaison.type is not None:
                liaison.valider()
                validees.append(liaison.nom)
        return validees

    def verifier_coherence(self) -> None:
        """Noms uniques et références valides (solides, liaisons) ; lève ErreurEtude."""
        for libelle, noms in (
            ("solide", [s.nom for s in self.solides]),
            ("liaison", [x.nom for x in self.liaisons]),
            ("couplage", [c.nom for c in self.couplages]),
            ("capteur", [c.nom for c in self.capteurs]),
            ("action", [a.nom for a in self.actions]),
            ("ressort", [r.nom for r in self.ressorts]),
        ):
            if len(set(noms)) != len(noms):
                raise ErreurEtude(f"Fichier d'étude incohérent : nom de {libelle} en double.")
        solides = {s.nom for s in self.solides}
        liaisons = {x.nom for x in self.liaisons}
        for liaison in self.liaisons:
            for nom in (liaison.solide_a, liaison.solide_b):
                if nom not in solides:
                    raise ErreurEtude(f"Liaison {liaison.nom} : solide inconnu « {nom} ».")
        for action in self.actions:
            if action.solide not in solides:
                raise ErreurEtude(f"Action {action.nom} : solide inconnu « {action.solide} ».")
        for ressort in self.ressorts:
            for nom in (ressort.solide_1, ressort.solide_2):
                if nom not in solides:
                    raise ErreurEtude(f"Ressort {ressort.nom} : solide inconnu « {nom} ».")
        for couplage in self.couplages:
            for nom in (couplage.liaison_1, couplage.liaison_2):
                if nom not in liaisons:
                    raise ErreurEtude(f"Couplage {couplage.nom} : liaison inconnue « {nom} ».")
        for capteur in self.capteurs:
            if isinstance(capteur, CapteurLiaison):
                if capteur.liaison not in liaisons:
                    raise ErreurEtude(
                        f"Capteur {capteur.nom} : liaison inconnue « {capteur.liaison} »."
                    )
            elif isinstance(capteur, CapteurPoint):
                for nom in (capteur.solide, capteur.solide_reference):
                    if nom not in solides:
                        raise ErreurEtude(f"Capteur {capteur.nom} : solide inconnu « {nom} ».")

    def vers_dict(self) -> dict[str, Any]:
        d = self._vers_dict_base()
        if self.actions:
            d["actions"] = [a.vers_dict() for a in self.actions]
        if self.ressorts:
            d["ressorts"] = [r.vers_dict() for r in self.ressorts]
        if self.hyperstatique_autorise:
            d["hyperstatique_autorise"] = True
        return d

    def _vers_dict_base(self) -> dict[str, Any]:
        return {
            "version_etude": VERSION_ETUDE,
            "maquette": self.maquette,
            "revision": self.revision,
            "validation_en_bloc": self.validation_en_bloc,
            "solides": [s.vers_dict() for s in self.solides],
            "liaisons": [x.vers_dict() for x in self.liaisons],
            "couplages": [c.vers_dict() for c in self.couplages],
            "pilotes": [p.vers_dict() for p in self.pilotes],
            "capteurs": [c.vers_dict() for c in self.capteurs],
            "pesanteur": self.pesanteur.vers_dict(),
            "reglages": self.reglages.vers_dict(),
        }

    @classmethod
    def depuis_dict(cls, d: dict[str, Any]) -> "Etude":
        version = d.get("version_etude")
        if type(version) is not int or not 1 <= version <= VERSION_ETUDE:
            raise ErreurEtude(
                f"Étude en version {version!r} non prise en charge "
                f"(version attendue : {VERSION_ETUDE})."
            )
        _verifier_finis(d)
        try:
            donnees = copy.deepcopy(d)
            while donnees["version_etude"] < VERSION_ETUDE:
                donnees = _MIGRATIONS[donnees["version_etude"]](donnees)
            revision = donnees["revision"]
            etude = cls(
                maquette=str(donnees["maquette"]),
                revision=None if revision is None else int(revision),
                solides=[Solide.depuis_dict(s) for s in donnees["solides"]],
                liaisons=[Liaison.depuis_dict(x) for x in donnees["liaisons"]],
                pilotes=[Pilote.depuis_dict(p) for p in donnees["pilotes"]],
                pesanteur=Pesanteur.depuis_dict(donnees["pesanteur"]),
                reglages=Reglages.depuis_dict(donnees["reglages"]),
                couplages=[couplage_depuis_dict(c) for c in donnees["couplages"]],
                capteurs=[capteur_depuis_dict(c) for c in donnees["capteurs"]],
                validation_en_bloc=_booleen(donnees["validation_en_bloc"]),
                actions=[ActionExterieure.depuis_dict(a) for a in donnees.get("actions", [])],
                ressorts=[RessortAmortisseur.depuis_dict(r) for r in donnees.get("ressorts", [])],
                hyperstatique_autorise=_booleen(donnees.get("hyperstatique_autorise", False)),
            )
        except (KeyError, TypeError, ValueError, AttributeError, ErreurLoi, ErreurAction) as e:
            raise ErreurEtude(f"Fichier d'étude incohérent ({type(e).__name__} : {e}).") from e
        etude.verifier_coherence()
        return etude


def liaisons_non_validees(etude: Etude) -> list[str]:
    """Noms des liaisons qui ne sont pas encore validées (EX-11)."""
    return [x.nom for x in etude.liaisons if x.statut is not Statut.VALIDEE]


def simulation_possible(etude: Etude) -> bool:
    """EX-11 : aucune simulation tant qu'une liaison n'est pas validée.

    Fonction pure du modèle sur laquelle s'appuiera le bouton Simuler de l'IHM.
    """
    return not liaisons_non_validees(etude)


def ecrire_etude(etude: Etude, chemin: Path | str) -> None:
    texte = json.dumps(etude.vers_dict(), indent=2, ensure_ascii=False) + "\n"
    Path(chemin).write_text(texte, encoding="utf-8", newline="\n")


def lire_etude(chemin: Path | str) -> Etude:
    try:
        texte = Path(chemin).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        raise ErreurEtude(f"Impossible de lire le fichier d'étude : {e}") from e
    try:
        donnees = json.loads(texte)
    except (json.JSONDecodeError, RecursionError) as e:
        raise ErreurEtude(f"Fichier d'étude corrompu (JSON invalide) : {e}") from e
    if not isinstance(donnees, dict):
        raise ErreurEtude("Fichier d'étude corrompu : objet JSON attendu.")
    return Etude.depuis_dict(donnees)
