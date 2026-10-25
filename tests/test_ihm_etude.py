# SPDX-License-Identifier: GPL-3.0-or-later
"""Étude depuis l'IHM : Nouveau / Ouvrir / Enregistrer (EX-60), bandeau « maquette modifiée »
(EX-06, R3), hyperstatique autorisé et mode cinématique (R7, EX-23, EX-41), commande `meca3d`."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import json  # noqa: E402
from collections.abc import Iterator  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402
import pytest  # noqa: E402
from faux_serveur import JETON_DE_TEST, FauxServeur  # noqa: E402
from outils_bielle import etude_bielle  # noqa: E402
from outils_cinematique import courbes_piston, etude_bielle_60  # noqa: E402
from pytestqt.qtbot import QtBot  # noqa: E402

from meca3d import cli  # noqa: E402
from meca3d.cao.canal import CanalSolidCraft  # noqa: E402
from meca3d.ihm.fenetre import FenetrePrincipale  # noqa: E402
from meca3d.modele.etude import Etude, ecrire_etude, lire_etude  # noqa: E402
from meca3d.modele.liaison import TypeLiaison  # noqa: E402

DELAI = 120_000
FIXTURE = Path(__file__).parent / "fixtures" / "bielle" / "bielle.meca3d"


@pytest.fixture
def fenetre(qtbot: QtBot) -> Iterator[FenetrePrincipale]:
    f = FenetrePrincipale()
    qtbot.addWidget(f)
    f.confirmer = lambda titre, texte: True
    yield f
    f.annuler()


def _etude_courante(fenetre: FenetrePrincipale) -> Etude | None:
    return fenetre.etude


def _simuler(fenetre: FenetrePrincipale, qtbot: QtBot, cinematique: bool = False) -> None:
    fenetre.resultats = None
    (fenetre.action_simuler_cinematique if cinematique else fenetre.action_simuler).trigger()
    qtbot.waitUntil(lambda: fenetre.resultats is not None, timeout=DELAI)


# --- EX-60 : enregistrer, rouvrir, simuler -------------------------------------------------
@pytest.mark.slow
def test_ex60_enregistrer_rouvrir_simuler_resultats_identiques_bit_a_bit(
    fenetre: FenetrePrincipale, qtbot: QtBot, tmp_path: Path
) -> None:
    fenetre.charger_etude(etude_bielle("60", 60.0))
    _simuler(fenetre, qtbot)
    premiers = fenetre.resultats
    assert premiers is not None
    chemin = tmp_path / "bielle.meca3d"
    assert fenetre.enregistrer_sous(chemin)
    assert chemin.exists()
    assert fenetre.chemin_etude == chemin
    fenetre.nouvelle_etude()
    assert fenetre.etude is None
    assert fenetre.ouvrir_etude(chemin)
    _simuler(fenetre, qtbot)
    seconds = fenetre.resultats
    assert seconds is not None
    assert np.array_equal(premiers.t, seconds.t)
    for nom in premiers.positions:
        assert np.array_equal(premiers.positions[nom], seconds.positions[nom])
    for nom in premiers.forces:
        assert np.array_equal(premiers.forces[nom], seconds.forces[nom])
        assert np.array_equal(premiers.moments[nom], seconds.moments[nom])


def test_ex60_fichier_corrompu_message_et_aucune_etude_partielle(
    fenetre: FenetrePrincipale, tmp_path: Path
) -> None:
    corrompu = tmp_path / "corrompu.meca3d"
    corrompu.write_text('{"version_etude": 2, "maquette": ', encoding="utf-8")
    assert not fenetre.ouvrir_etude(corrompu)
    assert fenetre.etude is None
    assert "corrompu" in fenetre.dernier_message
    # avec une étude déjà ouverte, elle reste intacte
    etude = etude_bielle("60", 60.0)
    fenetre.charger_etude(etude)
    incoherent = tmp_path / "incoherent.meca3d"
    donnees = json.loads(FIXTURE.read_text(encoding="utf-8"))
    del donnees["liaisons"]
    incoherent.write_text(json.dumps(donnees), encoding="utf-8")
    assert not fenetre.ouvrir_etude(incoherent)
    assert fenetre.etude is etude
    assert "incohérent" in fenetre.dernier_message
    assert not fenetre.ouvrir_etude(tmp_path / "absent.meca3d")
    assert fenetre.etude is etude


def test_ex60_menu_fichier_nouveau_ouvrir_enregistrer(
    fenetre: FenetrePrincipale, tmp_path: Path
) -> None:
    chemin = tmp_path / "e.meca3d"
    fenetre.charger_etude(etude_bielle("60", 60.0))
    fenetre.dialogue_enregistrer = lambda suggestion: chemin
    fenetre.action_enregistrer_sous.trigger()
    assert chemin.exists()
    assert "e.meca3d" in fenetre.windowTitle()
    # modification puis Enregistrer : écrit dans le même fichier, sans dialogue
    fenetre.dialogue_enregistrer = lambda suggestion: pytest.fail("pas de dialogue attendu")
    assert fenetre.etude is not None
    fenetre.etude.liaison("L01_pivot").centre = np.array([0.0, 0.0, 0.001])
    fenetre.action_enregistrer.trigger()
    assert lire_etude(chemin).liaison("L01_pivot").centre[2] == pytest.approx(0.001, abs=1e-15)
    fenetre.action_nouveau.trigger()
    assert fenetre.etude is None
    assert fenetre.arbre.elements("Liaisons") == []
    assert fenetre.chemin_etude is None
    fenetre.dialogue_ouvrir = lambda: chemin
    fenetre.action_ouvrir.trigger()
    rouverte = _etude_courante(fenetre)  # relue par une fonction : pyright garderait « None »
    assert rouverte is not None
    assert [x.nom for x in rouverte.liaisons] == [
        "L01_pivot",
        "L12_pivot",
        "L23_rotule",
        "L30_glissiere",
    ]
    assert len(fenetre.arbre.elements("Liaisons")) == 4


# --- R3 : signature de structure persistée -------------------------------------------------
def test_r3_etude_sans_signature_ecrite_comme_avant() -> None:
    etude = lire_etude(FIXTURE)
    assert etude.signature == ""
    assert "signature_structure" not in etude.vers_dict()
    assert etude.vers_dict()["version_etude"] == 2


def test_r3_signature_ecrite_et_relue(tmp_path: Path) -> None:
    etude = etude_bielle("60", 60.0)
    etude.signature = "abc123"
    chemin = tmp_path / "s.meca3d"
    ecrire_etude(etude, chemin)
    assert json.loads(chemin.read_text(encoding="utf-8"))["signature_structure"] == "abc123"
    assert lire_etude(chemin).signature == "abc123"


def _brancher(fenetre: FenetrePrincipale, faux: FauxServeur) -> None:
    fenetre.fabrique_canal = lambda: CanalSolidCraft(
        port=faux.port, jeton=JETON_DE_TEST, intervalle_pending=0.01
    )


def _connecter_et_importer(fenetre: FenetrePrincipale, qtbot: QtBot) -> None:
    fenetre.action_connecter.trigger()
    qtbot.waitUntil(lambda: fenetre.action_importer.isEnabled(), timeout=10_000)
    fenetre.action_importer.trigger()
    qtbot.waitUntil(lambda: fenetre.etude is not None, timeout=20_000)


def _verifier(fenetre: FenetrePrincipale, qtbot: QtBot) -> None:
    avant = fenetre.verifications
    fenetre.verifier_structure()
    qtbot.waitUntil(lambda: fenetre.verifications > avant, timeout=20_000)


def test_ex06_signature_de_limport_persistee_dans_le_fichier(
    fenetre: FenetrePrincipale, qtbot: QtBot, tmp_path: Path
) -> None:
    with FauxServeur(theta="60") as faux:
        _brancher(fenetre, faux)
        _connecter_et_importer(fenetre, qtbot)
    assert fenetre.etude is not None
    assert fenetre.etude.signature != ""
    chemin = tmp_path / "importee.meca3d"
    assert fenetre.enregistrer_sous(chemin)
    assert lire_etude(chemin).signature == fenetre.etude.signature


def test_ex06_bandeau_affiche_quand_la_structure_change(
    fenetre: FenetrePrincipale, qtbot: QtBot
) -> None:
    with FauxServeur(theta="60") as faux:
        _brancher(fenetre, faux)
        _connecter_et_importer(fenetre, qtbot)
        assert fenetre.bandeau.isHidden()
        faux.types_modifies = {"L23_rotule": "revolute"}
        _verifier(fenetre, qtbot)
        assert not fenetre.bandeau.isHidden()
        assert "réimporter" in fenetre.etiquette_bandeau.text()
        # réimport : le bandeau disparaît
        fenetre.bouton_reimporter.click()
        qtbot.waitUntil(lambda: fenetre.bandeau.isHidden(), timeout=20_000)


def test_ex06_bandeau_absent_quand_seules_les_poses_changent(
    fenetre: FenetrePrincipale, qtbot: QtBot
) -> None:
    with FauxServeur(theta="60") as faux:
        _brancher(fenetre, faux)
        _connecter_et_importer(fenetre, qtbot)
        faux.theta = "00"  # poses différentes, structure identique
        _verifier(fenetre, qtbot)
        assert fenetre.bandeau.isHidden()


def test_ex06_verification_a_la_connexion(fenetre: FenetrePrincipale, qtbot: QtBot) -> None:
    with FauxServeur(theta="60") as faux:
        _brancher(fenetre, faux)
        _connecter_et_importer(fenetre, qtbot)
        assert fenetre.bandeau.isHidden()
        faux.types_modifies = {"L23_rotule": "revolute"}
        avant = fenetre.verifications
        fenetre.action_connecter.trigger()  # reconnexion
        qtbot.waitUntil(lambda: fenetre.verifications > avant, timeout=20_000)
        assert not fenetre.bandeau.isHidden()


def test_ex06_verification_avant_simulation(fenetre: FenetrePrincipale, qtbot: QtBot) -> None:
    with FauxServeur(theta="60") as faux:
        _brancher(fenetre, faux)
        _connecter_et_importer(fenetre, qtbot)
        etude = fenetre.etude
        assert etude is not None
        modele = etude_bielle("60", 60.0)
        etude.liaison("L23_rotule").choisir(TypeLiaison.LINEAIRE_ANNULAIRE)
        etude.liaison("L23_rotule").reorienter_axe((0.0, 0.0, 1.0))
        for liaison in etude.liaisons:
            liaison.valider()
        etude.pilotes = modele.pilotes
        etude.reglages = modele.reglages
        fenetre.charger_etude(etude)
        faux.types_modifies = {"L23_rotule": "revolute"}
        avant = faux.methodes_recues().count("joint.list")
        fenetre.action_simuler.trigger()
        qtbot.waitUntil(lambda: fenetre.calcul is not None, timeout=20_000)
        assert faux.methodes_recues().count("joint.list") > avant
        assert not fenetre.bandeau.isHidden()
        fenetre.annuler()


# --- R7 : hyperstatique autorisé et mode cinématique ---------------------------------------
def test_r7_hyperstatique_autorise_branche_sur_letude(
    fenetre: FenetrePrincipale, tmp_path: Path
) -> None:
    etude = etude_bielle_60("pivot")
    fenetre.charger_etude(etude)
    assert not fenetre.action_hyperstatique.isChecked()
    assert etude.hyperstatique_autorise is False
    fenetre.action_hyperstatique.trigger()
    assert etude.hyperstatique_autorise is True
    chemin = tmp_path / "h.meca3d"
    assert fenetre.enregistrer_sous(chemin)
    assert lire_etude(chemin).hyperstatique_autorise is True
    fenetre.nouvelle_etude()
    assert fenetre.ouvrir_etude(chemin)
    assert fenetre.action_hyperstatique.isChecked()
    assert fenetre.hyperstatique_autorise


def test_r7_garde_fou_hyperstatique_dans_lihm(fenetre: FenetrePrincipale, qtbot: QtBot) -> None:
    fenetre.charger_etude(etude_bielle_60("pivot"))  # h = 3
    fenetre.action_simuler_cinematique.trigger()
    assert fenetre.calcul is None
    assert "h = 3" in fenetre.dernier_message
    fenetre.action_hyperstatique.trigger()
    fenetre.action_simuler.trigger()  # dynamique : toujours refusé
    assert fenetre.calcul is None
    assert "indéterminé" in fenetre.dernier_message


@pytest.mark.slow
def test_r7_mode_cinematique_isostatique_depuis_lihm(
    fenetre: FenetrePrincipale, qtbot: QtBot
) -> None:
    fenetre.charger_etude(etude_bielle_60())
    assert fenetre.action_simuler_cinematique.isEnabled()
    assert "développement" not in fenetre.action_simuler_cinematique.toolTip()
    _simuler(fenetre, qtbot, cinematique=True)
    resultats = fenetre.resultats
    assert resultats is not None
    assert resultats.forces == {}
    x_b, _, _ = courbes_piston(resultats.t)
    assert np.abs(resultats.positions["Piston"][:, 0] - x_b).max() < 1e-6


@pytest.mark.slow
def test_r7_ex23_trois_pivots_et_glissiere_option_cochee_depuis_lihm(
    fenetre: FenetrePrincipale, qtbot: QtBot
) -> None:
    fenetre.charger_etude(etude_bielle_60("pivot"))
    fenetre.action_hyperstatique.trigger()
    _simuler(fenetre, qtbot, cinematique=True)
    resultats = fenetre.resultats
    assert resultats is not None
    assert len(resultats.ddl_liberes) == 3
    assert "ddl libérés" in fenetre.journal.toPlainText()
    x_b, _, _ = courbes_piston(resultats.t)
    assert np.abs(resultats.positions["Piston"][:, 0] - x_b).max() < 1e-6


# --- commande meca3d sans argument ---------------------------------------------------------
def test_ex62_meca3d_sans_argument_ouvre_la_fenetre(monkeypatch: pytest.MonkeyPatch) -> None:
    from meca3d.ihm import fenetre as module_fenetre

    monkeypatch.setattr(module_fenetre, "lancer", lambda: 7)
    assert cli.main([]) == 7


def test_ex62_meca3d_simuler_inchange(tmp_path: Path) -> None:
    sortie = tmp_path / "s.csv"
    etude = etude_bielle_60()
    fichier = tmp_path / "e.meca3d"
    ecrire_etude(etude, fichier)
    assert cli.main(["simuler", str(fichier), "--csv", str(sortie), "--mode", "cinematique"]) == 0
    assert sortie.exists()
    assert isinstance(lire_etude(fichier), Etude)
