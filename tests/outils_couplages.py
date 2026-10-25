# SPDX-License-Identifier: GPL-3.0-or-later
"""Outils de test du lot 7 : mécanismes à couplages, frottement et rendement décrits à la main.

Les valeurs de référence des tests viennent de la SPEC (EX-14 à EX-16) ou d'un calcul analytique
écrit dans le test ; aucune ne sort du code testé.
"""

import math

import numpy as np

from meca3d.modele.actions import ActionExterieure, LoiEntree, NatureAction, Pilote
from meca3d.modele.etude import Etude, Reglages
from meca3d.modele.liaison import Liaison, TypeLiaison
from meca3d.modele.solide import Solide

RHO_ACIER = 7800.0
G = 9.81

X = np.array([1.0, 0.0, 0.0])
Z = np.array([0.0, 0.0, 1.0])


def bati() -> Solide:
    return Solide("Bati", True, 1.0, np.zeros(3), np.eye(3))


def cylindre(nom: str, rayon: float, longueur: float, centre: np.ndarray, axe: str = "z") -> Solide:
    """Cylindre plein d'acier d'axe x ou z (inertie au CdG, axes monde)."""
    masse = RHO_ACIER * math.pi * rayon**2 * longueur
    i_axe = 0.5 * masse * rayon**2
    i_trans = masse * (3.0 * rayon**2 + longueur**2) / 12.0
    diag = [i_axe, i_trans, i_trans] if axe == "x" else [i_trans, i_trans, i_axe]
    return Solide(nom, False, masse, np.asarray(centre, dtype=float), np.diag(diag))


def liaison(
    nom: str,
    type_liaison: TypeLiaison,
    a: str,
    b: str,
    centre: np.ndarray,
    axe: np.ndarray,
    **options: float,
) -> Liaison:
    """Liaison validée ; `options` : frottement, rayon_axe, pas, epsilon, valeur_pose."""
    valeur_pose = options.pop("valeur_pose", None)
    x = Liaison(
        nom=nom,
        type_sc="revolute",
        solide_a=a,
        solide_b=b,
        centre=np.asarray(centre, dtype=float),
        axe_sc=np.asarray(axe, dtype=float),
        valeur_pose=valeur_pose,
        type=type_liaison,
    )
    for cle, valeur in options.items():
        setattr(x, cle, valeur)
    x.valider()
    return x


def rampe(omega: float, montee: float = 0.2) -> str:
    """Angle θ(t) (rad) d'une montée en vitesse (cosinus relevé) jusqu'à ω, puis ω constant."""
    return (
        f"Piecewise(({omega / 2!r}*(t - {montee!r}/pi*sin(pi*t/{montee!r})), t < {montee!r}), "
        f"({omega / 2 * montee!r} + {omega!r}*(t - {montee!r}), True))"
    )


def pilote(nom_liaison: str, omega: float) -> Pilote:
    return Pilote(liaison=nom_liaison, loi=LoiEntree(rampe(omega)), grandeur=None)


def action(
    nom: str, solide: str, nature: NatureAction, composantes: tuple[str | float, ...]
) -> ActionExterieure:
    return ActionExterieure(nom=nom, solide=solide, nature=nature, composantes=composantes)


def couple(nom: str, solide: str, cz: str | float) -> ActionExterieure:
    return action(nom, solide, NatureAction.COUPLE, (0.0, 0.0, cz))


def reglages(duree: float, nb_pas: int, periode: float | None = None) -> Reglages:
    return Reglages(duree=duree, nb_pas=nb_pas, periode_ecriture=periode or duree / nb_pas)


# ------------------------------------------------------------------------------ réducteur
Z1, Z2 = 20, 60
MODULE = 0.002
R1, R2 = Z1 * MODULE / 2, Z2 * MODULE / 2
ENTRAXE = R1 + R2
EP = 0.010


