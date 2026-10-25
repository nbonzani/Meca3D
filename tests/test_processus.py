# SPDX-License-Identifier: GPL-3.0-or-later
"""Calcul dans un processus séparé : identité des résultats, progression, annulation, erreurs
(EX-42, EX-43, D9)."""

import importlib
import time
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
from outils_bielle import LOI_MONTEE, etude_bielle, etude_proposee

from meca3d.modele.actions import LoiEntree, Pesanteur, Pilote
from meca3d.modele.etude import Etude, Reglages, lire_etude
from meca3d.moteur.base import ErreurModele, ErreurSolveur, ResultatsBruts
from meca3d.moteur.exudyn_dyn import MoteurExudynDyn
from meca3d.moteur.processus import (
    CalculEnCours,
    EtatCalcul,
    Progression,
    simuler_en_processus,
)

ETUDE = Path(__file__).parent / "fixtures" / "bielle" / "bielle.meca3d"
TOLERANCE_IDENTITE = 1e-12
DELAI_ANNULATION_MAX = 1.0  # s, EX-42


def _etude_longue() -> Etude:
    """Même bielle, mais 60 s simulées : le calcul dure bien plus longtemps que le test."""
    etude = etude_bielle()
    etude.reglages = Reglages(duree=60.0, nb_pas=240000, periode_ecriture=0.01)
    return etude


def _etude_hyperstatique() -> Etude:
    """Bielle avec la rotule d'origine en B : h = 1. Le garde-fou (EX-22) est contourné ici."""
    etude = etude_proposee("00")
    for liaison in etude.liaisons:
        liaison.valider()
    etude.pilotes = [Pilote(liaison="L01_pivot", loi=LoiEntree(LOI_MONTEE))]
    etude.pesanteur = Pesanteur(vecteur=(0.0, -9.81, 0.0))
    etude.reglages = Reglages(duree=1.0, nb_pas=4000, periode_ecriture=0.002)
    return etude


def _attendre_progression(calcul: CalculEnCours, delai: float = 60.0) -> None:
    fin = time.perf_counter() + delai
    while calcul.progression is None:
        calcul.interroger()
        assert calcul.etat is EtatCalcul.EN_COURS, f"calcul arrêté : {calcul.erreur}"
        assert time.perf_counter() < fin, "aucune progression reçue"
        time.sleep(0.01)


def _ecart_max(a: ResultatsBruts, b: ResultatsBruts) -> float:
    assert a.t.shape == b.t.shape
    ecarts = [float(np.max(np.abs(a.t - b.t)))]
    for nom in ("positions", "rotations", "forces", "moments"):
        da, db = getattr(a, nom), getattr(b, nom)
        assert da.keys() == db.keys()
        ecarts += [float(np.max(np.abs(da[k] - db[k]))) for k in da]
    return max(ecarts)


def test_ex42_resultats_identiques_au_calcul_direct() -> None:
    etude = lire_etude(ETUDE)
    direct = MoteurExudynDyn().simuler(etude)
    mesures: list[Progression] = []
    en_processus = simuler_en_processus(etude, rappel_progression=mesures.append)
    assert _ecart_max(direct, en_processus) <= TOLERANCE_IDENTITE
    assert en_processus.t.shape == (501,)


def test_ex42_progression_recue_et_croissante() -> None:
    etude = lire_etude(ETUDE)
    mesures: list[Progression] = []
    simuler_en_processus(etude, rappel_progression=mesures.append)
    assert len(mesures) >= 2
    fractions = [m.fraction for m in mesures]
    assert fractions == sorted(fractions)
    assert all(0.0 <= f <= 1.0 for f in fractions)
    assert max(fractions) > 0.5
    instants = [m.t for m in mesures]
    assert instants == sorted(instants)
    assert max(instants) <= etude.reglages.duree + 1e-9


def test_ex42_annulation_retour_a_letat_pret_en_moins_dune_seconde() -> None:
    calcul = CalculEnCours(_etude_longue())
    calcul.demarrer()
    _attendre_progression(calcul)
    debut = time.perf_counter()
    calcul.annuler()
    duree = time.perf_counter() - debut
    assert duree < DELAI_ANNULATION_MAX
    assert calcul.etat is EtatCalcul.ANNULE
    assert calcul.resultats is None
    assert calcul.erreur is None
    assert not calcul.processus_vivant


def test_ex42_annulation_immediate_pendant_le_demarrage() -> None:
    calcul = CalculEnCours(_etude_longue())
    calcul.demarrer()
    debut = time.perf_counter()
    calcul.annuler()
    assert time.perf_counter() - debut < DELAI_ANNULATION_MAX
    assert calcul.etat is EtatCalcul.ANNULE
    assert calcul.resultats is None
    assert not calcul.processus_vivant


def test_ex42_nouveau_calcul_possible_apres_annulation() -> None:
    premier = CalculEnCours(_etude_longue())
    premier.demarrer()
    _attendre_progression(premier)
    premier.annuler()
    second = CalculEnCours(lire_etude(ETUDE))
    second.demarrer()
    assert second.attendre(timeout=120.0) is EtatCalcul.TERMINE
    assert second.resultats is not None
    assert second.resultats.t.shape == (501,)


def test_ex43_modele_hyperstatique_erreur_typee_avec_message_et_instant() -> None:
    etude = _etude_hyperstatique()
    calcul = CalculEnCours(etude)
    calcul.demarrer()
    assert calcul.attendre(timeout=120.0) is EtatCalcul.ECHEC
    assert calcul.resultats is None
    erreur = calcul.erreur
    assert isinstance(erreur, ErreurSolveur)
    message = str(erreur)
    assert "hyperstatique" in message
    assert "point mort" in message
    assert erreur.t_echec is not None
    assert 0.0 <= erreur.t_echec <= etude.reglages.duree
    assert f"{erreur.t_echec:.4g}" in message


def test_ex43_simuler_en_processus_relance_lerreur_typee() -> None:
    with pytest.raises(ErreurSolveur) as exc:
        simuler_en_processus(_etude_hyperstatique())
    assert exc.value.t_echec is not None


def test_ex43_modele_invalide_erreur_modele_pedagogique() -> None:
    etude = etude_proposee("00")  # aucune liaison validée
    calcul = CalculEnCours(etude)
    calcul.demarrer()
    assert calcul.attendre(timeout=120.0) is EtatCalcul.ECHEC
    assert isinstance(calcul.erreur, ErreurModele)
    assert "validée" in str(calcul.erreur)


def test_ex42_etude_transmise_sous_forme_de_dict() -> None:
    """La frontière est sérialisée : le calcul ne voit pas l'objet Etude du processus parent."""
    etude = lire_etude(ETUDE)
    calcul = CalculEnCours(etude)
    assert calcul.donnees_etude == etude.vers_dict()
    assert isinstance(calcul.donnees_etude, dict)


def test_ex42_reglages_surcharges() -> None:
    etude = lire_etude(ETUDE)
    court = replace(etude.reglages, duree=0.2, nb_pas=800)
    resultats = simuler_en_processus(etude, reglages=court)
    assert resultats.t[-1] == pytest.approx(0.2, abs=1e-9)


def test_ex42_point_dentree_sans_effet_a_limport() -> None:
    """`python -m meca3d` : importer le module ne lance rien (nécessaire au démarrage spawn)."""
    module = importlib.import_module("meca3d.__main__")
    assert callable(module.principal)
