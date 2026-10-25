# SPDX-License-Identifier: GPL-3.0-or-later
"""Catalogue des 11 liaisons en grands déplacements (EX-10), via le moteur Exudyn.

Transpose les essais de prototypes/exudyn_bielle/test_liaisons.py : un solide relié au bâti par
une seule liaison, base de liaison inclinée, CdG décalé du centre, pesanteur oblique. On contrôle
les invariants géométriques physiques de la liaison à 1e-9, que les ddl libres ont bougé, qu'une
rotation d'au moins 0,3 rad a eu lieu quand une rotation est libre, et que les efforts sont nuls
sur les ddl libres.
"""

import math

import numpy as np
import pytest

from meca3d.modele.etude import Etude, Reglages
from meca3d.modele.liaison import DDL_BLOQUES, Liaison, TypeLiaison
from meca3d.modele.solide import Solide
from meca3d.moteur.base import ErreurLiaisonNonPriseEnCharge, ErreurModele
from meca3d.moteur.exudyn_dyn import MoteurExudynDyn

TOL_INVARIANT = 1e-9
TOL_EFFORT = 1e-9
SEUIL_LIBRE = 1e-5
ROTATION_MIN = 0.3  # rad

# Axe z SolidCraft et seconde direction obliques (monde), centre et CdG quelconques
AXE = np.array([0.3, -0.5, 0.8]) / np.linalg.norm([0.3, -0.5, 0.8])
DIRECTION = np.array([1.0, 0.4, -0.2])
CENTRE = np.array([0.2, -0.1, 0.3])
MASSE = 2.0
G = (3.0, -2.0, -9.0)

TYPES_A_DIRECTION = {TypeLiaison.ROTULE_A_DOIGT, TypeLiaison.LINEAIRE_RECTILIGNE}


def _rot_x(a: float) -> np.ndarray:
    c, s = math.cos(a), math.sin(a)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


def _rot_z(a: float) -> np.ndarray:
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def _etude(type_liaison: TypeLiaison) -> Etude:
    r = _rot_z(0.4) @ _rot_x(0.2)
    cdg = CENTRE + r @ np.array([0.05, 0.03, 0.02])
    inertie = r @ np.diag([0.01, 0.02, 0.03]) @ r.T  # axes monde, au CdG
    bati = Solide("Bati", True, 1.0, np.zeros(3), np.eye(3))
    corps = Solide("Corps", False, MASSE, cdg, inertie)
    liaison = Liaison(
        nom="L",
        type_sc="revolute",
        solide_a="Bati",
        solide_b="Corps",
        centre=CENTRE,
        axe_sc=AXE,
        valeur_pose=None,
        type=type_liaison,
        direction=DIRECTION if type_liaison in TYPES_A_DIRECTION else None,
    )
    liaison.valider()
    etude = Etude(solides=[bati, corps], liaisons=[liaison])
    etude.pesanteur.vecteur = G
    etude.reglages = Reglages(duree=0.6, nb_pas=1200, periode_ecriture=0.005)
    return etude


def _vecteur_rotation(a: np.ndarray) -> np.ndarray:
    angle = math.acos(max(-1.0, min(1.0, (np.trace(a) - 1.0) / 2.0)))
    if angle < 1e-12:
        return np.zeros(3)
    axe = np.array([a[2, 1] - a[1, 2], a[0, 2] - a[2, 0], a[1, 0] - a[0, 1]])
    return axe / (2.0 * math.sin(angle)) * angle


# Invariants physiques (d : déplacement du point initialement au centre, en base de liaison ;
# D[i, j] = e_i . (A e_j), A rotation du solide) qui doivent rester nuls.
INVARIANTS = {
    TypeLiaison.ENCASTREMENT: lambda d, D: [*d, *(D - np.eye(3)).ravel()],
    TypeLiaison.PIVOT: lambda d, D: [*d, D[0, 0] - 1],
    TypeLiaison.GLISSIERE: lambda d, D: [d[1], d[2], *(D - np.eye(3)).ravel()],
    TypeLiaison.PIVOT_GLISSANT: lambda d, D: [d[1], d[2], D[0, 0] - 1],
    TypeLiaison.ROTULE_A_DOIGT: lambda d, D: [*d, D[0, 1]],  # x_a perpendiculaire à y_b
    TypeLiaison.ROTULE: lambda d, D: [*d],
    TypeLiaison.APPUI_PLAN: lambda d, D: [d[2], D[2, 2] - 1],
    TypeLiaison.LINEAIRE_ANNULAIRE: lambda d, D: [d[1], d[2]],
    TypeLiaison.LINEAIRE_RECTILIGNE: lambda d, D: [d[2], D[2, 0]],
    TypeLiaison.PONCTUELLE: lambda d, D: [d[2]],
}

