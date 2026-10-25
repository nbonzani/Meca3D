# SPDX-License-Identifier: GPL-3.0-or-later
"""Test de fumée du lot 0 : le paquet et ses dépendances s'importent."""

import importlib

import pytest

from meca3d import __version__, cli


def test_version() -> None:
    assert __version__ == "0.1.0"


def test_cli_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as sortie:
        cli.main(["--version"])
    assert sortie.value.code == 0
    assert "meca3d 0.1.0" in capsys.readouterr().out


DEPENDANCES = ["exudyn", "numpy", "networkx", "sympy", "PyQt6.QtWidgets", "matplotlib"]


@pytest.mark.parametrize("module", DEPENDANCES)
def test_dependances_importables(module: str) -> None:
    importlib.import_module(module)


def test_exudyn_version_figee() -> None:
    import exudyn

    assert exudyn.__version__ == "1.13.6"
