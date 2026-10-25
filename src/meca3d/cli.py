# SPDX-License-Identifier: GPL-3.0-or-later
"""Point d'entrée en ligne de commande (EX-62, D11).

`meca3d simuler <etude.meca3d> --csv <sortie.csv>` : simulation dynamique sans interface.
Le garde-fou h > 0 (code 2) arrive au lot 4.
"""

import argparse
import sys
from pathlib import Path

from meca3d import __version__

CODE_ERREUR = 1


def construire_analyseur() -> argparse.ArgumentParser:
    analyseur = argparse.ArgumentParser(prog="meca3d", description="Meca3D")
    analyseur.add_argument("--version", action="version", version=f"meca3d {__version__}")
    sous = analyseur.add_subparsers(dest="commande")
    simuler = sous.add_parser("simuler", help="simuler une étude sans interface (EX-62)")
    simuler.add_argument("etude", type=Path, help="fichier d'étude .meca3d")
    simuler.add_argument("--csv", type=Path, required=True, help="fichier CSV de sortie")
    return analyseur


def _simuler(etude_chemin: Path, csv_chemin: Path) -> int:
    # Imports tardifs : exudyn n'est chargé que pour simuler
    from meca3d.modele.etude import ErreurEtude, lire_etude
    from meca3d.moteur.base import ErreurMoteur
    from meca3d.moteur.exudyn_dyn import MoteurExudynDyn
    from meca3d.resultats.export import colonnes_resultats, ecrire_csv

    try:
        etude = lire_etude(etude_chemin)
        resultats = MoteurExudynDyn().simuler(etude)
        ecrire_csv(csv_chemin, colonnes_resultats(etude, resultats))
    except (ErreurEtude, ErreurMoteur, OSError) as e:
        print(f"Erreur : {e}", file=sys.stderr)
        return CODE_ERREUR
    return 0


def main(argv: list[str] | None = None) -> int:
    args = construire_analyseur().parse_args(argv)
    if args.commande == "simuler":
        return _simuler(args.etude, args.csv)
    return 0


if __name__ == "__main__":
    sys.exit(main())
