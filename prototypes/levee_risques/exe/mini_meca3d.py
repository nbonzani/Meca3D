"""Mini programme de test de l'exécutable : fenêtre PyQt6 + calcul Exudyn en processus spawn.

    python mini_meca3d.py --sortie resultat.json --sans-fenetre
    mini_meca3d.exe --sortie resultat.json --sans-fenetre
    mini_meca3d.exe --sortie resultat.json --fermer-apres 1500     (vraie fenêtre, fermée seule)
"""

from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import os
import sys
import time
from pathlib import Path


def calculer() -> dict:
    """Lance le calcul dans un processus séparé (démarrage spawn) et attend le résultat."""
    from calcul_exudyn import fils

    ctx = mp.get_context("spawn")
    file_attente = ctx.Queue()
    p = ctx.Process(target=fils, args=(file_attente,))
    t0 = time.perf_counter()
    p.start()
    res = file_attente.get(timeout=120)
    p.join(timeout=30)
    res["duree_totale_processus_s"] = time.perf_counter() - t0
    res["code_sortie_fils"] = p.exitcode
    res["pid_parent"] = os.getpid()
    return res


def fenetre(texte: str, sans_fenetre: bool, fermer_apres_ms: int) -> dict:
    from PyQt6.QtCore import QTimer
    from PyQt6.QtWidgets import QApplication, QLabel, QMainWindow

    if sans_fenetre:
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
    app = QApplication(sys.argv[:1])
    win = QMainWindow()
    win.setWindowTitle("Mini Meca3D")
    win.setCentralWidget(QLabel(texte))
    info = {"plateforme_qt": app.platformName(), "fenetre_affichee": False}
    if not sans_fenetre:
        win.show()
        info["fenetre_affichee"] = win.isVisible()
        QTimer.singleShot(fermer_apres_ms, app.quit)
        app.exec()
    return info


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sortie", type=Path, required=True)
    ap.add_argument("--sans-fenetre", action="store_true", help="Qt hors écran, aucune fenêtre")
    ap.add_argument("--fermer-apres", type=int, default=1500, help="ms avant fermeture auto")
    args = ap.parse_args()
    res = calculer()
    res["mode"] = "exe" if getattr(sys, "frozen", False) else "source"
    res["python"] = sys.version.split()[0]
    res["methode_demarrage"] = mp.get_start_method(allow_none=True)
    texte = f"theta(1 s) = {res['theta_fin_rad']:.12f} rad" if res.get("ok") else str(res)
    res.update(fenetre(texte, args.sans_fenetre, args.fermer_apres))
    args.sortie.parent.mkdir(parents=True, exist_ok=True)
    args.sortie.write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")
    print(texte)
    return 0 if res.get("ok") else 1


if __name__ == "__main__":
    mp.freeze_support()
    sys.exit(main())
