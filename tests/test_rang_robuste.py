# SPDX-License-Identifier: GPL-3.0-or-later
"""Q8 : rang évalué le long du mouvement, pour une configuration d'import singulière.

Cas de référence : le parallélogramme articulé (quatre pivots d'axes parallèles, manivelle et
balancier de longueur a, bielle et bâti de longueur b), importé en position aplatie. Les quatre
centres sont alignés : le rang du système cinématique chute (rc = 2 au lieu de 3) alors que le
mécanisme garde un seul degré de mobilité réel. Valeurs génériques (calcul de la SPEC EX-21 pour
quatre pivots plans) : Ic = 4, Ec = 6, rc = 3, m = 1, h = 3.
"""

import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
from outils_graphe import (
    LINEAIRE_ANNULAIRE,
    PIVOT,
    X,
    Z,
    bielle,
    liaison,
    pendule_double,
    trois_pivots_glissiere,
)

from meca3d.graphe.configurations import mobilite_robuste
from meca3d.graphe.graphe import DescriptionMecanisme, SolideGraphe, depuis_etude
from meca3d.graphe.mobilite import (
    calculer_mobilite,
    designer_ddl_redondants,
    liberer,
)
from meca3d.modele.etude import lire_etude

A, B = 0.1, 0.3  # m


def parallelogramme(phi: float = 0.0) -> DescriptionMecanisme:
    """Manivelle O→A (a), bielle A→B (b), balancier C→B (a), bâti O→C (b) ; φ = angle de la
    manivelle. φ = 0 : position aplatie (quatre centres alignés), singulière."""
    u = np.array([np.cos(phi), np.sin(phi), 0.0])
    o, c = np.zeros(3), np.array([B, 0.0, 0.0])
    a_, b_ = A * u, c + A * u
    return DescriptionMecanisme(
        solides=(
            SolideGraphe("Bati", "Bâti", True),
            SolideGraphe("Manivelle", "Manivelle", False),
            SolideGraphe("Bielle", "Bielle", False),
            SolideGraphe("Balancier", "Balancier", False),
        ),
        liaisons=(
            liaison("L1", "Bati", "Manivelle", PIVOT, o),
            liaison("L2", "Manivelle", "Bielle", PIVOT, a_),
            liaison("L3", "Bielle", "Balancier", PIVOT, b_),
            liaison("L4", "Bati", "Balancier", PIVOT, c),
        ),
    )


def test_q8_le_rang_naif_est_faux_en_position_aplatie() -> None:
    naif = calculer_mobilite(parallelogramme(0.0))
    assert (naif.ic, naif.rc, naif.m, naif.h) == (4, 2, 2, 4)  # le problème posé par Q8
    generique = calculer_mobilite(parallelogramme(np.radians(50.0)))
    assert (generique.ic, generique.rc, generique.m, generique.h) == (4, 3, 1, 3)


def test_q8_rang_robuste_en_position_singuliere() -> None:
    r = mobilite_robuste(parallelogramme(0.0))
    assert (r.rang_import, r.resultat.rc, r.m, r.h) == (2, 3, 1, 3)
    assert (r.resultat.ic, r.resultat.ec) == (4, 6)
    assert r.singuliere_a_l_import
    assert r.rang_variable
    assert r.nb_configurations >= 1
    assert max(r.rangs) == 3


def test_q8_avertissement_nomme_les_rangs_et_la_correction() -> None:
    r = mobilite_robuste(parallelogramme(0.0))
    assert len(r.avertissements) == 1
    texte = r.avertissements[0]
    assert "singulière" in texte
    assert "rc = 2" in texte and "rc = 3" in texte
    assert "m = 1" in texte and "h = 3" in texte


def test_q8_aucun_avertissement_en_configuration_generique() -> None:
    r = mobilite_robuste(parallelogramme(np.radians(50.0)))
    assert (r.rang_import, r.m, r.h) == (3, 1, 3)
    assert not r.singuliere_a_l_import
    assert not r.rang_variable
    assert r.avertissements == ()


def test_q8_description_de_rang_maximal_utilisable_pour_les_ddl_redondants() -> None:
    d = parallelogramme(0.0)
    r = mobilite_robuste(d)
    ddl = designer_ddl_redondants(r.description, r.resultat)
    assert len(ddl) == 3
    apres = calculer_mobilite(liberer(r.description, ddl))
    assert (apres.m, apres.h) == (1, 0)


CAS_EX21 = {
    "bielle_pivot_pivot_rotule_glissiere": (bielle(), 6, 5, 1, 1),
    "lineaire_annulaire_axe_z": (bielle(LINEAIRE_ANNULAIRE, Z), 7, 6, 1, 0),
    "lineaire_annulaire_axe_x": (bielle(LINEAIRE_ANNULAIRE, X), 7, 5, 2, 1),
    "trois_pivots_glissiere": (trois_pivots_glissiere(), 4, 3, 1, 3),
    "pendule_double": (pendule_double(), 2, 0, 2, 0),
}


@pytest.mark.parametrize("cas", list(CAS_EX21))
def test_q8_le_tableau_d_ex21_est_inchange_et_sans_avertissement(cas: str) -> None:
    description, ic, rc, m, h = CAS_EX21[cas]
    r = mobilite_robuste(description)
    assert (r.resultat.ic, r.resultat.rc, r.m, r.h) == (ic, rc, m, h)
    assert r.avertissements == ()
    assert not r.singuliere_a_l_import


def test_q8_fixture_bielle_a_theta_zero_nest_pas_singuliere_pour_le_rang() -> None:
    # Constat du lot 6 : au point mort (θ = 0, fixture), le rang cinématique de la bielle-manivelle
    # ne chute pas ; Ic = 7, rc = 6, m = 1, h = 0 (linéaire annulaire d'axe z en B).
    chemin = Path(__file__).parent / "fixtures" / "bielle" / "bielle.meca3d"
    r = mobilite_robuste(depuis_etude(lire_etude(chemin)))
    assert (r.resultat.ic, r.resultat.rc, r.m, r.h) == (7, 6, 1, 0)
    assert r.avertissements == ()


def test_q8_structure_sans_mobilite() -> None:
    d = DescriptionMecanisme(
        solides=(SolideGraphe("Bati", "Bâti", True), SolideGraphe("S", "S", False)),
        liaisons=(liaison("E", "Bati", "S", (1, 1, 1, 1, 1, 1), (0.0, 0.0, 0.0)),),
    )
    r = mobilite_robuste(d)
    assert (r.resultat.ic, r.m, r.h) == (0, 0, 0)
    assert r.nb_configurations == 0
    assert r.avertissements == ()


def test_q8_calcul_pur_sans_exudyn_ni_moteur() -> None:
    code = (
        "import sys; from meca3d.graphe.configurations import mobilite_robuste; "
        "assert 'exudyn' not in sys.modules and 'meca3d.moteur' not in sys.modules"
    )
    subprocess.run([sys.executable, "-c", code], check=True)


def test_q8_deterministe() -> None:
    a = mobilite_robuste(parallelogramme(0.0))
    b = mobilite_robuste(parallelogramme(0.0))
    assert a.rangs == b.rangs
    assert a.avertissements == b.avertissements
