# SPDX-License-Identifier: GPL-3.0-or-later
"""Scénario de bout en bout de la SPEC § 7, au complet : l'étape 1 passe par le canal de contrôle.

Le faux serveur rejoue les réponses enregistrées de SolidCraft pour la bielle-manivelle (θ = 0).
Les étapes 2 à 6 reprennent celles de test_bout_en_bout.py sur l'étude importée par le réseau.
"""

from pathlib import Path

import numpy as np
import reference_bielle as ref
from faux_serveur import JETON_DE_TEST, FauxServeur
from outils_bielle import LOI_MONTEE

from meca3d.cao.canal import CanalSolidCraft
from meca3d.cao.solidcraft import importer
from meca3d.graphe.mobilite import Mode
from meca3d.modele.actions import LoiEntree, Pesanteur, Pilote
from meca3d.modele.etude import Reglages, ecrire_etude, lire_etude
from meca3d.modele.liaison import TypeLiaison
from meca3d.moteur.base import ErreurGardeFou
from meca3d.moteur.simulation import analyser_etude, simuler_etude
from meca3d.resultats.export import colonnes_resultats, ecrire_csv
from meca3d.resultats.torseurs import torseur_statique

TOLERANCE_EX40 = 5e-3


def _ecart(calcule: np.ndarray, reference: np.ndarray) -> float:
    return float(np.abs(calcule - reference).max() / np.abs(reference).max())


def test_scenario_complet_par_le_canal(tmp_path: Path) -> None:
    # 1. connexion au faux serveur et import
    with FauxServeur() as faux:
        canal = CanalSolidCraft(port=faux.port, jeton=JETON_DE_TEST, intervalle_pending=0.01)
        canal.connecter()
        try:
            etude = importer(canal, tmp_path)
        finally:
            canal.fermer()
    assert [s.nom for s in etude.solides] == ["Bati", "Manivelle", "Bielle", "Piston"]
    assert [x.type for x in etude.liaisons] == [
        TypeLiaison.PIVOT,
        TypeLiaison.PIVOT,
        TypeLiaison.ROTULE,
        TypeLiaison.GLISSIERE,
    ]

    # 2. graphe et refus (h = 1)
    for liaison in etude.liaisons:
        liaison.valider()
    mobilite = analyser_etude(etude)
    assert (mobilite.resultat.mu, mobilite.m, mobilite.h) == (1, 1, 1)
    etude.pilotes = [Pilote("L01_pivot", LoiEntree(LOI_MONTEE))]
    try:
        simuler_etude(etude, Mode.DYNAMIQUE)
        raise AssertionError("la simulation aurait dû être refusée (h = 1)")
    except ErreurGardeFou as erreur:
        assert "h = 1" in str(erreur)

    # 3. linéaire annulaire d'axe z en B → isostatique
    l23 = etude.liaison("L23_rotule")
    l23.choisir(TypeLiaison.LINEAIRE_ANNULAIRE)
    l23.reorienter_axe("z")
    l23.valider()
    mobilite = analyser_etude(etude)
    assert (mobilite.m, mobilite.h) == (1, 0)

    # 4. données d'entrée
    etude.pesanteur = Pesanteur(vecteur=(0.0, -9.81, 0.0))
    etude.reglages = Reglages(duree=1.0, nb_pas=4000, periode_ecriture=0.002)

    # 5. simulation dynamique comparée à la référence Newton-Euler
    res = simuler_etude(etude, Mode.DYNAMIQUE)
    tors = torseur_statique(etude, res, "L01_pivot", de="Bati", base="monde")
    refs_c = np.array([ref.reference(float(t))["C"] for t in res.t])
    assert _ecart(tors[:, 5], refs_c) <= TOLERANCE_EX40
    refs_o = np.array([ref.reference(float(t))["O"] for t in res.t])
    assert _ecart(tors[:, :2], refs_o) <= TOLERANCE_EX40

    # 6. CSV, enregistrement, réouverture, nouvelle simulation identique bit à bit
    csv_1 = tmp_path / "premier.csv"
    ecrire_csv(csv_1, colonnes_resultats(etude, res))
    fichier = tmp_path / "etude.meca3d"
    ecrire_etude(etude, fichier)
    rouverte = lire_etude(fichier)
    csv_2 = tmp_path / "second.csv"
    ecrire_csv(csv_2, colonnes_resultats(rouverte, simuler_etude(rouverte, Mode.DYNAMIQUE)))
    assert csv_2.read_bytes() == csv_1.read_bytes()
