# SPDX-License-Identifier: GPL-3.0-or-later
"""Animation du mouvement simulé dans SolidCraft et trajectoires de points (EX-53, EX-52, D14).

Moyen retenu au lot 1b : les poses calculées par Exudyn sont appliquées par `occurrence.move`
(`capture: false`, déplacement en attente : ni `dirty`, ni pile d'annulation), un `engine.batch`
par image ; la pose initiale est rendue par `component.revert_position`. L'animation restaure
TOUJOURS la pose (`terminer`, appelé en fin de lecture, à l'interruption et à la sortie du bloc
`with`) et n'enregistre JAMAIS la maquette. La logique est indépendante de Qt ; l'horloge et
l'attente sont injectables pour les tests.

Pose d'un solide (D15) : le repère du solide est celui de son composant SolidCraft, noté (R₀, o₀) à
l'import ; le centre de gravité est c₀ à l'import ; à l'instant t Exudyn donne la position x(t) du
CdG et la rotation R(t) (relative à la pose d'import). La transformation du composant est
    R(t)·R₀   et   x(t) + R(t)·(o₀ − c₀).
`occurrence.move` est relatif et cumulatif : on envoie D = T_cible · T_courante⁻¹ (axe-angle autour
de l'origine monde, puis translation), où T_courante est la transformation rendue par SolidCraft.
Les trajectoires sont des esquisses 3D (`sketch.spline3d`) effacées par `timeline.delete`.
"""

import math
import time
from collections.abc import Callable
from types import TracebackType
from typing import Any

import numpy as np

from meca3d import unites
from meca3d.cao.canal import CanalSolidCraft, ErreurCanal
from meca3d.modele.etude import Etude
from meca3d.moteur.base import ResultatsBruts
from meca3d.resultats.capteurs import etat_solide

VITESSE_MIN = 0.1  # SPEC EX-53 : ×0,1 à ×2
VITESSE_MAX = 2.0
CADENCE_MAX = 60.0  # images/s : l'affichage de SolidCraft est à 60 Hz (RESULTATS_1b § Q3)
NOMBRE_POINTS_TRAJECTOIRE = 200  # points d'une spline (200 points : 93 ms, RESULTATS_1b § Q4)
NOM_TRAJECTOIRE = "Trajectoire"
ANGLE_NUL = 1e-14  # rad : en dessous, aucune rotation n'est envoyée
SINUS_MIN = 1e-6  # au-dessous, l'axe d'une rotation d'angle proche de π se lit sur R + I


def _virgule(valeur: float) -> str:
    return f"{valeur:g}".replace(".", ",")


class ErreurAnimation(ErreurCanal):
    """Animation ou trajectoire impossible ; le message est destiné à l'élève, en français."""


# --- géométrie des rotations --------------------------------------------------------------------
def _axe_angle(r: np.ndarray) -> tuple[np.ndarray, float] | None:
    """(axe unitaire, angle en rad dans [0, π]) d'une rotation ; None si elle est nulle."""
    v = np.array([r[2, 1] - r[1, 2], r[0, 2] - r[2, 0], r[1, 0] - r[0, 1]]) / 2.0
    sinus = float(np.linalg.norm(v))
    cosinus = (float(np.trace(r)) - 1.0) / 2.0
    angle = math.atan2(sinus, cosinus)
    if angle < ANGLE_NUL:
        return None
    if cosinus >= 0.0 or sinus > SINUS_MIN:
        return v / sinus, angle
    m = (r + np.eye(3)) / 2.0  # angle ≈ π : R + I = 2·a·aᵀ
    k = int(np.argmax(np.diag(m)))
    axe = m[:, k] / math.sqrt(float(m[k, k]))
    return axe / float(np.linalg.norm(axe)), angle


def _rotation(axe: np.ndarray, angle: float) -> np.ndarray:
    """Rotation d'axe unitaire et d'angle donnés (Rodrigues)."""
    k = np.array([[0.0, -axe[2], axe[1]], [axe[2], 0.0, -axe[0]], [-axe[1], axe[0], 0.0]])
    return np.eye(3) + math.sin(angle) * k + (1.0 - math.cos(angle)) * (k @ k)


def _transformation(rotation: np.ndarray, translation_mm: np.ndarray) -> np.ndarray:
    t = np.eye(4)
    t[:3, :3] = rotation
    t[:3, 3] = translation_mm
    return t


