# SPDX-License-Identifier: GPL-3.0-or-later
"""Export CSV au format Excel français et statistiques (EX-52)."""

from pathlib import Path

import numpy as np
import pytest

from meca3d import cli
from meca3d.resultats.export import ecrire_csv, statistiques

FIXTURE = Path(__file__).parent / "fixtures" / "bielle" / "bielle.meca3d"


def test_ex52_format_excel_francais_sur_colonnes_synthetiques(tmp_path: Path) -> None:
    chemin = tmp_path / "s.csv"
    ecrire_csv(chemin, {"t (s)": np.array([0.0, 0.5]), "C (N·m)": np.array([1.5, -2.25])})
    brut = chemin.read_bytes()
    assert brut.startswith(b"\xef\xbb\xbf")
    lignes = brut.decode("utf-8-sig").splitlines()
    assert lignes == ["t (s);C (N·m)", "0,0;1,5", "0,5;-2,25"]


def test_ex52_statistiques_min_max_moyenne() -> None:
    s = statistiques(np.array([1.0, 2.0, 3.0, 6.0]))
    assert s.minimum == pytest.approx(1.0, abs=1e-15)
    assert s.maximum == pytest.approx(6.0, abs=1e-15)
    assert s.moyenne == pytest.approx(3.0, abs=1e-15)


def test_ex52_csv_de_la_bielle_501_lignes_en_francais(tmp_path: Path) -> None:
    sortie = tmp_path / "bielle.csv"
    assert cli.main(["simuler", str(FIXTURE), "--csv", str(sortie)]) == 0
    brut = sortie.read_bytes()
    assert brut.startswith(b"\xef\xbb\xbf")
    lignes = brut.decode("utf-8-sig").splitlines()
    entetes = lignes[0].split(";")
    assert entetes[0] == "t (s)"
    assert "C (N·m)" in entetes
    assert all("(" in e and e.endswith(")") for e in entetes)
    donnees = lignes[1:]
    assert len(donnees) == 501
    for ligne in donnees:
        champs = ligne.split(";")
        assert len(champs) == len(entetes)
        assert "." not in ligne
    t = [float(ligne.split(";")[0].replace(",", ".")) for ligne in donnees]
    assert t[0] == pytest.approx(0.0, abs=1e-12)
    assert t[-1] == pytest.approx(1.0, abs=1e-12)
