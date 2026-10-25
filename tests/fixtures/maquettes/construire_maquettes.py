# SPDX-License-Identifier: GPL-3.0-or-later
"""Construit les quatre maquettes de référence du lot 11 dans SolidCraft et enregistre les réponses.

Usage (SolidCraft lancé avec `--control 7878`, fenêtre visible) :
    uv run python tests/fixtures/maquettes/construire_maquettes.py [cas ...]

Chaque cas crée un NOUVEAU design (`file.new`), construit la maquette par le canal de contrôle,
enregistre les réponses réelles (`document.inspect`, `joint.list`, `component.list`,
`component.properties`, exports URDF et JSON ; chemins personnels anonymisés, aucun jeton) sous
`tests/fixtures/<cas>/solidcraft/`, puis la maquette sous
`tests/fixtures/maquettes/<cas>.solidcraft`.
La maquette ouverte avant le lancement est perdue sans être enregistrée : la rouvrir ensuite.
"""

import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any

from meca3d.cao.canal import CanalSolidCraft

MAQUETTES = Path(__file__).resolve().parent
FIXTURES = MAQUETTES.parent

ACIER_G_CM3 = 7.8  # kg/m³ = 7 800 (SPEC, pendules)


def anonymiser(texte: str) -> str:
    return re.sub(r"[A-Za-z]:(\\\\|\\|/)Users(\\\\|\\|/)[^\\/\"]+", "<UTILISATEUR>", texte)


def ecrire(chemin: Path, donnees: Any) -> None:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    texte = json.dumps(donnees, indent=1, ensure_ascii=False, sort_keys=True)
    chemin.write_text(anonymiser(texte), encoding="utf-8")


class Maquette:
    """Aides de construction (reprend sc_maquette.py du lot 1b)."""

    def __init__(self, canal: CanalSolidCraft, cas: str) -> None:
        self.c = canal
        self.cas = cas
        self.dossier = FIXTURES / cas / "solidcraft"

    def exe(self, commande: str, params: dict[str, Any] | None = None) -> Any:
        return self.c.executer(commande, params)

    def nouveau(self) -> None:
        self.exe("file.new", {"name": self.cas})
        self.exe("material.create", {"name": "Acier", "density_g_cm3": ACIER_G_CM3})

    def composant(self, nom: str, commande: str, params: dict[str, Any], fixe: bool = False) -> int:
        """Composant à un corps d'acier ; rend l'identifiant de l'occurrence."""
        r = self.exe("component.create", {"name": nom})
        self.exe(commande, {**params, "body_name": f"{nom}_corps"})
        self.exe("component.activate", {"component": "root"})
        self.exe("material.assign", {"bodies": [f"{nom}_corps"], "material": "Acier"})
        if fixe:
            self.exe("occurrence.ground", {"occurrence": r["occurrence"], "grounded": True})
        return int(r["occurrence"])

    def liaison(
        self,
        nom: str,
        type_: str,
        a: int,
        pt_a: list[float],
        b: int,
        pt_b: list[float],
        z: list[float] | None = None,
    ) -> None:
        for suffixe, occ, pt in (("a", a, pt_a), ("b", b, pt_b)):
            p: dict[str, Any] = {"name": f"{nom}_{suffixe}", "occurrence": occ, "point": pt}
            if z:
                p["z"] = z
            self.exe("joint.origin", p)
        self.exe(
            "joint.create",
            {"type": type_, "a": f"{nom}_a", "b": f"{nom}_b", "flip": True, "name": nom},
        )

    def enregistrer_reponses(self, etiquette: str) -> None:
        """Réponses du canal dans la pose courante (format de tests/fixtures/bielle/solidcraft)."""
        d = self.dossier
        ecrire(d / f"document_inspect_{etiquette}.json", self.c.requete("document.inspect"))
        ecrire(d / f"joint_list_{etiquette}.json", self.exe("joint.list"))
        liste = self.exe("component.list")
        ecrire(d / f"component_list_{etiquette}.json", liste)
        racine = next(x for x in liste["components"] if x.get("parent") is None)
        proprietes: dict[str, Any] = {}
        for occ in racine["children"]:
            if occ.get("parent", racine["id"]) == racine["id"]:
                cle = str(occ["component"])
                if cle not in proprietes:
                    proprietes[cle] = self.exe(
                        "component.properties", {"component": occ["component"]}
                    )
        ecrire(d / f"component_properties_{etiquette}.json", proprietes)
        export = d / f"export_{etiquette}"
        if export.exists():
            shutil.rmtree(export)
        export.mkdir(parents=True)
        for fmt in ("json", "urdf"):
            self.exe("file.export", {"path": str(export / f"{self.cas}.{fmt}"), "format": fmt})
        for f in export.iterdir():
            if f.suffix in (".json", ".urdf"):
                f.write_text(anonymiser(f.read_text(encoding="utf-8")), encoding="utf-8")
            else:
                f.unlink()  # maillages inutiles

    def enregistrer_maquette(self) -> None:
        chemin = MAQUETTES / f"{self.cas}.solidcraft"
        self.exe("file.save_as", {"path": str(chemin)})

    def piloter(self, liaison: str, valeur: float) -> None:
        self.exe("joint.drive", {"joint": liaison, "value": valeur})


