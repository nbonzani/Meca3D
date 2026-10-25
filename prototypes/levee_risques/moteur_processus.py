"""Lot 1a, risque 5 : calcul dans un processus séparé (D9) et annulation (EX-42).

Modèle : bielle-manivelle de prototypes/exudyn_bielle (pilotage par fonctions utilisateur Python).

Partie A : SolveDynamic long dans un processus `multiprocessing` (démarrage spawn), progression remontée par
          une file, deux annulations mesurées :
            - dure  : Process.terminate() (TerminateProcess sous Windows)
            - douce : Event partagé lu par le PostStepUserFunction, qui renvoie False (arrêt propre du solveur)
          « Retour à l'état prêt » = processus terminé (join) ; on mesure aussi le temps de démarrage d'un nouveau
          calcul (spawn + import d'exudyn) et celui d'un travailleur préchauffé.
Partie B : le même SolveDynamic dans un threading.Thread / un QThread ; latence d'un compteur dans le fil principal,
          avec et sans fonctions utilisateur Python (pour savoir si le GIL est libéré par le solveur).
"""
import multiprocessing as mp
import sys
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parent
BIELLE = RACINE.parent / "exudyn_bielle"

T_FIN_LONG = 60.0          # s simulées
N_PAS_LONG = 240000        # pas de 0,25 ms : calcul long (plusieurs dizaines de secondes réelles)


def construire_et_regler(t_fin, n_pas, avec_fonctions_utilisateur=True):
    """Construit la bielle-manivelle et ses réglages (importe exudyn)."""
    sys.path.insert(0, str(BIELLE))
    import exudyn as exu
    import bielle_manivelle as bm
    mbs, it = bm.construire()
    ss = exu.SimulationSettings()
    ss.timeIntegration.endTime = t_fin
    ss.timeIntegration.numberOfSteps = n_pas
    ss.timeIntegration.verboseMode = 0
    ss.timeIntegration.generalizedAlpha.spectralRadius = 0.9
    ss.solution.file.write = False
    ss.solution.sensors.writePeriod = 0.01
    mbs.Assemble()
    return mbs, ss


def travailleur(file_sortie, evt_annulation, t_fin, n_pas, pret_evt=None):
    """Exécuté dans le processus fils."""
    t_import = time.perf_counter()
    mbs, ss = construire_et_regler(t_fin, n_pas)
    dernier = [0.0]

    def post_pas(mbs_, t):
        now = time.perf_counter()
        if now - dernier[0] > 0.05:                  # au plus 20 messages par seconde
            dernier[0] = now
            file_sortie.put(("progression", t / t_fin))
        if evt_annulation.is_set():
            return False
        return True

    mbs.SetPostStepUserFunction(post_pas)
    if pret_evt is not None:
        pret_evt.set()
    file_sortie.put(("demarre", time.perf_counter() - t_import))
    t0 = time.perf_counter()
    ok = mbs.SolveDynamic(ss)
    file_sortie.put(("fin", dict(ok=bool(ok), duree=time.perf_counter() - t0, t_atteint=float(mbs.systemData.GetTime()))))


def lancer(ctx, t_fin=T_FIN_LONG, n_pas=N_PAS_LONG):
    q = ctx.Queue()
    ev = ctx.Event()
    p = ctx.Process(target=travailleur, args=(q, ev, t_fin, n_pas))
    t0 = time.perf_counter()
    p.start()
    return p, q, ev, t0


