# SPDX-License-Identifier: GPL-3.0-or-later
"""Outils de test : étude de la bielle-manivelle construite depuis les réponses enregistrées."""

import json
import math
from pathlib import Path
from typing import Any

from meca3d.cao.solidcraft import etude_depuis_reponses
from meca3d.modele.actions import LoiEntree, Pesanteur, Pilote
from meca3d.modele.etude import Etude, Reglages
from meca3d.modele.liaison import TypeLiaison

DOSSIER = Path(__file__).parent / "fixtures" / "bielle" / "solidcraft"

# Loi de montée en vitesse du prototype (EX-40), en radians
LOI_MONTEE = "Piecewise((10*(t - 0.2/pi*sin(pi*t/0.2)), t < 0.2), (2 + 20*(t - 0.2), True))"


def lire_json(nom: str) -> Any:
    return json.loads((DOSSIER / nom).read_text(encoding="utf-8"))


def etude_proposee(theta: str = "00") -> Etude:
    """Étude issue du seul import : liaisons proposées, aucune validée."""
    urdf = (DOSSIER / f"export_theta{theta}" / "bielle.urdf").read_text(encoding="utf-8")
    inspection = lire_json(f"document_inspect_theta{theta}.json")
    return etude_depuis_reponses(
        lire_json(f"joint_list_theta{theta}.json"),
        lire_json(f"component_list_theta{theta}.json"),
        lire_json(f"component_properties_theta{theta}.json"),
        urdf,
        inspection["revision"],
    )


def etude_bielle(theta: str = "00", theta0_deg: float = 0.0) -> Etude:
    """Étude prête à simuler : choix de l'élève, pilote L01, pesanteur (0, −9,81, 0), 1 s, 4 000 pas."""
    etude = etude_proposee(theta)
    etude.maquette = "bielle_manivelle.solidcraft"
    etude.liaison("L23_rotule").type = TypeLiaison.LINEAIRE_ANNULAIRE
    etude.liaison("L23_rotule").reorienter_axe((0.0, 0.0, 1.0))
    for liaison in etude.liaisons:
        liaison.valider()
    texte = LOI_MONTEE if theta0_deg == 0.0 else f"{math.radians(theta0_deg)!r} + {LOI_MONTEE}"
    etude.pilotes = [Pilote(liaison="L01_pivot", loi=LoiEntree(texte))]
    etude.pesanteur = Pesanteur(vecteur=(0.0, -9.81, 0.0))
    etude.reglages = Reglages(duree=1.0, nb_pas=4000, periode_ecriture=0.002)
    return etude
