# SPDX-License-Identifier: GPL-3.0-or-later
"""Études et maquettes récentes (EX-65, lot 16).

Frontières simulées comme dans `test_ihm_lancement.py` : mémoire des réglages, canal (faux
serveur), dialogues. Les entrées des menus sont déclenchées comme un clic de l'élève.
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from collections.abc import Iterator  # noqa: E402
from pathlib import Path  # noqa: E402

import pytest  # noqa: E402
from faux_serveur import JETON_DE_TEST, FauxServeur  # noqa: E402
from meca3d.ihm.recents import MAXIMUM_RECENTS, ajouter_recent, retirer_recent  # noqa: E402
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


def _fenetre(qtbot: QtBot, memoire: Memoire) -> FenetrePrincipale:
    f = FenetrePrincipale()
    qtbot.addWidget(f)
    f.memoire = memoire
    f.confirmer = lambda titre, texte: True
    f.actualiser_recents()
    return f


@pytest.fixture
def memoire() -> Memoire:
    return Memoire()


@pytest.fixture
def fenetre(qtbot: QtBot, memoire: Memoire) -> Iterator[FenetrePrincipale]:
    f = _fenetre(qtbot, memoire)
    yield f
    f.annuler()
    if f.canal is not None:
        f.canal.fermer()


def _etudes(dossier: Path, nombre: int) -> list[Path]:
    etude = lire_etude(FIXTURE)
    chemins = []
    for rang in range(nombre):
        chemin = dossier / f"etude_{rang:02d}.meca3d"
        ecrire_etude(etude, chemin)
        chemins.append(chemin)
    return chemins


def _entrees(fenetre: FenetrePrincipale, maquettes: bool = False) -> list[str]:
    menu = fenetre.menu_maquettes_recentes if maquettes else fenetre.menu_etudes_recentes
    return [a.text() for a in menu.actions() if a.isEnabled()]


def _choisir(fenetre: FenetrePrincipale, chemin: Path, maquettes: bool = False) -> None:
    menu = fenetre.menu_maquettes_recentes if maquettes else fenetre.menu_etudes_recentes
    action = next(a for a in menu.actions() if a.data() == str(chemin))
    action.trigger()


# --- liste pure --------------------------------------------------------------------------------
def test_ex65_ajout_en_tete_sans_doublon_et_limite() -> None:
    liste: list[str] = []
    for rang in range(12):
        liste = ajouter_recent(liste, Path(f"C:/e/{rang}.meca3d"))
    assert MAXIMUM_RECENTS == 10
    assert len(liste) == 10
    assert Path(liste[0]) == Path("C:/e/11.meca3d")
    liste = ajouter_recent(liste, Path("C:/E/9.MECA3D"))  # même fichier, autre casse
    assert len(liste) == 10
    assert Path(liste[0]) == Path("C:/E/9.MECA3D")
    assert sum(Path(c).stem.casefold() == "9" for c in liste) == 1


def test_ex65_retrait() -> None:
    liste = [str(Path("C:/a.meca3d")), str(Path("C:/b.meca3d"))]
    assert retirer_recent(liste, Path("c:/A.meca3d")) == [str(Path("C:/b.meca3d"))]


# --- études récentes -------------------------------------------------------------------------
def test_ex65_menus_presents_et_vides(fenetre: FenetrePrincipale) -> None:
    assert fenetre.menu_etudes_recentes.title() == textes.MENU_ETUDES_RECENTES
    assert fenetre.menu_maquettes_recentes.title() == textes.MENU_MAQUETTES_RECENTES
    for menu in (fenetre.menu_etudes_recentes, fenetre.menu_maquettes_recentes):
        actions = menu.actions()
        assert len(actions) == 1
        assert actions[0].text() == textes.AUCUN_FICHIER_RECENT
        assert not actions[0].isEnabled()


def test_ex65_douze_etudes_ouvertes_dix_entrees_la_derniere_en_tete(
    fenetre: FenetrePrincipale, tmp_path: Path
) -> None:
    chemins = _etudes(tmp_path, 12)
    for chemin in chemins:
        assert fenetre.ouvrir_etude(chemin)
    recents = fenetre.etudes_recentes()
    assert len(recents) == 10
    assert recents[0] == chemins[11]
    assert len(_entrees(fenetre)) == 10
    troisieme = recents[2]
    assert fenetre.ouvrir_etude(troisieme)
    recents = fenetre.etudes_recentes()
    assert recents[0] == troisieme
    assert len(recents) == len(set(recents)) == 10


def test_ex65_etude_enregistree_entre_dans_la_liste(
    fenetre: FenetrePrincipale, tmp_path: Path
) -> None:
    (source,) = _etudes(tmp_path, 1)
    assert fenetre.ouvrir_etude(source)
    copie = tmp_path / "copie.meca3d"
    assert fenetre.enregistrer_sous(copie)
    assert fenetre.etudes_recentes()[:2] == [copie, source]


def test_ex65_choisir_une_etude_recente_l_ouvre(fenetre: FenetrePrincipale, tmp_path: Path) -> None:
    premiere, seconde = _etudes(tmp_path, 2)
    assert fenetre.ouvrir_etude(premiere)
    assert fenetre.ouvrir_etude(seconde)
    _choisir(fenetre, premiere)
    assert fenetre.chemin_etude == premiere
    assert fenetre.etudes_recentes()[0] == premiere


def test_ex65_etude_recente_supprimee_message_et_retrait(
    fenetre: FenetrePrincipale, tmp_path: Path
) -> None:
    premiere, seconde = _etudes(tmp_path, 2)
    assert fenetre.ouvrir_etude(premiere)
    assert fenetre.ouvrir_etude(seconde)
    premiere.unlink()
    _choisir(fenetre, premiere)
    assert fenetre.chemin_etude == seconde  # l'étude courante reste ouverte
    assert premiere.name in fenetre.dernier_message
    assert fenetre.etudes_recentes() == [seconde]
    assert str(premiere) not in [a.data() for a in fenetre.menu_etudes_recentes.actions()]


def test_ex65_liste_conservee_apres_fermeture(
    qtbot: QtBot, memoire: Memoire, tmp_path: Path
) -> None:
    chemins = _etudes(tmp_path, 3)
    premiere = _fenetre(qtbot, memoire)
    for chemin in chemins:
        assert premiere.ouvrir_etude(chemin)
    premiere.close()
    seconde = _fenetre(qtbot, memoire)
    assert seconde.etudes_recentes() == list(reversed(chemins))
    assert len(_entrees(seconde)) == 3


# --- maquettes récentes ----------------------------------------------------------------------
def _brancher(fenetre: FenetrePrincipale, faux: FauxServeur, qtbot: QtBot) -> None:
    fenetre.fabrique_canal = lambda: CanalSolidCraft(
        port=faux.port, jeton=JETON_DE_TEST, intervalle_pending=0.01
    )
    fenetre.action_connecter.trigger()
    qtbot.waitUntil(lambda: fenetre.canal is not None and fenetre.canal.connecte, timeout=DELAI)


def test_ex65_maquette_ouverte_entre_dans_la_liste_puis_se_rouvre(
    fenetre: FenetrePrincipale, qtbot: QtBot, tmp_path: Path
) -> None:
    pendule = tmp_path / "pendule.solidcraft"
    bielle = tmp_path / "bielle_manivelle.solidcraft"
    for maquette in (pendule, bielle):
        maquette.write_bytes(b"")
    with FauxServeur(theta="60") as faux:
        _brancher(fenetre, faux, qtbot)
        for maquette in (pendule, bielle):
            fenetre.ouvrir_maquette(maquette)
            qtbot.waitUntil(
                lambda m=maquette: faux.ouvertures[-1:] == [str(m.resolve())], timeout=DELAI
            )
        qtbot.waitUntil(lambda: len(fenetre.maquettes_recentes()) == 2, timeout=DELAI)
        assert fenetre.maquettes_recentes() == [bielle.resolve(), pendule.resolve()]
        assert len(_entrees(fenetre, maquettes=True)) == 2
        _choisir(fenetre, pendule.resolve(), maquettes=True)
        qtbot.waitUntil(lambda: len(faux.ouvertures) == 3, timeout=DELAI)
    assert faux.ouvertures[-1] == str(pendule.resolve())


def test_ex65_maquette_recente_supprimee_message_et_retrait(
    fenetre: FenetrePrincipale, memoire: Memoire, tmp_path: Path
) -> None:
    absente = tmp_path / "disparue.solidcraft"
    memoire.ecrire("recents/maquettes", str(absente))
    fenetre.actualiser_recents()
    assert fenetre.maquettes_recentes() == [absente]
    _choisir(fenetre, absente, maquettes=True)
    assert absente.name in fenetre.dernier_message
    assert fenetre.maquettes_recentes() == []
