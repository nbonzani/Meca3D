# SPDX-License-Identifier: GPL-3.0-or-later
"""`python -m meca3d` : fenêtre (sans argument) ou ligne de commande (`simuler`, EX-62).

Le garde `__main__` est indispensable : le processus de calcul démarre en mode spawn et
ré-importe ce module (D9). `freeze_support` est requis par PyInstaller.
"""

import multiprocessing
import sys


def principal(argv: list[str] | None = None) -> int:
    multiprocessing.freeze_support()
    arguments = sys.argv[1:] if argv is None else argv
    if not arguments:
        from meca3d.ihm.fenetre import lancer

        return lancer()
    from meca3d.cli import main

    return main(arguments)


if __name__ == "__main__":
    sys.exit(principal())
