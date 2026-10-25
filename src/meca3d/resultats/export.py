# SPDX-License-Identifier: GPL-3.0-or-later
"""Export CSV au format Excel français (EX-52) : `;`, décimale `,`, UTF-8 avec BOM."""

import csv
from pathlib import Path

import numpy as np

from meca3d.modele.etude import Etude
from meca3d.modele.liaison import TypeLiaison
from meca3d.moteur.base import ResultatsBruts
from meca3d.resultats.torseurs import torseur_statique

_COMPOSANTES = ("Fx (N)", "Fy (N)", "Fz (N)", "Mx (N·m)", "My (N·m)", "Mz (N·m)")


def colonnes_resultats(etude: Etude, resultats: ResultatsBruts) -> dict[str, np.ndarray]:
    """Colonnes du CSV : t, couple/effort moteur des pilotes, torseurs {a→b} en base monde."""
    colonnes: dict[str, np.ndarray] = {"t (s)": resultats.t}
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
        for i, composante in enumerate(_COMPOSANTES):
            nom = f"{liaison.nom} {liaison.solide_a}→{liaison.solide_b} {composante}"
            colonnes[nom] = tors[:, i]
    return colonnes


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
