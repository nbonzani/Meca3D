# SPDX-License-Identifier: GPL-3.0-or-later
"""Couplages, hélicoïdale, frottement de Coulomb et rendement dans Exudyn (D13, EX-14 à EX-16).

Formulations validées au lot 1a (prototypes/levee_risques/RESULTATS_1a.md) :

- **Couplage** : une équation au niveau vitesse g = s₂ − ρ·s₁ = 0, où s_i est la vitesse relative
  (rotation autour de l'axe, ou translation le long de l'axe) de la liaison i, et ρ le rapport :
  −k ou +k (engrenage), r (pignon-crémaillère), p/2π (vis-écrou, hélicoïdale à une seule liaison).
  Chaque s_i = (vitesse du solide b) − (vitesse du solide a) projetée sur l'axe de la liaison, fixe
  dans le solide a : g est linéaire dans les vitesses des solides concernés. Elle est posée par
  `ObjectConnectorCoordinateVector` (`velocityLevel`, `constraintUserFunction`,
  `jacobianUserFunction`)
  sur les paramètres d'Euler des corps. Le multiplicateur de Lagrange λ de g donne les efforts
  transmis : −λ sur la coordonnée relative de la liaison 2, +ρ·λ sur celle de la liaison 1.
- **Q7, au-delà de deux corps** (train épicycloïdal : les axes sont portés par un porte-satellites
  mobile) : le connecteur n'a que deux marqueurs. Une relation Σ f_i = 0 entre N corps est
  décomposée en N contraintes à deux marqueurs (corps i, nœud auxiliaire) à N − 1 coordonnées
  auxiliaires x_i : f₁ − ẋ₁ = 0, f_i + ẋ_{i−1} − ẋ_i = 0, f_N + ẋ_{N−1} = 0. Les multiplicateurs
  sont tous égaux (équilibre du nœud auxiliaire) et valent celui de la relation unique.
- **Coulomb** : `ObjectConnectorRigidBodySpringDamper` dont la fonction utilisateur rend
  F = f·|N|·tanh(v/v_ε), N lu dans l'effort de la liaison parfaite à la configuration COURANTE
  (point fixe de Newton).
- **Rendement** : deux couples (ou efforts) de perte pondérés par le sens de la puissance.

Limites : le frottement ne couvre que la glissière, l'appui plan et le pivot ; le moment de la
réaction (glissière) et le frottement de pivotement (appui plan) sont ignorés ; la composante
radiale d'un effort de denture n'est pas modélisée (contrainte idéale).
"""

import importlib
import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

import numpy as np

from meca3d.modele.couplage import (
    Couplage,
    Engrenage,
    PignonCremaillere,
    VisEcrou,
)
from meca3d.modele.etude import Etude
from meca3d.modele.liaison import Liaison, TypeLiaison
from meca3d.moteur.base import ErreurModele, Fluage

exu: Any = importlib.import_module("exudyn")
_u: Any = importlib.import_module("exudyn.utilities")
_rb: Any = importlib.import_module("exudyn.rigidBodyUtilities")

# RESULTATS_1a § 2.3 : valeurs par défaut de la SPEC (EX-15). Au-delà de 1e-3 m/s,
# l'adhérence n'est plus tenue.
V_EPSILON_DEFAUT = 1e-4  # m/s, translation
OMEGA_EPSILON_DEFAUT = 1e-2  # rad/s, rotation
# Zone d'adhérence apparente : |v| ≤ 3·ε (tanh(3) = 0,995, l'effort tangent est à 0,5 % de f·|N|)
FACTEUR_ZONE_ADHERENCE = 3.0
# Un fluage n'est signalé que s'il occupe au moins cette part de la durée simulée
PART_DUREE_FLUAGE_SIGNALE = 0.1
# RESULTATS_1a § 2.4 : largeur (W) de la transition du sens de la puissance d'un rendement
P_EPS_RENDEMENT = 0.5
# Masse (kg) des coordonnées auxiliaires de la décomposition d'une relation à plus de deux corps
MASSE_AUXILIAIRE = 1e-9

