# SPDX-License-Identifier: GPL-3.0-or-later
"""Mobilité et hyperstatisme par la méthode cinématique (EX-21), garde-fou (EX-22), ddl
redondants à libérer pour le mode cinématique hyperstatique (EX-23, calcul seulement).

Convention des torseurs, réduits au point commun P : colonne cinématique [ω ; V(P)] avec
rotation libre d'axe u en C → (u, (C − P) ∧ u) et translation libre selon u → (0, u). La colonne
statique d'un ddl bloqué est la duale [F ; M(P)] : force selon u → (u, (C − P) ∧ u), couple
selon u → (0, u).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum

import numpy as np

from meca3d.graphe.graphe import (
    NB_DDL,
    DescriptionMecanisme,
    LiaisonGraphe,
    ResultatGraphe,
    construire_graphe,
)

# SPEC EX-21 : tolérance relative du rang (SVD), relative à la plus grande valeur singulière
TOLERANCE_RANG_RELATIVE = 1e-9

NOMS_DDL = ("Tx", "Ty", "Tz", "Rx", "Ry", "Rz")


class ErreurMobilite(ValueError):
    """Description incohérente ou calcul de mobilité impossible (message en français)."""


class Mode(StrEnum):
    CINEMATIQUE = "cinematique"
    DYNAMIQUE = "dynamique"


@dataclass(frozen=True)
class DdlLiaison:
    """Un ddl (indice 0..5 de [Tx Ty Tz Rx Ry Rz]) d'une liaison désignée par son nom."""

    liaison: str
    ddl: int


@dataclass(frozen=True, eq=False)
class ResultatMobilite:
    ic: int  # inconnues cinématiques (ddl libres)
    rc: int  # rang de Kc
    m: int  # mobilité : Ic − rc
    h: int  # degré d'hyperstatisme : Ec − rc
    ec: int  # équations : 6μ + nombre de couplages
    mu: int
    nb_couplages: int
    inconnues: tuple[DdlLiaison, ...]
    matrice: np.ndarray  # Kc, (Ec × Ic)
    valeurs_singulieres: np.ndarray
    graphe: ResultatGraphe


@dataclass(frozen=True)
class Decision:
    autorise: bool
    message: str  # vide si rien à signaler
    avertissement: bool = False


def _point_reduction(description: DescriptionMecanisme) -> np.ndarray:
    if not description.liaisons:
        return np.zeros(3)
    return np.mean([x.centre for x in description.liaisons], axis=0)


def _colonne(x: LiaisonGraphe, ddl: int, point: np.ndarray, statique: bool) -> np.ndarray:
    """Torseur [ω ; V(P)] (cinématique) ou [F ; M(P)] (statique) associé au ddl de la liaison."""
    u = x.base[:, ddl % 3]
    rotation = ddl >= 3
    moment = np.cross(x.centre - point, u)
    zero = np.zeros(3)
    if rotation != statique:  # rotation cinématique ou force statique
        return np.concatenate([u, moment])
    return np.concatenate([zero, u])


def _rang(m: np.ndarray, tolerance: float) -> tuple[int, np.ndarray]:
    if m.size == 0:
        return 0, np.zeros(0)
    s = np.linalg.svd(m, compute_uv=False)
    if s[0] == 0.0:
        return 0, s
    return int(np.sum(s > tolerance * s[0])), s


def _couplages_explicites(
    description: DescriptionMecanisme,
) -> list[tuple[str, int, str, int, float]]:
    """(liaison_a, ddl_a, liaison_b, ddl_b, rapport), ddl par défaut résolus et validés."""
    resolus = []
    for c in description.couplages:
        ddls = []
        for nom, ddl in ((c.liaison_a, c.ddl_a), (c.liaison_b, c.ddl_b)):
            try:
                x = description.liaison(nom)
            except KeyError as e:
                raise ErreurMobilite(f"Couplage : liaison inconnue {nom!r}.") from e
            if ddl is None:
                if not x.ddl_libres:
                    raise ErreurMobilite(f"Couplage : la liaison {nom} n'a aucun ddl libre.")
                ddl = x.ddl_libres[0]
            elif ddl not in x.ddl_libres:
                raise ErreurMobilite(
                    f"Couplage : le ddl {NOMS_DDL[ddl] if 0 <= ddl < NB_DDL else ddl} de la "
                    f"liaison {nom} n'est pas libre."
                )
            ddls.append(ddl)
        resolus.append((c.liaison_a, ddls[0], c.liaison_b, ddls[1], c.rapport))
    return resolus


