# SPDX-License-Identifier: GPL-3.0-or-later
"""Mise en forme des valeurs de torseurs pour l'élève (EX-50) : pure, sans Qt.

Règles :
- composante nulle par construction (ddl libre de la liaison dans la base de liaison, hors
  pilote, pour le torseur statique ; ddl bloqué pour le torseur cinématique) : « 0 » exact ;
- les autres valeurs ont `CHIFFRES_SIGNIFICATIFS` chiffres significatifs, virgule décimale ;
- seuil relatif : une valeur dont la valeur absolue est inférieure à `SEUIL_RELATIF` fois le
  maximum du tableau affiché (toutes liaisons, six composantes, à l'instant choisi) est du bruit
  numérique et s'affiche « 0 ».

Base monde : les composantes nulles par construction en base de liaison ne le sont plus
forcément une fois le torseur tourné dans le repère monde. Le masque « par construction » n'y est
donc pas appliqué : seul le seuil relatif l'est. Les unités sont portées par les en-têtes de
colonnes (`COMPOSANTES_STATIQUES`, `COMPOSANTES_CINEMATIQUES`).
"""

import numpy as np

CHIFFRES_SIGNIFICATIFS = 4
SEUIL_RELATIF = 1e-9  # devant le maximum du tableau : en dessous, bruit numérique


def formater_valeur(x: float, reference: float) -> str:
    """4 chiffres significatifs ; 0 si |x| < SEUIL_RELATIF × `reference` (ou x nul)."""
    if x == 0.0 or abs(x) < SEUIL_RELATIF * reference or reference <= 0.0:
        return "0"
    return f"{x:.{CHIFFRES_SIGNIFICATIFS}g}".replace(".", ",")


def formater_tableau(valeurs: np.ndarray, nuls: np.ndarray) -> list[list[str]]:
    """`valeurs` et `nuls` (booléens, composantes nulles par construction) de forme (lignes, 6).

    La référence du seuil relatif est le maximum du tableau (hors composantes nulles par
    construction)."""
    valeurs = np.asarray(valeurs, dtype=float)
    utiles = np.where(nuls, 0.0, np.abs(valeurs))
    reference = float(utiles.max()) if utiles.size else 0.0
    return [
        [
            "0" if nuls[i, j] else formater_valeur(float(valeurs[i, j]), reference)
            for j in range(valeurs.shape[1])
        ]
        for i in range(valeurs.shape[0])
    ]
