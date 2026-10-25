# SPDX-License-Identifier: GPL-3.0-or-later
"""Rang cinématique évalué le long du mouvement (Q8) : configuration d'import singulière.

Problème. Le rang rc de Kc (EX-21) dépend de la configuration : en position singulière (centres
de pivots alignés d'un parallélogramme articulé, par exemple) il chute, et m et h calculés à
l'import sont faux (m trop grand, h trop grand). Perturber les centres au hasard masquerait les
géométries voulues (axes parallèles) ; il faut donc rester sur la variété des configurations
réellement atteintes par le mécanisme.

Méthode (pure, sans moteur, déterministe). Les inconnues sont les déplacements rigides des
solides mobiles (vecteur de rotation et translation). Les équations de fermeture annulent, pour
chaque ddl bloqué de chaque liaison, la composante correspondante du déplacement relatif exprimé
dans la base de liaison liée au solide a. À l'import, les directions du noyau du jacobien (mobilité
instantanée) servent de directions d'exploration : un pas de petite amplitude est suivi d'une
projection de Gauss-Newton (moindres carrés de norme minimale, donc valable en présence de
redondances) sur la variété de fermeture. Le rang de Kc est recalculé dans chaque configuration
atteinte et le rang MAXIMAL est retenu (le rang est semi-continu inférieurement : le rang
générique est le plus grand). L'élève est prévenu quand le rang varie.

Limites : seuls les ddl bloqués interviennent (couplages ignorés pour le déplacement, ils
n'ajoutent que des lignes indépendantes de la configuration) ; la paramétrisation des rotations
est celle du vecteur rotation, exacte pour les liaisons à un ddl de rotation et du second ordre
pour la rotule à doigt ; un point singulier isolé qui n'est pas dans le voisinage de l'import
n'est pas détecté ; un mécanisme de mobilité réelle nulle n'est pas exploré (aucune direction).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace

import numpy as np

from meca3d.graphe.graphe import DescriptionMecanisme, LiaisonGraphe
from meca3d.graphe.mobilite import (
    TOLERANCE_RANG_RELATIVE,
    ResultatMobilite,
    calculer_mobilite,
)

# Amplitude des pas d'exploration : rad pour les rotations, fraction de la taille du mécanisme
# pour les translations. Deux amplitudes (×1 et ×3) pour échapper à un voisinage trop singulier.
AMPLITUDE_EXPLORATION = 0.1
FACTEURS_AMPLITUDE = (1.0, 3.0)
NB_DIRECTIONS_ALEATOIRES = 3  # combinaisons du noyau, graine fixe : résultat reproductible
GRAINE = 20261025
MAX_CONFIGURATIONS = 24
# Jacobien par différences centrées (pas EPS_DIFF) ; rang du jacobien pour le noyau
EPS_DIFF = 1e-6
TOLERANCE_NOYAU = 1e-6
TOLERANCE_FERMETURE = 1e-11
ITERATIONS_MAX = 40
DEPLACEMENT_MAX = 1.5  # rejet d'une projection qui s'éloigne trop (en rad / taille)


@dataclass(frozen=True, eq=False)
class MobiliteRobuste:
    """Mobilité et hyperstatisme au rang maximal atteint le long du mouvement (Q8).

    `resultat` / `description` : configuration de rang maximal (l'import en cas d'égalité) ;
    ses m et h sont ceux à afficher, et la description sert à désigner les ddl redondants.
    """

    resultat: ResultatMobilite
    description: DescriptionMecanisme
    import_: ResultatMobilite
    rangs: tuple[int, ...]  # rangs des configurations explorées (hors import)
    nb_configurations: int
    avertissements: tuple[str, ...]

    @property
    def m(self) -> int:
        return self.resultat.m

    @property
    def h(self) -> int:
        return self.resultat.h

    @property
    def rang_import(self) -> int:
        return self.import_.rc

    @property
    def singuliere_a_l_import(self) -> bool:
        return self.import_.rc < self.resultat.rc

    @property
    def rang_variable(self) -> bool:
        return len({self.import_.rc, *self.rangs}) > 1


def _skew(w: np.ndarray) -> np.ndarray:
    return np.array([[0.0, -w[2], w[1]], [w[2], 0.0, -w[0]], [-w[1], w[0], 0.0]])


def _exp_rotation(w: np.ndarray) -> np.ndarray:
    angle = float(np.linalg.norm(w))
    k = _skew(w)
    if angle < 1e-12:
        return np.eye(3) + k
    return np.eye(3) + math.sin(angle) / angle * k + (1.0 - math.cos(angle)) / angle**2 * (k @ k)


def _log_rotation(r: np.ndarray) -> np.ndarray:
    angle = math.acos(max(-1.0, min(1.0, (float(np.trace(r)) - 1.0) / 2.0)))
    v = np.array([r[2, 1] - r[1, 2], r[0, 2] - r[2, 0], r[1, 0] - r[0, 1]])
    if angle < 1e-9:
        return v / 2.0
    return v * angle / (2.0 * math.sin(angle))


class _Fermeture:
    """Équations de fermeture et déplacements rigides des solides mobiles."""

    def __init__(self, description: DescriptionMecanisme) -> None:
        self.description = description
        mobiles = [s.identifiant for s in description.solides if not s.fixe]
        self.indice = {nom: k for k, nom in enumerate(mobiles)}
        self.nb_inconnues = 6 * len(mobiles)
        centres = [x.centre for x in description.liaisons]
        taille = 0.0
        for i, a in enumerate(centres):
            for b in centres[i + 1 :]:
                taille = max(taille, float(np.linalg.norm(a - b)))
        self.taille = taille if taille > 0.0 else 1.0

    def poses(self, q: np.ndarray) -> dict[str, tuple[np.ndarray, np.ndarray]]:
        """Rotation et translation de chaque solide mobile ; q = [w, d / taille] par solide."""
        resultat = {}
        for nom, k in self.indice.items():
            w = q[6 * k : 6 * k + 3]
            d = self.taille * q[6 * k + 3 : 6 * k + 6]
            resultat[nom] = (_exp_rotation(w), d)
        return resultat

    @staticmethod
    def _pose(
        poses: dict[str, tuple[np.ndarray, np.ndarray]], nom: str
    ) -> tuple[np.ndarray, np.ndarray]:
        return poses.get(nom, (np.eye(3), np.zeros(3)))

    def residu(self, q: np.ndarray) -> np.ndarray:
        poses = self.poses(q)
        lignes: list[float] = []
        for x in self.description.liaisons:
            ra, da = self._pose(poses, x.solide_a)
            rb, db = self._pose(poses, x.solide_b)
            relatif = ra.T @ ((rb @ x.centre + db) - (ra @ x.centre + da))
            en_liaison = x.base.T @ relatif
            rotation = _log_rotation(x.base.T @ (ra.T @ rb) @ x.base)
            for k, bloque in enumerate(x.ddl_bloques):
                if bloque:
                    lignes.append(float(en_liaison[k] if k < 3 else rotation[k - 3]))
        return np.array(lignes)

    def jacobien(self, q: np.ndarray) -> np.ndarray:
        colonnes = []
        for i in range(self.nb_inconnues):
            dq = np.zeros(self.nb_inconnues)
            dq[i] = EPS_DIFF
            colonnes.append((self.residu(q + dq) - self.residu(q - dq)) / (2.0 * EPS_DIFF))
        if not colonnes:
            return np.zeros((len(self.residu(q)), 0))
        return np.column_stack(colonnes)

    def projeter(self, q: np.ndarray) -> np.ndarray | None:
        """Gauss-Newton de norme minimale vers la variété de fermeture ; None si échec."""
        for _ in range(ITERATIONS_MAX):
            f = self.residu(q)
            if f.size == 0 or float(np.linalg.norm(f)) < TOLERANCE_FERMETURE:
                return q
            pas = np.linalg.lstsq(self.jacobien(q), -f, rcond=1e-9)[0]
            q = q + pas
            if float(np.linalg.norm(q)) > DEPLACEMENT_MAX:
                return None
        return q if float(np.linalg.norm(self.residu(q))) < TOLERANCE_FERMETURE else None

    def decrire(self, q: np.ndarray) -> DescriptionMecanisme:
        """Description dans la configuration q (centres et bases suivent le solide a)."""
        poses = self.poses(q)
        liaisons: list[LiaisonGraphe] = []
        for x in self.description.liaisons:
            ra, da = self._pose(poses, x.solide_a)
            liaisons.append(replace(x, centre=ra @ x.centre + da, base=ra @ x.base))
        return replace(self.description, liaisons=tuple(liaisons))


def _noyau(jacobien: np.ndarray) -> np.ndarray:
    if jacobien.shape[1] == 0:
        return np.zeros((0, 0))
    if jacobien.shape[0] == 0:
        return np.eye(jacobien.shape[1])
    _, s, vt = np.linalg.svd(jacobien)
    rang = int(np.sum(s > TOLERANCE_NOYAU * s[0])) if s[0] > 0.0 else 0
    return vt[rang:].T


def explorer_configurations(description: DescriptionMecanisme) -> list[DescriptionMecanisme]:
    """Configurations voisines de l'import, atteintes par le mouvement (variété de fermeture)."""
    fermeture = _Fermeture(description)
    n = fermeture.nb_inconnues
    if n == 0 or not description.liaisons:
        return []
    noyau = _noyau(fermeture.jacobien(np.zeros(n)))
    if noyau.shape[1] == 0:
        return []
    generateur = np.random.default_rng(GRAINE)
    directions = [noyau[:, k] for k in range(noyau.shape[1])]
    directions += [
        noyau @ generateur.standard_normal(noyau.shape[1]) for _ in range(NB_DIRECTIONS_ALEATOIRES)
    ]
    configurations: list[DescriptionMecanisme] = []
    for direction in directions:
        direction = direction / np.linalg.norm(direction)
        for facteur in FACTEURS_AMPLITUDE:
            if len(configurations) >= MAX_CONFIGURATIONS:
                return configurations
            q = fermeture.projeter(facteur * AMPLITUDE_EXPLORATION * direction)
            if q is not None:
                configurations.append(fermeture.decrire(q))
    return configurations


