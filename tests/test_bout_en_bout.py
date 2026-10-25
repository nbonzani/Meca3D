# SPDX-License-Identifier: GPL-3.0-or-later
"""Scénario de bout en bout de la SPEC § 7, étapes 2 à 6, SANS faux serveur.

L'étape 1 (connexion et import par le canal de contrôle) sera ajoutée après le lot 5. Ici,
l'import est remplacé par les réponses enregistrées de SolidCraft (`etude_depuis_reponses`).

Choix de configuration (Q8) : les étapes de mobilité (2 et 3) utilisent les réponses à θ = 60°,
configuration générique, et sont recoupées à θ = 0 grâce au rang évalué le long du mouvement. La
simulation (étapes 4 à 6) part de θ = 0, car la référence Newton-Euler d'EX-40 démarre à θ = 0.
"""

import numpy as np
import pytest
import reference_bielle as ref
from outils_bielle import LOI_MONTEE, etude_proposee

from meca3d.graphe.graphe import construire_graphe, depuis_etude
from meca3d.graphe.mobilite import Mode
from meca3d.modele.actions import LoiEntree, Pesanteur, Pilote
from meca3d.modele.etude import Etude, Reglages, ecrire_etude, lire_etude
from meca3d.modele.liaison import TypeLiaison
from meca3d.moteur.base import ErreurGardeFou
from meca3d.moteur.simulation import analyser_etude, simuler_etude
from meca3d.resultats.export import colonnes_resultats, ecrire_csv
from meca3d.resultats.torseurs import torseur_statique

TOLERANCE_EX40 = 5e-3


def _ecart(calcule: np.ndarray, reference: np.ndarray) -> float:
    return float(np.abs(calcule - reference).max() / np.abs(reference).max())


def _valider_tout(etude: Etude) -> None:
    for liaison in etude.liaisons:
        liaison.valider()


def _donnees_d_entree(etude: Etude) -> None:
    """Étape 4 : loi sur L01 (montée puis 20 rad/s), g = (0, −9,81, 0), 1 s, 4 000 pas."""
    etude.pilotes = [Pilote("L01_pivot", LoiEntree(LOI_MONTEE))]
    etude.pesanteur = Pesanteur(vecteur=(0.0, -9.81, 0.0))
    etude.reglages = Reglages(duree=1.0, nb_pas=4000, periode_ecriture=0.002)


@pytest.mark.parametrize("theta", ["60", "00"])
def test_bout_en_bout_etape_2_graphe_et_refus(theta: str) -> None:
    etude = etude_proposee(theta)
    # import : 4 solides, 4 liaisons proposées pivot, pivot, rotule, glissière
    assert [s.nom for s in etude.solides] == ["Bati", "Manivelle", "Bielle", "Piston"]
    assert [x.type for x in etude.liaisons] == [
        TypeLiaison.PIVOT,
        TypeLiaison.PIVOT,
        TypeLiaison.ROTULE,
        TypeLiaison.GLISSIERE,
    ]
    _valider_tout(etude)
    graphe = construire_graphe(depuis_etude(etude))
    assert graphe.mu == 1
    assert len(graphe.cycles) == 1 and len(graphe.cycles[0].liaisons) == 4
    mobilite = analyser_etude(etude)
    assert (mobilite.m, mobilite.h) == (1, 1)
    # la simulation est refusée (EX-22), dans les deux modes
    etude.pilotes = [Pilote("L01_pivot", LoiEntree("20*t"))]
    for mode in (Mode.DYNAMIQUE, Mode.CINEMATIQUE):
        with pytest.raises(ErreurGardeFou, match="h = 1"):
            simuler_etude(etude, mode)


@pytest.mark.parametrize("theta", ["60", "00"])
def test_bout_en_bout_etape_3_lineaire_annulaire_selon_z(theta: str) -> None:
    etude = etude_proposee(theta)
    liaison = etude.liaison("L23_rotule")
    liaison.choisir(TypeLiaison.LINEAIRE_ANNULAIRE)
    liaison.reorienter_axe("z")
    _valider_tout(etude)
    mobilite = analyser_etude(etude)
    assert (mobilite.m, mobilite.h) == (1, 0)
    assert mobilite.resultat.mu == 1


@pytest.fixture(scope="module")
def etude_simulee() -> Etude:
    etude = etude_proposee("00")
    etude.maquette = "bielle_manivelle.solidcraft"
    liaison = etude.liaison("L23_rotule")
    liaison.choisir(TypeLiaison.LINEAIRE_ANNULAIRE)
    liaison.reorienter_axe("z")
    _valider_tout(etude)
    _donnees_d_entree(etude)
    return etude


def test_bout_en_bout_etape_5_simulation_dynamique(etude_simulee: Etude) -> None:
    res = simuler_etude(etude_simulee, Mode.DYNAMIQUE)
    assert res.avertissements == []
    assert len(res.t) == 501
    for grandeur, liaison, de in (
        ("O", "L01_pivot", "Bati"),
        ("A", "L12_pivot", "Manivelle"),
        ("B", "L23_rotule", "Bielle"),
    ):
        tors = torseur_statique(etude_simulee, res, liaison, de=de, base="monde")
        refs = np.array([ref.reference(float(t))[grandeur] for t in res.t])
        assert _ecart(tors[:, :2], refs) <= TOLERANCE_EX40, grandeur
    tors = torseur_statique(etude_simulee, res, "L01_pivot", de="Bati", base="monde")
    refs_c = np.array([ref.reference(float(t))["C"] for t in res.t])
    assert _ecart(tors[:, 5], refs_c) <= TOLERANCE_EX40
    tors = torseur_statique(etude_simulee, res, "L30_glissiere", de="Bati", base="monde")
    refs_n = np.array([ref.reference(float(t))["N"] for t in res.t])
    assert _ecart(tors[:, 1], refs_n) <= TOLERANCE_EX40


def test_bout_en_bout_etape_6_csv_enregistrement_reouverture(
    etude_simulee: Etude, tmp_path_factory: pytest.TempPathFactory
) -> None:
    dossier = tmp_path_factory.mktemp("bout_en_bout")
    res = simuler_etude(etude_simulee, Mode.DYNAMIQUE)
    csv_1 = dossier / "premier.csv"
    ecrire_csv(csv_1, colonnes_resultats(etude_simulee, res))
    entete = csv_1.read_text(encoding="utf-8-sig").splitlines()[0].split(";")
    assert entete[0] == "t (s)"
    assert "C (N·m)" in entete
    assert len(csv_1.read_text(encoding="utf-8-sig").splitlines()) - 1 == 501

    fichier = dossier / "etude.meca3d"
    ecrire_etude(etude_simulee, fichier)
    rouverte = lire_etude(fichier)
    assert rouverte.vers_dict() == etude_simulee.vers_dict()
    csv_2 = dossier / "second.csv"
    ecrire_csv(csv_2, colonnes_resultats(rouverte, simuler_etude(rouverte, Mode.DYNAMIQUE)))
    assert csv_2.read_bytes() == csv_1.read_bytes()  # résultats identiques bit à bit
