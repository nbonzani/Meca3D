"""Q2 : maquette réducteur (bâti + deux roues sur pivots, joint.gear) et relevé des réponses."""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from sc_client import Client, sauver
from sc_maquette import composant, enregistrer, etat, exe, exporter, liaison


def main() -> None:
    c = Client()
    exe(c, "file.new", {"name": "reducteur"})
    r = exe(c, "component.create", {"name": "Bati"})
    exe(c, "solid.box", {"length": 200, "width": 120, "height": 10, "corner": [-60, -60, -10],
                         "body_name": "Bati_corps"})
    exe(c, "component.activate", {"component": "root"})
    exe(c, "occurrence.ground", {"occurrence": r["occurrence"], "grounded": True})
    r1 = composant(c, "Roue1", "solid.cylinder", {"radius": 20, "height": 10, "base": [0, 0, 0]})
    r2 = composant(c, "Roue2", "solid.cylinder", {"radius": 60, "height": 10, "base": [80, 0, 0]})
    print("occurrences", r["occurrence"], r1["occurrence"], r2["occurrence"])
    l1 = liaison(c, "L1_pivot", "revolute", r["occurrence"], [0, 0, 0], r1["occurrence"], [0, 0, 0])
    l2 = liaison(c, "L2_pivot", "revolute", r["occurrence"], [80, 0, 0], r2["occurrence"], [80, 0, 0])
    sauver("q2_reducteur_joint_create.json", [l1, l2])
    jl = exe(c, "joint.list", {}, "q2_reducteur_avant_gear_joint_list.json")
    print("dof avant couplage :", jl["dof"], "links", jl["links"])

    # couplage : Z1 = 20, Z2 = 60 -> rapport 1/3, sens inverse (engrenage extérieur)
    g = exe(c, "joint.gear", {"a": "L1_pivot", "b": "L2_pivot", "ra": 20, "rb": 60},
            "q2_reducteur_gear_reponse.json")
    print("joint.gear ->", json.dumps(g))
    jl = exe(c, "joint.list", {}, "q2_reducteur_joint_list.json")
    print("links :", json.dumps(jl["links"]))
    print("dof   :", json.dumps(jl["dof"]))

    # vérification du rapport par joint.drive : L1 de 0 à 30 deg par pas de 7,5
    mesures = []
    for th in (0.0, 7.5, 30.0, 90.0, -45.0, 360.0, 0.0):
        d = exe(c, "joint.drive", {"joint": "L1_pivot", "value": th})
        v = {j["name"]: j["values"][0]["value"] for j in exe(c, "joint.list")["joints"]}
        mesures.append({"L1_demande": th, "reponse_drive": d, "L1": v["L1_pivot"], "L2": v["L2_pivot"],
                        "rapport": (v["L2_pivot"] / v["L1_pivot"]) if th else None})
    sauver("q2_reducteur_drive.json", mesures)
    for m in mesures:
        print(m["L1_demande"], m["L1"], m["L2"], m["rapport"])
    # pilotage de la sortie : le couplage est-il réversible (b entraîne a) ?
    d = exe(c, "joint.drive", {"joint": "L2_pivot", "value": -20.0})
    v = {j["name"]: j["values"][0]["value"] for j in exe(c, "joint.list")["joints"]}
    sauver("q2_reducteur_drive_sortie.json", {"reponse": d, "valeurs": v})
    print("drive L2=-20 ->", json.dumps(d)[:400], v)
    exe(c, "joint.drive", {"joint": "L1_pivot", "value": 0.0})

    # variante : roues désignées par leur face ronde (rayon lu dans la maquette) et tooth count
    ce = exe(c, "joint.gear", {"a": "L1_pivot", "b": "L2_pivot",
                               "ra": {"circle": [20, 0, 5], "occurrence": r1["occurrence"]},
                               "rb": {"circle": [140, 0, 5], "occurrence": r2["occurrence"]},
                               "link": 0}, "q2_reducteur_gear_circle.json")
    print("variante circle ->", json.dumps(ce))
    # engrenage intérieur
    ci = exe(c, "joint.gear", {"a": "L1_pivot", "b": "L2_pivot", "ra": 20, "rb": 60, "internal": True,
                               "link": 0}, "q2_reducteur_gear_internal.json")
    print("internal ->", json.dumps(ci))
    exe(c, "joint.gear", {"a": "L1_pivot", "b": "L2_pivot", "ra": 20, "rb": 60, "link": 0})
    exporter(c, "reducteur")
    chemin = enregistrer(c, "reducteur")
    print("enregistré", chemin.name, etat(c))
    # le drive modifie-t-il l'état « modifié » d'un document enregistré ?
    avant = etat(c)
    exe(c, "joint.drive", {"joint": "L1_pivot", "value": 12.0})
    apres = etat(c)
    exe(c, "joint.drive", {"joint": "L1_pivot", "value": 0.0})
    sauver("q2_reducteur_dirty.json", {"apres_enregistrement": avant, "apres_drive": apres,
                                       "apres_retour": etat(c)})
    print(avant, apres, etat(c))
    print(math.degrees(0))


if __name__ == "__main__":
    main()
