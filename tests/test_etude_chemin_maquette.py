# SPDX-License-Identifier: GPL-3.0-or-later
"""Chemin de la maquette dans le fichier d'étude (EX-07, EX-60, lot 15)."""

import json
import shutil
from pathlib import Path

from outils_bielle import etude_bielle

from meca3d.modele.etude import chercher_maquette, ecrire_etude, lire_etude

FIXTURE = Path(__file__).parent / "fixtures" / "bielle" / "bielle.meca3d"


def test_ex07_chemin_enregistre_relatif_au_dossier_de_l_etude(tmp_path: Path) -> None:
    maquette = tmp_path / "td" / "maquettes" / "bielle_manivelle.solidcraft"
    maquette.parent.mkdir(parents=True)
    maquette.write_bytes(b"")
    etude = etude_bielle()
    etude.chemin_maquette = str(maquette)
    chemin = tmp_path / "td" / "bielle.meca3d"
    ecrire_etude(etude, chemin)
    donnees = json.loads(chemin.read_text(encoding="utf-8"))
    assert donnees["chemin_maquette"] == "maquettes/bielle_manivelle.solidcraft"
    assert Path(lire_etude(chemin).chemin_maquette) == maquette


def test_ex07_chemin_relu_apres_deplacement_conjoint(tmp_path: Path) -> None:
    maquette = tmp_path / "td" / "maquettes" / "bielle_manivelle.solidcraft"
    maquette.parent.mkdir(parents=True)
    maquette.write_bytes(b"")
    etude = etude_bielle()
    etude.chemin_maquette = str(maquette)
    ecrire_etude(etude, tmp_path / "td" / "bielle.meca3d")
    shutil.move(tmp_path / "td", tmp_path / "copie_eleve")
    relue = lire_etude(tmp_path / "copie_eleve" / "bielle.meca3d")
    attendu = tmp_path / "copie_eleve" / "maquettes" / "bielle_manivelle.solidcraft"
    assert Path(relue.chemin_maquette) == attendu
    assert chercher_maquette(relue, tmp_path / "copie_eleve" / "bielle.meca3d") == attendu


def test_ex07_etude_sans_chemin_inchangee(tmp_path: Path) -> None:
    """Aucune clé `chemin_maquette` sans chemin : les études existantes restent identiques."""
    etude = lire_etude(FIXTURE)
    assert etude.chemin_maquette == ""
    chemin = tmp_path / "bielle.meca3d"
    ecrire_etude(etude, chemin)
    assert "chemin_maquette" not in json.loads(chemin.read_text(encoding="utf-8"))


def test_ex07_maquette_cherchee_a_cote_de_l_etude(tmp_path: Path) -> None:
    """Étude sans chemin (ou chemin disparu) : `<maquette>.solidcraft` à côté du `.meca3d`."""
    etude = lire_etude(FIXTURE)  # maquette = "bielle_manivelle.solidcraft"
    chemin_etude = tmp_path / "bielle.meca3d"
    assert chercher_maquette(etude, chemin_etude) is None
    voisine = tmp_path / "bielle_manivelle.solidcraft"
    voisine.write_bytes(b"")
    assert chercher_maquette(etude, chemin_etude) == voisine
    etude.maquette = "bielle_manivelle"  # nom rendu par document.inspect, sans extension
    assert chercher_maquette(etude, chemin_etude) == voisine
    etude.chemin_maquette = str(tmp_path / "disparu" / "bielle_manivelle.solidcraft")
    assert chercher_maquette(etude, chemin_etude) == voisine


def test_ex07_maquette_introuvable(tmp_path: Path) -> None:
    etude = lire_etude(FIXTURE)
    assert chercher_maquette(etude, None) is None
    etude.maquette = ""
    assert chercher_maquette(etude, tmp_path / "e.meca3d") is None
