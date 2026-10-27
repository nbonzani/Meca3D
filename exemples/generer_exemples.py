# SPDX-License-Identifier: GPL-3.0-or-later
"""Génère les études d'exemple livrées avec Meca3D (dossier `exemples/`).

Usage : uv run python exemples/generer_exemples.py

Chaque étude part des réponses RÉELLES de SolidCraft enregistrées sous `tests/fixtures/<cas>/`
(même chemin que l'import) ; elle est complète : liaisons validées, lois d'entrée, actions,
capteurs et réglages. Les maquettes correspondantes sont copiées dans `exemples/maquettes/`.
"""

import json
import shutil
from pathlib import Path
from typing import Any

from meca3d.cao.solidcraft import etude_depuis_reponses
from meca3d.modele.actions import ActionExterieure, LoiEntree, NatureAction, Pesanteur, Pilote
from meca3d.modele.capteurs import BaseCapteur, CapteurLiaison, CapteurPoint
from meca3d.modele.etude import Etude, Reglages, ecrire_etude
from meca3d.modele.liaison import TypeLiaison

RACINE = Path(__file__).resolve().parents[1]
EXEMPLES = RACINE / "exemples"
FIXTURES = RACINE / "tests" / "fixtures"
MAQUETTES = {
    "bielle_manivelle": RACINE / "prototypes" / "sonde_solidcraft" / "export",
    "pendule_simple": FIXTURES / "maquettes",
    "pendule_double": FIXTURES / "maquettes",
    "reducteur": FIXTURES / "maquettes",
    "vis_ecrou": FIXTURES / "maquettes",
}


def rampe(omega: float, montee: float = 0.2) -> str:
    """Angle θ(t) (rad) : montée en vitesse (cosinus relevé) jusqu'à ω, puis ω constant."""
    return (
        f"Piecewise(({omega / 2!r}*(t - {montee!r}/pi*sin(pi*t/{montee!r})), t < {montee!r}), "
        f"({omega / 2 * montee!r} + {omega!r}*(t - {montee!r}), True))"
    )


def importer(cas: str, etiquette: str) -> Etude:
    dossier = FIXTURES / cas / "solidcraft"

    def lire(nom: str) -> Any:
        return json.loads((dossier / f"{nom}_{etiquette}.json").read_text(encoding="utf-8"))

    urdf = (dossier / f"export_{etiquette}" / f"{cas}.urdf").read_text(encoding="utf-8")
    return etude_depuis_reponses(
        lire("joint_list"),
        lire("component_list"),
        lire("component_properties"),
        urdf,
        lire("document_inspect")["revision"],
    )


def valider(etude: Etude) -> Etude:
    for liaison in etude.liaisons:
        liaison.valider()
    return etude


def bielle_manivelle() -> Etude:
    """Cas de référence EX-40 : linéaire annulaire d'axe z en B (isostatique), ω = 20 rad/s."""
    etude = importer("bielle", "theta00")
    etude.liaison("L23_rotule").type = TypeLiaison.LINEAIRE_ANNULAIRE
    etude.liaison("L23_rotule").reorienter_axe((0.0, 0.0, 1.0))
    valider(etude)
    etude.pilotes = [Pilote(liaison="L01_pivot", loi=LoiEntree(rampe(20.0)))]
    etude.pesanteur = Pesanteur(vecteur=(0.0, -9.81, 0.0))
    etude.reglages = Reglages(duree=1.0, nb_pas=4000, periode_ecriture=0.002)
    etude.capteurs = [
        CapteurPoint("B_piston", "Piston", (0.4, 0.0, 0.0), "Bati", BaseCapteur.MONDE),
        CapteurPoint("A_bielle_sur_manivelle", "Bielle", (0.1, 0.0, 0.0), "Manivelle"),
        CapteurLiaison("T_L01", "L01_pivot"),
        CapteurLiaison("T_L12", "L12_pivot"),
        CapteurLiaison("T_L30", "L30_glissiere"),
    ]
    return etude


