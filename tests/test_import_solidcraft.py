# SPDX-License-Identifier: GPL-3.0-or-later
"""Import en direct de la maquette depuis le faux serveur (EX-03 à EX-06)."""

import math
from pathlib import Path
from typing import Any

import pytest
from faux_serveur import (
    JETON_DE_TEST,
    NOM_LIAISON_SOUS_OCCURRENCE,
    FauxServeur,
    Scenario,
)
from outils_bielle import etude_proposee

from meca3d.cao.canal import CanalSolidCraft, ConnexionPerdue
from meca3d.cao.solidcraft import (
    FORMAT_SUPPORTE,
    importer,
    reimporter,
    structure_a_change,
)
from meca3d.modele.actions import LoiEntree, Pesanteur, Pilote
from meca3d.modele.etude import Etude
from meca3d.modele.liaison import Statut, TypeLiaison


def _canal(faux: FauxServeur) -> CanalSolidCraft:
    return CanalSolidCraft(port=faux.port, jeton=JETON_DE_TEST, intervalle_pending=0.01)


def _sans_maquette(etude: Etude) -> dict[str, Any]:
    d = etude.vers_dict()
    d.pop("maquette")
    return d


def test_ex04_import_identique_aux_reponses_enregistrees(tmp_path: Path) -> None:
    with FauxServeur() as faux:
        etude = importer(_canal(faux), tmp_path)
    assert _sans_maquette(etude) == _sans_maquette(etude_proposee("00"))
    solides = {s.nom: s for s in etude.solides}
    assert solides["Manivelle"].inertie[2, 2] == pytest.approx(2.704e-4, rel=1e-9)
    assert solides["Bielle"].inertie[2, 2] == pytest.approx(7.0512e-3, rel=1e-9)
    assert solides["Manivelle"].masse == pytest.approx(0.312, rel=1e-9)
    assert len(etude.liaisons) == 4
    assert all(x.proposition is not None for x in etude.liaisons)
    assert all(x.statut is Statut.PROPOSEE for x in etude.liaisons)
    assert etude.avertissements == []


def test_ex04_sequence_des_requetes_et_export_dans_un_dossier_temporaire(
    tmp_path: Path,
) -> None:
    with FauxServeur() as faux:
        importer(_canal(faux), tmp_path)
        recues = faux.methodes_recues()
        exports = [
            r["params"]["params"]
            for r in faux.requetes
            if r["method"] == "engine.execute" and r["params"]["command"] == "file.export"
        ]
    assert recues[0] == "document.inspect"
    for attendu in ("joint.list", "component.list", "component.properties", "file.export"):
        assert attendu in recues
    assert recues.count("component.properties") == 4
    assert sorted(e["format"] for e in exports) == ["json", "urdf"]
    for e in exports:
        assert Path(e["path"]).parent.is_relative_to(tmp_path)
        assert not Path(e["path"]).exists()  # dossier temporaire nettoyé
    assert list(tmp_path.iterdir()) == []


