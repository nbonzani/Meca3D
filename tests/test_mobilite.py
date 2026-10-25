# SPDX-License-Identifier: GPL-3.0-or-later
"""Mobilité, hyperstatisme, garde-fou et ddl redondants (EX-21, EX-22, EX-23 calcul)."""

import subprocess
import sys
from pathlib import Path

import pytest
from meca3d.graphe.graphe import (
    CouplageGraphe,
    DescriptionMecanisme,
    SolideGraphe,
    depuis_etude,
)
from meca3d.graphe.mobilite import (
    ErreurMobilite,
    Mode,
    calculer_mobilite,
    designer_ddl_redondants,
    liberer,
    verifier_avant_simulation,
)
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

from meca3d.modele.etude import lire_etude

# Tableau d'EX-21 : (description, Ic, rc, m, h), valeurs de la SPEC
CAS_EX21 = {
    "bielle_pivot_pivot_rotule_glissiere": (bielle(), 6, 5, 1, 1),
    "lineaire_annulaire_axe_z": (bielle(LINEAIRE_ANNULAIRE, Z), 7, 6, 1, 0),
    "lineaire_annulaire_axe_x": (bielle(LINEAIRE_ANNULAIRE, X), 7, 5, 2, 1),
    "trois_pivots_glissiere": (trois_pivots_glissiere(), 4, 3, 1, 3),
    "pendule_double": (pendule_double(), 2, 0, 2, 0),
}


@pytest.mark.parametrize("cas", list(CAS_EX21))
def test_ex21_tableau(cas):
    description, ic, rc, m, h = CAS_EX21[cas]
    r = calculer_mobilite(description)
    assert (r.ic, r.rc, r.m, r.h) == (ic, rc, m, h)


def test_ex21_equations_et_mu():
    r = calculer_mobilite(bielle())
    assert r.mu == 1
    assert r.ec == 6
    r0 = calculer_mobilite(pendule_double())
    assert r0.mu == 0
    assert r0.ec == 0


def test_ex21_couplage_engrenage():
    """Deux pivots sur le bâti et un engrenage : Ic = 2, μ = 0, Ec = 1, m = 1, h = 0."""
    d = DescriptionMecanisme(
        solides=(
            SolideGraphe("Bati", "Bâti", True),
            SolideGraphe("S1", "Pignon", False),
            SolideGraphe("S2", "Roue", False),
        ),
        liaisons=(
            liaison("P1", "Bati", "S1", PIVOT, (0.0, 0.0, 0.0)),
            liaison("P2", "Bati", "S2", PIVOT, (0.08, 0.0, 0.0)),
        ),
        couplages=(CouplageGraphe("P1", "P2", rapport=-3.0),),
    )
    r = calculer_mobilite(d)
    assert (r.ic, r.mu, r.ec, r.m, r.h) == (2, 0, 1, 1, 0)


def test_ex21_depuis_etude_fixture_bielle():
    """Structure de la fixture (importée à θ = 0, position singulière : seuls Ic et Ec sont
    indépendants de la configuration)."""
    chemin = Path(__file__).parent / "fixtures" / "bielle" / "bielle.meca3d"
    r = calculer_mobilite(depuis_etude(lire_etude(chemin)))
    assert (r.ic, r.ec, r.mu) == (7, 6, 1)


def test_ex22_refus_hyperstatique_sans_moteur():
    r = calculer_mobilite(bielle())
    assert r.h == 1
    decision = verifier_avant_simulation(
        r, Mode.CINEMATIQUE, n_lois=1, hyperstatique_autorise=False
    )
    assert not decision.autorise
    assert "h = 1" in decision.message
    for nom in ("L01", "L12", "L23", "L30"):
        assert nom in decision.message
    # fonction pure : même entrée, même sortie ; aucun module de moteur n'est importé
    assert decision == verifier_avant_simulation(r, Mode.CINEMATIQUE, 1, False)
    code = (
        "import sys; import meca3d.graphe.mobilite, meca3d.graphe.graphe; "
        "assert 'exudyn' not in sys.modules and 'meca3d.moteur' not in sys.modules"
    )
    subprocess.run([sys.executable, "-c", code], check=True)


