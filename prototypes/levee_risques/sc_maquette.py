"""Aides de construction de maquettes SolidCraft par le canal de contrôle (prototype jetable)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from sc_client import RACINE, Client, anonymiser, sauver

MAQ = RACINE / "maquettes"
REP = RACINE / "reponses"


def exe(c: Client, cmd: str, params: dict | None = None, nom: str | None = None) -> dict:
    r = c.cmd(cmd, params)
    if nom:
        sauver(nom, r)
    if not r.get("ok"):
        raise SystemExit(f"{cmd} {json.dumps(params)} -> {json.dumps(r)[:800]}")
    return r["result"]


def composant(c: Client, nom: str, cmd: str, params: dict, parent: str | None = None) -> dict:
    """Crée un composant, y place un corps, puis revient à la racine. Renvoie le résultat de create."""
    p = {"name": nom}
    if parent:
        p["parent"] = parent
    r = exe(c, "component.create", p)
    exe(c, cmd, {**params, "body_name": f"{nom}_corps"})
    exe(c, "component.activate", {"component": "root"})
    return r


def liaison(c: Client, nom: str, type_: str, occ_a: int | str, pt_a: list[float],
            occ_b: int | str, pt_b: list[float], z: list[float] | None = None, **extra) -> dict:
    """joint.origin ×2 puis joint.create (flip: true : les repères restent où ils sont)."""
    for suffixe, occ, pt in (("a", occ_a, pt_a), ("b", occ_b, pt_b)):
        p = {"name": f"{nom}_{suffixe}", "occurrence": occ, "point": pt}
        if z:
            p["z"] = z
        exe(c, "joint.origin", p)
    return exe(c, "joint.create", {"type": type_, "a": f"{nom}_a", "b": f"{nom}_b", "flip": True,
                                   "name": nom, **extra})


def exporter(c: Client, nom: str) -> None:
    """Enregistre joint.list, component.list, l'export JSON et l'export URDF (chemins anonymisés)."""
    sauver(f"{nom}_joint_list.json", c.cmd("joint.list"))
    sauver(f"{nom}_component_list.json", c.cmd("component.list"))
    dossier = REP / f"export_{nom}"
    if dossier.exists():
        shutil.rmtree(dossier)
    dossier.mkdir(parents=True)
    for fmt in ("json", "urdf"):
        r = c.cmd("file.export", {"path": str(dossier / f"{nom}.{fmt}"), "format": fmt})
        if not r.get("ok"):
            print("export", fmt, "échec :", json.dumps(r)[:300])
    for f in dossier.iterdir():
        if f.suffix in (".json", ".urdf"):
            f.write_text(anonymiser(f.read_text(encoding="utf-8")), encoding="utf-8")
        elif f.suffix == ".stl":
            f.unlink()  # maillages inutiles pour la sonde


def enregistrer(c: Client, nom: str) -> Path:
    MAQ.mkdir(exist_ok=True)
    chemin = MAQ / f"{nom}.solidcraft"
    exe(c, "file.save_as", {"path": str(chemin)})
    return chemin


def etat(c: Client) -> dict:
    d = c.appel("document.inspect")["result"]
    return {k: d[k] for k in ("name", "dirty", "revision", "undo", "marker")}