def calculer_mobilite(
    description: DescriptionMecanisme,
    *,
    tolerance: float = TOLERANCE_RANG_RELATIVE,
    point_reduction: np.ndarray | None = None,
) -> ResultatMobilite:
    """EX-21 : Kc de dimension (6μ + n_couplages) × Ic, rc par SVD, m = Ic − rc, h = Ec − rc."""
    graphe = construire_graphe(description)
    point = _point_reduction(description) if point_reduction is None else point_reduction
    inconnues = tuple(DdlLiaison(x.nom, d) for x in description.liaisons for d in x.ddl_libres)
    colonne_de = {(i.liaison, i.ddl): k for k, i in enumerate(inconnues)}
    couplages = _couplages_explicites(description)
    ec = 6 * graphe.mu + len(couplages)
    kc = np.zeros((ec, len(inconnues)))
    for k, cycle in enumerate(graphe.cycles):
        lignes = slice(6 * k, 6 * k + 6)
        for nom, signe in cycle.liaisons:
            x = description.liaison(nom)
            for d in x.ddl_libres:
                kc[lignes, colonne_de[(nom, d)]] += signe * _colonne(x, d, point, False)
    for j, (la, da, lb, db, rapport) in enumerate(couplages):
        ligne = 6 * graphe.mu + j
        kc[ligne, colonne_de[(lb, db)]] += 1.0
        kc[ligne, colonne_de[(la, da)]] -= rapport
    rc, s = _rang(kc, tolerance)
    ic = len(inconnues)
    return ResultatMobilite(
        ic=ic,
        rc=rc,
        m=ic - rc,
        h=ec - rc,
        ec=ec,
        mu=graphe.mu,
        nb_couplages=len(couplages),
        inconnues=inconnues,
        matrice=kc,
        valeurs_singulieres=s,
        graphe=graphe,
    )


def _description_cycles(resultat: ResultatMobilite) -> str:
    cycles = resultat.graphe.cycles
    if not cycles:
        return "aucun cycle"
    return " ; ".join(
        f"cycle {i} : " + " – ".join(nom for nom, _ in c.liaisons) for i, c in enumerate(cycles, 1)
    )


def verifier_avant_simulation(
    resultat: ResultatMobilite, mode: Mode, n_lois: int, hyperstatique_autorise: bool
) -> Decision:
    """EX-22 : garde-fou pur (aucun appel au moteur), message pédagogique en français."""
    refus: list[str] = []
    notes: list[str] = []
    if resultat.h > 0:
        base = (
            f"Le mécanisme est hyperstatique (h = {resultat.h}) : les liaisons choisies imposent "
            f"{resultat.h} équation(s) redondante(s). Liaisons concernées, "
            f"{_description_cycles(resultat)}."
        )
        if mode is Mode.DYNAMIQUE:
            refus.append(
                base + " En dynamique, les efforts de liaison sont indéterminés : revoyez le "
                "choix des liaisons (par exemple une rotule remplacée par une linéaire annulaire "
                "bien orientée)."
            )
        elif hyperstatique_autorise:
            notes.append(
                f"Option « Hyperstatique autorisé » : {resultat.h} équation(s) redondante(s) "
                "seront retirées ; le mouvement est celui du mécanisme réel si ses dimensions "
                "sont compatibles."
            )
        else:
            refus.append(
                base + " Revoyez le choix des liaisons, ou cochez « Hyperstatique autorisé » "
                "pour une simulation cinématique."
            )
    if n_lois != resultat.m:
        texte = (
            f"{n_lois} loi(s) d'entrée pour une mobilité m = {resultat.m} : il faut exactement "
            "une loi par mobilité."
        )
        if mode is Mode.CINEMATIQUE:
            refus.append("Simulation cinématique impossible : " + texte)
        else:
            notes.append("Attention, " + texte)
    if refus:
        return Decision(False, " ".join(refus))
    return Decision(True, " ".join(notes), avertissement=bool(notes))


