# SPDX-License-Identifier: GPL-3.0-or-later
"""EX-64 : en-tête SPDX dans chaque module de src/, licences des dépendances d'exécution
compatibles GPL v3, documentées dans docs/LICENCES.md."""

from pathlib import Path

from outils_licences import dependances_execution, est_compatible_gpl3, licences_dependances

RACINE = Path(__file__).resolve().parent.parent
SPDX = "# SPDX-License-Identifier: GPL-3.0-or-later"


def test_ex64_en_tete_spdx_dans_chaque_module() -> None:
    modules = sorted((RACINE / "src").rglob("*.py"))
    assert len(modules) > 30
    sans = [
        str(m.relative_to(RACINE))
        for m in modules
        if not m.read_text(encoding="utf-8").startswith(SPDX)
    ]
    assert sans == []


def test_ex64_fichier_licence_gpl3() -> None:
    texte = (RACINE / "LICENSE").read_text(encoding="utf-8")
    assert "GNU GENERAL PUBLIC LICENSE" in texte
    assert "Version 3, 29 June 2007" in texte
    assert 'license = "GPL-3.0-or-later"' in (RACINE / "pyproject.toml").read_text(encoding="utf-8")


def test_ex64_dependances_directes_presentes() -> None:
    noms = dependances_execution()
    for attendu in ("exudyn", "numpy", "networkx", "sympy", "pyqt6", "matplotlib"):
        assert attendu in noms


def test_ex64_licences_des_dependances_compatibles_gpl3() -> None:
    incompatibles = [(d.nom, d.licence) for d in licences_dependances() if not est_compatible_gpl3(d)]
    assert incompatibles == []


def test_ex64_licences_documentees() -> None:
    texte = (RACINE / "docs" / "LICENCES.md").read_text(encoding="utf-8")
    for d in licences_dependances():
        assert d.nom in texte.lower(), d.nom
