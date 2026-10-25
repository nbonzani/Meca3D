# SPDX-License-Identifier: GPL-3.0-or-later
"""Point d'entrée en ligne de commande (EX-62, D11).

`meca3d simuler <etude.meca3d> --csv <sortie.csv> [--mode dynamique|cinematique]` : simulation
sans interface. Le garde-fou EX-22 refuse (code 2) un mécanisme hyperstatique en dynamique, en
cinématique sans l'option « Hyperstatique autorisé » de l'étude, ou sans une loi par mobilité en
cinématique ; les avertissements vont sur la sortie d'erreur.
"""

import argparse
import sys
from pathlib import Path

from meca3d import __version__

CODE_ERREUR = 1
CODE_REFUS = 2  # garde-fou EX-22 (EX-62)


def construire_analyseur() -> argparse.ArgumentParser:
    analyseur = argparse.ArgumentParser(prog="meca3d", description="Meca3D")
    analyseur.add_argument("--version", action="version", version=f"meca3d {__version__}")
    sous = analyseur.add_subparsers(dest="commande")
    simuler = sous.add_parser("simuler", help="simuler une étude sans interface (EX-62)")
    simuler.add_argument("etude", type=Path, help="fichier d'étude .meca3d")
    simuler.add_argument("--csv", type=Path, required=True, help="fichier CSV de sortie")
    simuler.add_argument(
        "--mode",
        choices=("dynamique", "cinematique"),
        default="dynamique",
        help="mode de simulation (défaut : dynamique)",
    )
    return analyseur


def _simuler(etude_chemin: Path, csv_chemin: Path, mode: str = "dynamique") -> int:
    # Imports tardifs : exudyn n'est chargé que pour simuler
    from meca3d.graphe.mobilite import Mode
    from meca3d.modele.etude import ErreurEtude, lire_etude
    from meca3d.moteur.base import ErreurGardeFou, ErreurMoteur
    from meca3d.moteur.simulation import simuler_etude
    from meca3d.resultats.export import colonnes_resultats, ecrire_csv

    try:
        etude = lire_etude(etude_chemin)
        resultats = simuler_etude(
            etude, Mode.CINEMATIQUE if mode == "cinematique" else Mode.DYNAMIQUE
        )
        for message in resultats.avertissements:
            print(f"Avertissement : {message}", file=sys.stderr)
        ecrire_csv(csv_chemin, colonnes_resultats(etude, resultats))
    except ErreurGardeFou as e:
        print(f"Erreur : {e}", file=sys.stderr)
        return CODE_REFUS
    except (ErreurEtude, ErreurMoteur, OSError) as e:
        print(f"Erreur : {e}", file=sys.stderr)
        return CODE_ERREUR
    return 0


def main(argv: list[str] | None = None) -> int:
    args = construire_analyseur().parse_args(argv)
    if args.commande == "simuler":
        return _simuler(args.etude, args.csv, args.mode)
    # Sans argument : la fenêtre (le processus de calcul démarre en mode spawn : D9)
    import multiprocessing

    from meca3d.ihm import fenetre

    multiprocessing.freeze_support()
    return fenetre.lancer()


if __name__ == "__main__":
    sys.exit(main())
