# SPDX-License-Identifier: GPL-3.0-or-later
"""Lecture de la maquette SolidCraft vers une Etude (EX-04, EX-05).

Lot 2 : fonction PURE sur les réponses du canal de contrôle (le client socket arrive au lot 5).
Toutes les conversions mm / g / deg passent par `unites`, à cette seule porte d'entrée.
"""

from typing import Any

import numpy as np

from meca3d import unites
from meca3d.cao.urdf import lire_urdf
from meca3d.modele.etude import Etude
from meca3d.modele.liaison import Liaison
from meca3d.modele.solide import Solide


class ErreurImport(ValueError):
    """Réponses SolidCraft inexploitables ; le message nomme l'élément en cause."""


def _nom_solide(nom_occurrence: str, tous: list[str]) -> str:
    """« Bielle:1 » -> « Bielle » quand le nom abrégé est unique."""
    court = nom_occurrence.rsplit(":", 1)[0]
    return court if sum(1 for n in tous if n.rsplit(":", 1)[0] == court) == 1 else nom_occurrence


def _valeur_articulaire(joint: dict[str, Any]) -> float | None:
    """Coordonnée de la liaison pilotable (angle ou distance) en SI ; None pour les autres types."""
    if joint["type"] not in ("revolute", "slider"):
        return None
    valeur = joint["values"][0]
    unite = valeur.get("unit")
    if unite == "deg":
        return unites.deg_vers_rad(float(valeur["value"]))
    if unite == "mm":
        return unites.mm_vers_m(float(valeur["value"]))
    return float(valeur["value"])


def etude_depuis_reponses(
    joint_list: dict[str, Any],
    component_list: dict[str, Any],
    component_properties: dict[str, Any],
    urdf_texte: str,
    revision: int,
) -> Etude:
    racine = next((c for c in component_list["components"] if c.get("parent") is None), None)
    if racine is None:
        raise ErreurImport("component.list : composant racine introuvable.")
    occurrences = racine["children"]
    noms_occ = [o["name"] for o in occurrences]
    inerties = lire_urdf(urdf_texte)

    solides: list[Solide] = []
    nom_par_occurrence: dict[int, str] = {}
    for occ in occurrences:
        nom = _nom_solide(occ["name"], noms_occ)
        nom_par_occurrence[occ["id"]] = nom
        proprietes = component_properties.get(str(occ["component"]))
        if proprietes is None:
            raise ErreurImport(f"component.properties : composant de « {occ['name']} » absent.")
        total = proprietes["total"]
        lien = inerties.get(proprietes["name"])
        if lien is None:
            raise ErreurImport(f"URDF : lien « {proprietes['name']} » (inertie) absent.")
        r_occ, _ = unites.rotation_translation(occ["transform"])
        r_ref = lien.rotation_composant
        # repère monde de référence -> repère du composant -> pose courante
        inertie = r_occ @ (r_ref.T @ lien.inertie @ r_ref) @ r_occ.T
        solides.append(
            Solide(
                nom=nom,
                fixe=bool(occ["grounded"]),
                masse=unites.g_vers_kg(float(total["mass_g"])),
                cdg=unites.mm_vers_m(np.array(total["center_of_mass"], dtype=float)),
                inertie=0.5 * (inertie + inertie.T),
            )
        )

    liaisons: list[Liaison] = []
    for joint in joint_list["joints"]:
        if joint.get("suppressed"):
            continue
        for cote in ("a", "b"):
            if joint[cote] not in nom_par_occurrence:
                raise ErreurImport(
                    f"Liaison {joint['name']} : l'occurrence {joint[cote]} "
                    "n'est pas de premier niveau."
                )
        liaisons.append(
            Liaison(
                nom=joint["name"],
                type_sc=joint["type"],
                solide_a=nom_par_occurrence[joint["a"]],
                solide_b=nom_par_occurrence[joint["b"]],
                centre=unites.mm_vers_m(np.array(joint["frame_a"]["origin"], dtype=float)),
                axe_sc=np.array(joint["frame_a"]["z"], dtype=float),
                valeur_pose=_valeur_articulaire(joint),
            )
        )
    return Etude(solides=solides, liaisons=liaisons, revision=int(revision))
