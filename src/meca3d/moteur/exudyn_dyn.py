# SPDX-License-Identifier: GPL-3.0-or-later
"""Moteur dynamique Exudyn : corps rigides, GenericJoint, pilotes, pesanteur, actions extérieures
et ressorts-amortisseurs (D1, EX-40, EX-32, EX-33)."""

import importlib
from collections.abc import Callable, Collection, Mapping, Sequence
from typing import Any

import numpy as np

from meca3d.modele.actions import ActionExterieure, NatureAction, Pilote, RepereAction
from meca3d.modele.etude import Etude
from meca3d.modele.liaison import DDL_BLOQUES, Liaison, Statut, TypeLiaison
from meca3d.moteur.base import (
    ErreurLiaisonNonPriseEnCharge,
    ErreurModele,
    ErreurSolveur,
    Reglages,
    ResultatsBruts,
)

# Les stubs d'exudyn sont inexacts : le module est manipulé comme Any.
exu: Any = importlib.import_module("exudyn")
_utilitaires: Any = importlib.import_module("exudyn.utilities")
ObjectGround = _utilitaires.ObjectGround
RigidBodyInertia = _utilitaires.RigidBodyInertia
SensorBody = _utilitaires.SensorBody
SensorObject = _utilitaires.SensorObject

# ARCHITECTURE § 5, CLAUDE.md : sans amortissement numérique (ρ∞ < 1), les réactions divergent.
RHO_INFINI = 0.9

# Linéaire rectiligne = deux ponctuelles de même normale, placées à ±ECART_PONCTUELLES le long de
# la ligne de contact (x local). La cinématique est exacte quel que soit l'écartement (z des deux
# points nul <=> Tz = 0 et Ry = 0) ; 0,1 m (valeur du prototype) évite seulement un mauvais
# conditionnement du jacobien (le bras de levier de Ry vaut l'écartement).
ECART_PONCTUELLES = 0.1  # m, demi-écartement
_AXES_PONCTUELLE = list(DDL_BLOQUES[TypeLiaison.PONCTUELLE])

# Capteurs cinématiques d'un corps mobile (repère monde) : V, W (vitesses), A, B (accélérations)
_CAPTEURS_CINEMATIQUES = {
    "V": "Velocity",
    "W": "AngularVelocity",
    "A": "Acceleration",
    "B": "AngularAcceleration",
}

# Indices de [Tx Ty Tz Rx Ry Rz] pilotés selon la grandeur imposée (EX-30)
_INDICE_PILOTE = {"angle": 3, "position": 0}
_GRANDEUR_PAR_TYPE = {
    TypeLiaison.PIVOT: "angle",
    TypeLiaison.GLISSIERE: "position",
    TypeLiaison.HELICOIDALE: "angle",
}


def _grandeur_pilote(pilote: Pilote, liaison: Liaison) -> str:
    if pilote.grandeur is not None:
        return pilote.grandeur
    grandeur = _GRANDEUR_PAR_TYPE.get(liaison.type) if liaison.type is not None else None
    if grandeur is None:
        raise ErreurModele(
            f"Liaison pilote {liaison.nom} : préciser la grandeur imposée (angle ou position)."
        )
    return grandeur


def _fonctions_offset(
    pilote: Pilote, indice: int, valeur_pose: float
) -> tuple[Callable[..., list[float]], Callable[..., list[float]]]:
    """Offsets du GenericJoint : l'écart à la pose d'import vaut loi(t) − valeur à l'import."""
    loi = pilote.loi

    def offset(mbs: Any, t: float, item: int, p: Any) -> list[float]:
        v = [0.0] * 6
        v[indice] = loi.valeur(t) - valeur_pose
        return v

    def offset_t(mbs: Any, t: float, item: int, p: Any) -> list[float]:
        v = [0.0] * 6
        v[indice] = loi.vitesse(t)
        return v

    return offset, offset_t


def _fonction_charge(action: ActionExterieure) -> Callable[..., list[float]]:
    """Fonction utilisateur d'Exudyn : vecteur force ou couple de l'action à l'instant t."""

    def charge(mbs: Any, t: float, load: Any) -> list[float]:
        return [float(x) for x in action.valeur(t)]

    return charge


