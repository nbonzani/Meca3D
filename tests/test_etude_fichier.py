# SPDX-License-Identifier: GPL-3.0-or-later
"""Fichier d'étude `.meca3d` complet (EX-60) et définitions de capteurs (EX-50, EX-51)."""

import copy
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from meca3d.modele.capteurs import (
    BaseCapteur,
    CapteurLiaison,
    CapteurPoint,
    ErreurCapteur,
    SensTorseur,
    capteur_depuis_dict,
)
from meca3d.modele.couplage import Engrenage, PignonCremaillere, SensEngrenage, VisEcrou
from outils_bielle import etude_bielle

from meca3d.modele.etude import (
    VERSION_ETUDE,
    ErreurEtude,
    Etude,
    ecrire_etude,
    lire_etude,
)
from meca3d.modele.liaison import TypeLiaison

FIXTURES = Path(__file__).parent / "fixtures" / "bielle"
FIXTURE = FIXTURES / "bielle.meca3d"
FIXTURE_V1 = FIXTURES / "bielle_v1.meca3d"


def _etude_complete() -> Etude:
    """Bielle-manivelle enrichie de tout ce que le format doit porter."""
    etude = etude_bielle("00")
    etude.validation_en_bloc = True
    etude.liaison("L01_pivot").couplage_screw = True
    etude.liaison("L01_pivot").deplacer_centre((0.01, 0.02, -0.03))
    l12 = etude.liaison("L12_pivot")
    l12.choisir(TypeLiaison.ROTULE_A_DOIGT)
    l12.definir_direction((1.0, 1.0, 0.0))
    l12.valider()
    etude.couplages = [
        Engrenage(
            "R1", "L01_pivot", "L12_pivot", k=1 / 3, sens=SensEngrenage.INTERIEUR, rendement=0.95
        ),
        PignonCremaillere("PC", "L01_pivot", "L12_pivot", r=0.02),
        VisEcrou("VE", "L12_pivot", "L01_pivot", p=0.005, rendement=0.8),
    ]
    etude.capteurs = [
        CapteurLiaison("C_L12", "L12_pivot", sens=SensTorseur.J_VERS_I, base=BaseCapteur.MONDE),
        CapteurLiaison("C_L01", "L01_pivot"),
        CapteurPoint(
            "P_B", "Piston", point=(0.4, 0.0, 0.0), solide_reference="Bati", base=BaseCapteur.MONDE
        ),
        CapteurPoint("P_A", "Bielle", point=(0.1, 0.0, 0.0), solide_reference="Manivelle"),
    ]
    return etude


@pytest.fixture
def donnees_valides() -> dict[str, Any]:
    return _etude_complete().vers_dict()


def _ecrire_json(chemin: Path, donnees: Any) -> Path:
    chemin.write_text(json.dumps(donnees), encoding="utf-8")
    return chemin


def test_ex60_version_courante() -> None:
    assert VERSION_ETUDE == 2
    assert _etude_complete().vers_dict()["version_etude"] == 2


def test_ex60_aller_retour_identique(tmp_path: Path) -> None:
    etude = _etude_complete()
    premier, second = tmp_path / "a.meca3d", tmp_path / "b.meca3d"
    ecrire_etude(etude, premier)
    relue = lire_etude(premier)
    assert relue.vers_dict() == etude.vers_dict()
    ecrire_etude(relue, second)
    assert second.read_bytes() == premier.read_bytes()


def test_ex60_contenu_relu(tmp_path: Path) -> None:
    chemin = tmp_path / "e.meca3d"
    ecrire_etude(_etude_complete(), chemin)
    e = lire_etude(chemin)
    assert e.validation_en_bloc is True
    assert e.liaison("L01_pivot").couplage_screw is True
    assert e.liaison("L01_pivot").centre.tolist() == [0.01, 0.02, -0.03]
    l12 = e.liaison("L12_pivot")
    assert l12.type is TypeLiaison.ROTULE_A_DOIGT
    assert l12.direction is not None and l12.direction.tolist() == [1.0, 1.0, 0.0]
    assert [c.nom for c in e.couplages] == ["R1", "PC", "VE"]
    assert e.couplages[0] == Engrenage(
        "R1", "L01_pivot", "L12_pivot", k=1 / 3, sens=SensEngrenage.INTERIEUR, rendement=0.95
    )
    assert [c.nom for c in e.capteurs] == ["C_L12", "C_L01", "P_B", "P_A"]
    assert e.capteurs[0] == CapteurLiaison(
        "C_L12", "L12_pivot", sens=SensTorseur.J_VERS_I, base=BaseCapteur.MONDE
    )
    assert e.pilotes[0].loi.texte == _etude_complete().pilotes[0].loi.texte
    assert e.pesanteur.vers_dict() == _etude_complete().pesanteur.vers_dict()


