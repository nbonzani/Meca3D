# SPDX-License-Identifier: GPL-3.0-or-later
"""Lancement de SolidCraft et ouverture de la maquette, couche `cao/` (EX-07, lot 15).

Frontières externes simulées : le processus SolidCraft (`subprocess.Popen` remplacé), le canal de
contrôle (faux serveur) et le dossier de contrôle (`SOLIDCRAFT_CONTROL_DIR` dans tmp_path).
"""

import socket
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

import pytest
from faux_serveur import JETON_DE_TEST, FauxServeur, Scenario

from meca3d.cao import lancement
from meca3d.cao.canal import CanalSolidCraft, JetonIntrouvable, JetonRefuse, SolidCraftAbsent
from meca3d.cao.lancement import (
    DELAI_LANCEMENT,
    PORT_LANCEMENT,
    attendre_solidcraft,
    chercher_solidcraft,
    etat_maquette,
    lancer_solidcraft,
    meme_maquette,
    ouvrir_maquette,
    sonder_solidcraft,
)
from meca3d.cao.solidcraft import importer


def _port_libre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _executable(dossier: Path) -> Path:
    dossier.mkdir(parents=True, exist_ok=True)
    exe = dossier / "solidcraft.exe"
    exe.write_bytes(b"")
    return exe


# --- recherche de l'exécutable -----------------------------------------------------------------
def test_ex07_recherche_executable_dans_un_dossier_voisin(tmp_path: Path) -> None:
    """Version portable dézippée à côté de Meca3D : <parent>/Solidcraft/<version>/solidcraft.exe."""
    application = tmp_path / "Meca3D"
    application.mkdir()
    exe = _executable(tmp_path / "Solidcraft" / "solidcraft-0.15.0-windows-x64-portable")
    assert chercher_solidcraft([application, tmp_path]) == exe


def test_ex07_recherche_executable_dans_le_dossier_de_l_application(tmp_path: Path) -> None:
    exe = _executable(tmp_path / "Meca3D")
    assert chercher_solidcraft([tmp_path / "Meca3D", tmp_path]) == exe


def test_ex07_recherche_executable_absent(tmp_path: Path) -> None:
    (tmp_path / "Meca3D" / "a" / "b" / "c").mkdir(parents=True)
    _executable(tmp_path / "Meca3D" / "a" / "b" / "c")  # trop profond (3 niveaux)
    assert chercher_solidcraft([tmp_path / "Meca3D"]) is None
    assert chercher_solidcraft([tmp_path / "inexistant"]) is None


# --- lancement ---------------------------------------------------------------------------------
def test_ex07_lancement_avec_le_canal_de_controle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    appels: list[tuple[list[str], dict[str, Any]]] = []

    def faux_popen(args: list[str], **options: Any) -> object:
        appels.append((list(args), options))
        return object()

    monkeypatch.setattr(subprocess, "Popen", faux_popen)
    exe = _executable(tmp_path / "sc")
    lancer_solidcraft(exe)
    assert PORT_LANCEMENT == 7878
    assert len(appels) == 1
    args, options = appels[0]
    assert args == [str(exe), "--control", "7878"]
    assert Path(options["cwd"]) == exe.parent


def test_ex07_delai_de_lancement() -> None:
    assert DELAI_LANCEMENT == 90.0  # s (démarrage mesuré : 22,7 s le 28/10)


