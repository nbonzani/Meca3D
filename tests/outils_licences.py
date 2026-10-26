# SPDX-License-Identifier: GPL-3.0-or-later
"""Licences des dépendances d'exécution (EX-64), lues dans les métadonnées installées
(`importlib.metadata`). `uv run python tests/outils_licences.py` affiche le tableau pour
docs/LICENCES.md."""

import re
from dataclasses import dataclass
from importlib import metadata

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

# Familles compatibles avec une distribution sous GPL v3 ou ultérieure (FSF : liste des licences)
FAMILLES_COMPATIBLES = ("MIT", "BSD", "Apache-2.0", "PSF", "LGPL", "GPL", "Matplotlib", "HPND", "MPL")

_MOTIFS: tuple[tuple[str, str], ...] = (
    (r"\bLGPL|Lesser General Public", "LGPL"),
    (r"\bGPL|General Public License", "GPL"),
    (r"Apache", "Apache-2.0"),
    (r"\bBSD\b|BSD-", "BSD"),
    (r"\bMIT\b|MIT License", "MIT"),
    (r"\bPSF\b|Python Software Foundation", "PSF"),
    (r"Matplotlib|matplotlib", "Matplotlib"),
    (r"HPND|Historical Permission", "HPND"),
    (r"\bMPL\b|Mozilla Public", "MPL"),
)


@dataclass(frozen=True)
class LicenceDependance:
    nom: str
    version: str
    licence: str  # texte brut des métadonnées (abrégé)
    familles: tuple[str, ...]  # familles reconnues ; vide : licence non identifiée


def _texte_licence(meta: metadata.PackageMetadata) -> str:
    expression = meta.get("License-Expression")
    if expression:
        return str(expression)
    classes = [c.split("::")[-1].strip() for c in meta.get_all("Classifier") or [] if "License ::" in c]
    brute = (meta.get("License") or "").strip()
    # le champ License contient parfois le texte entier : seule la première ligne est gardée
    brute = brute.splitlines()[0] if brute else ""
    return " ; ".join(x for x in [*classes, brute] if x)


def _familles(texte: str) -> tuple[str, ...]:
    return tuple(dict.fromkeys(f for motif, f in _MOTIFS if re.search(motif, texte)))


def _texte_fichiers_licence(nom: str) -> str:
    """Texte des fichiers de licence installés avec le paquet (dist-info/licenses)."""
    morceaux = []
    for fichier in metadata.files(nom) or []:
        if "licen" in fichier.name.lower() and fichier.suffix.lower() in ("", ".txt", ".md", ".rst"):
            try:
                morceaux.append(fichier.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError):
                pass
    return "\n".join(morceaux)


def _famille_par_texte(texte: str) -> tuple[str, ...]:
    """Reconnaissance du texte de la licence BSD à trois clauses (cas d'un LicenseRef)."""
    if (
        "Redistribution and use in source and binary forms" in texte
        and "Neither the name" in texte
        and "retain the above copyright" in texte
    ):
        return ("BSD",)
    return ()


def dependances_execution(racine: str = "meca3d") -> list[str]:
    """Noms canoniques des dépendances d'exécution (directes et transitives, extras exclus)."""
    vus: dict[str, None] = {}
    a_voir = [racine]
    while a_voir:
        nom = a_voir.pop()
        for texte in metadata.requires(nom) or []:
            exigence = Requirement(texte)
            if exigence.marker is not None and not exigence.marker.evaluate({"extra": ""}):
                continue
            cle = canonicalize_name(exigence.name)
            if cle not in vus:
                vus[cle] = None
                a_voir.append(cle)
    return sorted(vus)


def licences_dependances(racine: str = "meca3d") -> list[LicenceDependance]:
    resultat = []
    for nom in dependances_execution(racine):
        try:
            meta = metadata.metadata(nom)
            version = metadata.version(nom)
        except metadata.PackageNotFoundError:
            resultat.append(LicenceDependance(nom, "?", "non installée", ()))
            continue
        texte = _texte_licence(meta)
        familles = _familles(texte) or _famille_par_texte(_texte_fichiers_licence(nom))
        resultat.append(LicenceDependance(nom, version, texte, familles))
    return resultat


def est_compatible_gpl3(dep: LicenceDependance) -> bool:
    return any(f in FAMILLES_COMPATIBLES for f in dep.familles)


if __name__ == "__main__":
    print("| Paquet | Version | Licence déclarée | Famille | Compatible GPL v3 |")
    print("|---|---|---|---|---|")
    for d in licences_dependances():
        oui = "oui" if est_compatible_gpl3(d) else "À VÉRIFIER"
        print(f"| {d.nom} | {d.version} | {d.licence[:70]} | {', '.join(d.familles)} | {oui} |")
