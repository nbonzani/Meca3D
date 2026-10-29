# SPDX-License-Identifier: GPL-3.0-or-later
"""Lancement de SolidCraft et ouverture de la maquette depuis l'IHM (EX-07, lot 15).

Frontières simulées : le lancement du processus (`fenetre.lanceur`, qui écrit le jeton comme le
fait SolidCraft au démarrage), le canal (faux serveur), les dialogues et la mémoire des réglages.
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import socket  # noqa: E402
from collections.abc import Iterator  # noqa: E402
from pathlib import Path  # noqa: E402

import pytest  # noqa: E402
from faux_serveur import JETON_DE_TEST, FauxServeur, Scenario  # noqa: E402
from pytestqt.qtbot import QtBot  # noqa: E402

from meca3d.cao.canal import CanalSolidCraft  # noqa: E402
from meca3d.ihm import textes  # noqa: E402
from meca3d.ihm.fenetre import FenetrePrincipale  # noqa: E402
from meca3d.modele.etude import ecrire_etude, lire_etude  # noqa: E402

DELAI = 20_000  # ms
FIXTURE = Path(__file__).parent / "fixtures" / "bielle" / "bielle.meca3d"


class Memoire:
    """Réglages mémorisés par utilisateur (QSettings en vrai)."""

    def __init__(self) -> None:
        self.valeurs: dict[str, str] = {}

    def lire(self, cle: str) -> str | None:
        return self.valeurs.get(cle)

    def ecrire(self, cle: str, valeur: str) -> None:
        self.valeurs[cle] = valeur


class Banc:
    """Fenêtre et frontières simulées ; `reponse` : réponse donnée aux questions."""

    def __init__(self, fenetre: FenetrePrincipale, dossier: Path) -> None:
        self.fenetre = fenetre
        self.dossier = dossier
        self.questions: list[str] = []
        self.reponse = True
        self.lances: list[tuple[Path, int]] = []
        self.exe = dossier / "sc" / "solidcraft.exe"
        self.exe.parent.mkdir(parents=True)
        self.exe.write_bytes(b"")
        fenetre.memoire = Memoire()
        fenetre.ouverture_maquette_auto = True  # actif dans l'application réelle (`lancer()`)
        fenetre.recherche_solidcraft = lambda: self.exe
        fenetre.confirmer = self._confirmer
        fenetre.lanceur = self._lanceur
        absent = _port_libre()
        fenetre.fabrique_canal = lambda: CanalSolidCraft(port=absent)

    def _confirmer(self, titre: str, texte: str) -> bool:
        self.questions.append(f"{titre}\n{texte}")
        return self.reponse

    def _lanceur(self, exe: Path, port: int) -> None:
        self.lances.append((exe, port))
        (self.dossier / f"{port}.token").write_text(JETON_DE_TEST, encoding="utf-8")

    def brancher(self, faux: FauxServeur) -> None:
        """SolidCraft déjà lancé : la sonde et la connexion atteignent le faux serveur."""
        self.fenetre.fabrique_canal = lambda: CanalSolidCraft(
            port=faux.port, jeton=JETON_DE_TEST, intervalle_pending=0.01
        )

    def connecte(self) -> bool:
        canal = self.fenetre.canal
        return canal is not None and canal.connecte


def _port_libre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def banc(qtbot: QtBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Banc]:
    monkeypatch.setenv("SOLIDCRAFT_CONTROL_DIR", str(tmp_path))
    f = FenetrePrincipale()
    qtbot.addWidget(f)
    yield Banc(f, tmp_path)
    f.annuler()
    if f.canal is not None:
        f.canal.fermer()


def _etude_avec_maquette(dossier: Path) -> tuple[Path, Path]:
    maquette = dossier / "maquettes" / "bielle_manivelle.solidcraft"
    maquette.parent.mkdir(parents=True)
    maquette.write_bytes(b"")
    etude = lire_etude(FIXTURE)
    etude.chemin_maquette = str(maquette)
    chemin = dossier / "bielle.meca3d"
    ecrire_etude(etude, chemin)
    return chemin, maquette


# --- démarrage ---------------------------------------------------------------------------------
def test_ex07_demarrage_solidcraft_absent_lance_sans_question(banc: Banc, qtbot: QtBot) -> None:
    """Révisé le 29/10 (accord de l'utilisateur) : SolidCraft démarre avec Meca3D, sans question."""
    with FauxServeur(theta="60") as faux:
        banc.fenetre.port_lancement = faux.port
        banc.fenetre.demarrer_avec_solidcraft()
        qtbot.waitUntil(banc.connecte, timeout=DELAI)
    assert banc.questions == []
    assert banc.lances == [(banc.exe, faux.port)]


def test_ex07_demarrage_solidcraft_present_connexion_sans_question(
    banc: Banc, qtbot: QtBot
) -> None:
    with FauxServeur(theta="60") as faux:
        banc.brancher(faux)
        banc.fenetre.demarrer_avec_solidcraft()
        qtbot.waitUntil(banc.connecte, timeout=DELAI)
    assert banc.questions == []
    assert banc.lances == []


# --- commande « Démarrer SolidCraft » ---------------------------------------------------------
def test_ex07_bouton_lancer_dans_le_menu_et_la_barre(banc: Banc) -> None:
    f = banc.fenetre
    menus = [a.menu() for a in f.menuBar().actions() if a.menu() is not None]  # type: ignore[union-attr]
    actions_menus = [action for menu in menus if menu for action in menu.actions()]
    assert f.action_lancer_solidcraft in actions_menus
    assert f.action_ouvrir_maquette in actions_menus
    assert f.action_emplacement_solidcraft in actions_menus
    assert f.action_lancer_solidcraft in f.barre_commandes.actions()
    assert f.action_lancer_solidcraft.isEnabled()
    assert f.action_lancer_solidcraft.text() == "Démarrer SolidCraft"  # libellé du 29/10


def test_ex07_lancer_alors_que_connecte_ne_relance_pas(banc: Banc, qtbot: QtBot) -> None:
    with FauxServeur(theta="60") as faux:
        banc.brancher(faux)
        banc.fenetre.action_connecter.trigger()
        qtbot.waitUntil(banc.connecte, timeout=DELAI)
        banc.fenetre.action_lancer_solidcraft.trigger()
        qtbot.wait(200)
    assert banc.lances == []
    assert banc.fenetre.dernier_message == textes.MSG_SOLIDCRAFT_DEJA_LANCE


def test_ex07_executable_demande_une_seule_fois_puis_memorise(banc: Banc, qtbot: QtBot) -> None:
    demandes: list[int] = []

    def dialogue() -> Path:
        demandes.append(1)
        return banc.exe

    f = banc.fenetre
    f.recherche_solidcraft = lambda: None
    f.dialogue_executable = dialogue
    with FauxServeur(theta="60") as faux:
        f.port_lancement = faux.port
        f.lancer_solidcraft()
        qtbot.waitUntil(banc.connecte, timeout=DELAI)
        assert demandes == [1]
        assert str(banc.exe) in f.memoire.valeurs.values()  # type: ignore[attr-defined]
        # nouvelle session de Meca3D, même utilisateur : plus de question
        f2 = FenetrePrincipale()
        qtbot.addWidget(f2)
        f2.memoire = f.memoire
        f2.recherche_solidcraft = lambda: None
        f2.dialogue_executable = dialogue
        f2.lanceur = banc._lanceur
        f2.port_lancement = faux.port
        f2.lancer_solidcraft()
        qtbot.waitUntil(lambda: f2.canal is not None and f2.canal.connecte, timeout=DELAI)
        f2.canal.fermer()  # type: ignore[union-attr]
    assert demandes == [1]
    assert banc.lances == [(banc.exe, faux.port), (banc.exe, faux.port)]


def test_ex07_solidcraft_ne_repond_pas_dans_le_delai(banc: Banc, qtbot: QtBot) -> None:
    f = banc.fenetre
    f.lanceur = lambda exe, port: banc.lances.append((exe, port))  # aucun jeton n'apparaît
    f.port_lancement = _port_libre()
    f.delai_lancement = 0.5
    f.lancer_solidcraft()
    qtbot.waitUntil(lambda: "répond pas" in f.dernier_message, timeout=DELAI)
    assert len(banc.lances) == 1
    assert f.canal is None
    assert f.etiquette_connexion.text() == textes.CONNEXION_ABSENTE


# --- ouverture de la maquette ------------------------------------------------------------------
def test_ex07_ouverture_etude_autre_maquette_modifiee_confirmee(
    banc: Banc, qtbot: QtBot, tmp_path: Path
) -> None:
    chemin, maquette = _etude_avec_maquette(tmp_path)
    scenario = Scenario(nom_maquette="autre", maquette_modifiee=True)
    with FauxServeur(theta="60", scenario=scenario) as faux:
        banc.brancher(faux)
        banc.fenetre.action_connecter.trigger()
        qtbot.waitUntil(banc.connecte, timeout=DELAI)
        assert banc.fenetre.ouvrir_etude(chemin)
        qtbot.waitUntil(lambda: bool(faux.ouvertures), timeout=DELAI)
    assert len(banc.questions) == 1
    question = banc.questions[0]
    assert "autre" in question and "bielle_manivelle" in question
    assert "perdu" in question
    assert faux.ouvertures == [str(maquette.resolve())]


def test_ex07_ouverture_etude_autre_maquette_refusee(
    banc: Banc, qtbot: QtBot, tmp_path: Path
) -> None:
    chemin, _ = _etude_avec_maquette(tmp_path)
    scenario = Scenario(nom_maquette="autre")
    with FauxServeur(theta="60", scenario=scenario) as faux:
        banc.brancher(faux)
        banc.fenetre.action_connecter.trigger()
        qtbot.waitUntil(banc.connecte, timeout=DELAI)
        banc.reponse = False
        assert banc.fenetre.ouvrir_etude(chemin)
        qtbot.waitUntil(lambda: len(banc.questions) == 1, timeout=DELAI)
        qtbot.wait(200)
    assert "perdu" not in banc.questions[0]  # maquette enregistrée, non modifiée
    assert faux.ouvertures == []
    assert banc.fenetre.etude is not None  # l'étude reste ouverte


def test_ex07_ouverture_etude_maquette_deja_ouverte(
    banc: Banc, qtbot: QtBot, tmp_path: Path
) -> None:
    chemin, _ = _etude_avec_maquette(tmp_path)
    with FauxServeur(theta="60", scenario=Scenario(nom_maquette="bielle_manivelle")) as faux:
        banc.brancher(faux)
        banc.fenetre.action_connecter.trigger()
        qtbot.waitUntil(banc.connecte, timeout=DELAI)
        assert banc.fenetre.ouvrir_etude(chemin)
        qtbot.waitUntil(
            lambda: banc.fenetre.dernier_message == textes.MSG_MAQUETTE_DEJA_OUVERTE,
            timeout=DELAI,
        )
    assert banc.questions == []
    assert faux.ouvertures == []


def test_ex07_ouverture_etude_lance_solidcraft_puis_ouvre_la_maquette(
    banc: Banc, qtbot: QtBot, tmp_path: Path
) -> None:
    chemin, maquette = _etude_avec_maquette(tmp_path)
    with FauxServeur(theta="60", scenario=Scenario(document_vide=True)) as faux:
        banc.fenetre.port_lancement = faux.port  # SolidCraft tout juste lancé : document vide
        assert banc.fenetre.ouvrir_etude(chemin)
        qtbot.waitUntil(lambda: bool(faux.ouvertures), timeout=DELAI)
    assert len(banc.questions) == 1  # proposition de lancement seulement
    assert banc.lances == [(banc.exe, faux.port)]
    assert faux.ouvertures == [str(maquette.resolve())]


def test_ex07_ouverture_etude_sans_maquette_trouvee_demande_le_fichier(
    banc: Banc, qtbot: QtBot, tmp_path: Path
) -> None:
    etude = lire_etude(FIXTURE)  # sans chemin ; aucune maquette à côté
    chemin = tmp_path / "etude" / "bielle.meca3d"
    chemin.parent.mkdir()
    ecrire_etude(etude, chemin)
    maquette = tmp_path / "ailleurs" / "bielle_manivelle.solidcraft"
    maquette.parent.mkdir()
    maquette.write_bytes(b"")
    demandes: list[int] = []

    def dialogue() -> Path:
        demandes.append(1)
        return maquette

    banc.fenetre.dialogue_maquette = dialogue
    with FauxServeur(theta="60", scenario=Scenario(document_vide=True)) as faux:
        banc.brancher(faux)
        banc.fenetre.action_connecter.trigger()
        qtbot.waitUntil(banc.connecte, timeout=DELAI)
        assert banc.fenetre.ouvrir_etude(chemin)
        qtbot.waitUntil(lambda: bool(faux.ouvertures), timeout=DELAI)
    assert demandes == [1]
    assert faux.ouvertures == [str(maquette.resolve())]
    assert banc.fenetre.etude is not None
    assert Path(banc.fenetre.etude.chemin_maquette) == maquette
    assert banc.fenetre.modifiee  # le chemin trouvé est à enregistrer


def test_ex07_commande_ouvrir_une_maquette(banc: Banc, qtbot: QtBot, tmp_path: Path) -> None:
    maquette = tmp_path / "pendule.solidcraft"
    maquette.write_bytes(b"")
    banc.fenetre.dialogue_maquette = lambda: maquette
    with FauxServeur(theta="60") as faux:
        banc.brancher(faux)
        banc.fenetre.action_connecter.trigger()
        qtbot.waitUntil(banc.connecte, timeout=DELAI)
        banc.fenetre.action_ouvrir_maquette.trigger()
        qtbot.waitUntil(lambda: bool(faux.ouvertures), timeout=DELAI)
    assert faux.ouvertures == [str(maquette.resolve())]


def test_ex07_import_apres_ouverture_memorise_le_chemin(
    banc: Banc, qtbot: QtBot, tmp_path: Path
) -> None:
    """Le chemin n'est connu que par `doc.open` : maquette ouverte par Meca3D puis importée."""
    maquette = tmp_path / "bielle_manivelle.solidcraft"
    maquette.write_bytes(b"")
    banc.fenetre.dialogue_maquette = lambda: maquette
    with FauxServeur(theta="60", scenario=Scenario(document_vide=True)) as faux:
        banc.brancher(faux)
        banc.fenetre.action_connecter.trigger()
        qtbot.waitUntil(banc.connecte, timeout=DELAI)
        banc.fenetre.action_ouvrir_maquette.trigger()
        qtbot.waitUntil(lambda: bool(faux.ouvertures), timeout=DELAI)
        qtbot.waitUntil(lambda: banc.fenetre.action_importer.isEnabled(), timeout=DELAI)
        banc.fenetre.action_importer.trigger()
        qtbot.waitUntil(lambda: banc.fenetre.etude is not None, timeout=DELAI)
    assert banc.questions == []  # document vide : rien à confirmer
    etude = banc.fenetre.etude
    assert etude is not None
    assert Path(etude.chemin_maquette) == maquette.resolve()