class Animateur:
    """Rejoue dans SolidCraft le mouvement d'une simulation (EX-53) et trace des trajectoires.

    `horloge` (secondes, croissante) et `attente(durée)` sont injectables ; `cadence` borne le
    nombre d'images par seconde de `jouer`. Aucune requête n'est envoyée avant la première image.
    """

    def __init__(
        self,
        canal: CanalSolidCraft,
        etude: Etude,
        resultats: ResultatsBruts,
        horloge: Callable[[], float] = time.monotonic,
        attente: Callable[[float], None] = time.sleep,
        cadence: float = CADENCE_MAX,
    ) -> None:
        self._canal = canal
        self._etude = etude
        self._resultats = resultats
        self._horloge = horloge
        self._attente = attente
        self._periode_image = 1.0 / cadence
        self._mobiles = [
            s.nom for s in etude.solides if not s.fixe and s.nom in resultats.positions
        ]
        self._identifiants: dict[str, int] = {}
        self._initiales: dict[str, np.ndarray] = {}
        self._courantes: dict[str, np.ndarray] = {}
        self._modifie = False  # des déplacements en attente existent dans SolidCraft
        self._position = 0.0
        self._vitesse = 1.0
        self._en_lecture = False
        self._t_ref = 0.0  # horloge au dernier recalage de la lecture
        self._pos_ref = 0.0  # position de lecture au dernier recalage
        self._trajectoires: list[str] = []
        self.images_envoyees = 0
        if len(resultats.t) < 2:
            raise ErreurAnimation("Aucun résultat à animer : la simulation n'a pas d'instants.")

    # --- état -----------------------------------------------------------------------------
    @property
    def duree(self) -> float:
        """Durée de la simulation (s)."""
        return float(self._resultats.t[-1] - self._resultats.t[0])

    @property
    def position(self) -> float:
        """Instant affiché (s)."""
        return self._position

    @property
    def en_lecture(self) -> bool:
        return self._en_lecture

    @property
    def vitesse(self) -> float:
        """Facteur de vitesse de lecture, de ×0,1 à ×2."""
        return self._vitesse

    @vitesse.setter
    def vitesse(self, valeur: float) -> None:
        if not VITESSE_MIN <= valeur <= VITESSE_MAX:
            raise ValueError(
                f"Vitesse de lecture {_virgule(valeur)} refusée : choisir un facteur entre "
                f"×{_virgule(VITESSE_MIN)} et ×{_virgule(VITESSE_MAX)}."
            )
        if self._en_lecture:
            self._recaler()
        self._vitesse = float(valeur)

    @property
    def trajectoires(self) -> tuple[str, ...]:
        return tuple(self._trajectoires)

    # --- cycle de vie ---------------------------------------------------------------------
    def __enter__(self) -> "Animateur":
        return self

    def __exit__(
        self,
        type_exception: type[BaseException] | None,
        exception: BaseException | None,
        trace: TracebackType | None,
    ) -> None:
        self.terminer()

    def terminer(self) -> None:
        """Arrête la lecture et restaure la pose initiale (idempotent, aucune requête inutile)."""
        self._en_lecture = False
        if not self._modifie:
            return
        self._canal.executer(
            "component.revert_position", {"occurrences": list(self._identifiants.values())}
        )
        self._modifie = False
        self._courantes = {nom: t.copy() for nom, t in self._initiales.items()}

    def reinitialiser(self) -> None:
        """Arrêt complet : pose restaurée (`terminer`) et position remise à t = 0."""
        self.terminer()
        self._position = 0.0

    def _terminer_sans_masquer(self) -> None:
        try:
            self.terminer()
        except ErreurCanal:
            pass  # connexion perdue : l'erreur d'origine prime

    # --- lecture --------------------------------------------------------------------------
    def _recaler(self) -> None:
        self._t_ref = self._horloge()
        self._pos_ref = self._position

    def lire(self) -> None:
        """Démarre ou reprend la lecture ; depuis la fin, elle repart du début."""
        if self._position >= self.duree - 1e-12:
            self._position = 0.0
        self._en_lecture = True
        self._recaler()

    def pause(self) -> None:
        """Fige la lecture ; la pose reste affichée jusqu'à `terminer`."""
        self._en_lecture = False

    def avancer(self) -> bool:
        """Affiche l'image due à l'horloge ; vrai si la lecture continue. À la fin de la
        simulation, la pose initiale est restaurée."""
        if not self._en_lecture:
            return False
        instant = self._pos_ref + (self._horloge() - self._t_ref) * self._vitesse
        if instant >= self.duree:
            self._position = self.duree
            self.terminer()
            return False
        try:
            self._afficher(instant)
        except Exception:
            self._terminer_sans_masquer()
            raise
        self._position = instant
        return True

    def aller_a(self, instant: float) -> None:
        """Curseur temporel : affiche l'image à `instant` (borné à [0, durée])."""
        instant = min(max(float(instant), 0.0), self.duree)
        try:
            self._afficher(instant)
        except Exception:
            self._terminer_sans_masquer()
            raise
        self._position = instant
        if self._en_lecture:
            self._recaler()

    def jouer(self, arret: Callable[[], bool] | None = None) -> int:
        """Lecture bloquante en temps réel jusqu'à la fin ou jusqu'à `arret()` ; la pose est
        restaurée dans tous les cas. Rend le nombre d'images envoyées."""
        avant = self.images_envoyees
        try:
            self.lire()
            while self._en_lecture:
                if arret is not None and arret():
                    break
                debut = self._horloge()
                if not self.avancer():
                    break
                reste = self._periode_image - (self._horloge() - debut)
                if reste > 0.0:
                    self._attente(reste)
        finally:
            self.terminer()
        return self.images_envoyees - avant

    # --- poses ----------------------------------------------------------------------------
    def _preparer(self) -> None:
        """Lit les occurrences de premier niveau (identifiants, poses initiales)."""
        composants = self._canal.executer("component.list")
        racine = next((c for c in composants["components"] if c.get("parent") is None), None)
        if racine is None:
            raise ErreurAnimation("component.list : composant racine introuvable.")
        occurrences = {o["name"]: o for o in racine["children"]}
        for nom in self._mobiles:
            occ = occurrences.get(nom) or next(
                (o for n, o in occurrences.items() if n.rsplit(":", 1)[0] == nom), None
            )
            if occ is None:
                raise ErreurAnimation(
                    f"Le solide « {nom} » n'a pas d'occurrence dans la maquette ouverte : "
                    "importer à nouveau la maquette."
                )
            self._identifiants[nom] = int(occ["id"])
            self._initiales[nom] = np.array(occ["transform"], dtype=float).T
        self._courantes = {nom: t.copy() for nom, t in self._initiales.items()}

    def _etat_a(self, instant: float) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray]]:
        """Position du CdG (m) et rotation de chaque mobile à l'instant, interpolées entre les
        deux échantillons voisins (linéaire en position, exacte sur la rotation relative)."""
        t = self._resultats.t
        i = int(np.clip(np.searchsorted(t, t[0] + instant, side="right") - 1, 0, len(t) - 2))
        f = float((t[0] + instant - t[i]) / (t[i + 1] - t[i]))
        positions: dict[str, np.ndarray] = {}
        rotations: dict[str, np.ndarray] = {}
        for nom in self._mobiles:
            positions[nom] = (1.0 - f) * self._resultats.positions[nom][i] + (
                f * self._resultats.positions[nom][i + 1]
            )
            r0, r1 = self._resultats.rotations[nom][i], self._resultats.rotations[nom][i + 1]
            relative = _axe_angle(r0.T @ r1)
            rotations[nom] = (
                r0 if relative is None else r0 @ _rotation(relative[0], relative[1] * f)
            )
        return positions, rotations

    def _cible(self, nom: str, x: np.ndarray, r: np.ndarray) -> np.ndarray:
        """Transformation 4×4 cible (mm) du composant du solide (D15, voir l'en-tête)."""
        solide = self._etude.solide(nom)
        origine = x + r @ (solide.repere_origine - solide.cdg)
        return _transformation(r @ solide.repere_rotation, unites.m_vers_mm(origine))

    @staticmethod
    def _deplacement(identifiant: int, cible: np.ndarray, courante: np.ndarray) -> dict[str, Any]:
        """Paramètres d'`occurrence.move` qui amènent `courante` sur `cible` (espace monde)."""
        d = cible @ np.linalg.inv(courante)
        params: dict[str, Any] = {"occurrence": identifiant, "space": "world", "capture": False}
        rotation = _axe_angle(d[:3, :3])
        if rotation is not None:
            params.update(
                axis=[float(x) for x in rotation[0]],
                angle=rotation[1],
                origin=[0.0, 0.0, 0.0],
            )
        params["translate"] = [float(x) for x in d[:3, 3]]
        return params

    def _afficher(self, instant: float) -> None:
        """Envoie l'image à `instant` : un `engine.batch` d'`occurrence.move`, un par mobile."""
        if not self._initiales and self._mobiles:
            self._preparer()
        positions, rotations = self._etat_a(instant)
        commandes = [
            {
                "command": "occurrence.move",
                "params": self._deplacement(
                    self._identifiants[nom],
                    self._cible(nom, positions[nom], rotations[nom]),
                    self._courantes[nom],
                ),
            }
            for nom in self._mobiles
        ]
        if not commandes:
            return
        self._modifie = True  # dès l'envoi : un échec partiel laisse des déplacements en attente
        reponse = self._canal.requete("engine.batch", {"commands": commandes}, nom="engine.batch")
        resultats = reponse.get("results", []) if isinstance(reponse, dict) else []
        if len(resultats) != len(commandes):
            raise ErreurAnimation(
                "SolidCraft n'a pas appliqué toutes les poses de l'image "
                f"({len(resultats)} sur {len(commandes)})."
            )
        for nom, resultat in zip(self._mobiles, resultats, strict=True):
            self._courantes[nom] = np.array(resultat["transform"], dtype=float).T
        self.images_envoyees += 1

    # --- trajectoires (EX-52) -------------------------------------------------------------
    def _points_trajectoire(
        self, point: tuple[float, float, float], solide: str, reference: str | None
    ) -> np.ndarray:
        """Points (n, 3) en mm de la trajectoire du point (m, repère monde à l'import) du
        solide, vue du solide de référence et dessinée à sa pose d'import (monde si fixe)."""
        noms = {s.nom for s in self._etude.solides}
        for nom in (solide, reference):
            if nom is not None and nom not in noms:
                raise ErreurAnimation(f"Solide « {nom} » inconnu de l'étude.")
        p, _, _ = etat_solide(self._etude, self._resultats, solide).point(np.array(point, float))
        if reference is not None:
            ref = etat_solide(self._etude, self._resultats, reference)
            p = ref.cdg_import + np.einsum("nji,nj->ni", ref.rotation, p - ref.x)
        return np.asarray(unites.m_vers_mm(p), dtype=float)

    def tracer_trajectoire(
        self,
        point: tuple[float, float, float],
        solide: str,
        reference: str | None = None,
        nom: str = NOM_TRAJECTOIRE,
        max_points: int | None = NOMBRE_POINTS_TRAJECTOIRE,
    ) -> str:
        """Trace dans SolidCraft, par une spline 3D, la trajectoire d'un point du `solide` (point
        en mètres, repère monde à l'import, comme un capteur de point). `reference` : solide dont
        on voit la trajectoire (défaut : le monde). `max_points` : nombre maximal de points
        (échantillonnage régulier, extrémités conservées ; None : tous). Rend le nom de
        l'esquisse créée. Cette esquisse est la seule écriture de Meca3D dans la maquette."""
        points = self._points_trajectoire(point, solide, reference)
        n = len(points)
        if max_points is not None and n > max_points:
            indices = np.unique(np.round(np.linspace(0, n - 1, max_points)).astype(int))
            points = points[indices]
        cree = self._canal.executer("sketch.create", {"plane": "XY", "name": nom})
        nom_cree = str(cree.get("name", nom)) if isinstance(cree, dict) else nom
        self._trajectoires.append(nom_cree)
        try:
            self._canal.executer("sketch.options", {"sketch_3d": True})
            self._canal.executer("sketch.spline3d", {"points": points.tolist()})
            self._canal.executer("sketch.finish")
        except ErreurCanal:
            self._effacer_sans_masquer()
            raise
        return nom_cree

    def effacer_trajectoires(self) -> int:
        """Efface les trajectoires tracées par cet animateur (`timeline.delete`) ; rend leur
        nombre. Aucune requête s'il n'y en a pas."""
        if not self._trajectoires:
            return 0
        nombre = len(self._trajectoires)
        self._canal.executer("timeline.delete", {"features": list(self._trajectoires)})
        self._trajectoires.clear()
        return nombre

    def _effacer_sans_masquer(self) -> None:
        try:
            self.effacer_trajectoires()
        except ErreurCanal:
            pass