LIAISONS_FROTTANTES = frozenset({TypeLiaison.GLISSIERE, TypeLiaison.APPUI_PLAN, TypeLiaison.PIVOT})
_LIBRES_ROTATION = frozenset(
    {TypeLiaison.PIVOT, TypeLiaison.PIVOT_GLISSANT, TypeLiaison.HELICOIDALE}
)
_LIBRES_TRANSLATION = frozenset(
    {TypeLiaison.GLISSIERE, TypeLiaison.PIVOT_GLISSANT, TypeLiaison.HELICOIDALE}
)


class Nature(StrEnum):
    ROTATION = "rotation"
    TRANSLATION = "translation"


# --------------------------------------------------------------------------- relations (pures)
@dataclass(frozen=True)
class Relation:
    """s₂ = rapport·s₁ entre les vitesses relatives de deux liaisons (ou de deux ddl d'une
    hélicoïdale : `liaison_1 is liaison_2`)."""

    nom: str
    liaison_1: Liaison
    nature_1: Nature
    liaison_2: Liaison
    nature_2: Nature
    rapport: float
    rendement: float


def _verifier_ddl(couplage: str, liaison: Liaison, nature: Nature) -> None:
    libres = _LIBRES_ROTATION if nature is Nature.ROTATION else _LIBRES_TRANSLATION
    if liaison.type not in libres:
        genre = "une rotation" if nature is Nature.ROTATION else "une translation"
        raise ErreurModele(
            f"Le couplage {couplage} exige {genre} libre sur la liaison {liaison.nom} "
            f"({liaison.type.value if liaison.type else 'sans type'}) : un couplage se pose "
            "entre liaisons à axe (pivot, pivot glissant, glissière ou hélicoïdale)."
        )


def _relation_couplage(etude: Etude, c: Couplage) -> Relation:
    l1, l2 = etude.liaison(c.liaison_1), etude.liaison(c.liaison_2)
    if isinstance(c, Engrenage):
        natures, rapport = (Nature.ROTATION, Nature.ROTATION), c.signe * c.k
    elif isinstance(c, PignonCremaillere):
        natures, rapport = (Nature.ROTATION, Nature.TRANSLATION), c.r
    elif isinstance(c, VisEcrou):
        natures, rapport = (Nature.ROTATION, Nature.TRANSLATION), c.p / (2.0 * math.pi)
    else:  # pragma: no cover - type fermé
        raise ErreurModele(f"Couplage {c.nom} : genre non pris en charge.")
    _verifier_ddl(c.nom, l1, natures[0])
    _verifier_ddl(c.nom, l2, natures[1])
    return Relation(c.nom, l1, natures[0], l2, natures[1], rapport, c.rendement)


def relations(etude: Etude) -> list[Relation]:
    """Relations de vitesse de l'étude : couplages (EX-14) puis couplages internes des hélicoïdales
    (Tx = p·Rx / 2π, EX-10). Lève ErreurModele si un couplage vise un ddl bloqué ou si le pas d'une
    hélicoïdale est inconnu."""
    sortie = [_relation_couplage(etude, c) for c in etude.couplages]
    for liaison in etude.liaisons:
        if liaison.type is TypeLiaison.HELICOIDALE:
            if liaison.pas is None:
                raise ErreurModele(
                    f"Liaison {liaison.nom} : le pas de la liaison hélicoïdale n'est pas renseigné "
                    "(m par tour) ; le saisir avant de simuler."
                )
            sortie.append(
                Relation(
                    liaison.nom,
                    liaison,
                    Nature.ROTATION,
                    liaison,
                    Nature.TRANSLATION,
                    liaison.pas / (2.0 * math.pi),
                    1.0,
                )
            )
    return sortie


