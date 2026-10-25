# SPDX-License-Identifier: GPL-3.0-or-later
"""Raccord R1 : `depuis_etude` lit les couplages de l'étude (EX-14, EX-21)."""

import math

import pytest
from outils_couplages import (
    PAS,
    Z1,
    Z2,
    etude_epicycloidal,
    etude_helicoidale,
    etude_reducteur,
    etude_vis_ecrou,
)

from meca3d.graphe.graphe import depuis_etude
from meca3d.graphe.mobilite import calculer_mobilite
from meca3d.modele.couplage import Engrenage, SensEngrenage, VisEcrou


def test_r1_engrenage_exterieur_lu_dans_l_etude() -> None:
    """Engrenage sur bâti : Ic = 2, Ec = 1, rc = 1, m = 1, h = 0 (lot 4), lu dans l'étude."""
    etude = etude_reducteur()
    etude.couplages = [Engrenage.depuis_dents("R", "L1", "L2", Z1, Z2)]
    description = depuis_etude(etude)
    assert len(description.couplages) == 1
    c = description.couplages[0]
    assert (c.liaison_a, c.liaison_b) == ("L1", "L2")
    assert c.rapport == pytest.approx(-1.0 / 3.0, rel=1e-15)
    r = calculer_mobilite(description)
    assert (r.ic, r.ec, r.rc, r.m, r.h) == (2, 1, 1, 1, 0)


def test_r1_engrenage_interieur_rapport_positif() -> None:
    etude = etude_reducteur()
    etude.couplages = [Engrenage.depuis_dents("R", "L1", "L2", Z1, Z2, SensEngrenage.INTERIEUR)]
    assert depuis_etude(etude).couplages[0].rapport == pytest.approx(1.0 / 3.0, rel=1e-15)


def test_r1_vis_ecrou_pivot_et_glissiere() -> None:
    etude = etude_vis_ecrou()
    etude.couplages = [VisEcrou("VE", "L_vis", "L_ecrou", PAS)]
    description = depuis_etude(etude)
    c = description.couplages[0]
    assert c.rapport == pytest.approx(PAS / (2.0 * math.pi), rel=1e-15)
    assert (c.ddl_a, c.ddl_b) == (3, 0)  # rotation de la vis, translation de l'écrou
    r = calculer_mobilite(description)
    assert (r.m, r.h) == (1, 0)


def test_r1_helicoidale_couplage_interne_au_pas_reel() -> None:
    description = depuis_etude(etude_helicoidale())
    assert len(description.couplages) == 1
    assert description.couplages[0].rapport == pytest.approx(PAS / (2.0 * math.pi), rel=1e-15)
    r = calculer_mobilite(description)
    assert (r.ic, r.ec, r.m, r.h) == (2, 1, 1, 0)


def test_r1_train_epicycloidal_trois_pivots_un_couplage() -> None:
    etude = etude_epicycloidal()
    etude.couplages = [Engrenage.depuis_dents("Willis", "Ls", "Lp", 20, 40)]
    r = calculer_mobilite(depuis_etude(etude))
    assert (r.ic, r.ec, r.rc, r.m, r.h) == (3, 1, 1, 2, 0)