def test_ex04_dossier_temporaire_nettoye_meme_en_cas_derreur(tmp_path: Path) -> None:
    with FauxServeur(scenario=Scenario(coupure_sur="file.export")) as faux:
        with pytest.raises(ConnexionPerdue):
            importer(_canal(faux), tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_ex03_format_different_avertissement_non_bloquant(tmp_path: Path) -> None:
    with FauxServeur(scenario=Scenario(format_export="solidcraft/27")) as faux:
        etude = importer(_canal(faux), tmp_path)
    assert FORMAT_SUPPORTE == "solidcraft/26"
    assert len(etude.liaisons) == 4
    assert len(etude.avertissements) == 1
    assert "solidcraft/26" in etude.avertissements[0]
    assert "solidcraft/27" in etude.avertissements[0]


def test_ex05_pose_courante_memorisee_a_60_degres(tmp_path: Path) -> None:
    with FauxServeur(theta="60") as faux:
        etude = importer(_canal(faux), tmp_path)
    assert _sans_maquette(etude) == _sans_maquette(etude_proposee("60"))
    assert etude.revision == 49
    pivot = etude.liaison("L01_pivot")
    assert pivot.valeur_pose == pytest.approx(math.radians(60.0), abs=1e-9)
    manivelle = etude.solide("Manivelle")
    assert manivelle.cdg == pytest.approx([0.025, 0.05 * math.sqrt(3) / 2, 0.0], abs=1e-9)


def test_ex06_signature_stable_sous_changement_de_pose(tmp_path: Path) -> None:
    with FauxServeur(theta="00") as faux:
        a = importer(_canal(faux), tmp_path)
    with FauxServeur(theta="60") as faux:
        b = importer(_canal(faux), tmp_path)
    assert a.signature
    assert a.signature == b.signature
    assert a.revision != b.revision


def test_ex06_structure_inchangee_puis_changee(tmp_path: Path) -> None:
    with FauxServeur() as faux:
        canal = _canal(faux)
        etude = importer(canal, tmp_path)
        assert not structure_a_change(canal, etude)
        faux.types_modifies = {"L23_rotule": "cylindrical"}
        assert structure_a_change(canal, etude)


def test_ex06_poses_modifiees_seules_pas_de_bandeau(tmp_path: Path) -> None:
    with FauxServeur(theta="00") as faux:
        canal = _canal(faux)
        etude = importer(canal, tmp_path)
        faux.theta = "60"  # animation : poses et revision changent, pas la structure
        faux.revision = 500
        assert not structure_a_change(canal, etude)


def test_ex06_couplage_ajoute_est_une_modification_de_structure(tmp_path: Path) -> None:
    couplage = {
        "a": 1,
        "b": 2,
        "ratio": 2.0,
        "unit": "deg",
        "coupling": {"type": "gear", "ra": 10.0, "rb": 20.0, "pitch": 0.0, "radius": 0.0},
    }
    with FauxServeur() as faux:
        canal = _canal(faux)
        etude = importer(canal, tmp_path)
        faux.links = [couplage]
        assert structure_a_change(canal, etude)
        avec = importer(canal, tmp_path)
        assert avec.signature != etude.signature
        assert not structure_a_change(canal, avec)


def test_ex06_etude_sans_signature_est_consideree_modifiee(tmp_path: Path) -> None:
    with FauxServeur() as faux:
        assert structure_a_change(_canal(faux), etude_proposee("00"))


def test_ex06_reimport_conserve_les_choix_pour_les_liaisons_de_meme_nom(
    tmp_path: Path,
) -> None:
    with FauxServeur() as faux:
        canal = _canal(faux)
        ancienne = importer(canal, tmp_path)
        ancienne.liaison("L23_rotule").type = TypeLiaison.LINEAIRE_ANNULAIRE
        ancienne.liaison("L23_rotule").reorienter_axe((0.0, 0.0, 1.0))
        for liaison in ancienne.liaisons:
            if liaison.nom != "L12_pivot":
                liaison.valider()
        ancienne.pilotes = [Pilote(liaison="L01_pivot", loi=LoiEntree("2*t"))]
        ancienne.pesanteur = Pesanteur(vecteur=(0.0, -9.81, 0.0))
        faux.types_modifies = {"L30_glissiere": "cylindrical"}
        assert structure_a_change(canal, ancienne)
        nouvelle = reimporter(canal, ancienne)
    rotule = nouvelle.liaison("L23_rotule")
    assert rotule.type is TypeLiaison.LINEAIRE_ANNULAIRE
    assert rotule.axe == pytest.approx([0.0, 0.0, 1.0], abs=1e-12)
    assert rotule.statut is Statut.VALIDEE
    assert nouvelle.liaison("L01_pivot").statut is Statut.VALIDEE
    assert nouvelle.liaison("L12_pivot").statut is Statut.PROPOSEE
    assert nouvelle.liaison("L12_pivot").type is TypeLiaison.PIVOT
    # type SolidCraft changé : le choix est abandonné et signalé
    glissiere = nouvelle.liaison("L30_glissiere")
    assert glissiere.type is TypeLiaison.PIVOT_GLISSANT
    assert glissiere.statut is Statut.PROPOSEE
    assert any("L30_glissiere" in a for a in nouvelle.avertissements)
    assert [p.liaison for p in nouvelle.pilotes] == ["L01_pivot"]
    assert nouvelle.pesanteur.vecteur == pytest.approx((0.0, -9.81, 0.0))
    assert len(nouvelle.solides) == 4


def test_ex06_reimport_ne_perd_pas_letude_en_cas_derreur(tmp_path: Path) -> None:
    with FauxServeur() as faux:
        canal = _canal(faux)
        ancienne = importer(canal, tmp_path)
        avant = ancienne.vers_dict()
        faux.scenario.coupure_sur = "joint.list"
        with pytest.raises(ConnexionPerdue):
            reimporter(canal, ancienne)
    assert ancienne.vers_dict() == avant


def test_ex04_liaison_sur_sous_occurrence_signalee_et_autres_importees(
    tmp_path: Path,
) -> None:
    with FauxServeur(scenario=Scenario(sous_occurrence=True)) as faux:
        etude = importer(_canal(faux), tmp_path)
    assert [x.nom for x in etude.liaisons] == [
        "L01_pivot",
        "L12_pivot",
        "L23_rotule",
        "L30_glissiere",
    ]
    assert etude.liaisons_ignorees == [NOM_LIAISON_SOUS_OCCURRENCE]
    assert any(NOM_LIAISON_SOUS_OCCURRENCE in a for a in etude.avertissements)
    assert len(etude.solides) == 4