@dataclass(frozen=True)
class Terme:
    """Contribution `poids`·(u·ω) ou `poids`·(u·v_P) du solide `solide` à une relation, u = axe de
    la liaison fixe dans `reference` (solide a ; fixe : u = axe0), P = centre de la liaison lié à
    `solide` (`s_local` = P − CdG en repère propre, identique au monde à la pose d'import)."""

    solide: str
    poids: float
    nature: Nature
    axe0: np.ndarray
    reference: str
    s_local: np.ndarray


def termes_liaison(etude: Etude, liaison: Liaison, nature: Nature, poids: float) -> list[Terme]:
    """Termes de `poids`·s_liaison, s = rotation ou translation de b par rapport à a (mobiles
    seulement : les solides fixes ne contribuent pas)."""
    axe0 = liaison.base()[:, 0]
    sortie = []
    for nom, signe in ((liaison.solide_b, 1.0), (liaison.solide_a, -1.0)):
        solide = etude.solide(nom)
        if solide.fixe:
            continue
        sortie.append(
            Terme(
                nom,
                signe * poids,
                nature,
                axe0,
                liaison.solide_a,
                np.asarray(liaison.centre - solide.cdg, dtype=float),
            )
        )
    return sortie


def termes_relation(etude: Etude, r: Relation) -> list[Terme]:
    """Termes de g = s₂ − ρ·s₁."""
    return termes_liaison(etude, r.liaison_2, r.nature_2, 1.0) + termes_liaison(
        etude, r.liaison_1, r.nature_1, -r.rapport
    )


# --------------------------------------------------------------------------- cinématique pure
def ligne_cinematique(
    etude: Etude,
    termes: list[Terme],
    x: Mapping[str, np.ndarray],
    r: Mapping[str, np.ndarray],
    torseurs: Mapping[str, tuple[np.ndarray, np.ndarray]] | None,
) -> tuple[dict[str, tuple[np.ndarray, np.ndarray]], float]:
    """Équation de la relation au niveau vitesse (torseurs None) ou accélération.

    Renvoie ({solide: (coef_v, coef_w)}, reste) : Σ coef_v·v + coef_w·ω + reste = 0 au niveau
    vitesse (reste = 0), et Σ coef_v·a + coef_w·α + reste = 0 au niveau accélération (`torseurs` :
    vitesses (v, ω) des CdG, repère monde, connues). Positions `x`, rotations `r` : repère monde.
    """
    del x  # les points d'application ne dépendent que des rotations (s = R·s_local)
    nul = (np.zeros(3), np.zeros(3))
    coefficients: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    reste = 0.0
    for t in termes:
        u = r[t.reference] @ t.axe0 if not etude.solide(t.reference).fixe else t.axe0
        s = r[t.solide] @ t.s_local
        coef_v = np.zeros(3) if t.nature is Nature.ROTATION else t.poids * u
        coef_w = t.poids * u if t.nature is Nature.ROTATION else t.poids * np.cross(s, u)
        ancien = coefficients.get(t.solide, nul)
        coefficients[t.solide] = (ancien[0] + coef_v, ancien[1] + coef_w)
        if torseurs is not None:
            v_b, w_b = torseurs.get(t.solide, nul)
            _, w_a = torseurs.get(t.reference, nul)
            u_point = np.cross(w_a, u)
            if t.nature is Nature.ROTATION:
                reste += t.poids * float(u_point @ w_b)
            else:
                v_p = v_b + np.cross(w_b, s)
                reste += t.poids * float(u_point @ v_p + u @ np.cross(w_b, np.cross(w_b, s)))
    return coefficients, reste


# --------------------------------------------------------------------------- Exudyn : relations
def _g_ep(e: np.ndarray) -> np.ndarray:
    """Matrice 3×4 telle que ω_local = G(e)·ė (paramètres d'Euler, prototype 1a)."""
    e0, e1, e2, e3 = e
    return 2.0 * np.array([[-e1, e0, e3, -e2], [-e2, -e3, e0, e1], [-e3, e2, -e1, e0]])


