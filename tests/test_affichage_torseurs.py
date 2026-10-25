# SPDX-License-Identifier: GPL-3.0-or-later
"""Affichage lisible des torseurs (EX-50) : zéros exacts, 4 chiffres significatifs, seuil relatif.

Les valeurs attendues sont des littéraux écrits à la main (règle d'affichage du lot 9b).
"""

import numpy as np
import pytest
from outils_bielle import etude_bielle

from meca3d.resultats.affichage import (
    CHIFFRES_SIGNIFICATIFS,
    SEUIL_RELATIF,
    formater_tableau,
    formater_valeur,
)
from meca3d.resultats.torseurs import masque_nul_par_construction


def test_ex50_constantes_de_laffichage() -> None:
    assert CHIFFRES_SIGNIFICATIFS == 4
    assert SEUIL_RELATIF == 1e-9


@pytest.mark.parametrize(
    ("x", "attendu"),
    [
        (0.0, "0"),
        (-0.0, "0"),
        (1.0, "1"),
        (123.456789, "123,5"),
        (-0.0123456, "-0,01235"),
        (2.5, "2,5"),
        (12345.678, "1,235e+04"),
        (1.5e-5, "1,5e-05"),
    ],
)
def test_ex50_quatre_chiffres_significatifs_virgule_decimale(x: float, attendu: str) -> None:
    assert formater_valeur(x, reference=1.0) == attendu


def test_ex50_bruit_numerique_sous_le_seuil_relatif_devient_zero() -> None:
    assert formater_valeur(-2.73e-26, reference=100.0) == "0"
    assert formater_valeur(1.5094e-13, reference=100.0) == "0"
    assert formater_valeur(9.9e-8, reference=100.0) == "0"  # < 1e-9 x 100 = 1e-7
    assert formater_valeur(1.1e-7, reference=100.0) == "1,1e-07"


def test_ex50_reference_nulle_tout_est_zero() -> None:
    assert formater_valeur(0.0, reference=0.0) == "0"
    assert formater_valeur(1e-30, reference=0.0) == "0"


def test_ex50_tableau_seuil_relatif_sur_le_maximum_du_tableau() -> None:
    valeurs = np.array(
        [
            [1000.0, -2.73e-26, 1.5094e-13, 0.0, 12.5, 0.0],
            [3.0e-13, 250.0, 0.0, 1e-20, 0.0, -4.0],
        ]
    )
    nuls = np.zeros_like(valeurs, dtype=bool)
    texte = formater_tableau(valeurs, nuls)
    assert texte[0] == ["1000", "0", "0", "0", "12,5", "0"]
    assert texte[1] == ["0", "250", "0", "0", "0", "-4"]


def test_ex50_composantes_nulles_par_construction_affichees_exactement_zero() -> None:
    valeurs = np.array([[5.0, 2e-3, 7.0, 1e-4, 3.0, 9.0]])
    nuls = np.array([[False, True, False, True, False, False]])
    assert formater_tableau(valeurs, nuls)[0] == ["5", "0", "7", "0", "3", "9"]


def test_ex50_masque_pivot_statique_et_cinematique() -> None:
    etude = etude_bielle("00")
    pivot = "L12_pivot"  # pivot d'axe x local, sans pilote
    # statique [Fx Fy Fz Mx My Mz] : seul Mx (axe libre) est nul par construction
    masque_statique = masque_nul_par_construction(etude, pivot, statique=True)
    assert masque_statique.tolist() == [False, False, False, True, False, False]
    # cinématique [Ωx Ωy Ωz Vx Vy Vz] : seul Ωx est libre, tout le reste est nul
    masque_cinematique = masque_nul_par_construction(etude, pivot, statique=False)
    assert masque_cinematique.tolist() == [False, True, True, True, True, True]


def test_ex50_masque_statique_pilote_non_nul() -> None:
    etude = etude_bielle("00")  # L01 est pilotée : le couple moteur sur l'axe n'est pas nul
    masque = masque_nul_par_construction(etude, "L01_pivot", statique=True)
    assert masque.tolist() == [False] * 6
