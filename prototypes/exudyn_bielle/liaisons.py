"""Catalogue des liaisons normalisées (NF EN ISO 3952) exprimées en ddl bloqués.

Convention du repère local de liaison (x, y, z) :
- liaisons à axe (pivot, glissière, pivot glissant, hélicoïdale, linéaire annulaire) : axe = x ;
- liaisons à normale (appui plan, ponctuelle, linéaire rectiligne) : normale = z ;
- linéaire rectiligne : ligne de contact = x ;
- rotule à doigt : rotation bloquée autour de z.

constrainedAxes = [Tx, Ty, Tz, Rx, Ry, Rz], 1 = bloqué (inconnue statique), 0 = libre (mobilité).
"""

LIAISONS = {
    "encastrement":        [1, 1, 1, 1, 1, 1],
    "pivot":               [1, 1, 1, 0, 1, 1],
    "glissiere":           [0, 1, 1, 1, 1, 1],
    "pivot_glissant":      [0, 1, 1, 0, 1, 1],
    "rotule_a_doigt":      [1, 1, 1, 0, 0, 1],
    "rotule":              [1, 1, 1, 0, 0, 0],
    "appui_plan":          [0, 0, 1, 1, 1, 0],
    "lineaire_annulaire":  [0, 1, 1, 0, 0, 0],
    "lineaire_rectiligne": [0, 0, 1, 0, 1, 0],
    "ponctuelle":          [0, 0, 1, 0, 0, 0],
    # hélicoïdale : pivot glissant + couplage Tx = pas/(2π)·Rx (traité à part)
    "helicoidale":         [0, 1, 1, 0, 1, 1],
}


def nb_inconnues_statiques(nom):
    return sum(LIAISONS[nom])


def nb_mobilites(nom):
    return 6 - sum(LIAISONS[nom])