class _Systeme:
    """Accès à l'état courant d'Exudyn pour les fonctions utilisateur."""

    def __init__(self, mbs: Any, etude: Etude, corps: Mapping[str, int]) -> None:
        self.mbs = mbs
        self.etude = etude
        self.noeuds: dict[str, int] = {
            nom: mbs.GetObject(numero)["nodeNumber"]
            for nom, numero in corps.items()
            if not etude.solide(nom).fixe
        }

    def rotation(self, nom: str) -> np.ndarray:
        if nom not in self.noeuds:
            return np.eye(3)
        sortie = self.mbs.GetNodeOutput(self.noeuds[nom], exu.OutputVariableType.RotationMatrix)
        return np.asarray(sortie, dtype=float).reshape(3, 3)

    def axe(self, t: Terme) -> np.ndarray:
        return self.rotation(t.reference) @ t.axe0

    def ligne(self, termes: list[Terme], q: np.ndarray) -> np.ndarray:
        """Coefficients de (ẋ, ė) (7 valeurs) des termes d'un même solide, à l'état `q`."""
        e = np.asarray(q[3:7], dtype=float)
        rotation = np.asarray(_rb.EulerParameters2RotationMatrix(e), dtype=float)
        g = _g_ep(e)
        ligne = np.zeros(7)
        for t in termes:
            u = self.axe(t)
            if t.nature is Nature.ROTATION:
                ligne[3:7] += t.poids * (rotation.T @ u) @ g
            else:
                ligne[0:3] += t.poids * u
                ligne[3:7] += t.poids * np.cross(t.s_local, rotation.T @ u) @ g
        return ligne

    def vitesse_relative(self, termes: list[Terme]) -> float:
        """Σ termes · vitesses courantes (vitesse relative pondérée)."""
        total = 0.0
        for nom in {t.solide for t in termes}:
            noeud = self.noeuds[nom]
            q = self.mbs.GetNodeOutput(noeud, exu.OutputVariableType.CoordinatesTotal)
            qt = self.mbs.GetNodeOutput(noeud, exu.OutputVariableType.Coordinates_t)
            total += float(self.ligne([t for t in termes if t.solide == nom], q) @ np.asarray(qt))
        return total


