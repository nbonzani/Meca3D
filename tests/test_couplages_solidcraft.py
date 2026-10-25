# SPDX-License-Identifier: GPL-3.0-or-later
"""Raccord R2 : lecture des couplages SolidCraft (`joint.list.links`, EX-04, EX-11, EX-14).

Données réelles du lot 1b (tests/fixtures/couplages/, réponses enregistrées de joint.list et
component.list, sans chemin ni jeton). Seuls les composants de `component.properties` et l'URDF,
non enregistrés pour ces maquettes, sont synthétisés par `_etude`.
"""

import copy
import json
import math
from pathlib import Path
from typing import Any

import pytest

from meca3d.cao.solidcraft import etude_depuis_reponses, lire_couplages
from meca3d.modele.couplage import Engrenage, PignonCremaillere, SensEngrenage, VisEcrou
from meca3d.modele.liaison import Statut, TypeLiaison

DOSSIER = Path(__file__).parent / "fixtures" / "couplages"


def _json(nom: str) -> Any:
    return json.loads((DOSSIER / nom).read_text(encoding="utf-8"))


def _etude(maquette: str):
    """Etude lue depuis les réponses enregistrées ; propriétés et URDF synthétiques."""
    joint_list = _json(f"{maquette}_joint_list.json")
    component_list = _json(f"{maquette}_component_list.json")
    occurrences = [
        o
        for c in component_list["components"]
        if c.get("parent") is None
        for o in c["children"]
        if o.get("parent") == c["id"]
    ]
    proprietes = {
        str(o["component"]): {
            "name": o["name"].rsplit(":", 1)[0],
            "total": {"mass_g": 100.0, "center_of_mass": [0.0, 0.0, 0.0]},
        }
        for o in occurrences
    }
    liens = "".join(
        f'<link name="{p["name"]}"><inertial><origin xyz="0 0 0" rpy="0 0 0"/>'
        '<mass value="0.1"/><inertia ixx="1e-4" ixy="0" ixz="0" iyy="1e-4" iyz="0" izz="1e-4"/>'
        "</inertial></link>"
        f'<joint name="j_{p["name"]}" type="fixed"><parent link="base_link"/>'
        f'<child link="{p["name"]}"/><origin xyz="0 0 0" rpy="0 0 0"/></joint>'
        for p in proprietes.values()
    )
    urdf = f'<robot name="m"><link name="base_link"/>{liens}</robot>'
    return etude_depuis_reponses(joint_list, component_list, proprietes, urdf, 1)


def _noms(joint_list: dict[str, Any]) -> dict[int, str]:
    return {j["id"]: j["name"] for j in joint_list["joints"]}


def test_ex14_lecture_engrenage_exterieur() -> None:
    joint_list = _json("reducteur_joint_list.json")
    lecture = lire_couplages(joint_list, _noms(joint_list))
    assert len(lecture.couplages) == 1
    c = lecture.couplages[0]
    assert isinstance(c, Engrenage)
    assert (c.liaison_1, c.liaison_2) == ("L1_pivot", "L2_pivot")
    assert c.k == pytest.approx(20.0 / 60.0, rel=1e-12)  # ra/rb, rapport −1/3 dans joint.list
    assert c.sens is SensEngrenage.EXTERIEUR
    assert c.rendement == 1.0
    assert lecture.avertissements == []


def test_ex14_lecture_engrenage_interieur_inverse_et_texte() -> None:
    variantes = _json("gear_variantes_links.json")
    noms = {1: "L1_pivot", 2: "L2_pivot"}
    for cle, sens in (
        ("exterieur", SensEngrenage.EXTERIEUR),
        ("interieur", SensEngrenage.INTERIEUR),
        ("exterieur_reverse", SensEngrenage.INTERIEUR),  # ratio +1/3 : engrenage de signe +
        ("depuis_dents_texte", SensEngrenage.EXTERIEUR),  # ra, rb saisis comme texte "20", "60"
    ):
        (c,) = lire_couplages({"links": variantes[cle]}, noms).couplages
        assert isinstance(c, Engrenage)
        assert c.sens is sens, cle
        assert c.k == pytest.approx(1.0 / 3.0, rel=1e-12), cle


def test_ex14_lecture_pignon_cremaillere() -> None:
    joint_list = _json("cremaillere_joint_list.json")
    (c,) = lire_couplages(joint_list, _noms(joint_list)).couplages
    assert isinstance(c, PignonCremaillere)
    assert (c.liaison_1, c.liaison_2) == ("L_pignon", "L_cremaillere")
    assert c.r == pytest.approx(0.020, rel=1e-12)  # radius = 20 mm


