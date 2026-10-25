# SPDX-License-Identifier: GPL-3.0-or-later
"""Mode cinématique (EX-41, D7) et option « Hyperstatique autorisé » (EX-23, simulation).

Les positions viennent d'Exudyn (`moteur/exudyn_dyn.py`) : m liaisons pilotées, pesanteur,
actions et ressorts mis de côté, aucun effort présenté, ddl redondants libérés (`constrainedAxes`
à 0). Les vitesses et accélérations de tous les solides sont ensuite obtenues DIRECTEMENT, sans
différence finie, en dérivant analytiquement une et deux fois les équations de liaison : à chaque
instant, un système linéaire en torseurs cinématiques (v, ω) puis en accélérations (a, α) est résolu
à partir des poses d'Exudyn.

Écart à D7 (« capteurs Exudyn ») : mesuré le 25 octobre 2026 sur la bielle-manivelle à 20 rad/s
avec 4 000 pas par seconde, les accélérations des capteurs d'Exudyn (generalized-α, contraintes
d'indice 3) ont une erreur de 4·10⁻³ relative au maximum (ordre 1 en h), et la vitesse relative d'un
point de pivot reste à 3·10⁻⁷ au lieu des 10⁻⁹ d'EX-51 ; la formulation d'indice 2 est indisponible
avec `offsetUserFunction_t`. La dérivation directe est exacte à la précision numérique.

Les rangées de rotation utilisent la vitesse angulaire relative exprimée dans la base de liaison,
exacte pour toutes les liaisons du catalogue ; la rotule à doigt a son équation propre, celle
qu'Exudyn contraint : (x local de a)·(y local de b) = 0.
"""

from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass, replace

import numpy as np

from meca3d.modele.actions import Pesanteur, Pilote
from meca3d.modele.etude import Etude, Reglages
from meca3d.modele.liaison import Liaison, TypeLiaison
from meca3d.moteur.base import ErreurModele, ResultatsBruts
from meca3d.moteur.exudyn_dyn import (
    _INDICE_PILOTE,
    ECART_PONCTUELLES,
    MoteurExudynDyn,
    _grandeur_pilote,
)

# Résidu admis sur le système des vitesses initiales (m/s ou rad/s)
TOLERANCE_VITESSES_INITIALES = 1e-6
RCOND_CINEMATIQUE = 1e-10


@dataclass(frozen=True)
class _Contrainte:
    """Une équation de liaison : composante `axe` (0..2) de la base de liaison, translation
    (`rotation` faux, au point décalé de `decalage` le long de x local) ou rotation relative."""

    liaison: Liaison
    rotation: bool
    axe: int
    decalage: float = 0.0
    pilote: Pilote | None = None
    doigt: bool = False  # rotule à doigt : x local du solide a ⟂ y local du solide b


def _contraintes(etude: Etude, liberes: Collection[tuple[str, int]]) -> list[_Contrainte]:
    pilotes = {p.liaison: p for p in etude.pilotes}
    contraintes: list[_Contrainte] = []
    for liaison in etude.liaisons:
        if liaison.type is TypeLiaison.LINEAIRE_RECTILIGNE:
            # réalisée par deux ponctuelles (Tz) aux points ±ECART_PONCTUELLES le long de x local
            contraintes += [
                _Contrainte(liaison, False, 2, -ECART_PONCTUELLES),
                _Contrainte(liaison, False, 2, ECART_PONCTUELLES),
            ]
            continue
        axes = liaison.ddl_bloques()
        for nom, ddl in liberes:
            if nom == liaison.nom:
                axes[ddl] = 0
        pilote = pilotes.get(liaison.nom)
        piloté = None
        if pilote is not None:
            piloté = _INDICE_PILOTE[_grandeur_pilote(pilote, liaison)]
            axes[piloté] = 1
        for ddl, bloque in enumerate(axes):
            if bloque and ddl == 5 and liaison.type is TypeLiaison.ROTULE_A_DOIGT:
                # Exudyn contraint Rz de la rotule à doigt par (x local de a)·(y local de b) = 0
                # (vérifié : R_rel[0, 1] = 1e-14), non par ω_rel·z = 0
                contraintes.append(_Contrainte(liaison, True, 2, doigt=True))
            elif bloque:
                est_pilote = ddl == piloté
                contraintes.append(
                    _Contrainte(liaison, ddl >= 3, ddl % 3, 0.0, pilote if est_pilote else None)
                )
    return contraintes


