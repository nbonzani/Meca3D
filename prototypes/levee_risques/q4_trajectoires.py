"""Q4 : motion.trace, motion.trace.keep et alternative par esquisse 3D, sur une COPIE de la bielle."""

from __future__ import annotations

import json
import math
import shutil
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from sc_client import Client, sauver
from sc_maquette import MAQ, etat, exe

SOURCE = Path("D:/CLAUDE/dev/Solidcraft/meca3d_sonde/bielle_manivelle.solidcraft")
R, L = 100.0, 300.0


def pt_p(theta: float) -> np.ndarray:
    """Point P de la bielle, à 100 mm de A vers B (monde, mm)."""
    a = np.array([R * math.cos(theta), R * math.sin(theta)])
    b = R * math.cos(theta) + math.sqrt(L**2 - (R * math.sin(theta)) ** 2)
    u = np.array([b, 0.0]) - a
    u /= np.linalg.norm(u)
    return np.append(a + 100.0 * u, 0.0)


def pt_b(theta: float) -> np.ndarray:
    return np.array([R * math.cos(theta) + math.sqrt(L**2 - (R * math.sin(theta)) ** 2), 0.0, 0.0])


def main() -> None:
    MAQ.mkdir(exist_ok=True)
    copie = MAQ / "bielle_trace.solidcraft"
    shutil.copyfile(SOURCE, copie)
    c = Client()
    exe(c, "doc.open", {"path": str(copie)})
    print("document actif :", etat(c))
    jl = exe(c, "joint.list")
    th0 = next(j for j in jl["joints"] if j["name"] == "L01_pivot")["values"][0]["value"]
    print("theta0 =", th0)
    sortie: dict = {"etat_depart": etat(c), "theta0_deg": th0}
    # point P et point B dans la pose courante (theta0 = 60 deg)
    p0 = pt_p(math.radians(th0))
    b0 = pt_b(math.radians(th0))
    N = 200
    thetas = [math.radians(360.0 * i / (N - 1)) for i in range(N)]  # joint de 0 à 360, N échantillons

    # --- 1. motion.trace par joint (from/to), sans étude ---
    for nom, occ, pt, f in (("P_bielle", 8, p0, pt_p), ("B_piston", 11, b0, pt_b)):
        t0 = time.perf_counter()
        r = c.cmd("motion.trace", {"occurrence": occ, "point": [float(x) for x in pt],
                                   "joint": "L01_pivot", "from": 0, "to": 360, "samples": N})
        dt = time.perf_counter() - t0
        sauver(f"q4_trace_{nom}.json", r)
        res = r["result"]
        pts = np.array(res["points"])
        ana = np.array([f(t) for t in thetas])
        sortie[f"trace_joint_{nom}"] = {
            "duree_s": dt, "samples": res.get("samples"), "stopped_at": res.get("stopped_at"),
            "stopped_by_loop": res.get("stopped_by_loop"), "stopped_by_contact": res.get("stopped_by_contact"),
            "cles": sorted(res.keys()),
            "ecart_max_mm_vs_analytique": float(np.abs(pts - ana).max()),
            "premier_point": res["points"][0], "dernier_point": res["points"][-1],
        }
        print(nom, sortie[f"trace_joint_{nom}"])
    sortie["etat_apres_trace"] = etat(c)  # motion.trace ne modifie pas la maquette

    # --- 2. étude de mouvement puis trace par étude ---
    r = c.cmd("motion.study", {"name": "rotation_manivelle", "steps": 100,
                               "keys": [{"joint": "L01_pivot", "points": [[0, 0], [100, 360]]}]})
    sauver("q4_motion_study.json", r)
    print("motion.study ->", json.dumps(r)[:600])
    sortie["motion_study_reponse"] = r
    sortie["etat_apres_study"] = etat(c)
    if r["ok"]:
        r = c.cmd("motion.trace", {"occurrence": 8, "point": [float(x) for x in p0],
                                   "study": "rotation_manivelle", "samples": 101})
        sauver("q4_trace_etude.json", r)
        if r["ok"]:
            pts = np.array(r["result"]["points"])
            ana = np.array([pt_p(math.radians(3.6 * i)) for i in range(101)])
            sortie["trace_etude_P"] = {"samples": r["result"]["samples"],
                                       "ecart_max_mm_vs_analytique": float(np.abs(pts - ana).max())}
        else:
            sortie["trace_etude_P"] = r
        print(sortie["trace_etude_P"])
        sauver("q4_motion_list.json", c.cmd("motion.list"))
        t0 = time.perf_counter()
        r = c.cmd("motion.plot", {"study": "rotation_manivelle", "joints": ["L01_pivot"],
                                  "occurrence": 11, "point": [float(x) for x in b0], "samples": 101,
                                  "duration": 1.0})
        sortie["motion_plot_duree_s"] = time.perf_counter() - t0
        sauver("q4_motion_plot.json", r)
        sortie["motion_plot_cles"] = sorted(r["result"].keys()) if r["ok"] else r

    # --- 3. motion.trace.keep : esquisse 3D conservée dans la maquette ---
    avant = etat(c)
    d_avant = c.appel("document.inspect")["result"]
    r = c.cmd("motion.trace.keep", {"occurrence": 8, "point": [float(x) for x in p0],
                                    "joint": "L01_pivot", "from": 0, "to": 360, "samples": N,
                                    "name": "Trace_P"})
    sauver("q4_trace_keep_reponse.json", r)
    print("keep ->", json.dumps(r)[:500])
    d_apres = c.appel("document.inspect")["result"]
    sortie["keep"] = {"avant": avant, "apres": etat(c), "reponse_cles": sorted(r["result"].keys()) if r["ok"] else r,
                      "sketches_avant": d_avant["sketches"], "sketches_apres": d_apres["sketches"],
                      "timeline_ajoute": [t["name"] for t in d_apres["timeline"][len(d_avant["timeline"]):]]}
    print(sortie["keep"])
    # la courbe suit-elle un changement de pose ? (fixe selon la doc)
    exe(c, "joint.drive", {"joint": "L01_pivot", "value": 120.0})
    sauver("q4_inspect_apres_keep.json", c.appel("document.inspect"))
    exe(c, "joint.drive", {"joint": "L01_pivot", "value": th0})
    sauver("q4_component_list_apres_keep.json", c.cmd("component.list"))
    out_png = Path(__file__).parent / "reponses" / "q4_trace_keep.png"
    s = c.appel("ui.screenshot", {"path": str(out_png)})
    sortie["screenshot"] = s.get("ok")

    # --- 4. alternative : esquisse 3D, points quelconques (p. ex. issus d'Exudyn) ---
    pts_exudyn = [[float(x) for x in pt_b(t) + np.array([0.0, 0.0, 40.0])] for t in thetas]  # arbitraires
    t0 = time.perf_counter()
    e = exe(c, "sketch.create", {"plane": "XY", "name": "Trace_alt"}, "q4_alt_sketch_create.json")
    o = exe(c, "sketch.options", {"sketch_3d": True}, "q4_alt_sketch_options.json")
    sp = c.cmd("sketch.spline3d", {"points": [[float(x) for x in pt_p(t)] for t in thetas]})
    sauver("q4_alt_spline3d.json", {"ok": sp["ok"], "cles": sorted(sp["result"].keys()) if sp["ok"] else sp,
                                    "created": sp["result"].get("created") if sp["ok"] else None})
    fin = c.cmd("sketch.finish")
    sauver("q4_alt_finish.json", fin)
    sortie["alternative_spline3d"] = {"duree_s": time.perf_counter() - t0, "ok": sp["ok"],
                                      "reponse_resume": (sp["result"] if sp["ok"] else sp)}
    print("alt ->", json.dumps(sortie["alternative_spline3d"])[:600])
    d = c.appel("document.inspect")["result"]
    sortie["sketches_finaux"] = d["sketches"]
    sortie["etat_final"] = etat(c)
    sauver("q4_resultats.json", sortie)
    print(json.dumps(sortie["sketches_finaux"])[:800])


if __name__ == "__main__":
    main()