class CouplageInstalle:
    """Une relation posée dans le système Exudyn, avec ses pertes (rendement)."""

    def __init__(self, systeme: _Systeme, relation: Relation) -> None:
        self.systeme = systeme
        self.relation = relation
        etude, mbs = systeme.etude, systeme.mbs
        self.termes_1 = termes_liaison(etude, relation.liaison_1, relation.nature_1, 1.0)
        self.termes = termes_relation(etude, relation)
        self.objets = self._poser_contrainte(mbs)
        self.capteur = -1

    # -- contrainte
    def _poser_contrainte(self, mbs: Any) -> list[int]:
        par_solide: dict[str, list[Terme]] = {}
        for t in self.termes:
            par_solide.setdefault(t.solide, []).append(t)
        if not par_solide:
            raise ErreurModele(
                f"Le couplage {self.relation.nom} ne relie que des solides fixes : rien à coupler."
            )
        systeme = self.systeme
        corps = [(nom, systeme.noeuds[nom], lst) for nom, lst in par_solide.items()]

        def ligne(k: int, q: Any) -> np.ndarray:
            return systeme.ligne(corps[k][2], np.asarray(q, dtype=float))

        n = len(corps)
        if n <= 2:
            noeud_0 = corps[0][1]
            noeud_1 = corps[-1][1]
            marqueurs = [
                mbs.AddMarker(_u.MarkerNodeCoordinates(nodeNumber=noeud_0)),
                mbs.AddMarker(_u.MarkerNodeCoordinates(nodeNumber=noeud_1)),
            ]

            def contrainte(mbs_: Any, t: float, item: int, q: Any, qt: Any, nv: bool) -> Any:
                q, qt = np.asarray(q), np.asarray(qt)
                g = ligne(0, q[:7]) @ qt[:7]
                if n == 2:
                    g += ligne(1, q[7:14]) @ qt[7:14]
                return np.array([g])

            def jacobien(mbs_: Any, t: float, item: int, q: Any, qt: Any, nv: bool) -> Any:
                q = np.asarray(q)
                jac = np.zeros((1, 14))
                jac[0, :7] = ligne(0, q[:7])
                if n == 2:
                    jac[0, 7:] = ligne(1, q[7:14])
                return jac

            return [
                mbs.AddObject(
                    _u.ObjectConnectorCoordinateVector(
                        markerNumbers=marqueurs,
                        scalingMarker0=np.zeros((1, 7)),
                        scalingMarker1=np.zeros((1, 7)),
                        velocityLevel=True,
                        constraintUserFunction=contrainte,
                        jacobianUserFunction=jacobien,
                    )
                )
            ]
        return self._poser_chaine(mbs, corps, ligne)

    @staticmethod
    def _poser_chaine(mbs: Any, corps: list[tuple[str, int, list[Terme]]], ligne: Any) -> list[int]:
        """Q7 : relation Σ f_i = 0 entre n > 2 corps, par un nœud auxiliaire à n − 1 coordonnées."""
        n = len(corps)
        nulle = [0.0] * (n - 1)
        noeud = mbs.AddNode(
            _u.NodeGenericODE2(
                referenceCoordinates=nulle,
                initialCoordinates=nulle,
                initialCoordinates_t=nulle,
                numberOfODE2Coordinates=n - 1,
            )
        )
        mbs.AddObject(
            _u.ObjectGenericODE2(
                nodeNumbers=[noeud],
                massMatrix=np.eye(n - 1) * MASSE_AUXILIAIRE,
                stiffnessMatrix=np.zeros((n - 1, n - 1)),
                dampingMatrix=np.zeros((n - 1, n - 1)),
                forceVector=np.zeros(n - 1),
            )
        )
        marqueur_aux = mbs.AddMarker(_u.MarkerNodeCoordinates(nodeNumber=noeud))
        objets = []
        for i, (_, noeud_corps, _) in enumerate(corps):
            marqueur = mbs.AddMarker(_u.MarkerNodeCoordinates(nodeNumber=noeud_corps))
            aux = np.zeros(n - 1)
            if i > 0:
                aux[i - 1] += 1.0
            if i < n - 1:
                aux[i] -= 1.0

            def contrainte(
                mbs_: Any, t: float, item: int, q: Any, qt: Any, nv: bool, i: int = i, aux=aux
            ) -> Any:
                q, qt = np.asarray(q), np.asarray(qt)
                return np.array([ligne(i, q[:7]) @ qt[:7] + aux @ qt[7:]])

            def jacobien(
                mbs_: Any, t: float, item: int, q: Any, qt: Any, nv: bool, i: int = i, aux=aux
            ) -> Any:
                jac = np.zeros((1, 7 + n - 1))
                jac[0, :7] = ligne(i, np.asarray(q)[:7])
                jac[0, 7:] = aux
                return jac

            objets.append(
                mbs.AddObject(
                    _u.ObjectConnectorCoordinateVector(
                        markerNumbers=[marqueur, marqueur_aux],
                        scalingMarker0=np.zeros((1, 7)),
                        scalingMarker1=np.zeros((1, n - 1)),
                        velocityLevel=True,
                        constraintUserFunction=contrainte,
                        jacobianUserFunction=jacobien,
                    )
                )
            )
        return objets

    # -- lectures à la configuration courante
    def multiplicateur(self) -> float:
        mbs = self.systeme.mbs
        indice = mbs.systemData.GetObjectLTGAE(self.objets[0])[0]
        return float(mbs.systemData.GetAECoordinates()[indice])

    def poids_direct(self) -> float:
        """w ∈ [0, 1] : 1 si la puissance va de la liaison 1 à la 2 (P_e = −ρ·λ·s₁ > 0)."""
        s1 = self.systeme.vitesse_relative(self.termes_1)
        p_e = -self.relation.rapport * self.multiplicateur() * s1
        return 0.5 * (1.0 + math.tanh(p_e / P_EPS_RENDEMENT))

    def efforts(self) -> tuple[float, float]:
        """Efforts exercés par le couplage (pertes comprises) sur les coordonnées relatives des
        liaisons 1 et 2."""
        lam, eta = self.multiplicateur(), self.relation.rendement
        w = self.poids_direct() if eta < 1.0 else 1.0
        rho = self.relation.rapport
        entree = rho * lam * (1.0 - (1.0 - eta) * (1.0 - w))
        sortie = -lam * (1.0 - (1.0 - eta) * w)
        return entree, sortie

    # -- rendement : pertes appliquées par des charges
    def installer_pertes(self, mbs: Any, corps: Mapping[str, int]) -> None:
        eta = self.relation.rendement
        if eta >= 1.0:
            return
        rho = self.relation.rapport

        def perte_sortie() -> float:
            return (1.0 - eta) * self.poids_direct() * self.multiplicateur()

        def perte_entree() -> float:
            return -(1.0 - eta) * (1.0 - self.poids_direct()) * rho * self.multiplicateur()

        self._charges(mbs, corps, self.relation.liaison_2, self.relation.nature_2, perte_sortie)
        self._charges(mbs, corps, self.relation.liaison_1, self.relation.nature_1, perte_entree)

    def _charges(
        self,
        mbs: Any,
        corps: Mapping[str, int],
        liaison: Liaison,
        nature: Nature,
        intensite: Callable[[], float],
    ) -> None:
        """Effort `intensite()` sur la coordonnée relative de `liaison` : +F·u sur b, −F·u sur a."""
        systeme = self.systeme
        etude = systeme.etude
        axe0 = liaison.base()[:, 0]
        for nom, signe in ((liaison.solide_b, 1.0), (liaison.solide_a, -1.0)):
            solide = etude.solide(nom)
            if solide.fixe:
                continue
            terme = Terme(
                nom, signe, nature, axe0, liaison.solide_a, np.asarray(liaison.centre - solide.cdg)
            )

            def charge(mbs_: Any, t: float, load: Any, terme: Terme = terme) -> list[float]:
                return [float(c) for c in terme.poids * intensite() * systeme.axe(terme)]

            if nature is Nature.ROTATION:
                mbs.CreateTorque(
                    itemNumber=corps[nom],
                    loadVector=[0.0, 0.0, 0.0],
                    bodyFixed=False,
                    loadVectorUserFunction=charge,
                    show=False,
                )
            else:
                mbs.CreateForce(
                    itemNumber=corps[nom],
                    loadVector=[0.0, 0.0, 0.0],
                    localPosition=[float(c) for c in terme.s_local],
                    loadVectorUserFunction=charge,
                    show=False,
                )

    def ajouter_capteur(self, mbs: Any) -> None:
        def fonction(mbs_: Any, t: float, numeros: Any, facteurs: Any, configuration: Any) -> Any:
            return list(self.efforts())

        self.capteur = mbs.AddSensor(
            _u.SensorUserFunction(
                sensorUserFunction=fonction, storeInternal=True, writeToFile=False
            )
        )


