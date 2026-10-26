# SPDX-License-Identifier: GPL-3.0-or-later
"""Fenêtre de SolidCraft visible avant d'animer (R10, EX-53, RESULTATS_1b § Q3).

SolidCraft traite une requête par image affichée : fenêtre réduite ou entièrement masquée, toute
requête coûte ~115-130 ms (contre ~35 ms) et l'animation tombe à ~7 images/s. La méthode de
connexion `ui.window` (de premier niveau, pas une commande d'`engine.execute`) agit comme les
boutons de la barre de titre. Mesuré sur SolidCraft 0.15.0 : `restore` ne ramène PAS une fenêtre
réduite (la fenêtre reste masquée), seul `maximize` la ramène. Il n'existe pas d'indicateur d'état
fiable (`ui.inspect` ne le donne pas ; `ui.screenshot` répond `hidden` mais coûte 300 ms et écrit
un fichier) : la détection se fait donc par la latence d'une requête de lecture.
"""

import time

from meca3d.cao.canal import CanalSolidCraft

SEUIL_LATENCE = 0.08  # s : 34 ms fenêtre visible, 115-130 ms fenêtre réduite
ECHANTILLONS = 3  # nombre de lectures ; la médiane écarte une lecture ralentie par hasard
ATTENTE_APRES_ACTION = 0.3  # s : laisse le système afficher la fenêtre avant de la remesurer
ACTION_ECRAN = "maximize"


def _latence(canal: CanalSolidCraft) -> float:
    """Médiane (s) de la durée d'une requête de lecture `document.inspect`."""
    durees = []
    for _ in range(ECHANTILLONS):
        debut = time.perf_counter()
        canal.requete("document.inspect")
        durees.append(time.perf_counter() - debut)
    return sorted(durees)[len(durees) // 2]


def ramener_au_premier_plan(canal: CanalSolidCraft) -> bool:
    """Rend visible la fenêtre de SolidCraft si elle est réduite ; vrai si une action a été
    envoyée. Une fenêtre visible n'est jamais modifiée."""
    if _latence(canal) < SEUIL_LATENCE:
        return False
    canal.requete("ui.window", {"action": ACTION_ECRAN})
    time.sleep(ATTENTE_APRES_ACTION)
    return True