def test_ex14_lecture_pignon_cremaillere_ordre_inverse() -> None:
    """a = crémaillère, b = pignon : l'unité du lien est « deg » ; les liaisons sont remises dans
    l'ordre (pignon, crémaillère). Lien dérivé de la réponse réelle (a et b permutés)."""
    joint_list = copy.deepcopy(_json("cremaillere_joint_list.json"))
    lien = joint_list["links"][0]
    lien["a"], lien["b"], lien["unit"] = 2, 1, "deg"
    lien["ratio"] = 1.0 / lien["ratio"]
    (c,) = lire_couplages(joint_list, _noms(joint_list)).couplages
    assert isinstance(c, PignonCremaillere)
    assert (c.liaison_1, c.liaison_2) == ("L_pignon", "L_cremaillere")
    assert c.r == pytest.approx(0.020, rel=1e-12)


def test_ex14_lecture_vis_ecrou_pivot_et_glissiere() -> None:
    joint_list = _json("vis_ecrou_joint_list.json")
    (c,) = lire_couplages(joint_list, _noms(joint_list)).couplages
    assert isinstance(c, VisEcrou)
    assert (c.liaison_1, c.liaison_2) == ("L_vis_pivot", "L_ecrou_glissiere")
    assert c.p == pytest.approx(0.005, rel=1e-12)  # pitch = 5 mm


def test_ex11_cylindrical_couple_screw_propose_helicoidale() -> None:
    """Une seule liaison cylindrique (a = b, ia = 0, ib = 1) couplée par screw : hélicoïdale de
    pas 5 mm, sans couplage supplémentaire."""
    joint_list = _json("vis_ecrou_cyl_joint_list.json")
    lecture = lire_couplages(joint_list, _noms(joint_list))
    assert lecture.couplages == []
    assert lecture.pas_helicoidales == {"L_helicoidale": pytest.approx(0.005, rel=1e-12)}
    etude = _etude("vis_ecrou_cyl")
    liaison = etude.liaison("L_helicoidale")
    assert liaison.type_sc == "cylindrical"
    assert liaison.couplage_screw is True
    assert liaison.proposition is TypeLiaison.HELICOIDALE
    assert liaison.type is TypeLiaison.HELICOIDALE
    assert liaison.statut is Statut.PROPOSEE
    assert liaison.pas == pytest.approx(0.005, rel=1e-12)
    assert etude.couplages == []


def test_ex14_etude_importee_porte_les_couplages() -> None:
    etude = _etude("reducteur")
    assert [type(c) for c in etude.couplages] == [Engrenage]
    assert math.isclose(etude.couplages[0].k, 1.0 / 3.0, rel_tol=1e-12)  # type: ignore[union-attr]
    etude = _etude("cremaillere")
    assert [type(c) for c in etude.couplages] == [PignonCremaillere]
    etude = _etude("vis_ecrou")
    assert [type(c) for c in etude.couplages] == [VisEcrou]
    assert etude.couplages[0].liaison_1 in {x.nom for x in etude.liaisons}


def test_ex14_sans_couplage_liste_vide() -> None:
    joint_list = _json("reducteur_joint_list.json")
    joint_list = {**joint_list, "links": []}
    lecture = lire_couplages(joint_list, _noms(joint_list))
    assert lecture.couplages == []
    assert lecture.pas_helicoidales == {}


def test_ex14_lien_sur_liaison_non_importee_signale() -> None:
    joint_list = _json("reducteur_joint_list.json")
    lecture = lire_couplages(joint_list, {1: "L1_pivot"})  # la liaison 2 n'est pas importée
    assert lecture.couplages == []
    assert len(lecture.avertissements) == 1
    assert "non importé" in lecture.avertissements[0]


def test_ex14_pas_a_gauche_signale_et_non_importe() -> None:
    """reverse sur un screw : pas à gauche, non pris en charge (le modèle exige p > 0)."""
    joint_list = copy.deepcopy(_json("vis_ecrou_joint_list.json"))
    joint_list["links"][0]["coupling"]["reverse"] = True
    lecture = lire_couplages(joint_list, _noms(joint_list))
    assert lecture.couplages == []
    assert any("non importé" in m and "reverse" in m for m in lecture.avertissements)


def test_ex14_type_de_couplage_inconnu_signale() -> None:
    joint_list = copy.deepcopy(_json("reducteur_joint_list.json"))
    joint_list["links"][0]["coupling"]["type"] = "cam"
    lecture = lire_couplages(joint_list, _noms(joint_list))
    assert lecture.couplages == []
    assert any("cam" in m for m in lecture.avertissements)
