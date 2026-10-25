# SPDX-License-Identifier: GPL-3.0-or-later
"""Lecture des inerties d'un export URDF SolidCraft, recomposées en repère monde (D3).

L'URDF est écrit à valeurs articulaires nulles. Les poses des liens sont recomposées le long de
l'arbre des joints. Hypothèse : l'origine du `visual` donne la transformation du repère du
composant (celui du maillage) vers le repère du lien.
"""

import xml.etree.ElementTree as ET
from dataclasses import dataclass

import numpy as np


class ErreurUrdf(ValueError):
    """URDF illisible ou arbre incohérent."""


@dataclass
class InertieLien:
    """Inertie d'un lien à la configuration de référence de l'URDF (SI, axes monde)."""

    nom: str
    masse: float
    cdg: np.ndarray
    inertie: np.ndarray  # au CdG, axes monde
    rotation_composant: np.ndarray  # repère du composant -> monde, à la référence


def _vecteur(texte: str | None) -> np.ndarray:
    if texte is None:
        return np.zeros(3)
    return np.array([float(x) for x in texte.split()], dtype=float)


def rotation_rpy(roll: float, pitch: float, yaw: float) -> np.ndarray:
    """Convention URDF : R = Rz(yaw) · Ry(pitch) · Rx(roll)."""
    cr, sr = np.cos(roll), np.sin(roll)
    cp, sp = np.cos(pitch), np.sin(pitch)
    cy, sy = np.cos(yaw), np.sin(yaw)
    rx = np.array([[1, 0, 0], [0, cr, -sr], [0, sr, cr]])
    ry = np.array([[cp, 0, sp], [0, 1, 0], [-sp, 0, cp]])
    rz = np.array([[cy, -sy, 0], [sy, cy, 0], [0, 0, 1]])
    return rz @ ry @ rx


def _origine(element: ET.Element | None) -> tuple[np.ndarray, np.ndarray]:
    """(R, xyz) d'un élément portant <origin xyz rpy>."""
    origine = None if element is None else element.find("origin")
    if origine is None:
        return np.eye(3), np.zeros(3)
    return rotation_rpy(*_vecteur(origine.get("rpy"))), _vecteur(origine.get("xyz"))


def lire_urdf(texte: str) -> dict[str, InertieLien]:
    """Inertie de chaque lien muni d'un `<inertial>`, en repère monde (référence de l'URDF)."""
    try:
        racine = ET.fromstring(texte)
    except ET.ParseError as e:
        raise ErreurUrdf(f"URDF illisible : {e}") from e
    liens = {lien.get("name", ""): lien for lien in racine.findall("link")}
    joints = racine.findall("joint")
    enfants = {j.find("child").get("link") for j in joints if j.find("child") is not None}  # type: ignore[union-attr]
    racines = [nom for nom in liens if nom not in enfants]
    if len(racines) != 1:
        raise ErreurUrdf("URDF : l'arbre des liens doit avoir une seule racine.")
    poses: dict[str, tuple[np.ndarray, np.ndarray]] = {racines[0]: (np.eye(3), np.zeros(3))}
    progres = True
    while progres and len(poses) < len(liens):
        progres = False
        for joint in joints:
            parent, enfant = joint.find("parent"), joint.find("child")
            if parent is None or enfant is None:
                raise ErreurUrdf("URDF : joint sans parent ou sans enfant.")
            nom_p, nom_e = str(parent.get("link")), str(enfant.get("link"))
            if nom_p in poses and nom_e not in poses:
                rp, tp = poses[nom_p]
                r0, t0 = _origine(joint)
                poses[nom_e] = (rp @ r0, rp @ t0 + tp)
                progres = True
    if len(poses) < len(liens):
        raise ErreurUrdf("URDF : liens non reliés à la racine.")

    resultat: dict[str, InertieLien] = {}
    for nom, lien in liens.items():
        inertial = lien.find("inertial")
        if inertial is None:
            continue
        rl, tl = poses[nom]
        ri, xyz = _origine(inertial)
        masse_el, inertie_el = inertial.find("mass"), inertial.find("inertia")
        if masse_el is None or inertie_el is None:
            raise ErreurUrdf(f"URDF : lien {nom} sans masse ou sans inertie.")
        a = {k: float(v) for k, v in inertie_el.attrib.items()}
        i_lien = np.array(
            [
                [a["ixx"], a["ixy"], a["ixz"]],
                [a["ixy"], a["iyy"], a["iyz"]],
                [a["ixz"], a["iyz"], a["izz"]],
            ]
        )
        r_inertie = rl @ ri
        rv, _ = _origine(lien.find("visual"))
        resultat[nom] = InertieLien(
            nom=nom,
            masse=float(masse_el.get("value", "nan")),
            cdg=rl @ xyz + tl,
            inertie=r_inertie @ i_lien @ r_inertie.T,
            rotation_composant=rl @ rv,
        )
    return resultat