def _verifier(etude: Etude) -> None:
    noms_solides = {s.nom for s in etude.solides}
    fixes = {s.nom for s in etude.solides if s.fixe}
    for action in etude.actions:
        if action.solide not in noms_solides:
            raise ErreurModele(f"Action {action.nom} : solide inconnu « {action.solide} ».")
        if action.solide in fixes:
            raise ErreurModele(
                f"Action {action.nom} : le solide {action.solide} est fixe (bâti), une action "
                "extérieure n'y produit aucun mouvement ; l'appliquer à un solide mobile."
            )
    for ressort in etude.ressorts:
        for nom in (ressort.solide_1, ressort.solide_2):
            if nom not in noms_solides:
                raise ErreurModele(f"Ressort {ressort.nom} : solide inconnu « {nom} ».")
    for liaison in etude.liaisons:
        if liaison.statut is not Statut.VALIDEE or liaison.type is None:
            raise ErreurModele(
                f"La liaison {liaison.nom} n'est pas validée : "
                "valider chaque liaison avant de simuler."
            )
        for nom in (liaison.solide_a, liaison.solide_b):
            if nom not in noms_solides:
                raise ErreurModele(f"Liaison {liaison.nom} : solide inconnu « {nom} ».")
    if not any(s.fixe for s in etude.solides):
        raise ErreurModele("Aucun solide fixe (bâti) dans le modèle.")
    noms_liaisons = {x.nom for x in etude.liaisons}
    for pilote in etude.pilotes:
        if pilote.liaison not in noms_liaisons:
            raise ErreurModele(f"Pilote : liaison inconnue « {pilote.liaison} ».")
        if etude.liaison(pilote.liaison).valeur_pose is None:
            raise ErreurModele(f"Pilote {pilote.liaison} : pose initiale inconnue.")
    for liaison in etude.liaisons:
        if liaison.type is TypeLiaison.HELICOIDALE:
            raise ErreurLiaisonNonPriseEnCharge(
                f"Liaison {liaison.nom} : liaison hélicoïdale non encore prise en charge par le "
                "moteur (le couplage Tx = p·Rx / 2π est prévu au lot 7)."
            )