def partie_a():
    ctx = mp.get_context("spawn")
    print("--- Partie A : processus spawn")
    # A0 : démarrage + durée d'un calcul court (référence)
    p, q, ev, t0 = lancer(ctx, 1.0, 4000)
    msgs = []
    while True:
        m = q.get(timeout=120)
        msgs.append(m)
        if m[0] == "fin":
            break
    p.join()
    dem = [m[1] for m in msgs if m[0] == "demarre"][0]
    fin = msgs[-1][1]
    print("   calcul court (1 s simulée, 4000 pas) : construction+import dans le fils = %.2f s, SolveDynamic = %.2f s"
          % (dem, fin["duree"]))
    print("   calcul long prévu (%d pas) ≈ %.0f s" % (N_PAS_LONG, fin["duree"] * N_PAS_LONG / 4000))

    # A1 : annulation dure
    for mode in ("dure", "douce"):
        p, q, ev, t0 = lancer(ctx)
        prog = []
        t_prog_debut = None
        while True:
            m = q.get(timeout=120)
            if m[0] == "progression":
                if t_prog_debut is None:
                    t_prog_debut = time.perf_counter()
                prog.append((time.perf_counter() - t0, m[1]))
                if time.perf_counter() - t_prog_debut > 3.0:      # laisser calculer 3 s
                    break
        if len(prog) > 2:
            dts = [b[0] - a[0] for a, b in zip(prog[:-1], prog[1:])]
            print("   [%s] %d messages de progression en 3 s, intervalle moyen %.3f s, max %.3f s, avancement final %.1f %%"
                  % (mode, len(prog), sum(dts) / len(dts), max(dts), 100 * prog[-1][1]))
        t_annul = time.perf_counter()
        if mode == "dure":
            p.terminate()
        else:
            ev.set()
        p.join()
        t_pret = time.perf_counter() - t_annul
        # drainer la file (messages résiduels)
        reste = []
        try:
            while True:
                reste.append(q.get(timeout=0.2))
        except Exception:
            pass
        info = [m[1] for m in reste if m[0] == "fin"]
        print("   [%s] annulation -> processus terminé en %.3f s (critère < 1 s -> %s)%s"
              % (mode, t_pret, "OK" if t_pret < 1.0 else "KO",
                 (" ; arrêt propre à t = %.3f s simulée (ok=%s)" % (info[0]["t_atteint"], info[0]["ok"])) if info else ""))
    # A2 : redémarrage d'un nouveau calcul après annulation : temps jusqu'au premier message de progression
    p, q, ev, t0 = lancer(ctx, 5.0, 20000)
    while True:
        m = q.get(timeout=120)
        if m[0] == "progression":
            break
    print("   nouveau calcul après annulation : 1er message de progression après %.2f s (spawn + import + construction)"
          % (time.perf_counter() - t0))
    ev.set()
    p.join()


def _solve_dans_fil(t_fin, n_pas, sortie):
    mbs, ss = construire_et_regler(t_fin, n_pas)
    t0 = time.perf_counter()
    mbs.SolveDynamic(ss)
    sortie["duree"] = time.perf_counter() - t0


def _modele_sans_fonction_utilisateur(t_fin, n_pas):
    """Pendule simple sans aucune fonction Python : le solveur n'appelle jamais l'interpréteur."""
    import numpy as np
    import exudyn as exu
    from exudyn.utilities import InertiaCuboid, ObjectGround, RotationMatrixY
    SC = exu.SystemContainer()
    mbs = SC.AddSystem()
    sol = mbs.AddObject(ObjectGround())
    b = mbs.CreateRigidBody(inertia=InertiaCuboid(7800, [0.3, 0.02, 0.02]), referencePosition=[0.15, 0, 0],
                            gravity=[0, -9.81, 0])
    mbs.CreateGenericJoint(itemNumbers=[sol, b], position=[0, 0, 0], rotationMatrixAxes=RotationMatrixY(-np.pi / 2),
                           constrainedAxes=[1, 1, 1, 0, 1, 1], show=False)
    mbs.Assemble()
    ss = exu.SimulationSettings()
    ss.timeIntegration.endTime = t_fin
    ss.timeIntegration.numberOfSteps = n_pas
    ss.timeIntegration.verboseMode = 0
    ss.timeIntegration.generalizedAlpha.spectralRadius = 0.9
    ss.solution.file.write = False
    ss.solution.sensors.writePeriod = 1.0
    return mbs, ss


def _mesure_latence(demarrer, duree_max=6.0):
    """Lance `demarrer()` (renvoie un objet avec is_alive) et mesure les écarts d'un compteur 1 ms dans le fil principal."""
    ecarts = []
    th = demarrer()
    t_prec = time.perf_counter()
    debut = t_prec
    while th.is_alive() and time.perf_counter() - debut < duree_max:
        time.sleep(0.001)
        now = time.perf_counter()
        ecarts.append(now - t_prec)
        t_prec = now
    return ecarts, th


