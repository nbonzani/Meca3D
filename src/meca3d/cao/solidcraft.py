# SPDX-License-Identifier: GPL-3.0-or-later
"""Lecture de la maquette SolidCraft vers une Etude (EX-03 à EX-06).

`etude_depuis_reponses` est PURE sur les réponses du canal de contrôle (lot 2) ; `importer`,
`revision_a_change` et `reimporter` (lot 5) les obtiennent par `cao.canal`.
Toutes les conversions mm / g / deg passent par `unites`, à cette seule porte d'entrée.
"""

import hashlib
import json
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

import numpy as np

from meca3d import unites
from meca3d.cao.canal import CanalSolidCraft
from meca3d.cao.urdf import lire_urdf
from meca3d.modele.couplage import (
    Couplage,
    Engrenage,
    ErreurCouplage,
    PignonCremaillere,
    SensEngrenage,
    VisEcrou,
)
from meca3d.modele.etude import Etude
from meca3d.modele.liaison import Liaison
from meca3d.modele.solide import Solide

FORMAT_SUPPORTE = "solidcraft/26"  # SolidCraft 0.15.0 (EX-03)


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


def _premier_niveau(component_list: dict[str, Any]) -> list[dict[str, Any]]:
    """Occurrences de premier niveau : enfants de la racine dont le parent est la racine."""
    racine = next((c for c in component_list["components"] if c.get("parent") is None), None)
    if racine is None:
        raise ErreurImport("component.list : composant racine introuvable.")
    return [o for o in racine["children"] if o.get("parent", racine["id"]) == racine["id"]]


def _noms_occurrences(component_list: dict[str, Any]) -> dict[int, str]:
    """Nom de toute occurrence connue (tous niveaux), pour nommer une sous-occurrence."""
    noms: dict[int, str] = {}
    for composant in component_list["components"]:
        for occ in composant["children"]:
            noms[occ["id"]] = occ["name"]
    return noms


class _LienNonPris(Exception):
    """Lien de couplage SolidCraft non pris en charge (message destiné à l'élève)."""


@dataclass
class LectureCouplages:
    """Couplages lus dans `joint.list.links` (R2, EX-14) : couplages entre deux liaisons, pas des
    liaisons cylindriques couplées par `joint.screw` (hélicoïdales, EX-11) par nom de liaison, et
    messages des liens non importés."""

    couplages: list[Couplage] = field(default_factory=list)
    pas_helicoidales: dict[str, float] = field(default_factory=dict)
    avertissements: list[str] = field(default_factory=list)


