# SPDX-License-Identifier: GPL-3.0-or-later
"""Graphe des liaisons (EX-20) et description minimale du mécanisme consommée par `graphe/`.

La description est découplée de `modele/` : `depuis_etude` est la seule fonction qui lit l'étude.

Choix du bâti : tous les solides fixes sont fusionnés en un seul nœud. Ils ont la même vitesse
nulle, donc une boucle qui passe de l'un à l'autre est une boucle cinématique fermée : sans
fusion, un solide lié à deux solides fixes ne formerait aucun cycle (μ = 0) et l'hyperstatisme
de la boucle serait perdu.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import TYPE_CHECKING

import networkx as nx
import numpy as np

if TYPE_CHECKING:
    from meca3d.modele.etude import Etude

NB_DDL = 6  # [Tx Ty Tz Rx Ry Rz] dans la base de liaison (EX-10)
INDICE_TX = 0
INDICE_RX = 3
# Rapport nominal du couplage interne d'une hélicoïdale : le pas ne change pas le rang tant
# qu'il est non nul (SPEC EX-10 : Tx = p·Rx / 2π).
RAPPORT_HELICE_NOMINAL = 1.0


@dataclass(frozen=True)
class SolideGraphe:
    identifiant: str
    nom: str
    fixe: bool


@dataclass(frozen=True, eq=False)
class LiaisonGraphe:
    """Liaison entre `solide_a` et `solide_b` (identifiants).

    `ddl_bloques` : [Tx Ty Tz Rx Ry Rz] en base de liaison (1 = bloqué). `centre` (3,) en repère
    monde. `base` (3×3) : colonnes = axes locaux en repère monde. Les inconnues cinématiques sont
    celles du mouvement de `solide_b` par rapport à `solide_a`.
    """

    nom: str
    solide_a: str
    solide_b: str
    ddl_bloques: tuple[int, ...]
    centre: np.ndarray
    base: np.ndarray

    def __post_init__(self) -> None:
        ddl = tuple(int(x) for x in self.ddl_bloques)
        if len(ddl) != NB_DDL or any(x not in (0, 1) for x in ddl):
            raise ValueError(f"Liaison {self.nom} : 6 ddl bloqués (0 ou 1) attendus, reçu {ddl}.")
        centre = np.array(self.centre, dtype=float)
        base = np.array(self.base, dtype=float)
        if centre.shape != (3,) or base.shape != (3, 3):
            raise ValueError(f"Liaison {self.nom} : centre (3,) et base (3, 3) attendus.")
        centre.flags.writeable = False
        base.flags.writeable = False
        object.__setattr__(self, "ddl_bloques", ddl)
        object.__setattr__(self, "centre", centre)
        object.__setattr__(self, "base", base)

    @property
    def ddl_libres(self) -> tuple[int, ...]:
        return tuple(i for i, b in enumerate(self.ddl_bloques) if b == 0)


@dataclass(frozen=True)
class CouplageGraphe:
    """Équation q̇(liaison_b, ddl_b) = rapport · q̇(liaison_a, ddl_a), une ligne dans Kc (EX-21).

    `ddl_a` / `ddl_b` : indice 0..5 d'un ddl LIBRE ; None = premier ddl libre de la liaison.
    """

    liaison_a: str
    liaison_b: str
    ddl_a: int | None = None
    ddl_b: int | None = None
    rapport: float = -1.0


@dataclass(frozen=True, eq=False)
class DescriptionMecanisme:
    solides: tuple[SolideGraphe, ...]
    liaisons: tuple[LiaisonGraphe, ...]
    couplages: tuple[CouplageGraphe, ...] = ()

    def liaison(self, nom: str) -> LiaisonGraphe:
        for x in self.liaisons:
            if x.nom == nom:
                return x
        raise KeyError(f"Liaison inconnue : {nom}")


@dataclass(frozen=True)
class Cycle:
    """Cycle indépendant : liaisons parcourues avec leur signe (+1 si a → b, −1 si b → a)."""

    liaisons: tuple[tuple[str, int], ...]
    solides: tuple[str, ...]  # nœuds visités, dans l'ordre du parcours


@dataclass(frozen=True, eq=False)
class ResultatGraphe:
    graphe: nx.MultiGraph
    bati: str | None
    solides_bati: tuple[str, ...]
    nb_solides: int  # nœuds, bâti fusionné compris
    nb_liaisons: int
    nb_composantes: int
    mu: int
    mu_par_composante: tuple[int, ...]
    cycles: tuple[Cycle, ...]
    isoles: tuple[str, ...]


def construire_graphe(description: DescriptionMecanisme) -> ResultatGraphe:
    """EX-20 : multigraphe des liaisons, μ = L − S + 1 par composante, base de cycles."""
    identifiants = [s.identifiant for s in description.solides]
    if len(set(identifiants)) != len(identifiants):
        raise ValueError("Identifiants de solides en double.")
    noms = [x.nom for x in description.liaisons]
    if len(set(noms)) != len(noms):
        raise ValueError("Noms de liaisons en double.")
    fixes = tuple(s.identifiant for s in description.solides if s.fixe)
    bati = fixes[0] if fixes else None

    def noeud(identifiant: str) -> str:
        if identifiant not in identifiants:
            raise ValueError(f"Solide inconnu : {identifiant}.")
        return bati if (identifiant in fixes and bati is not None) else identifiant

    g: nx.MultiGraph = nx.MultiGraph()
    for s in description.solides:
        n = noeud(s.identifiant)
        if n not in g:
            g.add_node(n, nom="Bâti" if n == bati else s.nom)
    for x in description.liaisons:
        g.add_edge(noeud(x.solide_a), noeud(x.solide_b), key=x.nom, a=noeud(x.solide_a))

    cycles: list[Cycle] = []
    mu_composantes: list[int] = []
    for comp in nx.connected_components(g):
        ordre = [n for n in g.nodes if n in comp]
        racine: str = bati if bati is not None and bati in comp else ordre[0]
        parent: dict[str, tuple[str, str] | None] = {racine: None}
        arbre: set[str] = set()
        file = deque([racine])
        while file:
            u = file.popleft()
            for _, v, cle in g.edges(u, keys=True):
                if v not in parent:
                    parent[v] = (u, cle)
                    arbre.add(cle)
                    file.append(v)
        nb_liaisons_comp = sum(1 for _, _, _ in g.subgraph(comp).edges(keys=True))
        mu_composantes.append(nb_liaisons_comp - len(comp) + 1)
        for x in description.liaisons:
            if noeud(x.solide_a) in comp and x.nom not in arbre:
                cycles.append(
                    _cycle_fondamental(g, parent, x.nom, noeud(x.solide_a), noeud(x.solide_b))
                )

    nb_liaisons = len(description.liaisons)
    isoles = tuple(n for n in g.nodes if g.degree(n) == 0)
    return ResultatGraphe(
        graphe=g,
        bati=bati,
        solides_bati=fixes,
        nb_solides=g.number_of_nodes(),
        nb_liaisons=nb_liaisons,
        nb_composantes=len(mu_composantes),
        mu=sum(mu_composantes),
        mu_par_composante=tuple(mu_composantes),
        cycles=tuple(cycles),
        isoles=isoles,
    )


def _ascendants(parent: dict[str, tuple[str, str] | None], n: str) -> list[str]:
    chaine = [n]
    while (p := parent[chaine[-1]]) is not None:
        chaine.append(p[0])
    return chaine


def _cycle_fondamental(
    g: nx.MultiGraph,
    parent: dict[str, tuple[str, str] | None],
    nom: str,
    na: str,
    nb: str,
) -> Cycle:
    """Cycle formé par la liaison `nom` (a → b) et le chemin de l'arbre de b vers a."""
    montee_b = _ascendants(parent, nb)
    montee_a = _ascendants(parent, na)
    commun = next(n for n in montee_b if n in montee_a)
    chemin = montee_b[: montee_b.index(commun) + 1] + list(
        reversed(montee_a[: montee_a.index(commun)])
    )
    liaisons: list[tuple[str, int]] = [(nom, 1)]
    for u, v in zip(chemin, chemin[1:], strict=False):
        pu, pv = parent[u], parent[v]
        cle = pu[1] if pu is not None and pu[0] == v else pv[1] if pv is not None else ""
        liaisons.append((cle, 1 if g.edges[u, v, cle]["a"] == u else -1))
    return Cycle(liaisons=tuple(liaisons), solides=(na, *chemin))


