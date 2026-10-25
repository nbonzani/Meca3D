# SPDX-License-Identifier: GPL-3.0-or-later
"""Simulation d'une étude : garde-fou EX-22 appelé avant tout appel au moteur, option EX-23, Q8.

Enchaînement : liaisons validées → mobilité au rang maximal le long du mouvement (Q8, calcul pur)
→ garde-fou (refus ou avertissements) → désignation des ddl redondants (cinématique et option
« Hyperstatique autorisé ») → moteur dynamique ou cinématique.
"""

from meca3d.graphe.configurations import MobiliteRobuste, mobilite_robuste
from meca3d.graphe.graphe import depuis_etude
from meca3d.graphe.mobilite import (
    ErreurMobilite,
    Mode,
    designer_ddl_redondants,
    verifier_avant_simulation,
)
from meca3d.modele.etude import Etude, liaisons_non_validees
from meca3d.moteur.base import ErreurGardeFou, ErreurModele, ResultatsBruts
from meca3d.moteur.cinematique import MoteurCinematique
from meca3d.moteur.exudyn_dyn import MoteurExudynDyn

NOMS_DDL = ("Tx", "Ty", "Tz", "Rx", "Ry", "Rz")


def analyser_etude(etude: Etude) -> MobiliteRobuste:
    """Mobilité et hyperstatisme de l'étude (Q8) ; exige des liaisons toutes validées."""
    non_validees = liaisons_non_validees(etude)
    if non_validees:
        raise ErreurModele(
            f"La liaison {non_validees[0]} n'est pas validée : "
            "valider chaque liaison avant de simuler."
        )
    try:
        description = depuis_etude(etude)
    except ValueError as e:
        raise ErreurModele(str(e)) from e
    return mobilite_robuste(description)


def simuler_etude(
    etude: Etude, mode: Mode = Mode.DYNAMIQUE, hyperstatique_autorise: bool | None = None
) -> ResultatsBruts:
    """Simule l'étude après le garde-fou. `hyperstatique_autorise` : None = réglage de l'étude.

    Lève ErreurGardeFou (refus EX-22 / EX-23, aucun appel au moteur) ou ErreurModele.
    """
    autorise = (
        etude.hyperstatique_autorise if hyperstatique_autorise is None else (hyperstatique_autorise)
    )
    mobilite = analyser_etude(etude)
    decision = verifier_avant_simulation(mobilite.resultat, mode, len(etude.pilotes), autorise)
    if not decision.autorise:
        raise ErreurGardeFou(decision.message)
    avertissements = list(mobilite.avertissements)
    if decision.message:
        avertissements.append(decision.message)
    if mode is Mode.CINEMATIQUE:
        liberes: list[tuple[str, int]] = []
        if mobilite.h > 0:
            try:
                designes = designer_ddl_redondants(mobilite.description, mobilite.resultat)
            except ErreurMobilite as e:
                raise ErreurGardeFou(str(e)) from e
            liberes = [(d.liaison, d.ddl) for d in designes]
            avertissements.append(
                "ddl libérés (équations redondantes retirées) : "
                + ", ".join(f"{nom} {NOMS_DDL[ddl]}" for nom, ddl in liberes)
                + "."
            )
        resultats = MoteurCinematique().simuler(etude, ddl_liberes=liberes)
    else:
        resultats = MoteurExudynDyn().simuler(etude)
    resultats.avertissements = avertissements
    return resultats