# --------------------------------------------------------------------------- Exudyn : frottement
@dataclass
class FrottementInstalle:
    liaison: Liaison
    connecteur: int
    epsilon: float
    capteur: int
    rotation: bool


def _epsilon(liaison: Liaison) -> float:
    if liaison.epsilon is not None:
        return liaison.epsilon
    return OMEGA_EPSILON_DEFAUT if liaison.type is TypeLiaison.PIVOT else V_EPSILON_DEFAUT


def verifier_frottements(etude: Etude) -> None:
    for liaison in etude.liaisons:
        if liaison.frottement <= 0.0:
            continue
        if liaison.type not in LIAISONS_FROTTANTES:
            raise ErreurModele(
                f"Liaison {liaison.nom} : le frottement de Coulomb n'est pris en charge que pour "
                "la glissière, l'appui plan et le pivot (EX-15)."
            )
        if liaison.type is TypeLiaison.PIVOT and liaison.rayon_axe is None:
            raise ErreurModele(
                f"Liaison {liaison.nom} : le rayon de l'axe est à saisir pour le frottement d'un "
                "pivot (couple résistant f·r·|R_radiale|)."
            )


def installer_frottements(
    mbs: Any,
    etude: Etude,
    corps: Mapping[str, int],
    joints: Mapping[str, int],
) -> list[FrottementInstalle]:
    """Pose le frottement de Coulomb des liaisons dont f > 0. `joints` : liaison parfaite (numéro
    d'objet) par nom de liaison, dont l'effort donne la réaction normale N."""
    installes = []
    types = exu.OutputVariableType
    for liaison in etude.liaisons:
        if liaison.frottement <= 0.0:
            continue
        a, b = etude.solide(liaison.solide_a), etude.solide(liaison.solide_b)
        base = liaison.base()
        pos_a = liaison.centre if a.fixe else liaison.centre - a.cdg
        pos_b = liaison.centre if b.fixe else liaison.centre - b.cdg
        m0 = mbs.AddMarker(
            _u.MarkerBodyRigid(
                bodyNumber=corps[a.nom],
                localPosition=[0.0, 0.0, 0.0],
                localHT=exu.HT(rotation=base, translation=[float(c) for c in pos_a]),
            )
        )
        m1 = mbs.AddMarker(
            _u.MarkerBodyRigid(bodyNumber=corps[b.nom], localPosition=[float(c) for c in pos_b])
        )
        noeud = mbs.AddNode(_u.NodeGenericData(initialCoordinates=[0], numberOfDataCoordinates=1))
        joint = joints[liaison.nom]
        f, epsilon = liaison.frottement, _epsilon(liaison)
        type_liaison = liaison.type
        rayon = liaison.rayon_axe or 1.0

        def reaction(joint: int = joint) -> np.ndarray:
            return np.asarray(mbs.GetObjectOutput(joint, types.ForceLocal), dtype=float)

        def fonction(
            mbs_: Any,
            t: float,
            item: int,
            u: Any,
            rot: Any,
            v: Any,
            w: Any,
            k: Any,
            d: Any,
            rj0: Any,
            rj1: Any,
            off: Any,
            f: float = f,
            epsilon: float = epsilon,
            type_liaison: TypeLiaison | None = type_liaison,
            rayon: float = rayon,
            reaction: Callable[[], np.ndarray] = reaction,
        ) -> list[float]:
            # Convention du prototype : la fonction rend +F (le connecteur applique l'opposé au
            # corps 1) ; N est lu à la configuration courante.
            efforts = reaction()
            sortie = [0.0] * 6
            if type_liaison is TypeLiaison.GLISSIERE:
                sortie[0] = f * math.hypot(efforts[1], efforts[2]) * math.tanh(v[0] / epsilon)
            elif type_liaison is TypeLiaison.APPUI_PLAN:
                vitesse = math.hypot(v[0], v[1])
                facteur = math.tanh(vitesse / epsilon) / vitesse if vitesse > 1e-14 else 1 / epsilon
                intensite = f * abs(efforts[2]) * facteur
                sortie[0], sortie[1] = intensite * v[0], intensite * v[1]
            else:  # pivot
                sortie[3] = (
                    f * rayon * math.hypot(efforts[1], efforts[2]) * math.tanh(w[0] / epsilon)
                )
            return sortie

        connecteur = mbs.AddObject(
            _u.ObjectConnectorRigidBodySpringDamper(
                markerNumbers=[m0, m1],
                nodeNumber=noeud,
                stiffness=np.zeros((6, 6)),
                damping=np.zeros((6, 6)),
                springForceTorqueUserFunction=fonction,
            )
        )
        rotation = type_liaison is TypeLiaison.PIVOT
        capteur = mbs.AddSensor(
            _u.SensorObject(
                objectNumber=connecteur,
                storeInternal=True,
                writeToFile=False,
                outputVariableType=types.AngularVelocityLocal if rotation else types.VelocityLocal,
            )
        )
        installes.append(FrottementInstalle(liaison, connecteur, epsilon, capteur, rotation))
    return installes


