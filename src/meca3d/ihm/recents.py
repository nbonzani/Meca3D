# SPDX-License-Identifier: GPL-3.0-or-later
"""Listes des fichiers récents : études et maquettes (EX-65, lot 16).

Une liste est mémorisée par utilisateur sous une clé des réglages, chemins séparés par des
sauts de ligne (un chemin Windows n'en contient pas). Le plus récent est en tête.
"""

import os
from pathlib import Path
from typing import Protocol

MAXIMUM_RECENTS = 10  # EX-65
CLE_ETUDES_RECENTES = "recents/etudes"
CLE_MAQUETTES_RECENTES = "recents/maquettes"
SEPARATEUR = "\n"


class Memoire(Protocol):
    def lire(self, cle: str) -> str | None: ...

    def ecrire(self, cle: str, valeur: str) -> None: ...


def _cle(chemin: str | Path) -> str:
    """Chemins comparés sans tenir compte de la casse (système de fichiers Windows) ; `resolve`
    développe les noms courts (8.3) et les `..` : un même fichier n'a qu'une clé."""
    return os.path.normcase(str(Path(chemin).resolve())).casefold()


def ajouter_recent(recents: list[str], chemin: Path) -> list[str]:
    """`chemin` en tête, sans doublon, `MAXIMUM_RECENTS` entrées au plus."""
    return [str(chemin), *retirer_recent(recents, chemin)][:MAXIMUM_RECENTS]


def retirer_recent(recents: list[str], chemin: Path) -> list[str]:
    cle = _cle(chemin)
    return [c for c in recents if _cle(c) != cle]


def lire_recents(memoire: Memoire, cle: str) -> list[str]:
    texte = memoire.lire(cle) or ""
    return [c for c in texte.split(SEPARATEUR) if c][:MAXIMUM_RECENTS]


def ecrire_recents(memoire: Memoire, cle: str, recents: list[str]) -> None:
    memoire.ecrire(cle, SEPARATEUR.join(recents))
