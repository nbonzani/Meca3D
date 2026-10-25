# SPDX-License-Identifier: GPL-3.0-or-later
"""Saisie des entrées dans l'IHM : lois (EX-30), pesanteur (EX-31), actions (EX-32), ressorts
(EX-33), capteurs (EX-50, EX-51), points en coordonnées pièce (R9, D15), affichage (R8)."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from collections.abc import Iterator, Sequence  # noqa: E402
from typing import Any  # noqa: E402

import pytest  # noqa: E402
from outils_bielle import etude_bielle, etude_proposee  # noqa: E402
from pytestqt.qtbot import QtBot  # noqa: E402

from meca3d.ihm import textes  # noqa: E402
from meca3d.ihm.fenetre import FenetrePrincipale  # noqa: E402
from meca3d.modele.actions import NatureAction, RepereAction  # noqa: E402
from meca3d.modele.capteurs import (  # noqa: E402
    BaseCapteur,
    CapteurLiaison,
    CapteurPoint,
    SensTorseur,
)
from meca3d.modele.etude import Etude  # noqa: E402
from meca3d.modele.liaison import TypeLiaison  # noqa: E402

# Point A de la manivelle importée à 60° : (100 mm, 0, 0) en coordonnées pièce
# -> (50 ; 86,603 ; 0) mm en repère monde (r = 100 mm, θ = 60°)
A_MONDE_M = (0.05, 0.1 * 0.8660254037844386, 0.0)


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


def _regler(champs: Sequence[Any], valeurs: tuple[float, ...]) -> None:
    for champ, valeur in zip(champs, valeurs, strict=True):
        champ.setValue(valeur)


# --- EX-30 : lois d'entrée -----------------------------------------------------------------
def test_ex30_loi_valide_apercu_valeur_vitesse_acceleration(fenetre: FenetrePrincipale) -> None:
    etude = _charger(fenetre, etude_proposee("60"))
    fenetre.arbre.selectionner_liaison("L01_pivot")
    editeur = fenetre.proprietes.editeur_pilote
    editeur.champ_t.setValue(0.5)
    editeur.champ.setText("20*t")
    assert editeur.valide
    assert editeur.etiquette_erreur.text() == ""
    apercu = editeur.etiquette_apercu.text()
    assert "10 rad" in apercu
    assert "20 rad/s" in apercu
    assert "0 rad/s²" in apercu
    assert etude.pilotes == []  # rien n'est créé avant « Appliquer »


@pytest.mark.parametrize("texte", ["__import__('os')", "20*", "t +"])
def test_ex30_loi_invalide_refusee_avec_message(fenetre: FenetrePrincipale, texte: str) -> None:
    etude = _charger(fenetre, etude_proposee("60"))
    fenetre.arbre.selectionner_liaison("L01_pivot")
    p = fenetre.proprietes
    p.editeur_pilote.champ.setText(texte)
    assert not p.editeur_pilote.valide
    assert p.editeur_pilote.etiquette_erreur.text() != ""
    p.bouton_pilote.click()
    assert etude.pilotes == []


def test_ex30_expression_vide_refusee(fenetre: FenetrePrincipale) -> None:
    _charger(fenetre, etude_proposee("60"))
    fenetre.arbre.selectionner_liaison("L01_pivot")
    editeur = fenetre.proprietes.editeur_pilote
    editeur.champ.setText("20*t")
    editeur.champ.setText("")
    assert not editeur.valide
    assert editeur.etiquette_erreur.text() != ""


def test_ex30_appliquer_cree_remplace_et_retire_le_pilote(fenetre: FenetrePrincipale) -> None:
    etude = _charger(fenetre, etude_proposee("60"))
    fenetre.arbre.selectionner_liaison("L01_pivot")
    p = fenetre.proprietes
    p.editeur_pilote.champ.setText("20*t")
    p.bouton_pilote.click()
    assert [x.liaison for x in etude.pilotes] == ["L01_pivot"]
    assert etude.pilotes[0].loi.valeur(0.5) == pytest.approx(10.0, abs=1e-12)
    assert etude.pilotes[0].loi.vitesse(0.5) == pytest.approx(20.0, abs=1e-12)
    p.editeur_pilote.champ.setText("3*t")
    p.bouton_pilote.click()
    assert len(etude.pilotes) == 1
    assert etude.pilotes[0].loi.vitesse(0.5) == pytest.approx(3.0, abs=1e-12)
    assert len(fenetre.arbre.elements("Pilotes")) == 1
    p.bouton_retirer_pilote.click()
    assert etude.pilotes == []
    assert fenetre.arbre.elements("Pilotes") == []


def test_ex30_liaison_non_pilotable_sans_groupe_pilote(fenetre: FenetrePrincipale) -> None:
    _charger(fenetre, etude_bielle("60", 60.0))
    p = fenetre.proprietes
    fenetre.arbre.selectionner_liaison("L23_rotule")  # linéaire annulaire
    assert p.groupe_pilote.isHidden()
    fenetre.arbre.selectionner_liaison("L30_glissiere")
    assert not p.groupe_pilote.isHidden()


def test_ex30_pivot_glissant_demande_la_grandeur(fenetre: FenetrePrincipale) -> None:
    etude = _charger(fenetre, etude_proposee("60"))
    etude.liaison("L01_pivot").choisir(TypeLiaison.PIVOT_GLISSANT)
    fenetre.arbre.selectionner_liaison("L01_pivot")
    p = fenetre.proprietes
    assert not p.choix_grandeur.isHidden()
    p.choix_grandeur.setCurrentIndex(p.choix_grandeur.findData("position"))
    p.editeur_pilote.champ.setText("0.1*t")
    p.bouton_pilote.click()
    assert etude.pilotes[0].grandeur == "position"


# --- R8 : affichage lisible et liste d'axe fidèle ------------------------------------------
def test_r8_loi_lisible_remplace_la_syntaxe_python() -> None:
    assert textes.loi_lisible("20*t") == "20·t"
    assert textes.loi_lisible("2*pi*t**2") == "2·π·t^2"
    assert "*" not in textes.loi_lisible("sqrt(t)*sin(pi*t)")


def test_r8_loi_affichee_lisiblement_dans_larbre_et_les_proprietes(
    fenetre: FenetrePrincipale,
) -> None:
    _charger(fenetre, etude_proposee("60"))
    fenetre.arbre.selectionner_liaison("L01_pivot")
    p = fenetre.proprietes
    p.editeur_pilote.champ.setText("2*pi*t")
    p.bouton_pilote.click()
    element = fenetre.arbre.elements("Pilotes")[0]
    assert "2·π·t" in element
    assert "*" not in element
    assert "2·π·t" in p.etiquette_loi.text()
    assert "rad" in p.etiquette_loi.text()


def test_r8_liste_axe_reflete_le_vecteur_affiche(fenetre: FenetrePrincipale) -> None:
    etude = _charger(fenetre, etude_bielle("60", 60.0))
    p = fenetre.proprietes
    fenetre.arbre.selectionner_liaison("L01_pivot")  # axe (0, 0, 1)
    assert p.choix_axe.currentData() == "z"
    fenetre.arbre.selectionner_liaison("L30_glissiere")  # axe (1, 0, 0)
    assert p.choix_axe.currentData() == "x"
    # vecteur quelconque : la liste indique « Vecteur saisi »
    p.choix_axe.setCurrentIndex(p.choix_axe.findData("vecteur"))
    _regler(p.saisie_axe, (1.0, 1.0, 0.0))
    p.bouton_axe.click()
    fenetre.arbre.selectionner_liaison("L01_pivot")
    fenetre.arbre.selectionner_liaison("L30_glissiere")
    assert p.choix_axe.currentData() == "vecteur"
    assert p.choix_axe.currentText() == "Vecteur saisi"
    axe = etude.liaison("L30_glissiere").axe
    assert axe is not None
    assert [c.value() for c in p.saisie_axe] == pytest.approx(list(axe), abs=1e-4)


# --- EX-31 : pesanteur ---------------------------------------------------------------------
def test_ex31_saisie_et_desactivation_de_la_pesanteur(fenetre: FenetrePrincipale) -> None:
    etude = _charger(fenetre, etude_proposee("60"))
    fenetre.arbre.selectionner_rubrique("Pesanteur")
    e = fenetre.proprietes.editeur_pesanteur
    assert not e.isHidden()
    assert [c.value() for c in e.saisie] == pytest.approx([0.0, 0.0, -9.81], abs=1e-12)
    assert e.case_active.isChecked()
    _regler(e.saisie, (0.0, -9.81, 0.0))
    e.bouton.click()
    assert tuple(etude.pesanteur.vecteur) == pytest.approx((0.0, -9.81, 0.0), abs=1e-12)
    assert etude.pesanteur.actif
    e.case_active.setChecked(False)
    e.bouton.click()
    assert not etude.pesanteur.actif
    assert list(etude.pesanteur.effectif()) == [0.0, 0.0, 0.0]


# --- EX-32, R9 : actions, points en coordonnées pièce --------------------------------------
def _remplir_action(
    fenetre: FenetrePrincipale, nom: str, solide: str, composantes: tuple[str, str, str]
) -> None:
    fenetre.arbre.selectionner_rubrique("Actions")
    e = fenetre.proprietes.editeur_action
    e.champ_nom.setText(nom)
    e.choix_solide.setCurrentIndex(e.choix_solide.findText(solide))
    for editeur, texte in zip(e.editeurs, composantes, strict=True):
        editeur.champ.setText(texte)


def test_ex32_force_au_point_saisi_en_coordonnees_piece(fenetre: FenetrePrincipale) -> None:
    etude = _charger(fenetre, etude_bielle("60", 60.0))
    _remplir_action(fenetre, "F1", "Manivelle", ("0", "-5", "0"))
    e = fenetre.proprietes.editeur_action
    e.choix_nature.setCurrentIndex(e.choix_nature.findData(NatureAction.FORCE))
    e.choix_repere.setCurrentIndex(e.choix_repere.findData(RepereAction.MONDE))
    _regler(e.saisie_point, (100.0, 0.0, 0.0))  # mm, repère de la pièce
    e.bouton_ajouter.click()
    assert [a.nom for a in etude.actions] == ["F1"]
    action = etude.actions[0]
    assert action.nature is NatureAction.FORCE
    assert action.point == pytest.approx(A_MONDE_M, abs=1e-9)  # A monde = (50 ; 86,603 ; 0) mm
    assert list(action.valeur(0.0)) == pytest.approx([0.0, -5.0, 0.0], abs=1e-12)
    assert len(fenetre.arbre.elements("Actions")) == 1


def test_ex32_couple_et_edition_en_coordonnees_piece(fenetre: FenetrePrincipale) -> None:
    etude = _charger(fenetre, etude_bielle("60", 60.0))
    _remplir_action(fenetre, "C1", "Manivelle", ("0", "0", "2"))
    e = fenetre.proprietes.editeur_action
    e.choix_nature.setCurrentIndex(e.choix_nature.findData(NatureAction.COUPLE))
    e.bouton_ajouter.click()
    assert etude.actions[0].nature is NatureAction.COUPLE
    assert list(etude.actions[0].valeur(0.0)) == pytest.approx([0.0, 0.0, 2.0], abs=1e-12)
    # une force avec point : relue en coordonnées pièce quand on la sélectionne
    _remplir_action(fenetre, "F1", "Manivelle", ("1", "0", "0"))
    e.choix_nature.setCurrentIndex(e.choix_nature.findData(NatureAction.FORCE))
    _regler(e.saisie_point, (100.0, 0.0, 0.0))
    e.bouton_ajouter.click()
    assert len(etude.actions) == 2
    fenetre.arbre.selectionner_action("F1")
    assert [c.value() for c in e.saisie_point] == pytest.approx([100.0, 0.0, 0.0], abs=1e-6)
    e.bouton_supprimer.click()
    assert [a.nom for a in etude.actions] == ["C1"]


def test_ex32_action_invalide_ou_nom_double_refuse(fenetre: FenetrePrincipale) -> None:
    etude = _charger(fenetre, etude_bielle("60", 60.0))
    _remplir_action(fenetre, "F1", "Manivelle", ("__import__('os')", "0", "0"))
    e = fenetre.proprietes.editeur_action
    e.bouton_ajouter.click()
    assert etude.actions == []
    assert e.message.text() != ""
    _remplir_action(fenetre, "F1", "Manivelle", ("1", "0", "0"))
    e.bouton_ajouter.click()
    assert len(etude.actions) == 1
    _remplir_action(fenetre, "F1", "Bielle", ("2", "0", "0"))
    e.bouton_ajouter.click()
    assert len(etude.actions) == 1
    assert e.message.text() != ""


def test_ex32_le_bati_nest_pas_propose_comme_solide_dapplication(
    fenetre: FenetrePrincipale,
) -> None:
    _charger(fenetre, etude_bielle("60", 60.0))
    fenetre.arbre.selectionner_rubrique("Actions")
    combo = fenetre.proprietes.editeur_action.choix_solide
    noms = [combo.itemText(i) for i in range(combo.count())]
    assert "Bati" not in noms
    assert {"Manivelle", "Bielle", "Piston"} <= set(noms)


# --- EX-33 : ressorts ----------------------------------------------------------------------
def _remplir_ressort(fenetre: FenetrePrincipale, nom: str, s1: str, s2: str) -> None:
    fenetre.arbre.selectionner_rubrique("Ressorts")
    e = fenetre.proprietes.editeur_ressort
    e.champ_nom.setText(nom)
    e.choix_solide_1.setCurrentIndex(e.choix_solide_1.findText(s1))
    e.choix_solide_2.setCurrentIndex(e.choix_solide_2.findText(s2))


def test_ex33_ressort_points_en_coordonnees_piece(fenetre: FenetrePrincipale) -> None:
    etude = _charger(fenetre, etude_bielle("60", 60.0))
    _remplir_ressort(fenetre, "R1", "Manivelle", "Bati")
    e = fenetre.proprietes.editeur_ressort
    _regler(e.saisie_point_1, (100.0, 0.0, 0.0))
    _regler(e.saisie_point_2, (300.0, 0.0, 0.0))
    e.saisie_raideur.setValue(1000.0)
    e.saisie_longueur_libre.setValue(250.0)  # mm
    e.saisie_amortissement.setValue(2.0)
    e.bouton_ajouter.click()
    assert [r.nom for r in etude.ressorts] == ["R1"]
    r = etude.ressorts[0]
    assert r.point_1 == pytest.approx(A_MONDE_M, abs=1e-9)
    assert r.point_2 == pytest.approx((0.3, 0.0, 0.0), abs=1e-9)  # bâti : repère = monde
    assert r.raideur == pytest.approx(1000.0, abs=1e-9)
    assert r.longueur_libre == pytest.approx(0.25, abs=1e-12)
    assert r.amortissement == pytest.approx(2.0, abs=1e-12)
    assert len(fenetre.arbre.elements("Ressorts")) == 1
    fenetre.arbre.selectionner_ressort("R1")
    e.bouton_supprimer.click()
    assert etude.ressorts == []


def test_ex33_ressort_sur_un_seul_solide_refuse(fenetre: FenetrePrincipale) -> None:
    etude = _charger(fenetre, etude_bielle("60", 60.0))
    _remplir_ressort(fenetre, "R1", "Bielle", "Bielle")
    e = fenetre.proprietes.editeur_ressort
    e.bouton_ajouter.click()
    assert etude.ressorts == []
    assert e.message.text() != ""


# --- EX-50, EX-51 : capteurs ---------------------------------------------------------------
def test_ex50_capteur_de_liaison(fenetre: FenetrePrincipale) -> None:
    etude = _charger(fenetre, etude_bielle("60", 60.0))
    fenetre.arbre.selectionner_rubrique("Capteurs")
    e = fenetre.proprietes.editeur_capteur
    e.choix_genre.setCurrentIndex(e.choix_genre.findData("liaison"))
    e.champ_nom.setText("T12")
    e.choix_liaison.setCurrentIndex(e.choix_liaison.findText("L12_pivot"))
    e.choix_sens.setCurrentIndex(e.choix_sens.findData(SensTorseur.J_VERS_I))
    e.choix_base_liaison.setCurrentIndex(e.choix_base_liaison.findData(BaseCapteur.MONDE))
    e.bouton_ajouter.click()
    assert etude.capteurs == [
        CapteurLiaison("T12", "L12_pivot", SensTorseur.J_VERS_I, BaseCapteur.MONDE)
    ]
    assert len(fenetre.arbre.elements("Capteurs")) == 1


def test_ex51_capteur_de_point_en_coordonnees_piece(fenetre: FenetrePrincipale) -> None:
    etude = _charger(fenetre, etude_bielle("60", 60.0))
    fenetre.arbre.selectionner_rubrique("Capteurs")
    e = fenetre.proprietes.editeur_capteur
    e.choix_genre.setCurrentIndex(e.choix_genre.findData("point"))
    e.champ_nom.setText("A")
    e.choix_solide.setCurrentIndex(e.choix_solide.findText("Manivelle"))
    _regler(e.saisie_point, (100.0, 0.0, 0.0))
    e.choix_reference.setCurrentIndex(e.choix_reference.findText("Bati"))
    e.choix_base_point.setCurrentIndex(e.choix_base_point.findData(BaseCapteur.REFERENCE))
    e.bouton_ajouter.click()
    assert len(etude.capteurs) == 1
    capteur = etude.capteurs[0]
    assert isinstance(capteur, CapteurPoint)
    assert capteur.solide == "Manivelle"
    assert capteur.solide_reference == "Bati"
    assert capteur.base is BaseCapteur.REFERENCE
    assert capteur.point == pytest.approx(A_MONDE_M, abs=1e-9)
    fenetre.arbre.selectionner_capteur("A")
    e.bouton_supprimer.click()
    assert etude.capteurs == []


def test_ex51_capteur_nom_vide_refuse(fenetre: FenetrePrincipale) -> None:
    etude = _charger(fenetre, etude_bielle("60", 60.0))
    fenetre.arbre.selectionner_rubrique("Capteurs")
    e = fenetre.proprietes.editeur_capteur
    e.champ_nom.setText("")
    e.bouton_ajouter.click()
    assert etude.capteurs == []
    assert e.message.text() != ""