# --------------------------------------------------------------------------------------- cas
BARRE = {"length": 20, "width": 20, "height": 400}  # mm, SPEC : 400 × 20 × 20, ρ = 7 800 kg/m³
Y = [0.0, 1.0, 0.0]  # axe horizontal des pivots des pendules


def _bati_pendule(m: Maquette) -> int:
    return m.composant(
        "Bati",
        "solid.box",
        {"length": 60, "width": 20, "height": 60, "corner": [-30, 10, -30]},
        fixe=True,
    )


def pendule_simple(canal: CanalSolidCraft) -> None:
    m = Maquette(canal, "pendule_simple")
    m.nouveau()
    bati = _bati_pendule(m)
    barre = m.composant("Barre", "solid.box", {**BARRE, "corner": [-10, -10, -400]})
    m.liaison("L01_pivot", "revolute", bati, [0, 0, 0], barre, [0, 0, 0], z=Y)
    for etiquette, angle in (("theta00", 0.0), ("theta01", 1.0), ("theta30", 30.0)):
        m.piloter("L01_pivot", angle)
        m.enregistrer_reponses(etiquette)
    m.enregistrer_maquette()  # enregistrée à 30° (lâcher de EX-31 et des tests réels)


def pendule_double(canal: CanalSolidCraft) -> None:
    m = Maquette(canal, "pendule_double")
    m.nouveau()
    bati = _bati_pendule(m)
    b1 = m.composant("Barre1", "solid.box", {**BARRE, "corner": [-10, -10, -400]})
    b2 = m.composant("Barre2", "solid.box", {**BARRE, "corner": [-10, -10, -800]})
    m.liaison("L01_pivot", "revolute", bati, [0, 0, 0], b1, [0, 0, 0], z=Y)
    m.liaison("L12_pivot", "revolute", b1, [0, 0, -400], b2, [0, 0, -400], z=Y)
    m.piloter("L01_pivot", 60.0)
    m.piloter("L12_pivot", 60.0)
    m.enregistrer_reponses("pose1")
    m.enregistrer_maquette()


def reducteur(canal: CanalSolidCraft) -> None:
    m = Maquette(canal, "reducteur")
    m.nouveau()
    bati = m.composant(
        "Bati",
        "solid.box",
        {"length": 200, "width": 120, "height": 10, "corner": [-60, -60, -10]},
        fixe=True,
    )
    r1 = m.composant("Roue1", "solid.cylinder", {"radius": 20, "height": 10, "base": [0, 0, 0]})
    r2 = m.composant("Roue2", "solid.cylinder", {"radius": 60, "height": 10, "base": [80, 0, 0]})
    m.liaison("L1_pivot", "revolute", bati, [0, 0, 0], r1, [0, 0, 0])
    m.liaison("L2_pivot", "revolute", bati, [80, 0, 0], r2, [80, 0, 0])
    m.exe("joint.gear", {"a": "L1_pivot", "b": "L2_pivot", "ra": 20, "rb": 60})  # Z1 = 20, Z2 = 60
    m.enregistrer_reponses("pose0")
    m.enregistrer_maquette()


def vis_ecrou(canal: CanalSolidCraft) -> None:
    m = Maquette(canal, "vis_ecrou")
    m.nouveau()
    bati = m.composant(
        "Bati",
        "solid.box",
        {"length": 200, "width": 120, "height": 10, "corner": [-100, -60, -10]},
        fixe=True,
    )
    vis = m.composant("Vis", "solid.cylinder", {"radius": 5, "height": 100, "base": [0, 0, 0]})
    ecrou = m.composant(
        "Ecrou", "solid.box", {"length": 20, "width": 20, "height": 10, "center": [0, 0, 35]}
    )
    m.liaison("L_vis_pivot", "revolute", bati, [0, 0, 0], vis, [0, 0, 0])
    m.liaison("L_ecrou_glissiere", "slider", bati, [0, 0, 35], ecrou, [0, 0, 35])
    m.exe("joint.screw", {"a": "L_vis_pivot", "b": "L_ecrou_glissiere", "pitch": 5})  # p = 5 mm
    m.enregistrer_reponses("pose0")
    m.enregistrer_maquette()


CAS = {
    "pendule_simple": pendule_simple,
    "pendule_double": pendule_double,
    "reducteur": reducteur,
    "vis_ecrou": vis_ecrou,
}


def main(noms: list[str]) -> None:
    canal = CanalSolidCraft(port=7878)
    for nom in noms or list(CAS):
        CAS[nom](canal)
        print("construit :", nom)
    canal.fermer()


if __name__ == "__main__":
    main(sys.argv[1:])