def pendule_simple() -> Etude:
    """Barre d'acier 400 × 20 × 20 mm lâchée à 30° : oscillations libres (T = 1,054 s)."""
    etude = valider(importer("pendule_simple", "theta30"))
    etude.reglages = Reglages(duree=3.0, nb_pas=3000, periode_ecriture=0.005)
    bout = 2.0 * etude.solide("Barre").cdg - etude.liaison("L01_pivot").centre
    etude.capteurs = [
        CapteurPoint("Bout_barre", "Barre", tuple(float(x) for x in bout), "Bati"),
        CapteurLiaison("T_L01", "L01_pivot"),
    ]
    return etude


def pendule_double() -> Etude:
    """Deux barres lâchées à 60° / 60° : mouvement libre à deux mobilités (m = 2)."""
    etude = valider(importer("pendule_double", "pose1"))
    etude.reglages = Reglages(duree=3.0, nb_pas=3000, periode_ecriture=0.005)
    bout = 2.0 * etude.solide("Barre2").cdg - etude.liaison("L12_pivot").centre
    etude.capteurs = [
        CapteurPoint("Bout_barre2", "Barre2", tuple(float(x) for x in bout), "Bati"),
        CapteurLiaison("T_L01", "L01_pivot"),
        CapteurLiaison("T_L12", "L12_pivot"),
    ]
    return etude


def reducteur() -> Etude:
    """Engrenage Z₁ = 20 / Z₂ = 60 lu dans SolidCraft ; ω_e = 30 rad/s, couple résistant 1 N·m."""
    etude = valider(importer("reducteur", "pose0"))
    etude.pesanteur.actif = False  # axes verticaux : la pesanteur ne travaille pas
    etude.pilotes = [Pilote(liaison="L1_pivot", loi=LoiEntree(rampe(30.0)))]
    # Roue2 tourne à −10 rad/s autour de z : un couple +z s'oppose au mouvement
    etude.actions = [ActionExterieure("C_resistant", "Roue2", NatureAction.COUPLE, (0.0, 0.0, 1.0))]
    etude.reglages = Reglages(duree=1.0, nb_pas=1000, periode_ecriture=0.002)
    etude.capteurs = [
        CapteurPoint("Point_jante_roue2", "Roue2", (0.14, 0.0, 0.005), "Bati"),
        CapteurLiaison("T_L1", "L1_pivot"),
        CapteurLiaison("T_L2", "L2_pivot"),
    ]
    return etude


def vis_ecrou() -> Etude:
    """Vis de pas 5 mm lue dans SolidCraft ; ω = 10 rad/s, effort résistant 100 N sur l'écrou."""
    etude = valider(importer("vis_ecrou", "pose0"))
    etude.pesanteur.actif = False
    etude.pilotes = [Pilote(liaison="L_vis_pivot", loi=LoiEntree(rampe(10.0)))]
    etude.actions = [
        ActionExterieure(
            "F_resistant", "Ecrou", NatureAction.FORCE, (0.0, 0.0, -100.0), point=(0.0, 0.0, 0.035)
        )
    ]
    etude.reglages = Reglages(duree=1.0, nb_pas=1000, periode_ecriture=0.002)
    etude.capteurs = [
        CapteurPoint("Centre_ecrou", "Ecrou", (0.0, 0.0, 0.035), "Bati"),
        CapteurLiaison("T_vis", "L_vis_pivot"),
        CapteurLiaison("T_ecrou", "L_ecrou_glissiere"),
    ]
    return etude


EXEMPLES_ETUDES = {
    "bielle_manivelle": bielle_manivelle,
    "pendule_simple": pendule_simple,
    "pendule_double": pendule_double,
    "reducteur": reducteur,
    "vis_ecrou": vis_ecrou,
}


def main() -> None:
    (EXEMPLES / "maquettes").mkdir(parents=True, exist_ok=True)
    for nom, fabrique in EXEMPLES_ETUDES.items():
        etude = fabrique()
        etude.maquette = f"maquettes/{nom}.solidcraft"
        ecrire_etude(etude, EXEMPLES / f"{nom}.meca3d")
        shutil.copyfile(MAQUETTES[nom] / f"{nom}.solidcraft", EXEMPLES / etude.maquette)
        print(f"{nom}.meca3d : {len(etude.liaisons)} liaisons, {len(etude.capteurs)} capteurs")


if __name__ == "__main__":
    main()
