"""Q2 : maquettes vis-écrou (deux variantes) et pignon-crémaillère ; forme des couplages lus."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from sc_client import Client, sauver
from sc_maquette import composant, enregistrer, etat, exe, exporter, liaison


def valeurs(c: Client) -> dict[str, list[float]]:
    jl = exe(c, "joint.list")
    return {j["name"]: [v["value"] for v in j["values"]] for j in jl["joints"]}


def bati(c: Client) -> int:
    r = exe(c, "component.create", {"name": "Bati"})
    exe(c, "solid.box", {"length": 200, "width": 120, "height": 10, "corner": [-100, -60, -10],
                         "body_name": "Bati_corps"})
    exe(c, "component.activate", {"component": "root"})
    exe(c, "occurrence.ground", {"occurrence": r["occurrence"], "grounded": True})
    return r["occurrence"]


def vis_ecrou_deux_liaisons(c: Client) -> None:
    exe(c, "file.new", {"name": "vis_ecrou"})
    ob = bati(c)
    ov = composant(c, "Vis", "solid.cylinder", {"radius": 5, "height": 100, "base": [0, 0, 0]})["occurrence"]
    oe = composant(c, "Ecrou", "solid.box", {"length": 20, "width": 20, "height": 10,
                                              "center": [0, 0, 35]})["occurrence"]
    liaison(c, "L_vis_pivot", "revolute", ob, [0, 0, 0], ov, [0, 0, 0])
    liaison(c, "L_ecrou_glissiere", "slider", ob, [0, 0, 35], oe, [0, 0, 35])
    exe(c, "joint.screw", {"a": "L_vis_pivot", "b": "L_ecrou_glissiere", "pitch": 5},
        "q2_vis_ecrou_screw_reponse.json")
    jl = exe(c, "joint.list", {}, "q2_vis_ecrou_joint_list.json")
    print("links :", json.dumps(jl["links"]))
    mes = []
    for th in (0, 90, 360, 720, -180):
        exe(c, "joint.drive", {"joint": "L_vis_pivot", "value": th})
        mes.append({"vis_deg": th, **valeurs(c)})
    d = exe(c, "joint.drive", {"joint": "L_ecrou_glissiere", "value": 12.0})
    mes.append({"drive_sur_ecrou": d.get("moved"), **valeurs(c)})
    sauver("q2_vis_ecrou_drive.json", mes)
    for m in mes:
        print(m)
    # pas à gauche
    g = exe(c, "joint.screw", {"a": "L_vis_pivot", "b": "L_ecrou_glissiere", "pitch": 5,
                               "reverse": True, "link": 0}, "q2_vis_ecrou_screw_reverse.json")
    print("reverse ->", json.dumps(g))
    exe(c, "joint.drive", {"joint": "L_vis_pivot", "value": 0})
    exe(c, "joint.drive", {"joint": "L_vis_pivot", "value": 360})
    print("reverse 360 deg ->", valeurs(c), json.dumps(exe(c, "joint.list")["links"]))
    exe(c, "joint.screw", {"a": "L_vis_pivot", "b": "L_ecrou_glissiere", "pitch": 5, "link": 0})
    exe(c, "joint.drive", {"joint": "L_vis_pivot", "value": 0})
    exporter(c, "vis_ecrou")
    enregistrer(c, "vis_ecrou")


def vis_ecrou_cylindrique(c: Client) -> None:
    exe(c, "file.new", {"name": "vis_ecrou_cyl"})
    ob = bati(c)
    oe = composant(c, "Ecrou", "solid.box", {"length": 20, "width": 20, "height": 10,
                                              "center": [0, 0, 35]})["occurrence"]
    liaison(c, "L_helicoidale", "cylindrical", ob, [0, 0, 35], oe, [0, 0, 35])
    r = exe(c, "joint.screw", {"joint": "L_helicoidale", "pitch": 5}, "q2_cyl_screw_reponse.json")
    print("cyl screw ->", json.dumps(r))
    jl = exe(c, "joint.list", {}, "q2_cyl_joint_list.json")
    print("links :", json.dumps(jl["links"]))
    print("joint :", json.dumps([{k: j[k] for k in ("name", "type", "values")} for j in jl["joints"]]))
    mes = []
    for i, val in enumerate((90.0, 360.0)):
        d = exe(c, "joint.drive", {"joint": "L_helicoidale", "values": [val, 0]})
        mes.append({"demande_values": [val, 0], "reponse": d["values"], "liste": valeurs(c)})
    d = exe(c, "joint.drive", {"joint": "L_helicoidale", "values": [0, 10.0]})
    mes.append({"demande_values": [0, 10], "reponse": d["values"], "liste": valeurs(c)})
    sauver("q2_cyl_drive.json", mes)
    for m in mes:
        print(m)
    exe(c, "joint.drive", {"joint": "L_helicoidale", "values": [0, 0]})
    exporter(c, "vis_ecrou_cyl")
    enregistrer(c, "vis_ecrou_cyl")


def cremaillere(c: Client) -> None:
    exe(c, "file.new", {"name": "cremaillere"})
    ob = bati(c)
    op = composant(c, "Pignon", "solid.cylinder", {"radius": 20, "height": 10, "base": [0, 0, 0]})["occurrence"]
    oc = composant(c, "Cremaillere", "solid.box", {"length": 160, "width": 10, "height": 10,
                                                    "center": [0, -25, 5]})["occurrence"]
    liaison(c, "L_pignon", "revolute", ob, [0, 0, 0], op, [0, 0, 0])
    liaison(c, "L_cremaillere", "slider", ob, [0, -25, 5], oc, [0, -25, 5], z=[1, 0, 0])
    r = exe(c, "joint.rack_pinion", {"a": "L_pignon", "b": "L_cremaillere", "radius": 20},
            "q2_cremaillere_reponse.json")
    print("rack_pinion ->", json.dumps(r))
    jl = exe(c, "joint.list", {}, "q2_cremaillere_joint_list.json")
    print("links :", json.dumps(jl["links"]))
    mes = []
    for th in (0, 30, 90, 180, -57.29577951308232):
        exe(c, "joint.drive", {"joint": "L_pignon", "value": th})
        mes.append({"pignon_deg": th, **valeurs(c)})
    sauver("q2_cremaillere_drive.json", mes)
    for m in mes:
        print(m)
    # ordre inverse des arguments (a = crémaillère, b = pignon)
    exe(c, "joint.drive", {"joint": "L_pignon", "value": 0})
    r2 = exe(c, "joint.rack_pinion", {"a": "L_cremaillere", "b": "L_pignon", "radius": 20, "link": 0},
             "q2_cremaillere_ordre_inverse.json")
    print("ordre inverse ->", json.dumps(r2))
    print("links :", json.dumps(exe(c, "joint.list")["links"]))
    exe(c, "joint.drive", {"joint": "L_cremaillere", "value": 20})
    print("drive crémaillère 20 mm ->", valeurs(c))
    exe(c, "joint.rack_pinion", {"a": "L_pignon", "b": "L_cremaillere", "radius": 20, "link": 0})
    exe(c, "joint.drive", {"joint": "L_pignon", "value": 0})
    exporter(c, "cremaillere")
    enregistrer(c, "cremaillere")


def main() -> None:
    c = Client()
    vis_ecrou_deux_liaisons(c)
    vis_ecrou_cylindrique(c)
    cremaillere(c)
    print(etat(c))


if __name__ == "__main__":
    main()
