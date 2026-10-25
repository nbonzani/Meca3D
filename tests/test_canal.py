# SPDX-License-Identifier: GPL-3.0-or-later
"""Client du canal de contrôle SolidCraft contre le faux serveur (EX-01, EX-02)."""

import socket
import time
from pathlib import Path
from typing import Any

import pytest
from faux_serveur import JETON_DE_TEST, FauxServeur, Scenario

from meca3d.cao.canal import (
    CanalSolidCraft,
    ConnexionPerdue,
    DelaiDepasse,
    ErreurCanal,
    JetonRefuse,
    Occupe,
    SolidCraftAbsent,
)


def _canal(faux: FauxServeur, **options: Any) -> CanalSolidCraft:
    return CanalSolidCraft(port=faux.port, jeton=JETON_DE_TEST, **options)


def _port_libre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.mark.perf
def test_ex01_connexion_et_document_inspect_sous_une_seconde() -> None:
    with FauxServeur() as faux:
        debut = time.monotonic()
        canal = _canal(faux)
        canal.connecter()
        inspection = canal.requete("document.inspect")
        duree = time.monotonic() - debut
        assert canal.connecte
        assert inspection["revision"] == 47
        assert duree < 1.0
        canal.fermer()
        assert not canal.connecte


def test_ex01_le_jeton_est_porte_par_la_premiere_requete_seulement() -> None:
    with FauxServeur() as faux:
        canal = _canal(faux)
        canal.requete("document.inspect")
        canal.requete("document.inspect")
        canal.fermer()
        assert [r.get("token") for r in faux.requetes] == [JETON_DE_TEST, None]


def test_ex01_executer_enveloppe_engine_execute() -> None:
    with FauxServeur() as faux:
        canal = _canal(faux)
        resultat = canal.executer("joint.list")
        assert len(resultat["joints"]) == 4
        requete = next(r for r in faux.requetes if r["method"] == "engine.execute")
        assert requete["params"] == {"command": "joint.list", "params": {}}
        assert isinstance(requete["id"], int)


def test_ex01_port_et_jeton_decouverts_dans_le_dossier_de_controle(tmp_path: Path) -> None:
    with FauxServeur() as faux:
        (tmp_path / "current.port").write_text(f"{faux.port}\n", encoding="utf-8")
        (tmp_path / f"{faux.port}.token").write_text(f"{JETON_DE_TEST}\n", encoding="utf-8")
        canal = CanalSolidCraft(dossier_controle=tmp_path)
        assert canal.port == faux.port
        assert canal.requete("document.inspect")["revision"] == 47


def test_ex01_port_par_defaut_sans_fichier(tmp_path: Path) -> None:
    assert CanalSolidCraft(dossier_controle=tmp_path).port == 27878


def test_ex01_dossier_de_controle_par_variable_denvironnement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "current.port").write_text("31999", encoding="utf-8")
    monkeypatch.setenv("SOLIDCRAFT_CONTROL_DIR", str(tmp_path))
    assert CanalSolidCraft().port == 31999


@pytest.mark.perf
def test_ex01_solidcraft_absent_message_en_moins_de_trois_secondes() -> None:
    port = _port_libre()
    canal = CanalSolidCraft(port=port, jeton=JETON_DE_TEST)
    debut = time.monotonic()
    with pytest.raises(SolidCraftAbsent) as erreur:
        canal.connecter()
    assert time.monotonic() - debut < 3.0
    assert str(erreur.value) == (
        f"SolidCraft n'est pas lancé ou n'accepte pas les connexions (port {port})"
    )
    assert not canal.connecte


def test_ex02_jeton_refuse_message_et_etat_deconnecte() -> None:
    with FauxServeur() as faux:
        canal = CanalSolidCraft(port=faux.port, jeton="mauvais-jeton")
        with pytest.raises(JetonRefuse, match="jeton refusé") as erreur:
            canal.requete("document.inspect")
        assert isinstance(erreur.value, ErreurCanal)
        assert not canal.connecte


def test_ex02_jeton_introuvable_est_un_jeton_refuse(tmp_path: Path) -> None:
    with FauxServeur() as faux:
        canal = CanalSolidCraft(port=faux.port, dossier_controle=tmp_path)
        with pytest.raises(JetonRefuse, match="jeton"):
            canal.connecter()
        assert not canal.connecte


def test_ex02_busy_est_traduit_et_la_connexion_reste_utilisable() -> None:
    with FauxServeur(scenario=Scenario(occupe_sur="joint.list")) as faux:
        canal = _canal(faux)
        with pytest.raises(Occupe, match="occup"):
            canal.executer("joint.list")
        assert canal.connecte
        assert canal.requete("document.inspect")["revision"] == 47


def test_ex02_timeout_relu_par_control_pending_sans_renvoyer_la_requete() -> None:
    scenario = Scenario(timeout_sur="joint.list", pending_attentes=2)
    with FauxServeur(scenario=scenario) as faux:
        canal = _canal(faux, intervalle_pending=0.01)
        resultat = canal.executer("joint.list")
        assert len(resultat["joints"]) == 4
        assert faux.methodes_recues().count("joint.list") == 1
        assert faux.methodes_recues().count("control.pending") == 3
        # la connexion reste utilisable après la relecture
        assert canal.requete("document.inspect")["revision"] == 47


def test_ex02_timeout_jamais_termine_leve_delai_depasse() -> None:
    scenario = Scenario(timeout_sur="joint.list", pending_attentes=10**9)
    with FauxServeur(scenario=scenario) as faux:
        canal = _canal(faux, intervalle_pending=0.01, attente_pending_max=0.3)
        with pytest.raises(DelaiDepasse, match="joint.list"):
            canal.executer("joint.list")
        assert faux.methodes_recues().count("joint.list") == 1


def test_ex02_coupure_de_connexion_message_et_etat_deconnecte() -> None:
    with FauxServeur(scenario=Scenario(coupure_sur="joint.list")) as faux:
        canal = _canal(faux)
        with pytest.raises(ConnexionPerdue, match="perdue"):
            canal.executer("joint.list")
        assert not canal.connecte


def test_ex02_reconnexion_apres_coupure() -> None:
    with FauxServeur(scenario=Scenario(coupure_sur="joint.list")) as faux:
        canal = _canal(faux)
        with pytest.raises(ConnexionPerdue):
            canal.executer("joint.list")
        faux.scenario.coupure_sur = None
        assert canal.requete("document.inspect")["revision"] == 47
        assert canal.connecte
        assert faux.connexions == 2