TYPES_ESSAI = [t for t in TypeLiaison if t is not TypeLiaison.HELICOIDALE]


# La pesanteur seule n'excite pas toutes les rotations libres : pour l'appui plan, tous les moments
# disponibles sont perpendiculaires à la normale. On lance alors le solide autour de la normale,
# vitesse compatible avec la liaison (rotation autour de l'axe passant par le centre).
VITESSE_ANGULAIRE_INITIALE = {TypeLiaison.APPUI_PLAN: 2.0}  # rad/s autour de z local


def _vitesses_initiales(etude: Etude, type_liaison: TypeLiaison):
    omega = VITESSE_ANGULAIRE_INITIALE.get(type_liaison)
    if omega is None:
        return None
    n = etude.liaison("L").base()[:, 2]
    w = omega * n
    v = np.cross(w, etude.solide("Corps").cdg - CENTRE)
    return {"Corps": (v, w)}


@pytest.mark.parametrize("type_liaison", TYPES_ESSAI, ids=lambda t: t.value)
def test_ex10_grands_deplacements(type_liaison: TypeLiaison) -> None:
    etude = _etude(type_liaison)
    liaison = etude.liaison("L")
    base = liaison.base()
    res = MoteurExudynDyn().simuler(
        etude, vitesses_initiales=_vitesses_initiales(etude, type_liaison)
    )
    rot = res.rotations["Corps"]  # (n, 3, 3)
    pos = res.positions["Corps"]
    cdg = etude.solide("Corps").cdg

    erreur_max = 0.0
    mouvement_max = np.zeros(6)
    angle_max = 0.0
    for a, p in zip(rot, pos, strict=True):
        point = p + a @ (CENTRE - cdg)
        d = base.T @ (point - CENTRE)
        grand_d = base.T @ a @ base
        erreur_max = max(erreur_max, float(np.abs(INVARIANTS[type_liaison](d, grand_d)).max()))
        mvt = np.concatenate([d, base.T @ _vecteur_rotation(a)])
        mouvement_max = np.maximum(mouvement_max, np.abs(mvt))
        angle_max = max(angle_max, float(np.linalg.norm(_vecteur_rotation(a))))
    assert erreur_max < TOL_INVARIANT

    bloques = np.array(DDL_BLOQUES[type_liaison], dtype=bool)
    assert (mouvement_max[~bloques] > SEUIL_LIBRE).all()
    if not bloques[3:].all():
        assert angle_max >= ROTATION_MIN

    efforts = np.hstack([res.forces["L"], res.moments["L"]])
    if (~bloques).any():  # encastrement : aucun ddl libre, rien à contrôler ici
        assert np.abs(efforts[:, ~bloques]).max() < TOL_EFFORT


def test_ex10_lineaire_rectiligne_transmet_un_torseur() -> None:
    """Deux ponctuelles : le torseur résultant est reporté sur les ddl bloqués (Tz, Ry)."""
    etude = _etude(TypeLiaison.LINEAIRE_RECTILIGNE)
    res = MoteurExudynDyn().simuler(etude)
    bloques = np.array(DDL_BLOQUES[TypeLiaison.LINEAIRE_RECTILIGNE], dtype=bool)
    efforts = np.hstack([res.forces["L"], res.moments["L"]])
    assert np.abs(efforts[:, bloques]).max() > 1e-3  # le torseur de liaison est bien transmis


def test_ex10_helicoidale_sans_pas_erreur_explicite() -> None:
    """Le couplage interne Tx = p·Rx / 2π exige le pas : sans lui, erreur de modèle explicite
    (l'essai positif de l'hélicoïdale est dans test_vis_ecrou.py)."""
    etude = _etude(TypeLiaison.HELICOIDALE)
    with pytest.raises(ErreurModele, match="pas de la liaison hélicoïdale n'est pas renseigné"):
        MoteurExudynDyn().simuler(etude)


def test_ex10_erreur_helicoidale_est_une_erreur_de_modele() -> None:
    assert issubclass(ErreurLiaisonNonPriseEnCharge, ErreurModele)


def test_ex10_pilote_sur_ddl_bloque_refuse() -> None:
    from meca3d.modele.actions import LoiEntree, Pilote

    etude = _etude(TypeLiaison.GLISSIERE)
    etude.liaison("L").valeur_pose = 0.0
    etude.pilotes = [Pilote(liaison="L", loi=LoiEntree("t"), grandeur="angle")]
    with pytest.raises(ErreurModele, match="bloqu"):
        MoteurExudynDyn().simuler(etude)