def depuis_etude(etude: Etude, couplages: tuple[CouplageGraphe, ...] = ()) -> DescriptionMecanisme:
    """Adapte une `Etude` (attributs publics actuels de `modele/`) à la description minimale.

    `couplages` : couplages EX-14 fournis par l'appelant (l'étude n'en porte pas encore). Une
    hélicoïdale reçoit son couplage interne Tx = p·Rx / 2π (rapport nominal). Une liaison sans
    type choisi lève la ValueError de `modele`.
    """
    solides = tuple(SolideGraphe(s.nom, s.nom, s.fixe) for s in etude.solides)
    liaisons = tuple(
        LiaisonGraphe(
            nom=x.nom,
            solide_a=x.solide_a,
            solide_b=x.solide_b,
            ddl_bloques=tuple(x.ddl_bloques()),
            centre=x.centre,
            base=x.base(),
        )
        for x in etude.liaisons
    )
    helices = tuple(
        CouplageGraphe(x.nom, x.nom, INDICE_RX, INDICE_TX, RAPPORT_HELICE_NOMINAL)
        for x in etude.liaisons
        if x.type is not None and x.type.value == "helicoidale"
    )
    return DescriptionMecanisme(
        solides=solides, liaisons=liaisons, couplages=(*helices, *couplages)
    )