def etude_reducteur(pesanteur: bool = False) -> Etude:
    """Deux roues sur le bâti (axes z parallèles), sans couplage (à ajouter par le test)."""
    solides = [
        bati(),
        cylindre("Roue1", R1, EP, np.zeros(3)),
        cylindre("Roue2", R2, EP, np.array([ENTRAXE, 0.0, 0.0])),
    ]
    liaisons = [
        liaison("L1", TypeLiaison.PIVOT, "Bati", "Roue1", np.zeros(3), Z, valeur_pose=0.0),
        liaison(
            "L2",
            TypeLiaison.PIVOT,
            "Bati",
            "Roue2",
            np.array([ENTRAXE, 0.0, 0.0]),
            Z,
            valeur_pose=0.0,
        ),
    ]
    etude = Etude(solides=solides, liaisons=liaisons)
    if not pesanteur:
        etude.pesanteur.actif = False
    return etude


# ------------------------------------------------------------------------------ vis-écrou
PAS = 0.005  # m par tour (SPEC EX-14)
LONGUEUR_VIS = 0.1


def etude_vis_ecrou() -> Etude:
    """Vis (pivot d'axe x) et écrou (glissière d'axe x) sur le bâti, sans couplage."""
    vis = cylindre("Vis", 0.01, LONGUEUR_VIS, np.zeros(3), axe="x")
    ecrou = Solide("Ecrou", False, 0.1, np.array([0.0, 0.0, 0.0]), np.diag([1e-4, 1e-4, 1e-4]))
    liaisons = [
        liaison("L_vis", TypeLiaison.PIVOT, "Bati", "Vis", np.zeros(3), X, valeur_pose=0.0),
        liaison("L_ecrou", TypeLiaison.GLISSIERE, "Bati", "Ecrou", np.zeros(3), X, valeur_pose=0.0),
    ]
    etude = Etude(solides=[bati(), vis, ecrou], liaisons=liaisons)
    etude.pesanteur.actif = False
    return etude


def etude_helicoidale(pas: float | None = PAS) -> Etude:
    """Vis sur une hélicoïdale (axe x) liée au bâti."""
    vis = cylindre("Vis", 0.01, LONGUEUR_VIS, np.zeros(3), axe="x")
    options: dict[str, float] = {"valeur_pose": 0.0}
    if pas is not None:
        options["pas"] = pas
    liaisons = [liaison("L_hel", TypeLiaison.HELICOIDALE, "Bati", "Vis", np.zeros(3), X, **options)]
    etude = Etude(solides=[bati(), vis], liaisons=liaisons)
    etude.pesanteur.actif = False
    return etude


# ------------------------------------------------------------------------------ épicycloïdal
ZS, ZP = 20, 40
R_SATELLITE = 0.04


def etude_epicycloidal() -> Etude:
    """Porte-satellites (pivot sur le bâti), planétaire et satellite (pivots sur le porte-
    satellites), axes z parallèles ; engrenage extérieur planétaire-satellite, k = Zs/Zp = 1/2."""
    entraxe = 0.06
    solides = [
        bati(),
        cylindre("Porte", 0.05, 0.01, np.zeros(3)),
        cylindre("Planetaire", 0.02, 0.01, np.array([0.0, 0.0, 0.02])),
        cylindre("Satellite", R_SATELLITE, 0.01, np.array([entraxe, 0.0, 0.02])),
    ]
    liaisons = [
        liaison("Lc", TypeLiaison.PIVOT, "Bati", "Porte", np.zeros(3), Z, valeur_pose=0.0),
        liaison(
            "Ls",
            TypeLiaison.PIVOT,
            "Porte",
            "Planetaire",
            np.array([0.0, 0.0, 0.02]),
            Z,
            valeur_pose=0.0,
        ),
        liaison(
            "Lp",
            TypeLiaison.PIVOT,
            "Porte",
            "Satellite",
            np.array([entraxe, 0.0, 0.02]),
            Z,
            valeur_pose=0.0,
        ),
    ]
    etude = Etude(solides=solides, liaisons=liaisons)
    etude.pesanteur.actif = False
    return etude