class MoteurExudynDyn:
    """Implémente `Moteur` : dynamique à pas fixe, generalized-α."""

    def simuler(
        self,
        etude: Etude,
        reglages: Reglages | None = None,
        vitesses_initiales: Mapping[
            str, tuple[Sequence[float] | np.ndarray, Sequence[float] | np.ndarray]
        ]
        | None = None,
        ddl_liberes: Collection[tuple[str, int]] | None = None,
    ) -> ResultatsBruts:
        """`vitesses_initiales` : par solide, (vitesse du CdG, vitesse angulaire), repère monde, SI.

        Par défaut, départ au repos. Elles doivent être compatibles avec les liaisons.
        `ddl_liberes` : (liaison, indice de ddl dans [Tx Ty Tz Rx Ry Rz]) dont le blocage est
        retiré (EX-23, option « Hyperstatique autorisé »).
        """
        reglages = reglages or etude.reglages
        vitesses_initiales = vitesses_initiales or {}
        liberes = set(ddl_liberes or ())
        _verifier(etude)
        exu.config.printToConsole = False
        conteneur = exu.SystemContainer()
        mbs = conteneur.AddSystem()
        sol = mbs.AddObject(ObjectGround())
        g = [float(x) for x in etude.pesanteur.effectif()]

        corps: dict[str, int] = {}
        for s in etude.solides:
            if s.fixe:
                corps[s.nom] = sol
                continue
            v0, w0 = vitesses_initiales.get(s.nom, ((0.0, 0.0, 0.0), (0.0, 0.0, 0.0)))
            corps[s.nom] = mbs.CreateRigidBody(
                initialVelocity=[float(x) for x in v0],
                initialAngularVelocity=[float(x) for x in w0],
                inertia=RigidBodyInertia(
                    mass=s.masse, inertiaTensor=s.inertie, inertiaTensorAtCOM=True
                ),
                referencePosition=[float(x) for x in s.cdg],
                gravity=g,
            )

        pilotes = {p.liaison: p for p in etude.pilotes}
        joints: dict[str, list[tuple[int, float]]] = {}  # (joint, décalage le long de x local)
        for liaison in etude.liaisons:
            axes = liaison.ddl_bloques()
            for nom_liberee, ddl in liberes:
                if nom_liberee == liaison.nom:
                    axes[ddl] = 0
            options: dict[str, Any] = {}
            pilote = pilotes.get(liaison.nom)
            if pilote is not None:
                if liaison.type is TypeLiaison.LINEAIRE_RECTILIGNE:
                    raise ErreurModele(
                        f"Liaison pilote {liaison.nom} : une linéaire rectiligne ne peut pas "
                        "être pilotée."
                    )
                indice = _INDICE_PILOTE[_grandeur_pilote(pilote, liaison)]
                if axes[indice] == 1:
                    raise ErreurModele(
                        f"Liaison pilote {liaison.nom} : la grandeur imposée correspond à un "
                        "ddl bloqué par la liaison."
                    )
                axes[indice] = 1
                assert liaison.valeur_pose is not None
                options["offsetUserFunction"], options["offsetUserFunction_t"] = _fonctions_offset(
                    pilote, indice, liaison.valeur_pose
                )
            base = liaison.base()
            if liaison.type is TypeLiaison.LINEAIRE_RECTILIGNE:
                decalages = [-ECART_PONCTUELLES, ECART_PONCTUELLES]
                axes = _AXES_PONCTUELLE
            else:
                decalages = [0.0]
            joints[liaison.nom] = [
                (
                    mbs.CreateGenericJoint(
                        itemNumbers=[corps[liaison.solide_a], corps[liaison.solide_b]],
                        position=[float(x) for x in liaison.centre + decalage * base[:, 0]],
                        rotationMatrixAxes=base,
                        constrainedAxes=axes,
                        show=False,
                        **options,
                    ),
                    decalage,
                )
                for decalage in decalages
            ]

        for action in etude.actions:
            solide = etude.solide(action.solide)
            creer = mbs.CreateForce if action.nature is NatureAction.FORCE else mbs.CreateTorque
            creer(
                itemNumber=corps[action.solide],
                loadVector=[0.0, 0.0, 0.0],
                # le repère du solide coïncide avec le monde à la pose d'import (rotation nulle)
                localPosition=[float(x) for x in np.array(action.point) - solide.cdg],
                bodyFixed=action.repere is RepereAction.SOLIDE,
                loadVectorUserFunction=_fonction_charge(action),
                show=False,
            )
        for ressort in etude.ressorts:
            locales = []
            for nom, point in (
                (ressort.solide_1, ressort.point_1),
                (ressort.solide_2, ressort.point_2),
            ):
                solide = etude.solide(nom)
                # solide fixe : repère local = repère monde ; solide mobile : relatif au CdG
                locales.append(
                    [
                        float(x)
                        for x in (np.array(point) if solide.fixe else np.array(point) - solide.cdg)
                    ]
                )
            mbs.CreateSpringDamper(
                itemNumbers=[corps[ressort.solide_1], corps[ressort.solide_2]],
                localPosition0=locales[0],
                localPosition1=locales[1],
                referenceLength=ressort.longueur_libre,
                stiffness=ressort.raideur,
                damping=ressort.amortissement,
                show=False,
            )

        capteurs: dict[str, int] = {}
        types = exu.OutputVariableType
        for nom, liste in joints.items():
            for k, (joint, _) in enumerate(liste):
                capteurs[f"F:{nom}:{k}"] = mbs.AddSensor(
                    SensorObject(
                        objectNumber=joint, storeInternal=True, outputVariableType=types.ForceLocal
                    )
                )
                capteurs[f"M:{nom}:{k}"] = mbs.AddSensor(
                    SensorObject(
                        objectNumber=joint,
                        storeInternal=True,
                        outputVariableType=types.TorqueLocal,
                    )
                )
        for s in etude.solides:
            if not s.fixe:
                capteurs[f"P:{s.nom}"] = mbs.AddSensor(
                    SensorBody(
                        bodyNumber=corps[s.nom],
                        storeInternal=True,
                        outputVariableType=types.Position,
                    )
                )
                for cle, type_sortie in _CAPTEURS_CINEMATIQUES.items():
                    capteurs[f"{cle}:{s.nom}"] = mbs.AddSensor(
                        SensorBody(
                            bodyNumber=corps[s.nom],
                            storeInternal=True,
                            outputVariableType=getattr(types, type_sortie),
                        )
                    )
                capteurs[f"R:{s.nom}"] = mbs.AddSensor(
                    SensorBody(
                        bodyNumber=corps[s.nom],
                        storeInternal=True,
                        outputVariableType=types.RotationMatrix,
                    )
                )

        ss = exu.SimulationSettings()
        ss.timeIntegration.endTime = reglages.duree
        ss.timeIntegration.numberOfSteps = reglages.nb_pas
        ss.timeIntegration.verboseMode = 0
        ss.timeIntegration.generalizedAlpha.spectralRadius = RHO_INFINI
        ss.solution.file.write = False
        ss.solution.sensors.writePeriod = reglages.periode_ecriture
        ss.show.computationTime = False
        ss.show.statistics = False

        mbs.Assemble()
        try:
            reussi = mbs.SolveDynamic(ss)
        except Exception as e:  # le moteur C++ lève des exceptions Python génériques
            raise ErreurSolveur(self._message_echec(mbs, str(e)), self._temps(mbs)) from e
        if reussi is False:
            raise ErreurSolveur(self._message_echec(mbs, ""), self._temps(mbs))

        donnees = {
            k: np.asarray(mbs.GetSensorStoredData(i), dtype=float) for k, i in capteurs.items()
        }
        t = donnees[next(iter(donnees))][:, 0].copy()
        res = ResultatsBruts(t=t)
        for nom, liste in joints.items():
            # Torseur résultant au centre de la liaison, en base de liaison (les ponctuelles de la
            # linéaire rectiligne partagent la même base : M_c = Σ M_i + (p_i − c) × F_i).
            force = np.zeros((len(t), 3))
            moment = np.zeros((len(t), 3))
            for k, (_, decalage) in enumerate(liste):
                f_k = donnees[f"F:{nom}:{k}"][:, 1:4]
                force += f_k
                moment += donnees[f"M:{nom}:{k}"][:, 1:4] + np.cross([decalage, 0.0, 0.0], f_k)
            res.forces[nom] = force
            res.moments[nom] = moment
        for s in etude.solides:
            if not s.fixe:
                res.positions[s.nom] = donnees[f"P:{s.nom}"][:, 1:4].copy()
                res.rotations[s.nom] = donnees[f"R:{s.nom}"][:, 1:10].reshape(-1, 3, 3).copy()
                res.vitesses[s.nom] = donnees[f"V:{s.nom}"][:, 1:4].copy()
                res.vitesses_angulaires[s.nom] = donnees[f"W:{s.nom}"][:, 1:4].copy()
                res.accelerations[s.nom] = donnees[f"A:{s.nom}"][:, 1:4].copy()
                res.accelerations_angulaires[s.nom] = donnees[f"B:{s.nom}"][:, 1:4].copy()
        return res

    @staticmethod
    def _temps(mbs: Any) -> float | None:
        try:
            return float(mbs.systemData.GetTime(exu.ConfigurationType.Current))
        except Exception:
            return None

    @staticmethod
    def _message_echec(mbs: Any, detail: str) -> str:
        t = MoteurExudynDyn._temps(mbs)
        quand = "" if t is None else f" à t = {t:.4g} s"
        return (
            f"Le solveur a échoué{quand}. Causes fréquentes : modèle hyperstatique (jacobien "
            "singulier) ou configuration singulière (point mort). Revoir les choix de liaison."
            + (f" Détail : {detail}" if detail else "")
        )