class _Cinematique:
    """Résolution des vitesses puis des accélérations à partir d'une pose des solides."""

    def __init__(self, etude: Etude, liberes: Collection[tuple[str, int]]) -> None:
        self.etude = etude
        self.contraintes = _contraintes(etude, liberes)
        self.mobiles = [s.nom for s in etude.solides if not s.fixe]
        self.colonne = {nom: 6 * k for k, nom in enumerate(self.mobiles)}
        self.cdg0 = {s.nom: s.cdg for s in etude.solides}
        self.bases = {x.nom: x.base() for x in etude.liaisons}

    def _systeme(
        self,
        x: Mapping[str, np.ndarray],
        r: Mapping[str, np.ndarray],
        t: float,
        vitesses: np.ndarray | None,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Matrice et second membre ; `vitesses` None : niveau vitesse, sinon niveau accélération
        (torseurs (v, ω) des solides mobiles, connus)."""
        n = 6 * len(self.mobiles)
        matrice = np.zeros((len(self.contraintes), n))
        membre = np.zeros(len(self.contraintes))

        def torseur(nom: str) -> tuple[np.ndarray, np.ndarray]:
            if vitesses is None or nom not in self.colonne:
                return np.zeros(3), np.zeros(3)
            c = self.colonne[nom]
            return vitesses[c : c + 3], vitesses[c + 3 : c + 6]

        for i, c in enumerate(self.contraintes):
            liaison = c.liaison
            na, nb = liaison.solide_a, liaison.solide_b
            ra, rb = r[na], r[nb]
            base0 = self.bases[liaison.nom]
            u = ra @ base0[:, c.axe]
            va, wa = torseur(na)
            vb, wb = torseur(nb)
            if c.pilote is None:
                derivee1 = derivee2 = 0.0
            else:
                derivee1 = c.pilote.loi.vitesse(t)
                derivee2 = c.pilote.loi.acceleration(t)
            if c.doigt:
                x_a = ra @ base0[:, 0]
                y_b = rb @ base0[:, 1]
                n = np.cross(y_b, x_a)
                coefficients = {nb: (np.zeros(3), n), na: (np.zeros(3), -n)}
                if vitesses is None:
                    membre[i] = 0.0
                else:
                    n_point = np.cross(np.cross(wb, y_b), x_a) + np.cross(y_b, np.cross(wa, x_a))
                    membre[i] = -float((wb - wa) @ n_point)
            elif c.rotation:
                coefficients = {nb: (np.zeros(3), u), na: (np.zeros(3), -u)}
                if vitesses is None:
                    membre[i] = derivee1
                else:
                    membre[i] = derivee2 + float(u @ np.cross(wa, wb - wa))
            else:
                p0 = liaison.centre + c.decalage * base0[:, 0]
                sa = ra @ (p0 - self.cdg0[na])
                sb = rb @ (p0 - self.cdg0[nb])
                ecart = (x[nb] + sb) - (x[na] + sa)
                coefficients = {
                    nb: (u, np.cross(sb, u)),
                    na: (-u, -np.cross(sa, u) - np.cross(ecart, u)),
                }
                if vitesses is None:
                    membre[i] = derivee1
                else:
                    vitesse_relative = (vb + np.cross(wb, sb)) - (va + np.cross(wa, sa))
                    w = vitesse_relative - np.cross(wa, ecart)
                    reste = (
                        np.cross(wb, np.cross(wb, sb))
                        - np.cross(wa, np.cross(wa, sa))
                        - np.cross(wa, vitesse_relative)
                        - np.cross(wa, w)
                    )
                    membre[i] = derivee2 - float(u @ reste)
            for nom, (coeff_v, coeff_w) in coefficients.items():
                if nom in self.colonne:
                    col = self.colonne[nom]
                    matrice[i, col : col + 3] += coeff_v
                    matrice[i, col + 3 : col + 6] += coeff_w
        return matrice, membre

    def resoudre(
        self,
        x: Mapping[str, np.ndarray],
        r: Mapping[str, np.ndarray],
        t: float,
    ) -> tuple[np.ndarray, np.ndarray, float]:
        """(vitesses, accélérations, résidu des vitesses) de tous les solides mobiles."""
        if not self.mobiles:
            return np.zeros(0), np.zeros(0), 0.0
        matrice, membre = self._systeme(x, r, t, None)
        vitesses = np.linalg.lstsq(matrice, membre, rcond=RCOND_CINEMATIQUE)[0]
        residu = float(np.abs(matrice @ vitesses - membre).max(initial=0.0))
        matrice, membre = self._systeme(x, r, t, vitesses)
        accelerations = np.linalg.lstsq(matrice, membre, rcond=RCOND_CINEMATIQUE)[0]
        return vitesses, accelerations, residu

    def etat_initial(self) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray]]:
        return (
            {nom: self.cdg0[nom] for nom in self.cdg0},
            {nom: np.eye(3) for nom in self.cdg0},
        )


def vitesses_initiales(
    etude: Etude, liberes: Collection[tuple[str, int]] = ()
) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    """Torseurs cinématiques de départ compatibles avec les liaisons et les lois (t = 0)."""
    cinematique = _Cinematique(etude, liberes)
    x, r = cinematique.etat_initial()
    vitesses, _, residu = cinematique.resoudre(x, r, 0.0)
    if residu > TOLERANCE_VITESSES_INITIALES:
        raise ErreurModele(
            "Les vitesses imposées par les lois d'entrée sont incompatibles avec les liaisons à "
            "l'instant initial (configuration singulière, point mort ou loi sur une liaison "
            "bloquée). Revoir les lois d'entrée ou la configuration."
        )
    return {
        nom: (vitesses[c : c + 3], vitesses[c + 3 : c + 6])
        for nom, c in cinematique.colonne.items()
    }


def residu_vitesses(
    etude: Etude, resultats: ResultatsBruts, liberes: Collection[tuple[str, int]] = ()
) -> np.ndarray:
    """Résidu (n, nb de contraintes) des équations de liaison au niveau vitesse, évalué avec les
    vitesses de `resultats` (diagnostic : nul si elles sont compatibles avec les liaisons)."""
    cinematique = _Cinematique(etude, liberes)
    sortie = np.zeros((len(resultats.t), len(cinematique.contraintes)))
    for i in range(len(resultats.t)):
        x = {nom: cinematique.cdg0[nom] for nom in cinematique.cdg0}
        r = {nom: np.eye(3) for nom in cinematique.cdg0}
        twist = np.zeros(6 * len(cinematique.mobiles))
        for nom, c in cinematique.colonne.items():
            x[nom] = resultats.positions[nom][i]
            r[nom] = resultats.rotations[nom][i]
            twist[c : c + 3] = resultats.vitesses[nom][i]
            twist[c + 3 : c + 6] = resultats.vitesses_angulaires[nom][i]
        matrice, membre = cinematique._systeme(x, r, float(resultats.t[i]), None)
        sortie[i] = matrice @ twist - membre
    return sortie


def calculer_cinematique(
    etude: Etude, resultats: ResultatsBruts, liberes: Collection[tuple[str, int]] = ()
) -> None:
    """Remplit vitesses et accélérations exactes (en place) à partir des poses d'Exudyn."""
    cinematique = _Cinematique(etude, liberes)
    n = len(resultats.t)
    for nom in cinematique.mobiles:
        resultats.vitesses[nom] = np.zeros((n, 3))
        resultats.vitesses_angulaires[nom] = np.zeros((n, 3))
        resultats.accelerations[nom] = np.zeros((n, 3))
        resultats.accelerations_angulaires[nom] = np.zeros((n, 3))
    for i in range(n):
        x = {nom: cinematique.cdg0[nom] for nom in cinematique.cdg0}
        r = {nom: np.eye(3) for nom in cinematique.cdg0}
        for nom in cinematique.mobiles:
            x[nom] = resultats.positions[nom][i]
            r[nom] = resultats.rotations[nom][i]
        vitesses, accelerations, _ = cinematique.resoudre(x, r, float(resultats.t[i]))
        for nom, c in cinematique.colonne.items():
            resultats.vitesses[nom][i] = vitesses[c : c + 3]
            resultats.vitesses_angulaires[nom][i] = vitesses[c + 3 : c + 6]
            resultats.accelerations[nom][i] = accelerations[c : c + 3]
            resultats.accelerations_angulaires[nom][i] = accelerations[c + 3 : c + 6]


class MoteurCinematique:
    """Mode cinématique : positions d'Exudyn, vitesses et accélérations directes, aucun effort."""

    def simuler(
        self,
        etude: Etude,
        reglages: Reglages | None = None,
        ddl_liberes: Sequence[tuple[str, int]] | None = None,
    ) -> ResultatsBruts:
        liberes = sorted(set(ddl_liberes or ()))
        etude_cinematique = replace(
            etude, pesanteur=Pesanteur(actif=False), actions=[], ressorts=[]
        )
        resultats = MoteurExudynDyn().simuler(
            etude_cinematique,
            reglages,
            vitesses_initiales=vitesses_initiales(etude_cinematique, liberes),
            ddl_liberes=liberes,
        )
        calculer_cinematique(etude_cinematique, resultats, liberes)
        resultats.forces = {}
        resultats.moments = {}
        resultats.ddl_liberes = [(nom, int(ddl)) for nom, ddl in liberes]
        return resultats
