# SPDX-License-Identifier: GPL-3.0-or-later
"""Point d'entrée de l'exécutable `meca3d.exe` (sans console).

`freeze_support` est indispensable : le processus de calcul est la même exécutable relancée avec
les arguments de `multiprocessing` (mode spawn, D9). `lanceur_console.py` est identique et sert
`meca3d-cli.exe` (PyInstaller exige deux scripts distincts pour partager les bibliothèques).
"""

import multiprocessing
import sys

if __name__ == "__main__":
    multiprocessing.freeze_support()
    from meca3d.__main__ import principal

    sys.exit(principal())