def lire_couplages(joint_list: dict[str, Any], noms: Mapping[int, str]) -> LectureCouplages:
    """Traduit `joint.list.links` en couplages de l'étude (Q2, D14, RESULTATS_1b § Q2).

    `noms` : nom des liaisons importées par identifiant SolidCraft. Le `ratio` par degré et les
    `values` ne sont pas lus : seuls `ra`, `rb` (rayons ou nombres de dents, seul leur rapport
    compte, parfois saisis comme texte), `pitch` et `radius` (mm, convertis par `unites`) servent.
    Le signe d'un engrenage est celui du `ratio` (négatif : extérieur ; positif : intérieur ou
    `reverse`). Un lien non pris en charge (type inconnu, `reverse` d'une vis ou d'une crémaillère,
    liaison non importée) est signalé et ignoré.
    """
    lecture = LectureCouplages()
    vus: dict[str, int] = {}

    def nom_unique(base: str) -> str:
        vus[base] = vus.get(base, 0) + 1
        return base if vus[base] == 1 else f"{base} ({vus[base]})"

    for lien in joint_list.get("links", []):
        coupling = lien.get("coupling", {})
        genre = str(coupling.get("type"))
        noms_lien = [noms.get(lien.get("a", -1)), noms.get(lien.get("b", -1))]
        if None in noms_lien:
            lecture.avertissements.append(
                f"Couplage « {genre} » non importé : il vise une liaison non importée "
                f"(identifiants {lien.get('a')} et {lien.get('b')})."
            )
            continue
        n1, n2 = str(noms_lien[0]), str(noms_lien[1])
        try:
            if genre == "gear":
                k = float(coupling["ra"]) / float(coupling["rb"])
                interieur = float(lien["ratio"]) > 0.0
                sens = SensEngrenage.INTERIEUR if interieur else SensEngrenage.EXTERIEUR
                lecture.couplages.append(
                    Engrenage(nom_unique(f"Engrenage {n1}-{n2}"), n1, n2, k, sens)
                )
            elif genre == "rack_pinion":
                if coupling.get("reverse"):
                    raise _LienNonPris("reverse (sens inverse) non pris en charge")
                if lien.get("unit") == "deg":  # a = crémaillère, b = pignon
                    n1, n2 = n2, n1
                r = unites.mm_vers_m(float(coupling["radius"]))
                lecture.couplages.append(
                    PignonCremaillere(nom_unique(f"Pignon-crémaillère {n1}-{n2}"), n1, n2, r)
                )
            elif genre == "screw":
                if coupling.get("reverse"):
                    raise _LienNonPris("reverse (pas à gauche) non pris en charge")
                p = unites.mm_vers_m(float(coupling["pitch"]))
                if lien["a"] == lien["b"]:  # liaison cylindrique : angle (ia) et distance (ib)
                    lecture.pas_helicoidales[n1] = p
                else:
                    lecture.couplages.append(
                        VisEcrou(nom_unique(f"Vis-écrou {n1}-{n2}"), n1, n2, p)
                    )
            else:
                raise _LienNonPris(f"type de couplage « {genre} » inconnu")
        except _LienNonPris as e:
            lecture.avertissements.append(f"Couplage « {genre} » non importé : {e}.")
        except (KeyError, TypeError, ValueError, ZeroDivisionError, ErreurCouplage) as e:
            lecture.avertissements.append(
                f"Couplage « {genre} » non importé : lien illisible ({type(e).__name__} : {e})."
            )
    return lecture


def etude_depuis_reponses(
    joint_list: dict[str, Any],
    component_list: dict[str, Any],
    component_properties: dict[str, Any],
    urdf_texte: str,
    revision: int,
) -> Etude:
    return _construire(joint_list, component_list, component_properties, urdf_texte, revision)[0]


def _construire(
    joint_list: dict[str, Any],
    component_list: dict[str, Any],
    component_properties: dict[str, Any],
    urdf_texte: str,
    revision: int,
) -> tuple[Etude, list[tuple[str, str]], list[str]]:
    """Etude, (nom, message) des liaisons non importées (sous-occurrences, EX-04) et messages
    des couplages non importés (R2)."""
    occurrences = _premier_niveau(component_list)
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
        r_occ, t_occ = unites.rotation_translation(occ["transform"])
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
                repere_rotation=r_occ,
                repere_origine=t_occ,
            )
        )

    liaisons: list[Liaison] = []
    ignorees: list[tuple[str, str]] = []
    noms_connus = _noms_occurrences(component_list)
    importables = {
        j["id"]: j["name"]
        for j in joint_list["joints"]
        if not j.get("suppressed") and all(j[c] in nom_par_occurrence for c in ("a", "b"))
    }
    lecture = lire_couplages(joint_list, importables)
    for joint in joint_list["joints"]:
        if joint.get("suppressed"):
            continue
        hors_niveau = [c for c in ("a", "b") if joint[c] not in nom_par_occurrence]
        if hors_niveau:
            occ = joint[hors_niveau[0]]
            ignorees.append(
                (
                    joint["name"],
                    f"Liaison « {joint['name']} » non importée : elle vise la sous-occurrence "
                    f"« {noms_connus.get(occ, occ)} » ; seules les occurrences de premier "
                    "niveau sont des classes d'équivalence.",
                )
            )
            continue
        liaisons.append(
            Liaison(
                nom=joint["name"],
                type_sc=joint["type"],
                solide_a=nom_par_occurrence[joint["a"]],
                solide_b=nom_par_occurrence[joint["b"]],
                centre=unites.mm_vers_m(np.array(joint["frame_a"]["origin"], dtype=float)),
                axe_sc=np.array(joint["frame_a"]["z"], dtype=float),
                valeur_pose=_valeur_articulaire(joint),
                couplage_screw=joint["name"] in lecture.pas_helicoidales,
                pas=lecture.pas_helicoidales.get(joint["name"]),
            )
        )
    etude = Etude(
        solides=solides,
        liaisons=liaisons,
        revision=int(revision),
        couplages=lecture.couplages,
    )
    return etude, ignorees, lecture.avertissements