def test_ex07_attente_du_canal_apres_lancement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Le jeton n'apparaît qu'après quelques dixièmes de seconde, comme au démarrage réel."""
    monkeypatch.setenv("SOLIDCRAFT_CONTROL_DIR", str(tmp_path))
    with FauxServeur(theta="60") as faux:

        def demarrage() -> None:
            time.sleep(0.4)
            (tmp_path / f"{faux.port}.token").write_text(JETON_DE_TEST, encoding="utf-8")

        threading.Thread(target=demarrage, daemon=True).start()
        canal = attendre_solidcraft(faux.port, delai=10.0, intervalle=0.05)
        try:
            assert canal.connecte
            assert canal.port == faux.port
        finally:
            canal.fermer()


def test_ex07_delai_depasse(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SOLIDCRAFT_CONTROL_DIR", str(tmp_path))
    port = _port_libre()
    debut = time.monotonic()
    with pytest.raises(SolidCraftAbsent) as erreur:
        attendre_solidcraft(port, delai=0.5, intervalle=0.05)
    assert time.monotonic() - debut < 3.0
    assert "SolidCraft" in str(erreur.value)
    assert "0,5 s" in str(erreur.value) or "0.5 s" in str(erreur.value)


def test_ex07_jeton_introuvable_est_un_jeton_refuse(tmp_path: Path) -> None:
    canal = CanalSolidCraft(port=_port_libre(), dossier_controle=tmp_path)
    with pytest.raises(JetonIntrouvable):
        canal.connecter()
    assert issubclass(JetonIntrouvable, JetonRefuse)  # EX-02 inchangée


def test_ex07_sonde_solidcraft_absent(tmp_path: Path) -> None:
    """Ni jeton ni serveur, ou jeton périmé sans serveur : SolidCraft n'est pas lancé."""
    port = _port_libre()
    assert sonder_solidcraft(lambda: CanalSolidCraft(port=port, dossier_controle=tmp_path)) is None
    (tmp_path / f"{port}.token").write_text("perime", encoding="utf-8")
    assert sonder_solidcraft(lambda: CanalSolidCraft(port=port, dossier_controle=tmp_path)) is None


def test_ex07_sonde_solidcraft_present() -> None:
    with FauxServeur(theta="60") as faux:
        canal = sonder_solidcraft(lambda: CanalSolidCraft(port=faux.port, jeton=JETON_DE_TEST))
        assert canal is not None
        try:
            assert canal.connecte
        finally:
            canal.fermer()


# --- maquette ouverte et doc.open --------------------------------------------------------------
def test_ex07_import_memorise_le_chemin_de_la_maquette(tmp_path: Path) -> None:
    maquette = tmp_path / "bielle_manivelle.solidcraft"
    with FauxServeur(theta="60", scenario=Scenario(chemin_maquette=str(maquette))) as faux:
        with CanalSolidCraft(port=faux.port, jeton=JETON_DE_TEST) as canal:
            etude = importer(canal)
    assert Path(etude.chemin_maquette) == maquette


def test_ex07_import_sans_chemin_document_sans_titre() -> None:
    with FauxServeur(theta="60") as faux:  # fixture : pas de champ `path`
        with CanalSolidCraft(port=faux.port, jeton=JETON_DE_TEST) as canal:
            etude = importer(canal)
    assert etude.chemin_maquette == ""


def test_ex07_etat_de_la_maquette_ouverte(tmp_path: Path) -> None:
    autre = tmp_path / "autre.solidcraft"
    scenario = Scenario(chemin_maquette=str(autre), maquette_modifiee=True)
    with FauxServeur(theta="60", scenario=scenario) as faux:
        with CanalSolidCraft(port=faux.port, jeton=JETON_DE_TEST) as canal:
            etat = etat_maquette(canal)
    assert etat.nom == "autre"
    assert etat.chemin == autre
    assert etat.modifiee


def test_ex07_meme_maquette(tmp_path: Path) -> None:
    maquette = tmp_path / "Bielle.solidcraft"
    etat = lancement.EtatMaquette(nom="Bielle", chemin=maquette, modifiee=False)
    assert meme_maquette(etat, maquette)
    assert meme_maquette(etat, Path(str(maquette).upper()))  # Windows : casse indifférente
    assert not meme_maquette(etat, tmp_path / "autre.solidcraft")
    sans_titre = lancement.EtatMaquette(nom="Untitled", chemin=None, modifiee=False)
    assert not meme_maquette(sans_titre, maquette)


def test_ex07_ouverture_par_doc_open(tmp_path: Path) -> None:
    maquette = tmp_path / "bielle_manivelle.solidcraft"
    maquette.write_bytes(b"")
    with FauxServeur(theta="60") as faux:
        with CanalSolidCraft(port=faux.port, jeton=JETON_DE_TEST) as canal:
            ouvrir_maquette(canal, maquette)
            etat = etat_maquette(canal)
    assert faux.ouvertures == [str(maquette.resolve())]
    assert etat.chemin == maquette.resolve()
