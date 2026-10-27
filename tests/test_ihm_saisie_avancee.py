# SPDX-License-Identifier: GPL-3.0-or-later
"""Saisies avancées dans l'IHM (lot 14) : réglages de simulation (EX-40), frottement de Coulomb
(EX-15), pas de l'hélicoïdale (EX-10), couplages saisis (EX-14) et rendement (EX-16).

Critère de sortie : plus aucun réglage n'exige d'éditer le `.meca3d`. Les valeurs attendues dans
le fichier enregistré sont celles de l'annexe B du guide utilisateur ; m et h viennent du calcul
analytique d'EX-21 (Ec = 6μ + nombre de couplages).
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import json  # noqa: E402
from collections.abc import Iterator  # noqa: E402
from pathlib import Path  # noqa: E402
from typing import Any  # noqa: E402

import pytest  # noqa: E402
from outils_bielle import etude_proposee  # noqa: E402
from outils_couplages import etude_reducteur, etude_vis_ecrou  # noqa: E402
from pytestqt.qtbot import QtBot  # noqa: E402

from meca3d.ihm import textes  # noqa: E402
from meca3d.ihm.fenetre import FenetrePrincipale  # noqa: E402
from meca3d.modele.couplage import (  # noqa: E402
    Engrenage,
    PignonCremaillere,
    SensEngrenage,
    VisEcrou,
)
from meca3d.modele.etude import Etude, Reglages, lire_etude  # noqa: E402
from meca3d.modele.liaison import TypeLiaison  # noqa: E402

RANG_ETAPE_SIMULATION = 2  # Modèle, Données, Simulation, Résultats

# Annexe B du guide utilisateur
REGLAGES_ANNEXE_B = {"duree": 3.0, "nb_pas": 3000, "periode_ecriture": 0.005}


@pytest.fixture
def fenetre(qtbot: QtBot) -> Iterator[FenetrePrincipale]:
    f = FenetrePrincipale()
    qtbot.addWidget(f)
    f.confirmer = lambda titre, texte: True
    yield f
    f.annuler()


def _charger(fenetre: FenetrePrincipale, etude: Etude) -> Etude:
    fenetre.charger_etude(etude)
    return etude


def _saisir_reglages(fenetre: FenetrePrincipale, duree: float, nb_pas: int, ms: float) -> None:
    e = fenetre.proprietes.editeur_reglages
    e.saisie_duree.setValue(duree)
    e.saisie_nb_pas.setValue(nb_pas)
    e.saisie_periode.setValue(ms)
    e.bouton.click()


def _choisir(combo: Any, donnee: Any) -> None:
    index = combo.findData(donnee)
    assert index >= 0, donnee
    combo.setCurrentIndex(index)


def _saisir_frottement(
    fenetre: FenetrePrincipale, f: float, rayon_mm: float = 0.0, epsilon: float = 0.0
) -> None:
    p = fenetre.proprietes
    p.saisie_frottement.setValue(f)
    p.saisie_rayon_axe.setValue(rayon_mm)
    p.saisie_epsilon.setValue(epsilon)
    p.bouton_frottement.click()


def _nouveau_couplage(fenetre: FenetrePrincipale) -> Any:
    fenetre.arbre.selectionner_rubrique(textes.RUBRIQUE_COUPLAGES)
    editeur = fenetre.proprietes.editeur_couplage
    assert not editeur.isHidden()
    return editeur


def _saisir_engrenage(
    editeur: Any, l1: str, l2: str, z1: int, z2: int, rendement: float = 1.0
) -> None:
    _choisir(editeur.choix_genre, Engrenage.GENRE)
    editeur.choix_liaison_1.setCurrentText(l1)
    editeur.choix_liaison_2.setCurrentText(l2)
    editeur.saisie_z1.setValue(z1)
    editeur.saisie_z2.setValue(z2)
    _choisir(editeur.choix_sens, SensEngrenage.EXTERIEUR)
    editeur.saisie_rendement.setValue(rendement)
    editeur.bouton_ajouter.click()


# --- EX-40 : réglages de simulation -----------------------------------------------------------
def test_ex40_reglages_saisis_depuis_l_etape_simulation(fenetre: FenetrePrincipale) -> None:
    etude = _charger(fenetre, etude_proposee("60"))
    fenetre.etapes.bouton(RANG_ETAPE_SIMULATION).click()
    assert not fenetre.proprietes.editeur_reglages.isHidden()
    fenetre.modifiee = False
    _saisir_reglages(fenetre, 3.0, 3000, 5.0)
    assert etude.reglages == Reglages(duree=3.0, nb_pas=3000, periode_ecriture=0.005)
    assert fenetre.modifiee


def test_ex40_reglages_accessibles_par_le_menu_simulation(fenetre: FenetrePrincipale) -> None:
    _charger(fenetre, etude_proposee("60"))
    fenetre.action_reglages.trigger()
    assert not fenetre.proprietes.editeur_reglages.isHidden()


def test_ex40_reglages_affiches_avec_leurs_valeurs(fenetre: FenetrePrincipale) -> None:
    etude = etude_proposee("60")
    etude.reglages = Reglages(duree=2.5, nb_pas=5000, periode_ecriture=0.002)
    _charger(fenetre, etude)
    fenetre.action_reglages.trigger()
    e = fenetre.proprietes.editeur_reglages
    assert e.saisie_duree.value() == pytest.approx(2.5, abs=1e-12)
    assert e.saisie_nb_pas.value() == 5000
    assert e.saisie_periode.value() == pytest.approx(2.0, abs=1e-12)  # ms
    assert "0,5 ms" in e.etiquette_pas.text()  # pas de temps h = 2,5 s / 5 000


def test_ex40_reglages_modifies_invalident_les_resultats(fenetre: FenetrePrincipale) -> None:
    _charger(fenetre, etude_proposee("60"))
    fenetre.action_reglages.trigger()
    signaux: list[bool] = []
    fenetre.proprietes.modifiee.connect(lambda: signaux.append(True))
    _saisir_reglages(fenetre, 2.0, 2000, 1.0)
    assert signaux == [True]


# --- EX-15 : frottement de Coulomb --------------------------------------------------------------
def test_ex15_frottement_glissiere_sans_rayon(fenetre: FenetrePrincipale) -> None:
    etude = _charger(fenetre, etude_proposee("60"))
    fenetre.arbre.selectionner_liaison("L30_glissiere")
    p = fenetre.proprietes
    assert not p.groupe_frottement.isHidden()
    assert p.saisie_rayon_axe.isHidden()  # le rayon d'axe ne concerne que le pivot
    _saisir_frottement(fenetre, 0.2)
    liaison = etude.liaison("L30_glissiere")
    assert liaison.frottement == pytest.approx(0.2, abs=1e-12)
    assert liaison.rayon_axe is None
    assert liaison.epsilon is None  # 0 affiché « défaut » : valeur de la SPEC
    assert p.message.text() == ""


def test_ex15_frottement_pivot_avec_rayon_d_axe(fenetre: FenetrePrincipale) -> None:
    etude = _charger(fenetre, etude_proposee("60"))
    fenetre.arbre.selectionner_liaison("L01_pivot")
    p = fenetre.proprietes
    assert not p.saisie_rayon_axe.isHidden()
    _saisir_frottement(fenetre, 0.1, rayon_mm=5.0)
    liaison = etude.liaison("L01_pivot")
    assert liaison.frottement == pytest.approx(0.1, abs=1e-12)
    assert liaison.rayon_axe == pytest.approx(0.005, abs=1e-15)


def test_ex15_pivot_frottant_sans_rayon_refuse(fenetre: FenetrePrincipale) -> None:
    etude = _charger(fenetre, etude_proposee("60"))
    fenetre.arbre.selectionner_liaison("L01_pivot")
    _saisir_frottement(fenetre, 0.1, rayon_mm=0.0)
    assert fenetre.proprietes.message.text() != ""
    assert etude.liaison("L01_pivot").frottement == 0.0


def test_ex15_vitesse_de_regularisation_reglable(fenetre: FenetrePrincipale) -> None:
    etude = _charger(fenetre, etude_proposee("60"))
    fenetre.arbre.selectionner_liaison("L30_glissiere")
    _saisir_frottement(fenetre, 0.2, epsilon=0.001)
    assert etude.liaison("L30_glissiere").epsilon == pytest.approx(1e-3, abs=1e-15)


def test_ex15_frottement_relu_a_l_affichage(fenetre: FenetrePrincipale) -> None:
    etude = etude_proposee("60")
    pivot = etude.liaison("L01_pivot")
    pivot.frottement, pivot.rayon_axe = 0.15, 0.008
    _charger(fenetre, etude)
    fenetre.arbre.selectionner_liaison("L01_pivot")
    p = fenetre.proprietes
    assert p.saisie_frottement.value() == pytest.approx(0.15, abs=1e-12)
    assert p.saisie_rayon_axe.value() == pytest.approx(8.0, abs=1e-9)  # mm


def test_ex15_frottement_absent_pour_une_liaison_non_frottante(fenetre: FenetrePrincipale) -> None:
    _charger(fenetre, etude_proposee("60"))
    fenetre.arbre.selectionner_liaison("L23_rotule")
    assert fenetre.proprietes.groupe_frottement.isHidden()


# --- EX-10 : pas de l'hélicoïdale ---------------------------------------------------------------
def test_ex10_pas_de_l_helicoidale_saisi(fenetre: FenetrePrincipale) -> None:
    etude = _charger(fenetre, etude_proposee("60"))
    fenetre.arbre.selectionner_liaison("L30_glissiere")
    p = fenetre.proprietes
    assert p.groupe_pas.isHidden()
    _choisir(p.choix_type, TypeLiaison.HELICOIDALE)
    assert not p.groupe_pas.isHidden()
    p.saisie_pas.setValue(5.0)  # mm par tour
    p.bouton_pas.click()
    assert etude.liaison("L30_glissiere").pas == pytest.approx(0.005, abs=1e-15)


# --- EX-14, EX-16 : couplages saisis ------------------------------------------------------------
def test_ex14_rubrique_couplages_dans_le_modele(fenetre: FenetrePrincipale) -> None:
    _charger(fenetre, etude_reducteur())
    assert textes.RUBRIQUE_COUPLAGES in fenetre.arbre.rubriques(textes.BRANCHE_MODELE)


def test_ex14_engrenage_saisi_reduit_la_mobilite(fenetre: FenetrePrincipale) -> None:
    etude = _charger(fenetre, etude_reducteur())
    assert fenetre.mobilite is not None
    assert (fenetre.mobilite.m, fenetre.mobilite.h) == (2, 0)  # deux pivots indépendants
    editeur = _nouveau_couplage(fenetre)
    _saisir_engrenage(editeur, "L1", "L2", 20, 60, rendement=0.95)
    assert editeur.message.text() == ""
    assert len(etude.couplages) == 1
    c = etude.couplages[0]
    assert isinstance(c, Engrenage)
    assert (c.liaison_1, c.liaison_2, c.sens) == ("L1", "L2", SensEngrenage.EXTERIEUR)
    assert c.k == pytest.approx(1.0 / 3.0, rel=1e-15)
    assert c.rendement == pytest.approx(0.95, abs=1e-12)
    # EX-21 : Ic = 2, Ec = 6·0 + 1 couplage, rc = 1 -> m = 1, h = 0
    assert (fenetre.mobilite.m, fenetre.mobilite.h) == (1, 0)
    assert len(fenetre.arbre.elements(textes.RUBRIQUE_COUPLAGES)) == 1


def test_ex14_vis_ecrou_saisi(fenetre: FenetrePrincipale) -> None:
    etude = _charger(fenetre, etude_vis_ecrou())
    editeur = _nouveau_couplage(fenetre)
    _choisir(editeur.choix_genre, VisEcrou.GENRE)
    editeur.choix_liaison_1.setCurrentText("L_vis")
    editeur.choix_liaison_2.setCurrentText("L_ecrou")
    editeur.saisie_pas.setValue(5.0)  # mm par tour (SPEC EX-14)
    editeur.bouton_ajouter.click()
    assert len(etude.couplages) == 1
    c = etude.couplages[0]
    assert isinstance(c, VisEcrou)
    assert c.p == pytest.approx(0.005, abs=1e-15)
    assert c.rendement == 1.0


def test_ex14_pignon_cremaillere_saisi(fenetre: FenetrePrincipale) -> None:
    etude = _charger(fenetre, etude_vis_ecrou())
    editeur = _nouveau_couplage(fenetre)
    _choisir(editeur.choix_genre, PignonCremaillere.GENRE)
    editeur.choix_liaison_1.setCurrentText("L_vis")
    editeur.choix_liaison_2.setCurrentText("L_ecrou")
    editeur.saisie_rayon.setValue(20.0)  # mm
    editeur.bouton_ajouter.click()
    c = etude.couplages[0]
    assert isinstance(c, PignonCremaillere)
    assert c.r == pytest.approx(0.02, abs=1e-15)


def test_ex14_couplage_d_une_liaison_avec_elle_meme_refuse(fenetre: FenetrePrincipale) -> None:
    etude = _charger(fenetre, etude_reducteur())
    editeur = _nouveau_couplage(fenetre)
    _saisir_engrenage(editeur, "L1", "L1", 20, 60)
    assert editeur.message.text() != ""
    assert etude.couplages == []


def test_ex16_rendement_modifie_sur_un_couplage_existant(fenetre: FenetrePrincipale) -> None:
    etude = etude_reducteur()
    etude.couplages = [Engrenage.depuis_dents("K1", "L1", "L2", 20, 60)]
    _charger(fenetre, etude)
    fenetre.arbre.selectionner_couplage("K1")
    editeur = fenetre.proprietes.editeur_couplage
    assert editeur.saisie_z1.value() == 20
    assert editeur.saisie_z2.value() == 60
    assert editeur.saisie_rendement.value() == pytest.approx(1.0, abs=1e-12)
    editeur.saisie_rendement.setValue(0.95)
    editeur.bouton_ajouter.click()
    assert len(etude.couplages) == 1
    assert etude.couplages[0].rendement == pytest.approx(0.95, abs=1e-12)
    assert etude.couplages[0].k == pytest.approx(1.0 / 3.0, rel=1e-15)


def test_ex14_couplage_supprime(fenetre: FenetrePrincipale) -> None:
    etude = etude_reducteur()
    etude.couplages = [Engrenage.depuis_dents("K1", "L1", "L2", 20, 60)]
    _charger(fenetre, etude)
    fenetre.arbre.selectionner_couplage("K1")
    fenetre.proprietes.editeur_couplage.bouton_supprimer.click()
    assert etude.couplages == []
    assert fenetre.mobilite is not None and fenetre.mobilite.m == 2


# --- Annexe B du guide : l'étude enregistrée depuis l'IHM ---------------------------------------
def _lire(chemin: Path) -> dict[str, Any]:
    return json.loads(chemin.read_text(encoding="utf-8"))


def _liaison(d: dict[str, Any], nom: str) -> dict[str, Any]:
    return next(x for x in d["liaisons"] if x["nom"] == nom)


def test_ex60_annexe_b_reglages_et_frottements_enregistres(
    fenetre: FenetrePrincipale, tmp_path: Path
) -> None:
    _charger(fenetre, etude_proposee("60"))
    fenetre.action_reglages.trigger()
    _saisir_reglages(fenetre, 3.0, 3000, 5.0)
    fenetre.arbre.selectionner_liaison("L30_glissiere")
    _saisir_frottement(fenetre, 0.2)
    fenetre.arbre.selectionner_liaison("L01_pivot")
    _saisir_frottement(fenetre, 0.1, rayon_mm=5.0)
    chemin = tmp_path / "bielle.meca3d"
    assert fenetre.enregistrer_sous(chemin)
    d = _lire(chemin)
    assert d["reglages"] == REGLAGES_ANNEXE_B
    glissiere, pivot = _liaison(d, "L30_glissiere"), _liaison(d, "L01_pivot")
    assert glissiere["frottement"] == 0.2
    assert "rayon_axe" not in glissiere
    assert (pivot["frottement"], pivot["rayon_axe"]) == (0.1, 0.005)
    relue = lire_etude(chemin)
    assert relue.reglages == Reglages(**REGLAGES_ANNEXE_B)


def test_ex60_annexe_b_couplage_et_rendement_enregistres(
    fenetre: FenetrePrincipale, tmp_path: Path
) -> None:
    _charger(fenetre, etude_reducteur())
    _saisir_engrenage(_nouveau_couplage(fenetre), "L1", "L2", 20, 60, rendement=0.95)
    chemin = tmp_path / "reducteur.meca3d"
    assert fenetre.enregistrer_sous(chemin)
    (c,) = _lire(chemin)["couplages"]
    assert c["genre"] == "engrenage"
    assert (c["liaison_1"], c["liaison_2"], c["sens"]) == ("L1", "L2", "exterieur")
    assert c["k"] == 0.3333333333333333
    assert c["rendement"] == 0.95
    assert lire_etude(chemin).couplages == [Engrenage("K1", "L1", "L2", 20 / 60, rendement=0.95)]
