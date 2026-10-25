# SPDX-License-Identifier: GPL-3.0-or-later
"""Point d'entrée en ligne de commande (EX-62). Les sous-commandes arrivent au lot 2."""

import argparse
import sys

from meca3d import __version__


def construire_analyseur() -> argparse.ArgumentParser:
    analyseur = argparse.ArgumentParser(prog="meca3d", description="Meca3D")
    analyseur.add_argument("--version", action="version", version=f"meca3d {__version__}")
    return analyseur


def main(argv: list[str] | None = None) -> int:
    construire_analyseur().parse_args(argv)
    return 0


if __name__ == "__main__":
    sys.exit(main())