def _avertissement(
    import_: ResultatMobilite, retenu: ResultatMobilite, rangs: tuple[int, ...]
) -> str | None:
    if import_.rc < retenu.rc:
        return (
            "Configuration d'import singulière (axes ou centres alignés, point mort) : le rang "
            f"du système cinématique vaut rc = {import_.rc} à l'import et rc = {retenu.rc} dans "
            "les configurations atteintes par le mouvement. La mobilité et l'hyperstatisme "
            f"affichés sont ceux du rang maximal : m = {retenu.m}, h = {retenu.h} "
            f"(à l'import : m = {import_.m}, h = {import_.h})."
        )
    if min(rangs, default=import_.rc) < import_.rc:
        return (
            f"Le rang du système varie le long du mouvement (rc de {min(rangs)} à {import_.rc}) : "
            "des configurations singulières existent près de la configuration d'import. "
            f"Valeurs retenues, au rang maximal : m = {import_.m}, h = {import_.h}."
        )
    return None


def mobilite_robuste(
    description: DescriptionMecanisme, *, tolerance: float = TOLERANCE_RANG_RELATIVE
) -> MobiliteRobuste:
    """Q8 : (m, h) au rang maximal sur l'import et les configurations atteintes par le mouvement."""
    import_ = calculer_mobilite(description, tolerance=tolerance)
    configurations = explorer_configurations(description)
    resultats = [(c, calculer_mobilite(c, tolerance=tolerance)) for c in configurations]
    rangs = tuple(r.rc for _, r in resultats)
    retenue, retenu = description, import_
    for c, r in resultats:
        if r.rc > retenu.rc:
            retenue, retenu = c, r
    note = _avertissement(import_, retenu, rangs)
    return MobiliteRobuste(
        resultat=retenu,
        description=retenue,
        import_=import_,
        rangs=rangs,
        nb_configurations=len(configurations),
        avertissements=() if note is None else (note,),
    )
