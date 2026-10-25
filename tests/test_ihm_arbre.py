# SPDX-License-Identifier: GPL-3.0-or-later
"""Fenêtre principale, arbre de l'étude, simulations (EX-61, EX-11, EX-22, EX-42)."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from collections.abc import Iterator  # noqa: E402

import pytest  # noqa: E402
from faux_serveur import JETON_DE_TEST, FauxServeur  # noqa: E402
from outils_bielle import LOI_MONTEE, etude_bielle, etude_proposee  # noqa: E402
from pytestqt.qtbot import QtBot  # noqa: E402

from meca3d.cao.canal import CanalSolidCraft  # noqa: E402
from meca3d.graphe.mobilite import Decision  # noqa: E402
from meca3d.ihm import fenetre as module_fenetre  # noqa: E402
from meca3d.ihm.fenetre import FenetrePrincipale  # noqa: E402
from meca3d.modele.actions import LoiEntree, Pesanteur, Pilote  # noqa: E402
from meca3d.modele.etude import Etude, Reglages  # noqa: E402
from meca3d.modele.liaison import Statut, TypeLiaison  # noqa: E402
from meca3d.moteur.processus import cinematique_disponible  # noqa: E402

BRANCHES = ["Modèle cinématique", "Données d'entrée", "Résultats"]
DELAI = 120_000  # ms, attente maximale d'un calcul
LIAISONS_BIELLE = {"L01_pivot", "L12_pivot", "L23_rotule", "L30_glissiere"}


@pytest.fixture
def fenetre(qtbot: QtBot) -> Iterator[FenetrePrincipale]:
    f = FenetrePrincipale()
    qtbot.addWidget(f)
    f.confirmer = lambda titre, texte: True
    yield f
    f.annuler()


def _bielle_60() -> Etude:
    """Bielle isostatique (linéaire annulaire d'axe z en B), importée à θ = 60°."""
    return etude_bielle("60", 60.0)


def _etude_hyperstatique() -> Etude:
    etude = etude_proposee("60")
    for liaison in etude.liaisons:
        liaison.valider()
    etude.pilotes = [Pilote(liaison="L01_pivot", loi=LoiEntree(LOI_MONTEE))]
    etude.pesanteur = Pesanteur(vecteur=(0.0, -9.81, 0.0))
    etude.reglages = Reglages(duree=1.0, nb_pas=4000, periode_ecriture=0.002)
    return etude


def _etude_longue() -> Etude:
    etude = _bielle_60()
    etude.reglages = Reglages(duree=60.0, nb_pas=240000, periode_ecriture=0.01)
    return etude


# --- EX-61 : arbre ------------------------------------------------------------------------
def test_ex61_trois_branches(fenetre: FenetrePrincipale) -> None:
    fenetre.charger_etude(etude_proposee("60"))
    assert fenetre.arbre.branches() == BRANCHES
    assert fenetre.arbre.rubriques("Modèle cinématique") == ["Solides", "Liaisons", "Graphe"]
    assert fenetre.arbre.rubriques("Données d'entrée") == [
        "Pilotes",
        "Pesanteur",
        "Actions",
        "Ressorts",
    ]
    assert fenetre.arbre.rubriques("Résultats") == ["Capteurs", "Courbes", "Animation"]


def test_ex61_branches_presentes_sans_etude(fenetre: FenetrePrincipale) -> None:
    assert fenetre.arbre.branches() == BRANCHES
    assert not fenetre.action_simuler.isEnabled()


def test_ex61_liaison_non_validee_marquee(fenetre: FenetrePrincipale) -> None:
    etude = etude_proposee("60")
    fenetre.charger_etude(etude)
    assert fenetre.arbre.elements("Solides") == [s.nom for s in etude.solides]
    assert len(fenetre.arbre.elements("Liaisons")) == 4
    for liaison in etude.liaisons:
        item = fenetre.arbre.item_liaison(liaison.nom)
        assert fenetre.arbre.est_incomplet(item)
        assert "proposée" in item.text(0)
    # la rubrique et la branche qui contiennent un élément incomplet le sont aussi
    assert fenetre.arbre.est_incomplet(fenetre.arbre.item_rubrique("Liaisons"))
    assert fenetre.arbre.est_incomplet(fenetre.arbre.item_branche("Modèle cinématique"))


def test_ex61_liaison_validee_non_marquee(fenetre: FenetrePrincipale) -> None:
    fenetre.charger_etude(_bielle_60())
    item = fenetre.arbre.item_liaison("L01_pivot")
    assert not fenetre.arbre.est_incomplet(item)
    assert "validée" in item.text(0)
    assert not fenetre.arbre.est_incomplet(fenetre.arbre.item_rubrique("Liaisons"))


# --- EX-11 : validation, bouton Simuler, validation en bloc --------------------------------
def test_ex11_simuler_inactif_tant_quune_liaison_nest_pas_validee(
    fenetre: FenetrePrincipale,
) -> None:
    etude = _bielle_60()
    etude.liaison("L12_pivot").statut = Statut.PROPOSEE
    fenetre.charger_etude(etude)
    assert not fenetre.action_simuler.isEnabled()
    assert not fenetre.action_simuler_cinematique.isEnabled()
    fenetre.arbre.selectionner_liaison("L12_pivot")
    fenetre.proprietes.bouton_valider.click()
    assert etude.liaison("L12_pivot").statut is Statut.VALIDEE
    assert fenetre.action_simuler.isEnabled()
    assert not fenetre.arbre.est_incomplet(fenetre.arbre.item_liaison("L12_pivot"))


def test_ex11_validation_une_par_une_depuis_les_proprietes(fenetre: FenetrePrincipale) -> None:
    etude = etude_proposee("60")
    fenetre.charger_etude(etude)
    for liaison in etude.liaisons:
        fenetre.arbre.selectionner_liaison(liaison.nom)
        assert fenetre.proprietes.etiquette_statut.text().endswith("proposée")
        fenetre.proprietes.bouton_valider.click()
    assert all(x.statut is Statut.VALIDEE for x in etude.liaisons)


def test_ex11_choix_de_type_parmi_les_onze_repasse_en_proposee(
    fenetre: FenetrePrincipale,
) -> None:
    etude = _bielle_60()
    fenetre.charger_etude(etude)
    fenetre.arbre.selectionner_liaison("L01_pivot")
    combo = fenetre.proprietes.choix_type
    types = {combo.itemData(i) for i in range(combo.count()) if combo.itemData(i) is not None}
    assert types == set(TypeLiaison)
    combo.setCurrentIndex(combo.findData(TypeLiaison.PIVOT_GLISSANT))
    assert etude.liaison("L01_pivot").type is TypeLiaison.PIVOT_GLISSANT
    assert etude.liaison("L01_pivot").statut is Statut.PROPOSEE
    assert not fenetre.action_simuler.isEnabled()


def test_ex11_validation_en_bloc_absente_par_defaut(fenetre: FenetrePrincipale) -> None:
    fenetre.charger_etude(etude_proposee("60"))
    assert not fenetre.action_validation_en_bloc.isChecked()
    assert not fenetre.action_valider_toutes.isVisible()
    assert not fenetre.action_valider_toutes.isEnabled()


def test_ex11_validation_en_bloc_activee_valide_toutes_les_liaisons(
    fenetre: FenetrePrincipale,
) -> None:
    etude = etude_proposee("60")
    fenetre.charger_etude(etude)
    fenetre.action_validation_en_bloc.trigger()
    assert etude.validation_en_bloc
    assert fenetre.action_valider_toutes.isVisible()
    fenetre.action_valider_toutes.trigger()
    assert all(x.statut is Statut.VALIDEE for x in etude.liaisons)
    assert not fenetre.arbre.est_incomplet(fenetre.arbre.item_rubrique("Liaisons"))
    fenetre.action_validation_en_bloc.trigger()
    assert not etude.validation_en_bloc
    assert not fenetre.action_valider_toutes.isVisible()


def test_ex11_validation_en_bloc_sans_confirmation_ne_valide_rien(
    fenetre: FenetrePrincipale,
) -> None:
    etude = etude_proposee("60")
    fenetre.charger_etude(etude)
    fenetre.action_validation_en_bloc.trigger()
    fenetre.confirmer = lambda titre, texte: False
    fenetre.action_valider_toutes.trigger()
    assert all(x.statut is Statut.PROPOSEE for x in etude.liaisons)


# --- EX-12, EX-13 : propriétés ------------------------------------------------------------
def test_ex12_seconde_direction_colineaire_refusee(fenetre: FenetrePrincipale) -> None:
    etude = _bielle_60()
    fenetre.charger_etude(etude)
    fenetre.arbre.selectionner_liaison("L01_pivot")
    p = fenetre.proprietes
    assert p.groupe_direction.isHidden()
    p.choix_type.setCurrentIndex(p.choix_type.findData(TypeLiaison.ROTULE_A_DOIGT))
    assert not p.groupe_direction.isHidden()
    for champ, valeur in zip(p.saisie_direction, (0.0, 0.0, 1.0), strict=True):
        champ.setValue(valeur)
    p.bouton_direction.click()
    assert etude.liaison("L01_pivot").direction is None
    assert p.message.text() != ""
    for champ, valeur in zip(p.saisie_direction, (1.0, 1.0, 0.0), strict=True):
        champ.setValue(valeur)
    p.bouton_direction.click()
    assert etude.liaison("L01_pivot").direction is not None
    assert p.message.text() == ""


def test_ex13_reorientation_de_laxe_met_a_jour_m_et_h(fenetre: FenetrePrincipale) -> None:
    """Bielle-manivelle : rotule en B -> linéaire annulaire d'axe z -> h passe de 1 à 0."""
    etude = etude_proposee("60")
    fenetre.charger_etude(etude)
    assert fenetre.etiquette_h.text() == "h = 1"
    fenetre.arbre.selectionner_liaison("L23_rotule")
    p = fenetre.proprietes
    p.choix_type.setCurrentIndex(p.choix_type.findData(TypeLiaison.LINEAIRE_ANNULAIRE))
    p.choix_axe.setCurrentIndex(p.choix_axe.findData("z"))
    p.bouton_axe.click()
    axe = etude.liaison("L23_rotule").axe
    assert axe is not None
    assert tuple(axe.tolist()) == (0.0, 0.0, 1.0)
    assert fenetre.mobilite is not None
    assert (fenetre.mobilite.m, fenetre.mobilite.h) == (1, 0)
    assert fenetre.etiquette_h.text() == "h = 0"


# --- Import depuis le faux serveur ---------------------------------------------------------
def test_ex61_import_depuis_le_faux_serveur_peuple_larbre(
    fenetre: FenetrePrincipale, qtbot: QtBot
) -> None:
    with FauxServeur(theta="60") as faux:
        fenetre.fabrique_canal = lambda: CanalSolidCraft(
            port=faux.port, jeton=JETON_DE_TEST, intervalle_pending=0.01
        )
        assert not fenetre.action_importer.isEnabled()  # se connecter d'abord
        fenetre.action_connecter.trigger()
        qtbot.waitUntil(lambda: fenetre.action_importer.isEnabled(), timeout=10_000)
        assert "connecté" in fenetre.etiquette_connexion.text().lower()
        fenetre.action_importer.trigger()
        qtbot.waitUntil(lambda: fenetre.etude is not None, timeout=20_000)
    assert len(fenetre.arbre.elements("Solides")) == 4
    assert len(fenetre.arbre.elements("Liaisons")) == 4
    assert all("proposée" in t for t in fenetre.arbre.elements("Liaisons"))
    assert fenetre.etiquette_m.text() == "m = 1"
    assert fenetre.etiquette_h.text() == "h = 1"
    assert not fenetre.action_simuler.isEnabled()


def test_ex01_solidcraft_absent_message_sans_plantage(
    fenetre: FenetrePrincipale, qtbot: QtBot
) -> None:
    fenetre.fabrique_canal = lambda: CanalSolidCraft(port=1, jeton=JETON_DE_TEST)
    fenetre.action_connecter.trigger()
    qtbot.waitUntil(lambda: "n'est pas lancé" in fenetre.dernier_message, timeout=10_000)
    assert "déconnecté" in fenetre.etiquette_connexion.text().lower()
    assert not fenetre.action_importer.isEnabled()


# --- Graphe --------------------------------------------------------------------------------
def test_ex20_graphe_met_en_evidence_un_cycle_de_quatre_liaisons(
    fenetre: FenetrePrincipale,
) -> None:
    fenetre.charger_etude(_bielle_60())
    vue = fenetre.vue_graphe
    assert vue.resume() == "μ = 1   m = 1   h = 0"
    assert set(vue.liaisons_en_evidence()) == LIAISONS_BIELLE


# --- EX-22 : garde-fou ---------------------------------------------------------------------
def test_ex22_hyperstatique_refuse_sans_aucun_processus(
    fenetre: FenetrePrincipale, monkeypatch: pytest.MonkeyPatch
) -> None:
    def interdit(*args: object, **kwargs: object) -> None:
        raise AssertionError("aucun processus de calcul ne doit être lancé")

    monkeypatch.setattr(module_fenetre, "CalculEnCours", interdit)
    fenetre.charger_etude(_etude_hyperstatique())
    assert fenetre.action_simuler.isEnabled()
    fenetre.action_simuler.trigger()
    assert fenetre.calcul is None
    assert "h = 1" in fenetre.dernier_message
    assert "L23_rotule" in fenetre.dernier_message
    assert fenetre.action_simuler.isEnabled()


# --- EX-23 / EX-41 : options enseignant et mode cinématique --------------------------------
def test_ex23_hyperstatique_autorise_decoche_par_defaut(fenetre: FenetrePrincipale) -> None:
    assert not fenetre.action_hyperstatique.isChecked()
    assert not fenetre.hyperstatique_autorise
    fenetre.action_hyperstatique.trigger()
    assert fenetre.hyperstatique_autorise


def test_ex41_mode_cinematique_prevu_ou_desactive_avec_message(
    fenetre: FenetrePrincipale,
) -> None:
    fenetre.charger_etude(_bielle_60())
    if cinematique_disponible():
        assert fenetre.action_simuler_cinematique.isEnabled()
    else:
        assert not fenetre.action_simuler_cinematique.isEnabled()
        assert "disponible" in fenetre.action_simuler_cinematique.toolTip()


# --- EX-42 : simulation depuis l'IHM -------------------------------------------------------
@pytest.mark.slow
def test_ex42_simulation_lancee_depuis_lihm_puis_annulee(
    fenetre: FenetrePrincipale, qtbot: QtBot
) -> None:
    fenetre.charger_etude(_etude_longue())
    fenetre.action_simuler.trigger()
    assert fenetre.calcul is not None
    assert fenetre.action_annuler.isEnabled()
    assert not fenetre.action_simuler.isEnabled()
    qtbot.waitUntil(lambda: fenetre.barre_progression.value() > 0, timeout=DELAI)
    fenetre.action_annuler.trigger()
    qtbot.waitUntil(lambda: fenetre.calcul is None, timeout=1000)
    assert fenetre.resultats is None
    assert not fenetre.action_annuler.isEnabled()
    assert fenetre.action_simuler.isEnabled()
    assert "annulé" in fenetre.dernier_message.lower()


@pytest.mark.slow
def test_ex42_simulation_depuis_lihm_menee_a_son_terme(
    fenetre: FenetrePrincipale, qtbot: QtBot
) -> None:
    fenetre.charger_etude(_bielle_60())
    fenetre.action_simuler.trigger()
    qtbot.waitUntil(lambda: fenetre.resultats is not None, timeout=DELAI)
    assert fenetre.resultats is not None
    assert fenetre.resultats.t.shape == (501,)
    assert fenetre.calcul is None
    assert fenetre.action_simuler.isEnabled()


@pytest.mark.slow
def test_ex43_echec_du_solveur_message_pedagogique_dans_lihm(
    fenetre: FenetrePrincipale, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Garde-fou court-circuité (h > 0 transmis au moteur) : message avec l'instant de l'échec."""

    def autorise_tout(*args: object, **kwargs: object) -> Decision:
        return Decision(True, "")

    monkeypatch.setattr(module_fenetre, "verifier_avant_simulation", autorise_tout)
    fenetre.charger_etude(_etude_hyperstatique())
    fenetre.action_simuler.trigger()
    qtbot.waitUntil(lambda: fenetre.calcul is None, timeout=DELAI)
    assert fenetre.resultats is None
    assert "hyperstatique" in fenetre.dernier_message
    assert "t = " in fenetre.dernier_message
    assert fenetre.action_simuler.isEnabled()
