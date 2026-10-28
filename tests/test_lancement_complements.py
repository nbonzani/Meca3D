# SPDX-License-Identifier: GPL-3.0-or-later
"""Compléments du lot 15 (EX-07) relevés à la relecture : ouverture demandée pendant un
lancement, attente interruptible, chemin conservé au réimport."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import threading  # noqa: E402
import time  # noqa: E402
from pathlib import Path  # noqa: E402

import pytest  # noqa: E402
from faux_serveur import JETON_DE_TEST, FauxServeur, Scenario  # noqa: E402
from pytestqt.qtbot import QtBot  # noqa: E402
from test_ihm_lancement import DELAI, Banc, _etude_avec_maquette, _port_libre  # noqa: E402
from test_ihm_lancement import banc as banc  # noqa: E402, F401 - fixture réutilisée

from meca3d.cao.canal import CanalSolidCraft, SolidCraftAbsent  # noqa: E402
from meca3d.cao.lancement import attendre_solidcraft  # noqa: E402
from meca3d.cao.solidcraft import importer, reimporter  # noqa: E402


def test_ex07_ouverture_d_etude_pendant_le_lancement(
    banc: Banc, qtbot: QtBot, tmp_path: Path
) -> None:
    """L'élève ouvre son étude pendant que SolidCraft démarre : la maquette est ouverte ensuite."""
    chemin, maquette = _etude_avec_maquette(tmp_path)
    with FauxServeur(theta="60", scenario=Scenario(document_vide=True)) as faux:
        banc.fenetre.port_lancement = faux.port
        banc.fenetre.lancer_solidcraft()
        assert banc.fenetre.ouvrir_etude(chemin)
        qtbot.waitUntil(lambda: bool(faux.ouvertures), timeout=DELAI)
    assert faux.ouvertures == [str(maquette.resolve())]


def test_ex07_attente_interrompue(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Fermeture de Meca3D pendant le démarrage : l'attente cesse sans attendre le délai."""
    monkeypatch.setenv("SOLIDCRAFT_CONTROL_DIR", str(tmp_path))
    arret = threading.Event()
    threading.Timer(0.3, arret.set).start()
    debut = time.monotonic()
    with pytest.raises(SolidCraftAbsent):
        attendre_solidcraft(_port_libre(), delai=60.0, intervalle=0.05, arret=arret)
    assert time.monotonic() - debut < 3.0


def test_ex07_echec_du_lancement_explique(banc: Banc, qtbot: QtBot) -> None:
    def lanceur_en_echec(exe: Path, port: int) -> None:
        raise FileNotFoundError(2, "fichier introuvable", str(exe))

    banc.fenetre.lanceur = lanceur_en_echec
    banc.fenetre.lancer_solidcraft()
    qtbot.waitUntil(lambda: "impossible" in banc.fenetre.dernier_message, timeout=DELAI)
    assert banc.fenetre.dernier_message.startswith("Lancement de SolidCraft impossible")
    assert banc.fenetre.action_lancer_solidcraft.isEnabled()


def test_ex07_reimport_conserve_le_chemin(tmp_path: Path) -> None:
    """`document.inspect` ne donne pas le chemin : le réimport (EX-06) garde celui de l'étude."""
    maquette = tmp_path / "bielle_manivelle.solidcraft"
    with FauxServeur(theta="60") as faux:
        with CanalSolidCraft(port=faux.port, jeton=JETON_DE_TEST) as canal:
            ancienne = importer(canal)
            ancienne.chemin_maquette = str(maquette)
            nouvelle = reimporter(canal, ancienne)
    assert nouvelle.chemin_maquette == str(maquette)