def fluage_frottement(
    f: FrottementInstalle, donnees: np.ndarray, duree: float
) -> tuple[Fluage, str | None]:
    """Fluage relevé dans la zone d'adhérence apparente et message à signaler (ou None)."""
    t = donnees[:, 0]
    v = donnees[:, 1:4]
    # appui plan : vitesse de glissement dans le plan ; glissière, pivot : composante sur l'axe
    plan = f.liaison.type is TypeLiaison.APPUI_PLAN
    vitesse = np.hypot(v[:, 0], v[:, 1]) if plan else np.abs(v[:, 0])
    zone = vitesse <= FACTEUR_ZONE_ADHERENCE * f.epsilon
    pas = np.diff(t, prepend=t[0])
    duree_zone = float(np.sum(pas[zone]))
    deplacement = float(np.sum(vitesse[zone] * pas[zone]))
    vitesse_max = float(vitesse[zone].max()) if zone.any() else 0.0
    fluage = Fluage(vitesse_max, deplacement, duree_zone, f.epsilon)
    if duree <= 0.0 or duree_zone < PART_DUREE_FLUAGE_SIGNALE * duree:
        return fluage, None
    unite_v, unite_d = ("rad/s", "rad") if f.rotation else ("m/s", "m")
    message = (
        f"Frottement de Coulomb régularisé sur la liaison {f.liaison.nom} (ε = {f.epsilon:g} "
        f"{unite_v}) : en adhérence apparente, fluage jusqu'à {vitesse_max:.3g} {unite_v} "
        f"(déplacement cumulé {deplacement:.3g} {unite_d} sur {duree_zone:.3g} s)."
    )
    return fluage, message


