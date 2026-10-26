# SPDX-License-Identifier: GPL-3.0-or-later
"""EX-63 : l'exécutable PyInstaller (dossier `dist/meca3d` ou `MECA3D_EXE_DIR`) simule comme le
mode source et son interface démarre puis se ferme proprement. Sautés si l'exécutable n'existe
pas. Construction : `uv run pyinstaller meca3d.spec --noconfirm`."""

import csv
import os
import subprocess
from pathlib import Path

import pytest

from meca3d import cli

pytestmark = pytest.mark.slow

RACINE = Path(__file__).resolve().parent.parent
DOSSIER_EXE = Path(os.environ.get("MECA3D_EXE_DIR") or RACINE / "dist" / "meca3d")
EXE_IHM = DOSSIER_EXE / "meca3d.exe"
EXE_CONSOLE = DOSSIER_EXE / "meca3d-cli.exe"
ETUDE = RACINE / "tests" / "fixtures" / "bielle" / "bielle.meca3d"
TOLERANCE = 1e-12  # SPEC EX-63 : identique, ou écart < 1e-12
DELAI_IHM = 120.0  # s

sans_exe = pytest.mark.skipif(
    not (EXE_IHM.exists() and EXE_CONSOLE.exists()),
    reason=f"exécutable non construit ({DOSSIER_EXE}) : uv run pyinstaller meca3d.spec",
)


def _lire_csv(chemin: Path) -> list[list[str]]:
    with chemin.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.reader(f, delimiter=";"))


@sans_exe
def test_ex63_exe_console_version() -> None:
    r = subprocess.run(
        [str(EXE_CONSOLE), "--version"], capture_output=True, text=True, timeout=60, check=False
    )
    assert r.returncode == 0
    assert r.stdout.startswith("meca3d ")


@sans_exe
def test_ex63_exe_simuler_identique_au_mode_source(tmp_path: Path) -> None:
    sortie_exe = tmp_path / "exe.csv"
    sortie_src = tmp_path / "source.csv"
    r = subprocess.run(
        [str(EXE_CONSOLE), "simuler", str(ETUDE), "--csv", str(sortie_exe)],
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
        cwd=tmp_path,  # lancé depuis un autre dossier courant
    )
    assert r.returncode == 0, r.stderr
    assert cli.main(["simuler", str(ETUDE), "--csv", str(sortie_src)]) == 0
    exe, src = _lire_csv(sortie_exe), _lire_csv(sortie_src)
    assert len(exe) == len(src) > 100
    assert exe[0] == src[0]  # en-têtes (unités comprises)
    pire = 0.0
    for ligne_exe, ligne_src in zip(exe[1:], src[1:], strict=True):
        assert len(ligne_exe) == len(ligne_src)
        for a, b in zip(ligne_exe, ligne_src, strict=True):
            pire = max(pire, abs(float(a.replace(",", ".")) - float(b.replace(",", "."))))
    assert pire < TOLERANCE


@sans_exe
def test_ex63_exe_ihm_demarre_et_se_ferme_hors_ecran() -> None:
    """La fenêtre s'ouvre (plateforme Qt offscreen), le processus de calcul préchauffé (spawn)
    est prêt, la fenêtre se ferme seule : code de sortie 0."""
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen", "MECA3D_AUTOTEST_DELAI_S": "90"}
    r = subprocess.run(
        [str(EXE_IHM)], capture_output=True, text=True, timeout=DELAI_IHM, check=False, env=env
    )
    assert r.returncode == 0, (r.stdout, r.stderr)
