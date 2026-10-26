# SPDX-License-Identifier: GPL-3.0-or-later
# Construction : uv run pyinstaller meca3d.spec --noconfirm   (résultat : dist/meca3d/)
#
# Deux exécutables dans un seul dossier (mode dossier, EX-63) qui partagent les bibliothèques :
#   meca3d.exe      interface graphique, sans console
#   meca3d-cli.exe  console : `meca3d-cli simuler <etude.meca3d> --csv <sortie.csv>` (EX-62)
# Choix documenté : un exécutable sans console n'a pas de sortie standard, d'où le second
# exécutable pour la ligne de commande.
from importlib import metadata
from pathlib import Path

RACINE = Path(SPECPATH)  # noqa: F821 - fourni par PyInstaller

# Allègement validé au lot 1b (RESULTATS_1b § Q5) : 136 Mo -> 105 Mo sans effet sur la fenêtre
# ni sur le calcul ; opengl32sw (rendu logiciel OpenGL) et Qt6Pdf/Qt6Network ne sont pas utilisés.
BIBLIOTHEQUES_EXCLUES = {"opengl32sw.dll", "qt6pdf.dll", "qt6network.dll"}
MODULES_EXCLUS = ["tkinter"]  # tiré par exudyn.utilities, 8 Mo de tcl/tk inutiles


def licences():
    """Fichiers de licence des paquets embarqués (obligation de reproduire les avis, EX-64)."""
    resultat = [
        (str(RACINE / "LICENSE"), "licences"),
        (str(RACINE / "docs" / "LICENCES.md"), "licences"),
    ]
    for paquet in ("exudyn", "numpy", "matplotlib", "pyqt6", "networkx", "sympy"):
        for fichier in metadata.files(paquet) or []:
            if "licen" in fichier.name.lower() and fichier.suffix.lower() in ("", ".txt", ".md"):
                resultat.append((str(fichier.locate()), f"licences/{paquet}"))
    return resultat


def analyser(script):
    a = Analysis(  # noqa: F821
        [str(RACINE / "packaging" / script)],
        pathex=[str(RACINE / "src")],
        datas=licences(),
        # Exudyn charge son module compilé par importlib : invisible pour l'analyse (Q5)
        hiddenimports=["exudyn.exudynCPP"],
        excludes=MODULES_EXCLUS,
        noarchive=False,
    )
    a.binaries = [b for b in a.binaries if Path(b[0]).name.lower() not in BIBLIOTHEQUES_EXCLUES]
    return a


a_ihm = analyser("lanceur.py")
a_cli = analyser("lanceur_console.py")
MERGE((a_ihm, "lanceur", "meca3d"), (a_cli, "lanceur_console", "meca3d-cli"))  # noqa: F821

pyz_ihm = PYZ(a_ihm.pure)  # noqa: F821
pyz_cli = PYZ(a_cli.pure)  # noqa: F821

exe_ihm = EXE(  # noqa: F821
    pyz_ihm, a_ihm.scripts, [], exclude_binaries=True, name="meca3d", console=False
)
exe_cli = EXE(  # noqa: F821
    pyz_cli, a_cli.scripts, [], exclude_binaries=True, name="meca3d-cli", console=True
)

COLLECT(  # noqa: F821
    exe_ihm,
    a_ihm.binaries,
    a_ihm.datas,
    exe_cli,
    a_cli.binaries,
    a_cli.datas,
    strip=False,
    upx=False,
    name="meca3d",
)