def partie_b():
    import threading
    print("--- Partie B : calcul dans un thread, latence du fil principal (compteur 1 ms)")
    # référence : fil principal seul
    ec = []
    t_prec = time.perf_counter()
    for _ in range(2000):
        time.sleep(0.001)
        now = time.perf_counter()
        ec.append(now - t_prec)
        t_prec = now
    print("   référence (rien d'autre) : écart moyen %.2f ms, max %.2f ms" % (1e3 * sum(ec) / len(ec), 1e3 * max(ec)))

    for etiquette, fabrique in (("bielle (fonctions utilisateur Python)", lambda: construire_et_regler(8.0, 32000)),
                                ("pendule sans fonction Python", lambda: _modele_sans_fonction_utilisateur(300.0, 600000))):
        mbs, ss = fabrique()
        res = {}

        def cible():
            t0 = time.perf_counter()
            mbs.SolveDynamic(ss)
            res["duree"] = time.perf_counter() - t0

        def demarrer():
            th = threading.Thread(target=cible, daemon=True)
            th.start()
            return th

        ecarts, th = _mesure_latence(demarrer)
        th.join(timeout=0.1)
        n = len(ecarts)
        print("   thread, %s :" % etiquette)
        print("      %d ticks sur ~6 s ; écart moyen %.2f ms, max %.1f ms, 99e centile %.2f ms%s"
              % (n, 1e3 * sum(ecarts) / max(n, 1), 1e3 * max(ecarts) if ecarts else float("nan"),
                 1e3 * sorted(ecarts)[int(0.99 * n)] if n else float("nan"),
                 " ; calcul terminé en %.1f s" % res["duree"] if "duree" in res else " ; calcul encore en cours"))
        if th.is_alive():
            print("      (le thread n'est pas interruptible : il continue ; fin du script forcée par os._exit)")
            return "thread_non_stoppable"
    return "ok"


def partie_b_qt():
    try:
        from PyQt6.QtCore import QCoreApplication, QThread, QTimer
    except Exception as e:  # noqa: BLE001
        print("   PyQt6 indisponible :", e)
        return
    print("--- Partie B' : QThread (PyQt6), minuteur Qt 1 ms dans le fil principal")
    app = QCoreApplication([])
    mbs, ss = construire_et_regler(8.0, 32000)
    res = {}

    class Fil(QThread):
        def run(self):
            t0 = time.perf_counter()
            mbs.SolveDynamic(ss)
            res["duree"] = time.perf_counter() - t0

    ecarts = []
    prec = [time.perf_counter()]
    tm = QTimer()
    tm.setInterval(1)

    def tick():
        now = time.perf_counter()
        ecarts.append(now - prec[0])
        prec[0] = now

    tm.timeout.connect(tick)
    tm.start()
    fil = Fil()
    fil.start()
    debut = time.perf_counter()
    while fil.isRunning() and time.perf_counter() - debut < 6.0:
        app.processEvents()
        time.sleep(0.0005)
    n = len(ecarts)
    print("   %d ticks en ~6 s (attendu ~ 6000 si fluide) ; écart moyen %.2f ms, max %.1f ms%s"
          % (n, 1e3 * sum(ecarts) / max(n, 1), 1e3 * max(ecarts) if ecarts else float("nan"),
             " ; calcul terminé en %.1f s" % res["duree"] if "duree" in res else " ; calcul encore en cours"))


if __name__ == "__main__":
    mp.freeze_support()
    sys.stdout.reconfigure(encoding="utf-8")
    which = sys.argv[1] if len(sys.argv) > 1 else "tout"
    if which in ("tout", "a"):
        partie_a()
    if which in ("tout", "b"):
        r = partie_b()
    if which in ("tout", "bq"):
        import os
        partie_b_qt()
        sys.stdout.flush()
        os._exit(0)
    if which in ("tout", "b"):
        import os
        sys.stdout.flush()
        os._exit(0)