def _statique(
    description: DescriptionMecanisme, resultat: ResultatMobilite, point: np.ndarray
) -> tuple[np.ndarray, list[DdlLiaison], int]:
    """Matrice d'équilibre des solides mobiles ; colonnes = couplages d'abord, puis ddl bloqués.

    Retourne (A, ddl bloqués dans l'ordre des colonnes bloquées, nombre de colonnes couplage).
    """
    g = resultat.graphe
    fixes = set(g.solides_bati)
    mobiles = [s.identifiant for s in description.solides if s.identifiant not in fixes]
    ligne_de = {ident: 6 * k for k, ident in enumerate(mobiles)}

    def ajouter(col: np.ndarray, x: LiaisonGraphe, w: np.ndarray, facteur: float) -> None:
        if x.solide_b in ligne_de:
            col[ligne_de[x.solide_b] : ligne_de[x.solide_b] + 6] += facteur * w
        if x.solide_a in ligne_de:
            col[ligne_de[x.solide_a] : ligne_de[x.solide_a] + 6] -= facteur * w

    colonnes: list[np.ndarray] = []
    for la, da, lb, db, rapport in _couplages_explicites(description):
        col = np.zeros(6 * len(mobiles))
        xa, xb = description.liaison(la), description.liaison(lb)
        ajouter(col, xb, _colonne(xb, db, point, True), 1.0)
        ajouter(col, xa, _colonne(xa, da, point, True), -rapport)
        colonnes.append(col)
    nb_couplages = len(colonnes)
    bloques: list[DdlLiaison] = []
    for x in description.liaisons:
        for d in range(NB_DDL):
            if x.ddl_bloques[d] == 1:
                col = np.zeros(6 * len(mobiles))
                ajouter(col, x, _colonne(x, d, point, True), 1.0)
                colonnes.append(col)
                bloques.append(DdlLiaison(x.nom, d))
    a = np.column_stack(colonnes) if colonnes else np.zeros((6 * len(mobiles), 0))
    return a, bloques, nb_couplages


def designer_ddl_redondants(
    description: DescriptionMecanisme,
    resultat: ResultatMobilite,
    *,
    tolerance: float = TOLERANCE_RANG_RELATIVE,
) -> tuple[DdlLiaison, ...]:
    """EX-23 (calcul) : h ddl bloqués à libérer pour retirer les h équations redondantes.

    Côté statique : inconnues Is = Σ ddl bloqués (+ un effort par couplage), matrice d'équilibre
    A des solides mobiles, rs = rang(A), h = Is − rs. Les colonnes dépendantes sont repérées par
    une orthogonalisation de Gram-Schmidt à pivot (colonne de plus grand résidu d'abord, couplages
    retenus en premier) ; les h colonnes non retenues sont les ddl à libérer. Libérer ces ddl
    laisse rs inchangé, donc m inchangé, et amène h à 0.
    """
    if resultat.h == 0:
        return ()
    a, bloques, nb_couplages = _statique(description, resultat, _point_reduction(description))
    residus = a.astype(float).copy()
    seuil = tolerance * max(float(np.max(np.linalg.norm(a, axis=0))), 1.0e-300)
    retenues = 0

    def retenir(j: int) -> None:
        nonlocal retenues
        q = residus[:, j] / np.linalg.norm(residus[:, j])
        residus[:] -= np.outer(q, q @ residus)
        retenues += 1

    for j in range(nb_couplages):
        if np.linalg.norm(residus[:, j]) <= seuil:
            raise ErreurMobilite(
                "Hyperstatisme dû à des couplages redondants : aucun ddl de liaison à libérer, "
                "retirez le ou les couplages en double."
            )
        retenir(j)
    candidates = set(range(nb_couplages, a.shape[1]))
    while candidates:
        j = max(candidates, key=lambda c: float(np.linalg.norm(residus[:, c])))
        if np.linalg.norm(residus[:, j]) <= seuil:
            break
        retenir(j)
        candidates.discard(j)
    designes = tuple(bloques[j - nb_couplages] for j in sorted(candidates))
    if len(designes) != resultat.h:
        raise ErreurMobilite(
            f"Incohérence statique/cinématique : {len(designes)} ddl redondants désignés pour "
            f"h = {resultat.h}."
        )
    return designes


def liberer(
    description: DescriptionMecanisme, ddl: tuple[DdlLiaison, ...] | list[DdlLiaison]
) -> DescriptionMecanisme:
    """Nouvelle description où les ddl donnés sont libérés (ddl bloqué → libre)."""
    a_liberer: dict[str, set[int]] = {}
    for x in ddl:
        a_liberer.setdefault(x.liaison, set()).add(x.ddl)
    # ddl par défaut des couplages figés avant libération (l'indice du premier libre peut changer)
    couplages = tuple(
        replace(c, ddl_a=da, ddl_b=db)
        for c, (_, da, _, db, _) in zip(
            description.couplages, _couplages_explicites(description), strict=True
        )
    )
    liaisons = tuple(
        replace(
            x,
            ddl_bloques=tuple(
                0 if d in a_liberer.get(x.nom, ()) else b for d, b in enumerate(x.ddl_bloques)
            ),
        )
        for x in description.liaisons
    )
    return replace(description, liaisons=liaisons, couplages=couplages)
