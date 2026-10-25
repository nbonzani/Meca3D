# SPDX-License-Identifier: GPL-3.0-or-later
"""Ligne de commande `meca3d simuler`, export CSV (EX-62, EX-52) et fichier d'étude (EX-60)."""

from pathlib import Path

import pytest
import reference_bielle as ref

from meca3d import cli
from meca3d.modele.etude import ErreurEtude, ecrire_etude, lire_etude

ETUDE = Path(__file__).parent / "fixtures" / "bielle" / "bielle.meca3d"


@pytest.fixture(scope="module")
def csv_bielle(tmp_path_factory: pytest.TempPathFactory) -> Path:
    sortie = tmp_path_factory.mktemp("cli") / "bielle.csv"
    assert cli.main(["simuler", str(ETUDE), "--csv", str(sortie)]) == 0
    return sortie


def test_ex62_code_zero_et_501_lignes(csv_bielle: Path) -> None:
    texte = csv_bielle.read_text(encoding="utf-8-sig")
    lignes = texte.splitlines()
    assert len(lignes) - 1 == 501


def test_ex52_format_excel_francais(csv_bielle: Path) -> None:
    brut = csv_bielle.read_bytes()
    assert brut.startswith(b"\xef\xbb\xbf")
    lignes = brut.decode("utf-8-sig").splitlines()
    en_tete = lignes[0].split(";")
    assert en_tete[0] == "t (s)"
    assert "C (N·m)" in en_tete
    premiere = lignes[1].split(";")
    assert len(premiere) == len(en_tete)
    assert "." not in lignes[1]
    assert premiere[0] == "0,0"


def test_ex52_couple_du_csv_conforme_a_la_reference(csv_bielle: Path) -> None:
    lignes = csv_bielle.read_text(encoding="utf-8-sig").splitlines()
    en_tete = lignes[0].split(";")
    i_t, i_c = en_tete.index("t (s)"), en_tete.index("C (N·m)")
    lignes_donnees = [ligne.split(";") for ligne in lignes[1:]]
    t = [float(ligne[i_t].replace(",", ".")) for ligne in lignes_donnees]
    c = [float(ligne[i_c].replace(",", ".")) for ligne in lignes_donnees]
    c_ref = [float(ref.reference(x)["C"]) for x in t]  # type: ignore[arg-type]
    pic = max(abs(x) for x in c_ref)
    assert max(abs(a - b) for a, b in zip(c, c_ref, strict=True)) / pic <= 5e-3


def test_ex60_aller_retour_identique(tmp_path: Path) -> None:
    copie = tmp_path / "copie.meca3d"
    etude = lire_etude(ETUDE)
    ecrire_etude(etude, copie)
    assert copie.read_bytes() == ETUDE.read_bytes()
    assert lire_etude(copie).vers_dict() == etude.vers_dict()


def test_ex60_resultats_identiques_apres_reouverture(csv_bielle: Path, tmp_path: Path) -> None:
    copie = tmp_path / "copie.meca3d"
    ecrire_etude(lire_etude(ETUDE), copie)
    sortie = tmp_path / "copie.csv"
    assert cli.main(["simuler", str(copie), "--csv", str(sortie)]) == 0
    assert sortie.read_bytes() == csv_bielle.read_bytes()


def test_ex60_fichier_corrompu(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    mauvais = tmp_path / "mauvais.meca3d"
    mauvais.write_text('{"version_etude": 1, "solides": [', encoding="utf-8")
    with pytest.raises(ErreurEtude):
        lire_etude(mauvais)
    sortie = tmp_path / "x.csv"
    code = cli.main(["simuler", str(mauvais), "--csv", str(sortie)])
    assert code != 0
    assert not sortie.exists()
    assert capsys.readouterr().err.strip() != ""


def test_ex60_version_inconnue(tmp_path: Path) -> None:
    fichier = tmp_path / "v.meca3d"
    fichier.write_text('{"version_etude": 99}', encoding="utf-8")
    with pytest.raises(ErreurEtude, match="version"):
        lire_etude(fichier)


def test_ex62_etude_absente(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code = cli.main(["simuler", str(tmp_path / "absente.meca3d"), "--csv", str(tmp_path / "x.csv")])
    assert code != 0
    assert capsys.readouterr().err.strip() != ""
