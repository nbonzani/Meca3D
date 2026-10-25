# SPDX-License-Identifier: GPL-3.0-or-later
"""`meca3d simuler` : garde-fou EX-22 (h > 0 → code 2), mode cinématique (EX-41, EX-23), EX-62."""

import math
from pathlib import Path

import pytest
from outils_cinematique import etude_bielle_60

from meca3d import cli
from meca3d.modele.etude import Etude, ecrire_etude


def _ecrire(etude: Etude, dossier: Path) -> Path:
    chemin = dossier / "etude.meca3d"
    ecrire_etude(etude, chemin)
    return chemin


def test_ex62_hyperstatique_code_2_et_message(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    chemin = _ecrire(etude_bielle_60("rotule"), tmp_path)  # h = 1
    sortie = tmp_path / "x.csv"
    code = cli.main(["simuler", str(chemin), "--csv", str(sortie)])
    assert code == 2
    erreur = capsys.readouterr().err
    assert "h = 1" in erreur
    assert "L23_rotule" in erreur
    assert not sortie.exists()


def test_ex62_hyperstatique_mode_cinematique_sans_option_code_2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    chemin = _ecrire(etude_bielle_60("pivot"), tmp_path)  # h = 3
    sortie = tmp_path / "x.csv"
    code = cli.main(["simuler", str(chemin), "--csv", str(sortie), "--mode", "cinematique"])
    assert code == 2
    assert "h = 3" in capsys.readouterr().err
    assert not sortie.exists()


def test_ex23_option_cochee_mode_dynamique_code_2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    etude = etude_bielle_60("pivot")
    etude.hyperstatique_autorise = True
    chemin = _ecrire(etude, tmp_path)
    code = cli.main(["simuler", str(chemin), "--csv", str(tmp_path / "x.csv")])
    assert code == 2
    assert "indéterminé" in capsys.readouterr().err


def test_ex23_option_cochee_mode_cinematique_code_0(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    etude = etude_bielle_60("pivot")
    etude.hyperstatique_autorise = True
    chemin = _ecrire(etude, tmp_path)
    sortie = tmp_path / "x.csv"
    code = cli.main(["simuler", str(chemin), "--csv", str(sortie), "--mode", "cinematique"])
    assert code == 0
    assert "libéré" in capsys.readouterr().err  # les ddl libérés sont signalés à l'élève
    lignes = sortie.read_text(encoding="utf-8-sig").splitlines()
    assert len(lignes) - 1 == 501
    entete = lignes[0].split(";")
    assert entete[0] == "t (s)"
    assert "Piston x (m)" in entete
    assert not any("(N)" in nom or "(N·m)" in nom for nom in entete)  # aucun effort


def test_ex62_mode_cinematique_isostatique_x_b_du_csv(tmp_path: Path) -> None:
    chemin = _ecrire(etude_bielle_60(), tmp_path)
    sortie = tmp_path / "x.csv"
    assert cli.main(["simuler", str(chemin), "--csv", str(sortie), "--mode", "cinematique"]) == 0
    lignes = sortie.read_text(encoding="utf-8-sig").splitlines()
    entete = lignes[0].split(";")
    derniere = lignes[-1].split(";")
    t = float(derniere[entete.index("t (s)")].replace(",", "."))
    x = float(derniere[entete.index("Piston x (m)")].replace(",", "."))
    # formule analytique de la SPEC (EX-41) : x_B = r cos θ + √(L² − r² sin² θ), θ = 60° + 20 t
    theta = math.radians(60.0) + 20.0 * t
    attendu = 0.1 * math.cos(theta) + math.sqrt(0.3**2 - (0.1 * math.sin(theta)) ** 2)
    assert abs(x - attendu) < 1e-6


def test_ex22_dynamique_sans_loi_avertit_et_continue(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    etude = etude_bielle_60(pilote=False, duree=0.05)
    chemin = _ecrire(etude, tmp_path)
    sortie = tmp_path / "x.csv"
    assert cli.main(["simuler", str(chemin), "--csv", str(sortie)]) == 0
    assert "loi" in capsys.readouterr().err
    assert sortie.exists()


def test_ex62_etude_liaison_non_validee_code_1(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    etude = etude_bielle_60()
    etude.liaison("L12_pivot").choisir(etude.liaison("L12_pivot").type)  # type: ignore[arg-type]
    chemin = _ecrire(etude, tmp_path)
    code = cli.main(["simuler", str(chemin), "--csv", str(tmp_path / "x.csv")])
    assert code == 1
    assert "L12_pivot" in capsys.readouterr().err
