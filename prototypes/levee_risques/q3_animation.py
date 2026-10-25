"""Q3 : comparaison de deux modes d'animation de la bielle-manivelle dans SolidCraft.

(a) joint.drive sur L01_pivot, image par image ;
(b) occurrence.move en déplacement « en attente » (capture: false) avec des poses calculées ;
(c) engine.batch pour envoyer plusieurs images en une requête.

Les poses calculées viennent de la cinématique analytique (r = 100 mm, l = 300 mm), pas de SolidCraft.
Le script restaure la pose initiale et mesure l'écart. Il n'enregistre jamais la maquette.
"""

from __future__ import annotations

import math
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from sc_client import Client, sauver

R, L = 100.0, 300.0
N = 200
ID = {"Manivelle": 5, "Bielle": 8, "Piston": 11}


def xb(theta: float) -> float:
    return R * math.cos(theta) + math.sqrt(L**2 - (R * math.sin(theta)) ** 2)


def matrice(rot_z: float, t: tuple[float, float]) -> np.ndarray:
    """4x4 (convention colonne) rotation autour de z puis translation, en mm."""
    c, s = math.cos(rot_z), math.sin(rot_z)
    m = np.eye(4)
    m[:2, :2] = [[c, -s], [s, c]]
    m[:2, 3] = t
    return m


def poses_analytiques(theta: float) -> dict[str, np.ndarray]:
    """Poses des trois solides mobiles au repère de leur composant (origine en O à theta = 0)."""
    a = (R * math.cos(theta), R * math.sin(theta))
    b = xb(theta)
    phi = math.atan2(-R * math.sin(theta), b - a[0])
    rphi = matrice(phi, (0, 0))
    t_biel = (a[0] - (rphi[0, 0] * R), a[1] - (rphi[1, 0] * R))
    return {
        "Manivelle": matrice(theta, (0, 0)),
        "Bielle": matrice(phi, t_biel),
        "Piston": matrice(0.0, (b - 400.0, 0.0)),
    }


def transform_vers_matrice(t: list[list[float]]) -> np.ndarray:
    """SolidCraft stocke la 4x4 par colonnes : t[j][i] = M[i][j]."""
    return np.array(t).T


def delta_deplacement(cible: np.ndarray, courant: np.ndarray) -> dict:
    """Paramètres d'occurrence.move (espace monde) qui font passer de courant à cible."""
    d = cible @ np.linalg.inv(courant)
    rot = d[:3, :3]
    angle = math.atan2(rot[1, 0] - rot[0, 1], rot[0, 0] + rot[1, 1])  # rotation autour de z
    p = {"space": "world", "capture": False}
    if abs(angle) > 1e-15:
        p.update(axis=[0, 0, 1], angle=angle, origin=[0, 0, 0])
    p["translate"] = [float(x) for x in d[:3, 3]]
    return p


def etat_document(c: Client) -> dict:
    d = c.appel("document.inspect")["result"]
    return {k: d[k] for k in ("dirty", "revision", "undo", "redo", "marker")}


def poses_lues(c: Client) -> dict[str, np.ndarray]:
    ch = c.cmd("component.list")["result"]["components"][0]["children"]
    return {x["name"].split(":")[0]: transform_vers_matrice(x["transform"]) for x in ch}


def valeurs_joints(c: Client) -> dict[str, list[float]]:
    jl = c.cmd("joint.list")["result"]
    return {j["name"]: [v["value"] for v in j["values"]] for j in jl["joints"]}


