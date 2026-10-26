# SPDX-License-Identifier: GPL-3.0-or-later
"""Point d'entrée de l'exécutable console `meca3d-cli.exe` (voir `lanceur.py`)."""

import multiprocessing
import sys

if __name__ == "__main__":
    multiprocessing.freeze_support()
    from meca3d.__main__ import principal

    sys.exit(principal())
