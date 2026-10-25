# SPDX-License-Identifier: GPL-3.0-or-later
"""Graphe des liaisons, μ, cycles indépendants, isolés, bâti (EX-20)."""

import pytest
from outils_graphe import PIVOT, bielle, liaison, pendule_double

from meca3d.graphe.graphe import DescriptionMecanisme, SolideGraphe, construire_graphe
from meca3d.modele.etude import lire_etude


def test_ex20_bielle_manivelle():
    g = construire_graphe(bielle())
    assert g.nb_solides == 4
    assert g.nb_liaisons == 4
    assert g.mu == 1
    assert len(g.cycles) == 1
    cycle = g.cycles[0]
    assert len(cycle.liaisons) == 4
    assert {nom for nom, _ in cycle.liaisons} == {"L01", "L12", "L23", "L30"}
    assert all(signe in (1, -1) for _, signe in cycle.liaisons)
    assert g.isoles == ()
    assert g.bati == "Bati"


def test_ex20_pendule_double():
    g = construire_graphe(pendule_double())
    assert g.mu == 0
    assert g.cycles == ()
    assert g.nb_composantes == 1


def test_ex20_solide_isole_signale():
    d = pendule_double()
    d = DescriptionMecanisme(
        solides=(*d.solides, SolideGraphe("Libre", "Pièce libre", False)),
        liaisons=d.liaisons,
    )
    g = construire_graphe(d)
    assert g.isoles == ("Libre",)
    assert g.mu == 0
    assert g.nb_composantes == 2


def test_ex20_deux_solides_fixes_un_seul_bati():
    """Les solides fixes sont fusionnés en un nœud : un solide mobile lié à deux fixes ferme
    une boucle par le bâti (μ = 1), ce que deux nœuds distincts ne verraient pas (μ = 0)."""
    d = DescriptionMecanisme(
        solides=(
            SolideGraphe("B1", "Bâti 1", True),
            SolideGraphe("B2", "Bâti 2", True),
            SolideGraphe("S", "Solide", False),
        ),
        liaisons=(
            liaison("A", "B1", "S", PIVOT, (0, 0, 0)),
            liaison("B", "B2", "S", PIVOT, (0.1, 0, 0)),
        ),
    )
    g = construire_graphe(d)
    assert g.bati == "B1"
    assert g.solides_bati == ("B1", "B2")
    assert g.nb_solides == 2
    assert g.mu == 1
    assert {nom for nom, _ in g.cycles[0].liaisons} == {"A", "B"}


def test_ex20_multigraphe_deux_liaisons_entre_memes_solides():
    d = DescriptionMecanisme(
        solides=(SolideGraphe("B", "Bâti", True), SolideGraphe("S", "Solide", False)),
        liaisons=(
            liaison("A", "B", "S", PIVOT, (0, 0, 0)),
            liaison("C", "B", "S", PIVOT, (0.1, 0, 0)),
        ),
    )
    g = construire_graphe(d)
    assert g.mu == 1
    assert len(g.cycles[0].liaisons) == 2


def test_ex20_mu_somme_des_composantes():
    """Deux pendules doubles disjoints sans bâti commun, puis un cycle : μ total = somme."""
    d = DescriptionMecanisme(
        solides=(
            SolideGraphe("B", "Bâti", True),
            SolideGraphe("S1", "S1", False),
            SolideGraphe("S2", "S2", False),
            SolideGraphe("T1", "T1", False),
            SolideGraphe("T2", "T2", False),
        ),
        liaisons=(
            liaison("A", "B", "S1", PIVOT, (0, 0, 0)),
            liaison("C", "S1", "S2", PIVOT, (0.1, 0, 0)),
            liaison("D", "S2", "B", PIVOT, (0.2, 0, 0)),  # cycle B-S1-S2 : μ = 1
            liaison("E", "T1", "T2", PIVOT, (0.3, 0, 0)),
            liaison("F", "T1", "T2", PIVOT, (0.4, 0, 0)),  # cycle à 2 liaisons : μ = 1
        ),
    )
    g = construire_graphe(d)
    assert g.nb_composantes == 2
    assert sorted(g.mu_par_composante) == [1, 1]
    assert g.mu == 2
    assert len(g.cycles) == 2


def test_ex20_liaison_vers_solide_inconnu_refusee():
    d = DescriptionMecanisme(
        solides=(SolideGraphe("B", "Bâti", True),),
        liaisons=(liaison("A", "B", "X", PIVOT, (0, 0, 0)),),
    )
    with pytest.raises(ValueError, match="X"):
        construire_graphe(d)


def test_ex20_depuis_etude_fixture_bielle():
    from pathlib import Path

    from meca3d.graphe.graphe import depuis_etude

    chemin = Path(__file__).parent / "fixtures" / "bielle" / "bielle.meca3d"
    g = construire_graphe(depuis_etude(lire_etude(chemin)))
    assert (g.nb_solides, g.nb_liaisons, g.mu) == (4, 4, 1)
    assert len(g.cycles[0].liaisons) == 4
