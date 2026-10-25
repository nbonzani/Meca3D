# SPDX-License-Identifier: GPL-3.0-or-later
"""Export CSV au format Excel français (EX-52) : `;`, décimale `,`, UTF-8 avec BOM."""

import csv
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from meca3d.modele.capteurs import BaseCapteur, CapteurLiaison, CapteurPoint, SensTorseur
from meca3d.modele.etude import Etude
from meca3d.modele.liaison import TypeLiaison
from meca3d.moteur.base import ResultatsBruts
from meca3d.resultats.capteurs import mesurer_point
from meca3d.resultats.torseurs import torseur_cinematique, torseur_statique

COMPOSANTES_STATIQUES = ("Fx (N)", "Fy (N)", "Fz (N)", "Mx (N·m)", "My (N·m)", "Mz (N·m)")
COMPOSANTES_CINEMATIQUES = (
    "Ωx (rad/s)",
    "Ωy (rad/s)",
    "Ωz (rad/s)",
    "Vx (m/s)",
    "Vy (m/s)",
    "Vz (m/s)",
)


def _colonnes_capteurs(etude: Etude, resultats: ResultatsBruts) -> dict[str, np.ndarray]:
    """Colonnes des capteurs définis dans l'étude (EX-50, EX-51)."""
    colonnes: dict[str, np.ndarray] = {}
    for capteur in etude.capteurs:
        if isinstance(capteur, CapteurPoint):
            mesure = mesurer_point(etude, resultats, capteur)
            for i, axe in enumerate("xyz"):
                colonnes[f"{capteur.nom} {axe} (m)"] = mesure.position[:, i]
            for i, axe in enumerate("xyz"):
                colonnes[f"{capteur.nom} v{axe} (m/s)"] = mesure.vitesse[:, i]
            for i, axe in enumerate("xyz"):
                colonnes[f"{capteur.nom} a{axe} (m/s²)"] = mesure.acceleration[:, i]
        elif isinstance(capteur, CapteurLiaison):
            liaison = etude.liaison(capteur.liaison)
            i = liaison.solide_a if capteur.sens is SensTorseur.I_VERS_J else liaison.solide_b
            base = "monde" if capteur.base is BaseCapteur.MONDE else "liaison"
            if capteur.liaison in resultats.forces:
                tors = torseur_statique(etude, resultats, capteur.liaison, de=i, base=base)
                for k, composante in enumerate(COMPOSANTES_STATIQUES):
                    colonnes[f"{capteur.nom} {composante}"] = tors[:, k]
            cine = torseur_cinematique(etude, resultats, capteur.liaison, i=i, base=base)
            for k, composante in enumerate(COMPOSANTES_CINEMATIQUES):
                colonnes[f"{capteur.nom} {composante}"] = cine[:, k]
    return colonnes


def colonnes_resultats(etude: Etude, resultats: ResultatsBruts) -> dict[str, np.ndarray]:
    """Colonnes du CSV : t, couple/effort moteur des pilotes, torseurs {a→b} en base monde, puis
    les capteurs de l'étude. En mode cinématique (aucun effort) : positions des centres de
    gravité à la place des torseurs."""
    colonnes: dict[str, np.ndarray] = {"t (s)": resultats.t}
    if not resultats.forces:
        for nom, position in resultats.positions.items():
            for i, axe in enumerate("xyz"):
                colonnes[f"{nom} {axe} (m)"] = position[:, i]
        colonnes.update(_colonnes_capteurs(etude, resultats))
        return colonnes
    for pilote in etude.pilotes:
        liaison = etude.liaison(pilote.liaison)
        tors = torseur_statique(
            etude, resultats, pilote.liaison, de=liaison.solide_a, base="liaison"
        )
        suffixe = "" if len(etude.pilotes) == 1 else f" {pilote.liaison}"
        if liaison.type in (TypeLiaison.GLISSIERE,) or pilote.grandeur == "position":
            colonnes[f"F{suffixe} (N)"] = tors[:, 0]  # effort sur l'axe x local
        else:
            colonnes[f"C{suffixe} (N·m)"] = tors[:, 3]  # couple d'axe x local
    for liaison in etude.liaisons:
        tors = torseur_statique(etude, resultats, liaison.nom, de=liaison.solide_a, base="monde")
        for i, composante in enumerate(COMPOSANTES_STATIQUES):
            nom = f"{liaison.nom} {liaison.solide_a}→{liaison.solide_b} {composante}"
            colonnes[nom] = tors[:, i]
    colonnes.update(_colonnes_capteurs(etude, resultats))
    return colonnes


@dataclass(frozen=True)
class Statistiques:
    """Valeurs extrêmes et moyenne d'une grandeur (EX-52)."""

    minimum: float
    maximum: float
    moyenne: float


def statistiques(valeurs: np.ndarray) -> Statistiques:
    return Statistiques(float(np.min(valeurs)), float(np.max(valeurs)), float(np.mean(valeurs)))


def _formater(x: float) -> str:
    return repr(float(x)).replace(".", ",")


def ecrire_csv(chemin: Path | str, colonnes: dict[str, np.ndarray]) -> None:
    noms = list(colonnes)
    n = len(colonnes[noms[0]])
    with Path(chemin).open("w", encoding="utf-8-sig", newline="") as f:
        ecrivain = csv.writer(f, delimiter=";")
        ecrivain.writerow(noms)
        for i in range(n):
            ecrivain.writerow([_formater(colonnes[nom][i]) for nom in noms])