def test_ex60_fichier_en_json_utf8_versionne(tmp_path: Path) -> None:
    chemin = tmp_path / "e.meca3d"
    ecrire_etude(_etude_complete(), chemin)
    texte = chemin.read_bytes().decode("utf-8")
    assert json.loads(texte)["version_etude"] == VERSION_ETUDE
    assert not texte.startswith("﻿")


def test_ex60_fixture_bielle_lisible() -> None:
    etude = lire_etude(FIXTURE)
    assert [s.nom for s in etude.solides] == ["Bati", "Manivelle", "Bielle", "Piston"]
    assert len(etude.liaisons) == 4
    assert etude.couplages == []
    assert etude.capteurs == []
    assert etude.validation_en_bloc is False


def test_ex60_fixture_version_1_migree() -> None:
    brut = json.loads(FIXTURE_V1.read_text(encoding="utf-8"))
    assert brut["version_etude"] == 1
    migree = lire_etude(FIXTURE_V1)
    assert migree.vers_dict()["version_etude"] == VERSION_ETUDE
    assert migree.vers_dict() == lire_etude(FIXTURE).vers_dict()
    assert all(x.couplage_screw is False for x in migree.liaisons)


def test_ex60_migration_ne_modifie_pas_le_fichier(tmp_path: Path) -> None:
    copie = tmp_path / "v1.meca3d"
    copie.write_bytes(FIXTURE_V1.read_bytes())
    lire_etude(copie)
    assert copie.read_bytes() == FIXTURE_V1.read_bytes()


@pytest.mark.parametrize("version", [0, 3, 99, "2", None, 2.5, True, [2]])
def test_ex60_version_inconnue(
    tmp_path: Path, donnees_valides: dict[str, Any], version: Any
) -> None:
    donnees_valides["version_etude"] = version
    with pytest.raises(ErreurEtude, match="version"):
        lire_etude(_ecrire_json(tmp_path / "v.meca3d", donnees_valides))


def test_ex60_version_absente(tmp_path: Path, donnees_valides: dict[str, Any]) -> None:
    del donnees_valides["version_etude"]
    with pytest.raises(ErreurEtude, match="version"):
        lire_etude(_ecrire_json(tmp_path / "v.meca3d", donnees_valides))


Modification = Callable[[dict[str, Any]], None]


def _sans(cle: str) -> Modification:
    def modifier(d: dict[str, Any]) -> None:
        del d[cle]

    return modifier


def _fixer(chemin: tuple[Any, ...], valeur: Any) -> Modification:
    def modifier(d: dict[str, Any]) -> None:
        cible: Any = d
        for cle in chemin[:-1]:
            cible = cible[cle]
        cible[chemin[-1]] = valeur

    return modifier


MODIFICATIONS_CORROMPUES = {
    "liaisons_absentes": _sans("liaisons"),
    "couplages_absents": _sans("couplages"),
    "capteurs_absents": _sans("capteurs"),
    "solides_entier": _fixer(("solides",), 5),
    "solide_entier": _fixer(("solides", 0), 1),
    "type_inconnu": _fixer(("liaisons", 0, "type"), "liaison_magique"),
    "statut_inconnu": _fixer(("liaisons", 0, "statut"), "peut-etre"),
    "centre_court": _fixer(("liaisons", 0, "centre"), [0.0, 1.0]),
    "centre_non_fini": _fixer(("liaisons", 0, "centre"), [float("nan"), 0.0, 0.0]),
    "masse_infinie": _fixer(("solides", 1, "masse"), float("inf")),
    "axe_nul": _fixer(("liaisons", 0, "axe"), [0.0, 0.0, 0.0]),
    "reglages_texte": _fixer(("reglages", "duree"), "longtemps"),
    "revision_texte": _fixer(("revision",), "x"),
    "loi_dangereuse": _fixer(("pilotes", 0, "loi"), "__import__('os')"),
    "rendement_hors_borne": _fixer(("couplages", 0, "rendement"), 2.0),
    "couplage_genre_inconnu": _fixer(("couplages", 0, "genre"), "courroie"),
    "couplage_liaison_inconnue": _fixer(("couplages", 0, "liaison_1"), "L99"),
    "capteur_liaison_inconnue": _fixer(("capteurs", 0, "liaison"), "L99"),
    "capteur_solide_inconnu": _fixer(("capteurs", 2, "solide"), "Fantome"),
    "capteur_reference_inconnue": _fixer(("capteurs", 2, "solide_reference"), "Fantome"),
    "capteur_sens_inconnu": _fixer(("capteurs", 0, "sens"), "aller_retour"),
    "direction_colineaire": _fixer(("liaisons", 1, "direction"), [0.0, 0.0, 1.0]),
    "liaison_solide_inconnu": _fixer(("liaisons", 0, "solide_a"), "Fantome"),
    "liaisons_homonymes": lambda d: d["liaisons"].append(copy.deepcopy(d["liaisons"][0])),
    "capteurs_homonymes": lambda d: d["capteurs"].append(copy.deepcopy(d["capteurs"][0])),
    "couplages_homonymes": lambda d: d["couplages"].append(copy.deepcopy(d["couplages"][0])),
}


