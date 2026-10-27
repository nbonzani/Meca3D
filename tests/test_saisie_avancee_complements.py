# SPDX-License-Identifier: GPL-3.0-or-later
"""Compléments du lot 14 demandés par la relecture : nombres de dents d'un engrenage (EX-14,
EX-60), frottement et changement de type (EX-15), rapport k d'un engrenage importé conservé
(EX-14, EX-16), dents écrites dans l'étude comme dans l'annexe B du guide."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import json  # noqa: E402
from collections.abc import Iterator  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402
import pytest  # noqa: E402
from outils_bielle import etude_proposee  # noqa: E402
from outils_couplages import etude_reducteur  # noqa: E402
from pytestqt.qtbot import QtBot  # noqa: E402

from meca3d.ihm import textes  # noqa: E402
from meca3d.ihm.fenetre import FenetrePrincipale  # noqa: E402
from meca3d.modele.couplage import (  # noqa: E402
    Engrenage,
    ErreurCouplage,
    SensEngrenage,
    couplage_depuis_dict,
)
from meca3d.modele.liaison import Liaison, TypeLiaison  # noqa: E402


@pytest.fixture
def fenetre(qtbot: QtBot) -> Iterator[FenetrePrincipale]:
    f = FenetrePrincipale()
    qtbot.addWidget(f)
    f.confirmer = lambda titre, texte: True
    yield f
    f.annuler()


def _pivot() -> Liaison:
    return Liaison(
        nom="L",
        type_sc="revolute",
        solide_a="A",
        solide_b="B",
        centre=np.zeros(3),
        axe_sc=np.array([0.0, 0.0, 1.0]),
        valeur_pose=0.0,
    )


# --- EX-14, EX-60 : nombres de dents d'un engrenage -------------------------------------------
def test_ex14_dents_sans_partenaire_refusees() -> None:
    with pytest.raises(ErreurCouplage, match="Z₁ et Z₂"):
        Engrenage("R", "L1", "L2", 1 / 3, z1=20)


def test_ex14_dents_incoherentes_avec_k_refusees() -> None:
    with pytest.raises(ErreurCouplage, match="Z₁/Z₂"):
        Engrenage("R", "L1", "L2", 0.5, z1=20, z2=60)


def test_ex60_dents_ecrites_et_relues() -> None:
    e = Engrenage.depuis_dents("R", "L1", "L2", 20, 60)
    d = e.vers_dict()
    assert (d["z1"], d["z2"]) == (20, 60)
    relu = couplage_depuis_dict(d)
    assert isinstance(relu, Engrenage)
    assert (relu.z1, relu.z2) == (20, 60)


def test_ex60_engrenage_sans_dents_relu_comme_avant() -> None:
    d = {
        "genre": "engrenage",
        "nom": "R",
        "liaison_1": "L1",
        "liaison_2": "L2",
        "k": 0.5,
        "sens": "exterieur",
        "rendement": 1.0,
    }
    relu = couplage_depuis_dict(d)
    assert isinstance(relu, Engrenage)
    assert (relu.z1, relu.z2) == (None, None)
    assert relu.vers_dict() == d


# --- EX-15 : frottement ----------------------------------------------------------------------
def test_ex15_regler_frottement_refuse_sans_modification() -> None:
    pivot = _pivot()
    pivot.regler_frottement(0.1, rayon_axe=0.005)
    with pytest.raises(ValueError):
        pivot.regler_frottement(0.2, rayon_axe=-1.0)
    assert (pivot.frottement, pivot.rayon_axe, pivot.epsilon) == (0.1, 0.005, None)


def test_ex15_frottement_efface_par_un_type_non_frottant() -> None:
    pivot = _pivot()
    pivot.regler_frottement(0.1, rayon_axe=0.005, epsilon=0.02)
    pivot.choisir(TypeLiaison.ROTULE)
    assert (pivot.frottement, pivot.rayon_axe, pivot.epsilon) == (0.0, None, None)


def test_ex15_rayon_efface_hors_pivot() -> None:
    pivot = _pivot()
    pivot.regler_frottement(0.1, rayon_axe=0.005)
    pivot.choisir(TypeLiaison.GLISSIERE)
    assert (pivot.frottement, pivot.rayon_axe) == (0.1, None)


def test_ex10_pas_non_positif_refuse() -> None:
    with pytest.raises(ValueError, match="pas"):
        _pivot().definir_pas(0.0)


def test_ex15_glissiere_devenue_rotule_reste_simulable(fenetre: FenetrePrincipale) -> None:
    etude = etude_proposee("60")
    fenetre.charger_etude(etude)
    fenetre.arbre.selectionner_liaison("L30_glissiere")
    p = fenetre.proprietes
    p.saisie_frottement.setValue(0.2)
    p.bouton_frottement.click()
    p.choix_type.setCurrentIndex(p.choix_type.findData(TypeLiaison.ROTULE))
    assert p.groupe_frottement.isHidden()
    assert etude.liaison("L30_glissiere").frottement == 0.0


# --- EX-14, EX-16 : engrenage importé par son seul rapport k -----------------------------------
@pytest.mark.parametrize("k", [0.3337, 2.0e-4, 1500.0])
def test_ex16_rendement_modifie_k_importe_conserve(fenetre: FenetrePrincipale, k: float) -> None:
    etude = etude_reducteur()
    etude.couplages = [Engrenage("K1", "L1", "L2", k, SensEngrenage.EXTERIEUR)]
    fenetre.charger_etude(etude)
    fenetre.arbre.selectionner_couplage("K1")
    editeur = fenetre.proprietes.editeur_couplage
    editeur.saisie_rendement.setValue(0.9)
    editeur.bouton_ajouter.click()
    (c,) = etude.couplages
    assert isinstance(c, Engrenage)
    assert c.k == k  # identique : aucune dent n'a été retouchée
    assert c.rendement == pytest.approx(0.9, abs=1e-12)


# --- Annexe B : dents écrites dans l'étude enregistrée depuis l'IHM ----------------------------
def test_ex60_annexe_b_dents_enregistrees(fenetre: FenetrePrincipale, tmp_path: Path) -> None:
    fenetre.charger_etude(etude_reducteur())
    fenetre.arbre.selectionner_rubrique(textes.RUBRIQUE_COUPLAGES)
    e = fenetre.proprietes.editeur_couplage
    e.choix_genre.setCurrentIndex(e.choix_genre.findData(Engrenage.GENRE))
    e.choix_liaison_1.setCurrentText("L1")
    e.choix_liaison_2.setCurrentText("L2")
    e.saisie_z1.setValue(20)
    e.saisie_z2.setValue(60)
    e.saisie_rendement.setValue(0.95)
    e.bouton_ajouter.click()
    chemin = tmp_path / "reducteur.meca3d"
    assert fenetre.enregistrer_sous(chemin)
    (c,) = json.loads(chemin.read_text(encoding="utf-8"))["couplages"]
    assert c == {
        "genre": "engrenage",
        "nom": "K1",
        "liaison_1": "L1",
        "liaison_2": "L2",
        "k": 0.3333333333333333,
        "sens": "exterieur",
        "rendement": 0.95,
        "z1": 20,
        "z2": 60,
    }