def main() -> None:
    c = Client()
    sortie: dict = {}
    sortie["etat_initial"] = etat_document(c)
    init_vals = valeurs_joints(c)
    init_poses = poses_lues(c)
    theta0 = init_vals["L01_pivot"][0]
    thetas = [math.radians(1.8 * k) for k in range(N)]  # 0 -> 358,2 deg

    # ---------- (a) joint.drive, une connexion persistante ----------
    t0 = time.perf_counter()
    reponses = []
    for th in thetas:
        reponses.append(
            c.cmd("joint.drive", {"joint": "L01_pivot", "value": math.degrees(th), "quiet": True})
        )
    dt = time.perf_counter() - t0
    sauver("q3_joint_drive_exemple.json", reponses[:3])
    sortie["a_drive"] = {
        "images": N,
        "duree_s": dt,
        "images_par_s": N / dt,
        "etat_apres": etat_document(c),
        "ok": all(r["ok"] for r in reponses),
    }

    # fidélité : relecture après chaque image (joint.list + component.list)
    ecarts_theta, ecarts_x = [], []
    t_lect = 0.0
    for th in thetas:
        c.cmd("joint.drive", {"joint": "L01_pivot", "value": math.degrees(th), "quiet": True})
        t1 = time.perf_counter()
        v = valeurs_joints(c)
        p = poses_lues(c)
        t_lect += time.perf_counter() - t1
        d = (v["L01_pivot"][0] - math.degrees(th) + 180) % 360 - 180
        ecarts_theta.append(abs(d))
        ecarts_x.append(abs(p["Piston"][0, 3] - (xb(th) - 400.0)))
    sortie["a_drive"]["fidelite"] = {
        "ecart_max_theta_deg": max(ecarts_theta),
        "ecart_max_xB_mm": max(ecarts_x),
        "duree_lecture_par_image_ms": 1000 * t_lect / N,
    }

    # joint.drive via engine.batch : 200 images en une requête
    cmds = [
        {"command": "joint.drive", "params": {"joint": "L01_pivot", "value": math.degrees(th), "quiet": True}}
        for th in thetas
    ]
    t0 = time.perf_counter()
    rb = c.appel("engine.batch", {"commands": cmds, "timings": True})
    dtb = time.perf_counter() - t0
    res = rb["result"]
    sauver("q3_batch_drive_extrait.json", {"ok": rb["ok"], "completed": res.get("completed"),
                                         "undone": res.get("undone"), "total_ms": res.get("total_ms"),
                                         "premiers_resultats": res["results"][:2],
                                         "premiers_timings": res.get("timings", [])[:3]})
    sortie["a_batch"] = {"images": N, "duree_s": dtb, "images_par_s": N / dtb,
                         "completed": res.get("completed"), "total_ms": res.get("total_ms"),
                         "etat_apres": etat_document(c)}

    # ---------- restauration (a) ----------
    c.cmd("joint.drive", {"joint": "L01_pivot", "value": theta0, "quiet": True})
    v = valeurs_joints(c)
    p = poses_lues(c)
    sortie["a_restauration"] = {
        "ecart_max_valeurs_articulaires": max(
            abs(a - b) for k in init_vals for a, b in zip(v[k], init_vals[k], strict=True)
        ),
        "ecart_max_poses": max(float(np.abs(p[k] - init_poses[k]).max()) for k in init_poses),
        "etat_apres": etat_document(c),
        "valeur_initiale_utilisee": theta0,
    }

    # ---------- (b) occurrence.move en attente, une commande par solide ----------
    courant = {k: init_poses[k].copy() for k in ID}
    # poses analytiques dans le repère « composant » : on ramène la pose initiale à celle de theta0
    ref0 = poses_analytiques(math.radians(theta0))
    # les poses analytiques ont pour repère celui du composant à theta = 0 ; on s'assure de la cohérence
    sortie["b_coherence_pose_initiale_mm"] = max(
        float(np.abs(ref0[k] - init_poses[k]).max()) for k in ID
    )
    t_calc = 0.0
    t0 = time.perf_counter()
    nreq = 0
    rep_b = []
    for th in thetas:
        t1 = time.perf_counter()
        cibles = poses_analytiques(th)
        reqs = {k: delta_deplacement(cibles[k], courant[k]) for k in ID}
        t_calc += time.perf_counter() - t1
        for k, p_ in reqs.items():
            r = c.cmd("occurrence.move", {"occurrence": ID[k], **p_})
            nreq += 1
            rep_b.append(r)
            courant[k] = transform_vers_matrice(r["result"]["transform"])
    dtb = time.perf_counter() - t0
    sauver("q3_occurrence_move_exemple.json", rep_b[:3])
    # fidélité : pose lue par occurrence.properties (centre de gravité du piston, monde)
    prop = c.cmd("occurrence.properties", {"occurrence": ID["Piston"]})["result"]
    x_cdg = prop["total"]["center_of_mass"][0]
    th_fin = thetas[-1]
    sortie["b_move"] = {
        "images": N,
        "requetes": nreq,
        "duree_s": dtb,
        "images_par_s": N / dtb,
        "calcul_python_s": t_calc,
        "ecart_xB_mm_derniere_image": abs(x_cdg - xb(th_fin)),
        "ecart_pose_retournee_vs_cible_max": max(
            float(np.abs(courant[k] - poses_analytiques(th_fin)[k]).max()) for k in ID
        ),
        "pending_moves": c.cmd("component.list")["result"]["pending_moves"],
        "etat_apres": etat_document(c),
        "joint_list_inchangee_pendant_le_deplacement": valeurs_joints(c) == init_vals
        or max(abs(a - b) for k in init_vals for a, b in zip(valeurs_joints(c)[k], init_vals[k], strict=True)),
    }
    rev = c.cmd("component.revert_position", {})
    sauver("q3_revert_position.json", rev)
    p = poses_lues(c)
    prop = c.cmd("occurrence.properties", {"occurrence": ID["Piston"]})["result"]
    sortie["b_restauration"] = {
        "reponse": rev["result"],
        "ecart_max_poses": max(float(np.abs(p[k] - init_poses[k]).max()) for k in init_poses),
        "xB_cdg_apres_revert": prop["total"]["center_of_mass"][0],
        "ecart_valeurs_articulaires": max(
            abs(a - b) for k, vv in valeurs_joints(c).items() for a, b in zip(vv, init_vals[k], strict=True)
        ),
        "etat_apres": etat_document(c),
    }

    # ---------- (c) engine.batch d'occurrence.move : 200 images x 3 solides ----------
    courant = {k: init_poses[k].copy() for k in ID}
    cmds = []
    for th in thetas:
        cibles = poses_analytiques(th)
        for k in ID:
            p_ = delta_deplacement(cibles[k], courant[k])
            cmds.append({"command": "occurrence.move", "params": {"occurrence": ID[k], **p_}})
            courant[k] = cibles[k]
    t0 = time.perf_counter()
    rb = c.appel("engine.batch", {"commands": cmds})
    dtc = time.perf_counter() - t0
    res = rb["result"]
    sortie["c_batch_move"] = {
        "images": N,
        "commandes": len(cmds),
        "duree_s": dtc,
        "images_par_s": N / dtc,
        "completed": res.get("completed"),
        "failed": res.get("failed"),
    }
    prop = c.cmd("occurrence.properties", {"occurrence": ID["Piston"]})["result"]
    sortie["c_batch_move"]["ecart_xB_mm_derniere_image"] = abs(
        prop["total"]["center_of_mass"][0] - xb(thetas[-1])
    )
    c.cmd("component.revert_position", {})
    p = poses_lues(c)
    sortie["c_batch_move"]["restauration_ecart_max_poses"] = max(
        float(np.abs(p[k] - init_poses[k]).max()) for k in init_poses
    )
    sortie["etat_final"] = etat_document(c)
    sortie["valeurs_finales_vs_initiales"] = {
        k: [a - b for a, b in zip(vv, init_vals[k], strict=True)] for k, vv in valeurs_joints(c).items()
    }
    sauver("q3_resultats.json", sortie)


if __name__ == "__main__":
    main()