@dataclass
class EtudeImportee(Etude):
    """Etude issue d'un import en direct, avec les messages non bloquants à afficher."""

    avertissements: list[str] = field(default_factory=list)
    liaisons_ignorees: list[str] = field(default_factory=list)
    signature: str = ""  # signature de structure à l'import (EX-06), non sérialisée par Etude


def signature_structure(
    joint_list: dict[str, Any],
    component_list: dict[str, Any],
    component_properties: dict[str, Any],
) -> str:
    """Empreinte stable de la STRUCTURE de la maquette (EX-06) : sha256 d'un JSON canonique.

    Composants, occurrences (id, composant, parent, fixe), liaisons (nom, type, a, b, supprimée),
    couplages (`links`) et masses (arrondies à 1e-6 g). Aucune pose : une animation change les
    poses et la révision, pas la structure.
    """
    composants = sorted([c["id"], c["name"], c.get("parent")] for c in component_list["components"])
    occurrences = sorted(
        [o["id"], o["component"], o.get("parent"), bool(o["grounded"]), o["name"]]
        for c in component_list["components"]
        for o in c["children"]
    )
    liaisons = sorted(
        [j["name"], j["type"], j["a"], j["b"], bool(j.get("suppressed"))]
        for j in joint_list["joints"]
    )
    couplages = sorted(
        json.dumps(lien, sort_keys=True, separators=(",", ":"))
        for lien in joint_list.get("links", [])
    )
    masses = sorted(
        [cle, f"{float(p['total']['mass_g']):.6f}"] for cle, p in component_properties.items()
    )
    canonique = json.dumps(
        {
            "composants": composants,
            "occurrences": occurrences,
            "liaisons": liaisons,
            "couplages": couplages,
            "masses": masses,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonique.encode("utf-8")).hexdigest()


def _lire_structure(
    canal: CanalSolidCraft,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    joint_list = canal.executer("joint.list")
    component_list = canal.executer("component.list")
    proprietes: dict[str, Any] = {}
    for occ in _premier_niveau(component_list):
        cle = str(occ["component"])
        if cle not in proprietes:
            proprietes[cle] = canal.executer(
                "component.properties", {"component": occ["component"]}
            )
    return joint_list, component_list, proprietes


def importer(canal: CanalSolidCraft, dossier_temporaire: Path | None = None) -> EtudeImportee:
    """Lit la maquette ouverte (EX-04) dans sa pose courante (EX-05), révision mémorisée (EX-06).

    Les exports URDF et JSON sont écrits dans un sous-dossier temporaire de `dossier_temporaire`
    (défaut : dossier temporaire du système), supprimé en sortie.
    """
    inspection = canal.requete("document.inspect")
    revision = int(inspection["revision"])
    joint_list, component_list, proprietes = _lire_structure(canal)
    with tempfile.TemporaryDirectory(prefix="meca3d_", dir=dossier_temporaire) as dossier:
        base = Path(dossier) / "maquette"
        canal.executer("file.export", {"path": str(base.with_suffix(".urdf")), "format": "urdf"})
        canal.executer("file.export", {"path": str(base.with_suffix(".json")), "format": "json"})
        urdf = base.with_suffix(".urdf").read_text(encoding="utf-8")
        export = json.loads(base.with_suffix(".json").read_text(encoding="utf-8"))
    etude, ignorees, avertissements_couplages = _construire(
        joint_list, component_list, proprietes, urdf, revision
    )
    avertissements: list[str] = []
    recu = export.get("format") if isinstance(export, dict) else None
    if recu != FORMAT_SUPPORTE:
        avertissements.append(
            f"Format SolidCraft « {recu if recu is not None else 'absent'} » reçu, "
            f"« {FORMAT_SUPPORTE} » attendu (SolidCraft 0.15.0) : l'import continue, "
            "mais les résultats sont à vérifier."
        )
    avertissements.extend(message for _, message in ignorees)
    avertissements.extend(avertissements_couplages)
    return EtudeImportee(
        solides=etude.solides,
        liaisons=etude.liaisons,
        couplages=etude.couplages,
        maquette=str(inspection.get("name", "")),
        revision=etude.revision,
        avertissements=avertissements,
        liaisons_ignorees=[nom for nom, _ in ignorees],
        signature=signature_structure(joint_list, component_list, proprietes),
    )


def structure_a_change(canal: CanalSolidCraft, etude: Etude) -> bool:
    """EX-06 : la structure de la maquette diffère de celle mémorisée à l'import.

    Une étude sans signature (non issue de `importer`) est considérée comme modifiée. La
    `revision` de document.inspect n'est pas utilisée : elle augmente à chaque animation.
    """
    memorisee = getattr(etude, "signature", "")
    if not memorisee:
        return True
    return signature_structure(*_lire_structure(canal)) != memorisee


def reimporter(
    canal: CanalSolidCraft, etude_ancienne: Etude, dossier_temporaire: Path | None = None
) -> EtudeImportee:
    """Réimporte la maquette en conservant les choix de l'élève (EX-06).

    Pour les liaisons de même nom et de même type SolidCraft : type retenu, statut, axe réorienté
    et direction. Pilotes, pesanteur et réglages sont conservés ; un pilote dont la liaison a
    disparu est abandonné avec un avertissement. `etude_ancienne` n'est jamais modifiée.
    """
    nouvelle = importer(canal, dossier_temporaire)
    anciennes = {x.nom: x for x in etude_ancienne.liaisons}
    for liaison in nouvelle.liaisons:
        ancienne = anciennes.get(liaison.nom)
        if ancienne is None:
            continue
        if ancienne.type_sc != liaison.type_sc:
            nouvelle.avertissements.append(
                f"Liaison « {liaison.nom} » : son type SolidCraft a changé "
                f"({ancienne.type_sc} -> {liaison.type_sc}), le choix précédent est abandonné."
            )
            continue
        liaison.type = ancienne.type
        liaison.statut = ancienne.statut
        assert ancienne.axe is not None
        if not np.allclose(ancienne.axe, ancienne.axe_sc, atol=1e-12):
            liaison.reorienter_axe(ancienne.axe)
        if ancienne.direction is not None:
            liaison.direction = ancienne.direction.copy()
        liaison.frottement = ancienne.frottement
        liaison.rayon_axe = ancienne.rayon_axe
        liaison.epsilon = ancienne.epsilon
        if liaison.pas is None:
            liaison.pas = ancienne.pas
    noms = {x.nom for x in nouvelle.liaisons}
    deja = {c.nom for c in nouvelle.couplages}
    for i, couplage in enumerate(nouvelle.couplages):  # le rendement choisi est conservé
        ancien = next((c for c in etude_ancienne.couplages if c.nom == couplage.nom), None)
        if ancien is not None:
            nouvelle.couplages[i] = replace(couplage, rendement=ancien.rendement)
    nouvelle.couplages.extend(  # couplages saisis dans Meca3D dont les liaisons existent encore
        c
        for c in etude_ancienne.couplages
        if c.nom not in deja and c.liaison_1 in noms and c.liaison_2 in noms
    )
    for pilote in etude_ancienne.pilotes:
        if pilote.liaison in noms:
            nouvelle.pilotes.append(pilote)
        else:
            nouvelle.avertissements.append(
                f"Pilote de la liaison « {pilote.liaison} » abandonné : liaison disparue."
            )
    nouvelle.pesanteur = etude_ancienne.pesanteur
    nouvelle.reglages = etude_ancienne.reglages
    return nouvelle
