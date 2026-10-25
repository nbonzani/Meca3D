# SPDX-License-Identifier: GPL-3.0-or-later
"""Calcul dans un processus séparé (D9, EX-42, EX-43).

Indépendant de Qt : l'IHM interroge `CalculEnCours.interroger()` depuis un minuteur, la ligne de
commande peut utiliser `simuler_en_processus()`.

- Démarrage `spawn` (seul mode sous Windows, compatible PyInstaller avec `freeze_support`).
- Frontière sérialisée : l'étude traverse sous forme de dict JSON (`Etude.vers_dict`), les
  résultats reviennent en tableaux numpy (`ResultatsBruts`), les erreurs en (type, message, t).
- Progression : un message au plus toutes les `PERIODE_PROGRESSION` s, émis par la fonction
  utilisateur post-pas du solveur ; la même fonction lit l'événement d'annulation douce.
- Annulation : douce (le solveur s'arrête proprement au pas suivant), puis `terminate()` si le
  processus n'a pas fini après `DELAI_ANNULATION_DOUCE` (prototype du lot 1a : terminate en 7 ms).
"""

import importlib
import importlib.util
import multiprocessing
import queue
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from multiprocessing.context import SpawnProcess
from multiprocessing.synchronize import Event as EvenementMP
from typing import Any

from meca3d.modele.etude import Etude, Reglages
from meca3d.moteur.base import (
    ErreurLiaisonNonPriseEnCharge,
    ErreurModele,
    ErreurMoteur,
    ErreurSolveur,
    ResultatsBruts,
)

PERIODE_PROGRESSION = 0.05  # s entre deux messages de progression (au plus 20 par seconde)
DELAI_ANNULATION_DOUCE = 0.3  # s avant le terminate() ; EX-42 exige < 1 s au total
DELAI_ARRET_PROCESSUS = 2.0  # s d'attente maximale du join après terminate()
SCRUTATION_MAX = 0.05  # s, attente maximale sur la file dans attendre()

_MODULE_CINEMATIQUE = "meca3d.moteur.cinematique"  # lot 6
_CLASSE_CINEMATIQUE = "MoteurCinematique"


class ModeSimulation(StrEnum):
    DYNAMIQUE = "dynamique"
    CINEMATIQUE = "cinematique"


class EtatCalcul(StrEnum):
    PRET = "pret"  # aucun calcul lancé
    EN_COURS = "en_cours"
    TERMINE = "termine"
    ANNULE = "annule"
    ECHEC = "echec"


@dataclass(frozen=True)
class Progression:
    fraction: float  # 0..1
    t: float  # instant simulé courant (s)


def cinematique_disponible() -> bool:
    """Le mode cinématique (lot 6, `moteur/cinematique.py`) est-il présent dans ce dépôt ?"""
    try:
        return importlib.util.find_spec(_MODULE_CINEMATIQUE) is not None
    except (ImportError, ValueError):
        return False


# --- côté processus fils --------------------------------------------------------------------
class _SystemeSuivi:
    """Enveloppe d'un `MainSystem` Exudyn : `SolveDynamic` installe la fonction post-pas."""

    def __init__(self, systeme: Any, post_pas: Callable[[Any, float], bool]) -> None:
        self._systeme = systeme
        self._post_pas = post_pas

    def SolveDynamic(self, *args: Any, **kwargs: Any) -> Any:
        self._systeme.SetPostStepUserFunction(self._post_pas)
        return self._systeme.SolveDynamic(*args, **kwargs)

    def __getattr__(self, nom: str) -> Any:
        return getattr(self._systeme, nom)


class _ConteneurSuivi:
    def __init__(self, conteneur: Any, post_pas: Callable[[Any, float], bool]) -> None:
        self._conteneur = conteneur
        self._post_pas = post_pas

    def AddSystem(self, *args: Any, **kwargs: Any) -> _SystemeSuivi:
        return _SystemeSuivi(self._conteneur.AddSystem(*args, **kwargs), self._post_pas)

    def __getattr__(self, nom: str) -> Any:
        return getattr(self._conteneur, nom)


class _ExudynSuivi:
    """Module `exudyn` vu par `moteur/exudyn_dyn.py` dans le fils : seul `SystemContainer` change.

    Cela donne la progression et l'annulation douce sans modifier le moteur (les modes dynamique
    et cinématique passent tous deux par `exudyn_dyn`).
    """

    def __init__(self, exu: Any, post_pas: Callable[[Any, float], bool]) -> None:
        self._exu = exu
        self._post_pas = post_pas

    def SystemContainer(self, *args: Any, **kwargs: Any) -> _ConteneurSuivi:
        return _ConteneurSuivi(self._exu.SystemContainer(*args, **kwargs), self._post_pas)

    def __getattr__(self, nom: str) -> Any:
        return getattr(self._exu, nom)