def test_ex22_hyperstatique_refuse_aussi_en_dynamique_meme_autorise():
    r = calculer_mobilite(bielle())
    d = verifier_avant_simulation(r, Mode.DYNAMIQUE, n_lois=1, hyperstatique_autorise=True)
    assert not d.autorise
    assert "indéterminé" in d.message


def test_ex23_option_autorise_le_cinematique():
    r = calculer_mobilite(bielle())
    d = verifier_avant_simulation(r, Mode.CINEMATIQUE, n_lois=1, hyperstatique_autorise=True)
    assert d.autorise


def test_ex22_nombre_de_lois_different_de_m():
    r = calculer_mobilite(pendule_double())  # m = 2, h = 0
    refus = verifier_avant_simulation(r, Mode.CINEMATIQUE, n_lois=1, hyperstatique_autorise=False)
    assert not refus.autorise
    assert "2" in refus.message
    avert = verifier_avant_simulation(r, Mode.DYNAMIQUE, n_lois=1, hyperstatique_autorise=False)
    assert avert.autorise
    assert avert.avertissement
    assert avert.message
    ok = verifier_avant_simulation(r, Mode.CINEMATIQUE, n_lois=2, hyperstatique_autorise=False)
    assert ok.autorise
    assert not ok.avertissement


def test_ex23_trois_pivots_glissiere_trois_ddl_a_liberer():
    d = trois_pivots_glissiere()
    r = calculer_mobilite(d)
    assert r.h == 3
    ddl = designer_ddl_redondants(d, r)
    assert len(ddl) == 3
    assert len(set(ddl)) == 3
    noms = {x.nom for x in d.liaisons}
    for x in ddl:
        assert x.liaison in noms
        assert 0 <= x.ddl <= 5
        assert d.liaison(x.liaison).ddl_bloques[x.ddl] == 1  # ddl effectivement bloqué
    apres = calculer_mobilite(liberer(d, ddl))
    assert apres.h == 0
    assert apres.m == 1


@pytest.mark.parametrize("cas", ["bielle_pivot_pivot_rotule_glissiere", "lineaire_annulaire_axe_x"])
def test_ex23_un_ddl_pour_h_egal_1(cas):
    d, _, _, m, h = CAS_EX21[cas]
    ddl = designer_ddl_redondants(d, calculer_mobilite(d))
    assert len(ddl) == h == 1
    apres = calculer_mobilite(liberer(d, ddl))
    assert (apres.h, apres.m) == (0, m)


def test_ex23_aucun_ddl_si_isostatique():
    d = pendule_double()
    assert designer_ddl_redondants(d, calculer_mobilite(d)) == ()


def test_ex23_couplage_redondant_non_liberable():
    """Deux couplages identiques : h = 1 mais aucun ddl de liaison n'est à libérer."""
    d = DescriptionMecanisme(
        solides=(
            SolideGraphe("Bati", "Bâti", True),
            SolideGraphe("S1", "Pignon", False),
            SolideGraphe("S2", "Roue", False),
        ),
        liaisons=(
            liaison("P1", "Bati", "S1", PIVOT, (0.0, 0.0, 0.0)),
            liaison("P2", "Bati", "S2", PIVOT, (0.08, 0.0, 0.0)),
        ),
        couplages=(
            CouplageGraphe("P1", "P2", rapport=-3.0),
            CouplageGraphe("P1", "P2", rapport=-3.0),
        ),
    )
    r = calculer_mobilite(d)
    assert (r.m, r.h) == (1, 1)
    with pytest.raises(ErreurMobilite, match="couplage"):
        designer_ddl_redondants(d, r)