# --------------------------------------------------------------------------- installation globale
class Installation:
    """Couplages, pertes de rendement et frottements d'une étude dans un système Exudyn."""

    def __init__(
        self,
        mbs: Any,
        etude: Etude,
        corps: Mapping[str, int],
        joints: Mapping[str, int],
    ) -> None:
        self.mbs = mbs
        self.etude = etude
        self.systeme = _Systeme(mbs, etude, corps)
        self.couplages = [CouplageInstalle(self.systeme, r) for r in relations(etude)]
        for c in self.couplages:
            c.installer_pertes(mbs, corps)
            c.ajouter_capteur(mbs)
        self.frottements = installer_frottements(mbs, etude, corps, joints)

    def extraire(self, resultats: Any, duree: float) -> None:
        """Renseigne `efforts_couplages`, `fluage` et les avertissements de `resultats`."""
        for c in self.couplages:
            donnees = np.asarray(self.mbs.GetSensorStoredData(c.capteur), dtype=float)
            resultats.efforts_couplages[c.relation.nom] = donnees[:, 1:3].copy()
        for f in self.frottements:
            donnees = np.asarray(self.mbs.GetSensorStoredData(f.capteur), dtype=float)
            fluage, message = fluage_frottement(f, donnees, duree)
            resultats.fluage[f.liaison.nom] = fluage
            if message is not None:
                resultats.avertissements.append(message)