def _charger_moteur(mode: ModeSimulation) -> Any:
    if mode is ModeSimulation.DYNAMIQUE:
        from meca3d.moteur.exudyn_dyn import MoteurExudynDyn

        return MoteurExudynDyn()
    if not cinematique_disponible():
        raise ErreurModele(
            "Le mode cinématique n'est pas encore disponible dans cette version de Meca3D."
        )
    module = importlib.import_module(_MODULE_CINEMATIQUE)
    return getattr(module, _CLASSE_CINEMATIQUE)()


def _travailleur(
    sortie: Any,
    annulation: EvenementMP,
    donnees_etude: dict[str, Any],
    donnees_reglages: dict[str, Any] | None,
    mode: str,
) -> None:
    """Point d'entrée du processus fils ; toute exception est convertie en message typé."""
    try:
        etude = Etude.depuis_dict(donnees_etude)
        reglages = None if donnees_reglages is None else Reglages.depuis_dict(donnees_reglages)
        duree = (reglages or etude.reglages).duree
        sortie.put(("demarre",))
        dernier = [0.0]

        def post_pas(mbs: Any, t: float) -> bool:
            maintenant = time.perf_counter()
            if maintenant - dernier[0] >= PERIODE_PROGRESSION:
                dernier[0] = maintenant
                sortie.put(("progression", min(1.0, max(0.0, t / duree)), float(t)))
            return not annulation.is_set()

        from meca3d.moteur import exudyn_dyn

        moteur = _charger_moteur(ModeSimulation(mode))
        reel = exudyn_dyn.exu
        exudyn_dyn.exu = _ExudynSuivi(reel, post_pas)
        try:
            resultats = moteur.simuler(etude, reglages)
        finally:
            exudyn_dyn.exu = reel
        if annulation.is_set():
            sortie.put(("annule",))
        else:
            sortie.put(("fin", resultats))
    except ErreurMoteur as e:
        if annulation.is_set():
            sortie.put(("annule",))
        else:
            t_echec = e.t_echec if isinstance(e, ErreurSolveur) else None
            sortie.put(("erreur", type(e).__name__, str(e), t_echec))
    except Exception as e:  # noqa: BLE001 - jamais de trace brute vers l'élève
        sortie.put(
            (
                "erreur",
                "ErreurMoteur",
                f"Erreur inattendue du calcul ({type(e).__name__}) : {e}",
                None,
            )
        )


_ERREURS_TYPEES: dict[str, type[ErreurMoteur]] = {
    "ErreurModele": ErreurModele,
    "ErreurLiaisonNonPriseEnCharge": ErreurLiaisonNonPriseEnCharge,
    "ErreurMoteur": ErreurMoteur,
}


def _reconstruire_erreur(nom: str, message: str, t_echec: float | None) -> ErreurMoteur:
    if nom == "ErreurSolveur":
        return ErreurSolveur(message, t_echec)
    return _ERREURS_TYPEES.get(nom, ErreurMoteur)(message)