@pytest.mark.parametrize("cas", list(MODIFICATIONS_CORROMPUES))
def test_ex60_contenu_incoherent_refuse(
    tmp_path: Path, donnees_valides: dict[str, Any], cas: str
) -> None:
    MODIFICATIONS_CORROMPUES[cas](donnees_valides)
    with pytest.raises(ErreurEtude) as info:
        lire_etude(_ecrire_json(tmp_path / "x.meca3d", donnees_valides))
    assert str(info.value).strip() != ""


@pytest.mark.parametrize(
    "contenu",
    [b"", b"null", b"[1, 2]", b'{"version_etude": 2, "solides": [', b"\xff\xfe\x00 pas du texte"],
    ids=["vide", "null", "liste", "tronque", "binaire"],
)
def test_ex60_fichier_corrompu(tmp_path: Path, contenu: bytes) -> None:
    chemin = tmp_path / "x.meca3d"
    chemin.write_bytes(contenu)
    with pytest.raises(ErreurEtude) as info:
        lire_etude(chemin)
    assert str(info.value).strip() != ""


def test_ex60_fichier_tronque_a_mi_chemin(tmp_path: Path) -> None:
    complet = tmp_path / "complet.meca3d"
    ecrire_etude(_etude_complete(), complet)
    octets = complet.read_bytes()
    coupe = tmp_path / "coupe.meca3d"
    coupe.write_bytes(octets[: len(octets) // 2])
    with pytest.raises(ErreurEtude, match="corrompu"):
        lire_etude(coupe)


def test_ex60_fichier_absent(tmp_path: Path) -> None:
    with pytest.raises(ErreurEtude):
        lire_etude(tmp_path / "absent.meca3d")


def test_ex60_depuis_dict_ne_modifie_pas_l_entree(donnees_valides: dict[str, Any]) -> None:
    avant = copy.deepcopy(donnees_valides)
    Etude.depuis_dict(donnees_valides)
    assert donnees_valides == avant
    ancien = json.loads(FIXTURE_V1.read_text(encoding="utf-8"))
    copie = copy.deepcopy(ancien)
    Etude.depuis_dict(ancien)
    assert ancien == copie


# --- Définitions de capteurs (EX-50, EX-51) : structure seulement, aucun calcul ---


def test_ex50_capteur_de_liaison_par_defaut() -> None:
    c = CapteurLiaison("C", "L1")
    assert c.sens is SensTorseur.I_VERS_J
    assert c.base is BaseCapteur.LIAISON


def test_ex50_capteur_de_liaison_base_reference_refusee() -> None:
    with pytest.raises(ErreurCapteur, match="base"):
        CapteurLiaison("C", "L1", base=BaseCapteur.REFERENCE)


def test_ex51_capteur_de_point_par_defaut_en_base_du_solide_de_reference() -> None:
    c = CapteurPoint("P", "Piston", point=(0.1, 0.2, 0.3), solide_reference="Bati")
    assert c.base is BaseCapteur.REFERENCE
    assert c.point == (0.1, 0.2, 0.3)


def test_ex51_capteur_de_point_base_liaison_refusee_et_point_invalide() -> None:
    with pytest.raises(ErreurCapteur, match="base"):
        CapteurPoint("P", "S", (0, 0, 0), "R", base=BaseCapteur.LIAISON)
    with pytest.raises(ErreurCapteur, match="point"):
        CapteurPoint("P", "S", (0, 0), "R")  # type: ignore[arg-type]
    with pytest.raises(ErreurCapteur, match="point"):
        CapteurPoint("P", "S", (0, float("nan"), 0), "R")


def test_ex51_noms_vides_refuses() -> None:
    with pytest.raises(ErreurCapteur, match="nom"):
        CapteurLiaison("", "L1")
    with pytest.raises(ErreurCapteur, match="solide"):
        CapteurPoint("P", "", (0, 0, 0), "R")
    with pytest.raises(ErreurCapteur, match="liaison"):
        CapteurLiaison("C", "")


@pytest.mark.parametrize("capteur", _etude_complete().capteurs, ids=lambda c: c.nom)
def test_ex50_capteur_aller_retour_dict(capteur: Any) -> None:
    d = capteur.vers_dict()
    assert json.loads(json.dumps(d)) == d
    relu = capteur_depuis_dict(d)
    assert relu == capteur
    assert relu.vers_dict() == d


def test_ex50_capteur_dict_invalide() -> None:
    with pytest.raises(ErreurCapteur, match="genre"):
        capteur_depuis_dict({"genre": "gyroscope", "nom": "G"})
    with pytest.raises(ErreurCapteur):
        capteur_depuis_dict({"genre": "liaison", "nom": "C"})
