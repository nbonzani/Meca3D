# SPDX-License-Identifier: GPL-3.0-or-later
"""EX-07 contre le vrai SolidCraft 0.15.0 (lancé à la main : `uv run pytest -m solidcraft`).

Le test lance sa propre instance de SolidCraft sur le port 7878 (aucune autre instance ne doit
l'occuper), y ouvre une copie de la maquette bielle, puis arrête cette instance.
"""

import shutil
from pathlib import Path

import pytest

from meca3d.cao.lancement import (
    PORT_LANCEMENT,
    attendre_solidcraft,
    chercher_solidcraft,
    dossiers_de_recherche,
    etat_maquette,
    lancer_solidcraft,
    ouvrir_maquette,
)

MAQUETTE = (
    Path(__file__).parents[1]
    / "prototypes"
    / "sonde_solidcraft"
    / "export"
    / "bielle_manivelle.solidcraft"
)


@pytest.mark.solidcraft
def test_ex07_reel_lancement_puis_ouverture_de_la_maquette(tmp_path: Path) -> None:
    exe = chercher_solidcraft(dossiers_de_recherche())
    assert exe is not None, "solidcraft.exe introuvable à côté de Meca3D"
    copie = tmp_path / MAQUETTE.name
    shutil.copyfile(MAQUETTE, copie)
    processus = lancer_solidcraft(exe)
    try:
        canal = attendre_solidcraft(PORT_LANCEMENT)
        with canal:
            avant = etat_maquette(canal)
            ouvert = ouvrir_maquette(canal, copie)
            etat = etat_maquette(canal)
        assert avant.vide  # SolidCraft tout juste lancé
        assert ouvert == copie.resolve()
        assert etat.nom == "bielle_manivelle"
        assert not etat.modifiee and not etat.vide
    finally:
        processus.kill()