# --- côté processus parent ------------------------------------------------------------------
class CalculEnCours:
    """Un calcul dans un processus séparé. Non réutilisable : un objet par simulation."""

    def __init__(
        self,
        etude: Etude,
        mode: ModeSimulation = ModeSimulation.DYNAMIQUE,
        reglages: Reglages | None = None,
    ) -> None:
        self.donnees_etude: dict[str, Any] = etude.vers_dict()
        self._donnees_reglages = None if reglages is None else reglages.vers_dict()
        self.mode = mode
        self.etat = EtatCalcul.PRET
        self.resultats: ResultatsBruts | None = None
        self.erreur: ErreurMoteur | None = None
        self.progression: Progression | None = None
        self._processus: SpawnProcess | None = None
        self._file: Any = None
        self._annulation: EvenementMP | None = None

    @property
    def processus_vivant(self) -> bool:
        return self._processus is not None and self._processus.is_alive()

    def demarrer(self) -> None:
        if self.etat is not EtatCalcul.PRET:
            raise RuntimeError("Un calcul ne se lance qu'une fois.")
        contexte = multiprocessing.get_context("spawn")
        self._file = contexte.Queue()
        self._annulation = contexte.Event()
        self._processus = contexte.Process(
            target=_travailleur,
            args=(
                self._file,
                self._annulation,
                self.donnees_etude,
                self._donnees_reglages,
                self.mode.value,
            ),
            daemon=True,
        )
        self._processus.start()
        self.etat = EtatCalcul.EN_COURS

    def _traiter(self, message: tuple[Any, ...], nouvelles: list[Progression]) -> None:
        genre = message[0]
        if genre == "progression":
            self.progression = Progression(fraction=message[1], t=message[2])
            nouvelles.append(self.progression)
        elif genre == "fin":
            self.resultats = message[1]
            self.etat = EtatCalcul.TERMINE
        elif genre == "erreur":
            self.erreur = _reconstruire_erreur(message[1], message[2], message[3])
            self.etat = EtatCalcul.ECHEC
        elif genre == "annule":
            self.etat = EtatCalcul.ANNULE

    def interroger(self, attente: float = 0.0) -> list[Progression]:
        """Vide la file sans bloquer (ou après `attente` s) ; renvoie les nouvelles progressions.

        Met à jour `etat`, `resultats` et `erreur`. Détecte la mort inattendue du processus.
        """
        nouvelles: list[Progression] = []
        if self.etat is not EtatCalcul.EN_COURS or self._file is None:
            return nouvelles
        while self.etat is EtatCalcul.EN_COURS:
            try:
                message = (
                    self._file.get(timeout=attente) if attente > 0 else self._file.get_nowait()
                )
            except queue.Empty:
                break
            attente = 0.0
            self._traiter(message, nouvelles)
        if self.etat is EtatCalcul.EN_COURS and not self.processus_vivant:
            # le processus est mort : lire ce qui reste dans le tuyau avant de conclure
            while True:
                try:
                    self._traiter(self._file.get(timeout=0.2), nouvelles)
                except queue.Empty:
                    break
            if self.etat is EtatCalcul.EN_COURS:
                self.erreur = ErreurMoteur(
                    "Le processus de calcul s'est arrêté de façon inattendue "
                    "(mémoire insuffisante ou plantage du solveur). Aucun résultat disponible."
                )
                self.etat = EtatCalcul.ECHEC
        if self.etat is not EtatCalcul.EN_COURS:
            self._liberer()
        return nouvelles

    def attendre(
        self,
        timeout: float | None = None,
        rappel_progression: Callable[[Progression], None] | None = None,
    ) -> EtatCalcul:
        """Bloque jusqu'à la fin du calcul (ou `timeout` s) et renvoie l'état."""
        fin = None if timeout is None else time.perf_counter() + timeout
        while self.etat is EtatCalcul.EN_COURS:
            for p in self.interroger(attente=SCRUTATION_MAX):
                if rappel_progression is not None:
                    rappel_progression(p)
            if fin is not None and time.perf_counter() > fin:
                break
        return self.etat

    def annuler(self) -> None:
        """EX-42 : arrêt doux puis terminate(), retour à l'état prêt (< 1 s), aucun résultat."""
        if self.etat is not EtatCalcul.EN_COURS or self._processus is None:
            return
        assert self._annulation is not None
        self._annulation.set()
        self._processus.join(timeout=DELAI_ANNULATION_DOUCE)
        if self._processus.is_alive():
            self._processus.terminate()
            self._processus.join(timeout=DELAI_ARRET_PROCESSUS)
        self.resultats = None
        self.erreur = None
        self.etat = EtatCalcul.ANNULE
        self._liberer()

    def _liberer(self) -> None:
        if self._processus is not None:
            self._processus.join(timeout=DELAI_ARRET_PROCESSUS)
        if self._file is not None:
            self._file.close()
            self._file.cancel_join_thread()
            self._file = None


def simuler_en_processus(
    etude: Etude,
    mode: ModeSimulation = ModeSimulation.DYNAMIQUE,
    reglages: Reglages | None = None,
    rappel_progression: Callable[[Progression], None] | None = None,
) -> ResultatsBruts:
    """Simulation bloquante dans un processus séparé ; relance l'erreur typée du moteur."""
    calcul = CalculEnCours(etude, mode, reglages)
    calcul.demarrer()
    try:
        calcul.attendre(rappel_progression=rappel_progression)
    except BaseException:
        calcul.annuler()
        raise
    if calcul.erreur is not None:
        raise calcul.erreur
    assert calcul.resultats is not None
    return calcul.resultats
