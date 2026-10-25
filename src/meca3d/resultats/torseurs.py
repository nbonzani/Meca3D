# SPDX-License-Identifier: GPL-3.0-or-later
"""Torseurs de liaison (EX-50) : statique {i→j} et cinématique {V j/i}, au centre de la liaison.

Seul endroit où la convention Exudyn (action du solide b sur le solide a, en base de liaison
liée à a) est convertie en {i→j} (ARCHITECTURE § 5). Les composantes nulles par construction (ddl
libres, hors pilote, pour le torseur statique ; ddl bloqués pour le torseur cinématique) sont
mises à zéro exactement.
"""

import numpy as np

from meca3d.modele.etude import Etude
from meca3d.modele.liaison import Liaison, TypeLiaison
from meca3d.moteur.base import ResultatsBruts
from meca3d.resultats.capteurs import etat_solide


def _indice_pilote(etude: Etude, liaison: Liaison) -> int | None:
    """Indice (0 ou 3) du ddl imposé par une loi d'entrée sur cette liaison, sinon None."""
    for pilote in etude.pilotes:
        if pilote.liaison == liaison.nom:
            grandeur = pilote.grandeur
            if grandeur is None:
                grandeur = "position" if liaison.type is TypeLiaison.GLISSIERE else "angle"
            return 0 if grandeur == "position" else 3
    return None


def masque_nul_par_construction(etude: Etude, liaison: str, statique: bool) -> np.ndarray:
    """Six booléens : composantes nulles par construction en base de liaison (EX-50).

    Statique [Fx Fy Fz Mx My Mz] : ddl libres de la liaison, hors pilote. Cinématique
    [Ωx Ωy Ωz Vx Vy Vz] : ddl bloqués. Valable en base de liaison seulement : une fois tourné en
    base monde, un torseur n'est plus nul par construction.
    """
    lia = etude.liaison(liaison)
    pilote = _indice_pilote(etude, lia)
    masque = np.zeros(6, dtype=bool)
    for ddl, bloque in enumerate(lia.ddl_bloques()):  # ddl : [Tx Ty Tz Rx Ry Rz]
        if statique:
            masque[ddl] = bloque == 0 and ddl != pilote
        elif bloque:
            masque[(ddl + 3) % 6] = True  # Tx -> Vx (3), Rx -> Ωx (0)
    return masque


def _base_liaison_a_chaque_instant(
    etude: Etude, resultats: ResultatsBruts, lia: Liaison
) -> np.ndarray:
    """Base de liaison liée au solide a, en repère monde, (n, 3, 3)."""
    return etat_solide(etude, resultats, lia.solide_a).rotation @ lia.base()


def torseur_statique(
    etude: Etude,
    resultats: ResultatsBruts,
    liaison: str,
    de: str | None = None,
    base: str = "monde",
) -> np.ndarray:
    """Torseur {de → autre solide} au centre, (n, 6) = [Fx Fy Fz Mx My Mz].

    `de` : solide agissant i (défaut : solide a). `base` : « monde » ou « liaison » (base de
    liaison liée au solide a). Les composantes sur les ddl libres hors pilote sont exactement
    nulles.
    """
    lia = etude.liaison(liaison)
    de = lia.solide_a if de is None else de
    if de not in (lia.solide_a, lia.solide_b):
        raise ValueError(f"{de} n'est pas un solide de la liaison {liaison}.")
    if base not in ("monde", "liaison"):
        raise ValueError("base : « monde » ou « liaison » attendu.")
    if liaison not in resultats.forces:
        raise ValueError(f"Aucun effort pour la liaison {liaison} (mode cinématique ?).")
    signe = -1.0 if de == lia.solide_a else 1.0  # brut = action de b sur a
    force = signe * resultats.forces[liaison]
    moment = signe * resultats.moments[liaison]
    pilote = _indice_pilote(etude, lia)
    for ddl, bloque in enumerate(lia.ddl_bloques()):
        if bloque == 0 and ddl != pilote:
            (force if ddl < 3 else moment)[:, ddl % 3] = 0.0
    if base == "monde":
        r = _base_liaison_a_chaque_instant(etude, resultats, lia)
        force = np.einsum("nij,nj->ni", r, force)
        moment = np.einsum("nij,nj->ni", r, moment)
    return np.hstack([force, moment])


def torseur_cinematique(
    etude: Etude,
    resultats: ResultatsBruts,
    liaison: str,
    i: str | None = None,
    base: str = "monde",
) -> np.ndarray:
    """Torseur cinématique {V j/i} au centre, (n, 6) = [Ωx Ωy Ωz Vx Vy Vz] (rad/s, m/s).

    `i` : solide de référence (défaut : solide a), j est l'autre solide. V est la vitesse relative
    du point de j situé au centre de la liaison. Les composantes bloquées par la liaison sont
    exactement nulles. `base` : « monde » ou « liaison » (base liée au solide a).
    """
    lia = etude.liaison(liaison)
    i = lia.solide_a if i is None else i
    if i not in (lia.solide_a, lia.solide_b):
        raise ValueError(f"{i} n'est pas un solide de la liaison {liaison}.")
    if base not in ("monde", "liaison"):
        raise ValueError("base : « monde » ou « liaison » attendu.")
    a = etat_solide(etude, resultats, lia.solide_a)
    b = etat_solide(etude, resultats, lia.solide_b)
    centre, v_a, _ = a.point(lia.centre)
    v_b = b.v + np.cross(b.omega, centre - b.x)
    omega = b.omega - a.omega  # {V b/a}
    vitesse = v_b - v_a
    if i == lia.solide_b:
        omega, vitesse = -omega, -vitesse
    r = _base_liaison_a_chaque_instant(etude, resultats, lia)
    omega = np.einsum("nji,nj->ni", r, omega)  # base de liaison : Rᵀ·vecteur
    vitesse = np.einsum("nji,nj->ni", r, vitesse)
    for ddl, bloque in enumerate(lia.ddl_bloques()):
        if bloque:
            (vitesse if ddl < 3 else omega)[:, ddl % 3] = 0.0
    if base == "monde":
        omega = np.einsum("nij,nj->ni", r, omega)
        vitesse = np.einsum("nij,nj->ni", r, vitesse)
    return np.hstack([omega, vitesse])
