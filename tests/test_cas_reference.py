# SPDX-License-Identifier: GPL-3.0-or-later
"""Lot 11 : cas de référence construits dans SolidCraft, de bout en bout (SPEC EX-14, EX-16, EX-20,
EX-21, EX-31, EX-40, EX-44).

Chaque maquette a été construite dans le vrai SolidCraft
(`fixtures/maquettes/construire_maquettes.py`) et ses réponses réelles du canal de contrôle sont
enregistrées sous `fixtures/<cas>/solidcraft/`. Les tests partent de ces réponses
(`etude_depuis_reponses`), font les choix de l'élève (validation des liaisons proposées),
simulent et comparent à des références analytiques ou à la SPEC. Les mêmes scénarios contre
le vrai SolidCraft sont dans `test_cas_reference_reel.py` (marqueur solidcraft).

Tolérances : 1e-3 en relatif sur les périodes, vitesses et efforts (celle d'EX-14 et d'EX-16) ;
l'énergie et l'intégrateur de Lagrange du pendule double sont justifiés à leur test.
"""

import math
import time

import numpy as np
import pytest
from outils_bielle import etude_bielle
from outils_cas_reference import (
    I_CDG_BARRE,
    LONGUEUR,
    MASSE_BARRE,
    G,
    angle_barre2_au_pas,
    angles_depuis_etude,
    energie_double,
    etude_enregistree,
    lagrange_rk4,
    omega_point_bas,
    periode_amplitude,
    periode_mesuree,
    periode_petites_oscillations,
    preparer,
    valider_tout,
    x_relatif_au_pivot,
)
from outils_couplages import PAS, action, couple, pilote, reglages

from meca3d.graphe.graphe import construire_graphe, depuis_etude
from meca3d.graphe.mobilite import Mode
from meca3d.modele.actions import NatureAction
from meca3d.modele.couplage import Engrenage, SensEngrenage, VisEcrou
from meca3d.modele.etude import Etude
from meca3d.modele.liaison import TypeLiaison
from meca3d.moteur.exudyn_dyn import MoteurExudynDyn
from meca3d.moteur.simulation import analyser_etude, simuler_etude

# Valeurs de la SPEC / du lot 11
T0_SPEC = 1.03625  # s, petites oscillations
T30_SPEC = 1.05429  # s, amplitude 30°
OMEGA_BAS_SPEC = 3.13863  # rad/s, point bas après un lâcher à 30°
TOL = 1e-3

# ---------------------------------------------------------------------------- pendule simple


def test_ex40_pendule_simple_references_analytiques() -> None:
    """Les trois valeurs de référence du lot sont celles de l'intégrale elliptique (calcul
    indépendant du moteur, par moyenne arithmético-géométrique) : barre 400 × 20 × 20 mm."""
    assert MASSE_BARRE == pytest.approx(1.248, rel=1e-12)
    assert periode_petites_oscillations() == pytest.approx(T0_SPEC, abs=5e-6)
    assert periode_amplitude(math.radians(30.0)) == pytest.approx(T30_SPEC, abs=5e-6)
    assert omega_point_bas(math.radians(30.0)) == pytest.approx(OMEGA_BAS_SPEC, abs=5e-6)


def test_ex04_pendule_simple_import() -> None:
    etude = etude_enregistree("pendule_simple", "theta30")
    assert [s.nom for s in etude.solides] == ["Bati", "Barre"]
    assert etude.solide("Bati").fixe and not etude.solide("Barre").fixe
    barre = etude.solide("Barre")
    assert barre.masse == pytest.approx(MASSE_BARRE, rel=1e-9)
    # axe du pivot horizontal (y), inertie d'axe y au CdG de la barre
    assert abs(etude.liaison("L01_pivot").axe_sc[1]) == pytest.approx(1.0, abs=1e-12)
    assert barre.inertie[1, 1] == pytest.approx(I_CDG_BARRE, rel=1e-6)
    assert [x.type for x in etude.liaisons] == [TypeLiaison.PIVOT]
    # barre lâchée à 30° de la verticale : CdG à L/2 du pivot
    c = barre.cdg - etude.liaison("L01_pivot").centre
    assert math.degrees(math.atan2(abs(c[0]), -c[2])) == pytest.approx(30.0, abs=1e-9)
    assert float(np.linalg.norm(c)) == pytest.approx(LONGUEUR / 2.0, rel=1e-9)


def _simuler_pendule(etiquette: str, duree: float, nb_pas: int):
    etude = preparer(etude_enregistree("pendule_simple", etiquette), duree, nb_pas, duree / 6400)
    return etude, simuler_etude(etude, Mode.DYNAMIQUE)


@pytest.fixture(scope="module")
def pendule_30():
    return _simuler_pendule("theta30", 3.4, 3400)


@pytest.fixture(scope="module")
def pendule_1():
    return _simuler_pendule("theta01", 3.4, 3400)


def test_ex40_pendule_simple_periode_petites_oscillations(pendule_1) -> None:
    """Lâcher à 1° (T(1°) = T₀·(1 + 1,9e-5)) : T₀ = 1,03625 s à 1e-3 près."""
    etude, res = pendule_1
    x = x_relatif_au_pivot(etude, res, "Barre", "L01_pivot")
    assert periode_mesuree(res.t, x) == pytest.approx(T0_SPEC, rel=TOL)


def test_ex40_pendule_simple_periode_30_degres(pendule_30) -> None:
    """Lâcher à 30° : T(30°) = 1,05429 s à 1e-3 près (l'isochronisme est bien faux)."""
    etude, res = pendule_30
    x = x_relatif_au_pivot(etude, res, "Barre", "L01_pivot")
    t30 = periode_mesuree(res.t, x)
    assert t30 == pytest.approx(T30_SPEC, rel=TOL)
    assert t30 > T0_SPEC * (1.0 + 5e-3)


def test_ex40_pendule_simple_omega_point_bas(pendule_30) -> None:
    """Vitesse angulaire maximale (au passage par la verticale) : 3,13863 rad/s à 1e-3 près."""
    _, res = pendule_30
    omega = np.linalg.norm(res.vitesses_angulaires["Barre"], axis=1)
    assert float(omega.max()) == pytest.approx(OMEGA_BAS_SPEC, rel=TOL)
    assert omega[0] == pytest.approx(0.0, abs=1e-9)  # lâché au repos


def test_ex31_pendule_simple_sans_pesanteur() -> None:
    """g désactivé, pendule lâché à 30° : aucun mouvement (rotation et position à 1e-9)."""
    etude = preparer(etude_enregistree("pendule_simple", "theta30"), 1.0, 500)
    etude.pesanteur.actif = False
    res = simuler_etude(etude, Mode.DYNAMIQUE)
    assert np.abs(res.rotations["Barre"] - res.rotations["Barre"][0]).max() < 1e-9
    assert np.abs(res.positions["Barre"] - res.positions["Barre"][0]).max() < 1e-9


# ---------------------------------------------------------------------------- pendule double


def _etude_double(duree: float = 2.0, nb_pas: int = 2000) -> Etude:
    return preparer(etude_enregistree("pendule_double", "pose1"), duree, nb_pas)


def test_ex20_pendule_double_graphe() -> None:
    etude = valider_tout(etude_enregistree("pendule_double", "pose1"))
    graphe = construire_graphe(depuis_etude(etude))
    assert graphe.mu == 0
    assert len(graphe.cycles) == 0


def test_ex21_pendule_double_mobilite() -> None:
    """Valeurs d'EX-21 : Ic = 2, rc = 0, m = 2, h = 0 (maquette SolidCraft de 3 solides)."""
    r = analyser_etude(valider_tout(etude_enregistree("pendule_double", "pose1"))).resultat
    assert (r.ic, r.rc, r.m, r.h, r.mu) == (2, 0, 2, 0, 0)


@pytest.fixture(scope="module")
def double_simule():
    etude = _etude_double()
    return etude, simuler_etude(etude, Mode.DYNAMIQUE)


def test_ex40_pendule_double_conservation_energie(double_simule) -> None:
    """Liaisons parfaites, 2 s, 2 000 pas : l'énergie mécanique dérive de moins de 1e-3 de
    l'énergie mise en jeu E₀ − E_repos (E_repos : les deux barres pendantes). Justification : le
    generalized-α (ρ∞ = 0,9) dissipe un peu les hautes fréquences ; à h = 1 ms, ω·h < 0,05."""
    _, res = double_simule
    e = energie_double(res)
    # barre 1 : CdG à −L/2 ; barre 2 : CdG à −3L/2 (barres pendantes, énergie potentielle seule)
    e_repos = -MASSE_BARRE * G * (LONGUEUR / 2.0 + 3.0 * LONGUEUR / 2.0)
    derive = float(np.abs(e - e[0]).max() / abs(e[0] - e_repos))
    assert derive < 1e-3


def test_ex40_pendule_double_lagrange_rk4(double_simule) -> None:
    """Angle absolu de la barre 2 à t = 1 s : écart à l'intégration RK4 (pas 0,1 ms) des équations
    de Lagrange écrites dans les tests : moins de 5e-4 rad (= 0,03°). Justification : erreur
    d'ordre 2 du generalized-α à h = 1 ms, sur un mouvement sensible mais non chaotique à 1 s
    (écart mesuré 9e-5 rad ; l'intégration RK4 est convergée à 1e-13 rad entre 0,1 et 0,02 ms)."""
    etude, res = double_simule
    phi1, phi2 = angles_depuis_etude(etude)
    _, phi2_ref = lagrange_rk4(phi1, phi2, 1.0)
    indice = int(np.argmin(np.abs(res.t - 1.0)))
    assert res.t[indice] == pytest.approx(1.0, abs=1e-9)
    assert angle_barre2_au_pas(etude, res, indice) == pytest.approx(phi2_ref, abs=5e-4)


# ---------------------------------------------------------------------------- réducteur
Z1, Z2 = 20, 60
K = Z1 / Z2


def _reducteur() -> Etude:
    etude = valider_tout(etude_enregistree("reducteur", "pose0"))
    etude.pesanteur.actif = False
    return etude


def test_ex14_reducteur_import() -> None:
    etude = _reducteur()
    assert [x.type for x in etude.liaisons] == [TypeLiaison.PIVOT, TypeLiaison.PIVOT]
    assert len(etude.couplages) == 1
    c = etude.couplages[0]
    assert isinstance(c, Engrenage)
    assert (c.liaison_1, c.liaison_2, c.sens) == ("L1_pivot", "L2_pivot", SensEngrenage.EXTERIEUR)
    assert c.k == pytest.approx(K, rel=1e-12)


def test_ex14_reducteur_rapport() -> None:
    """Z₁ = 20, Z₂ = 60, ω_e = 30 rad/s : |ω_s| = 10 rad/s et |ω_s + k·ω_e| < 1e-6 rad/s."""
    etude = _reducteur()
    etude.pilotes = [pilote("L1_pivot", 30.0)]
    etude.reglages = reglages(1.0, 1000, 0.001)
    res = simuler_etude(etude, Mode.DYNAMIQUE)
    w_e = res.vitesses_angulaires["Roue1"][:, 2]
    w_s = res.vitesses_angulaires["Roue2"][:, 2]
    assert w_e[-1] == pytest.approx(30.0, rel=TOL)
    assert abs(w_s[-1]) == pytest.approx(10.0, rel=TOL)
    assert np.abs(w_s + K * w_e).max() < 1e-6


def _equilibre_reducteur(etude: Etude, cs: float):
    etude.actions = [couple("Ce", "Roue1", 1.0), couple("Cs", "Roue2", cs)]
    etude.reglages = reglages(0.5, 500, 0.001)
    vitesses = {
        "Roue1": ((0.0, 0.0, 0.0), (0.0, 0.0, 30.0)),
        "Roue2": ((0.0, 0.0, 0.0), (0.0, 0.0, -10.0)),
    }
    return MoteurExudynDyn().simuler(etude, vitesses_initiales=vitesses)


def test_ex14_reducteur_couple_transmis() -> None:
    """Sans perte, Ce = 1 N·m : Cs = 3 N·m à 1e-3 près, vitesses constantes en régime établi."""
    etude = _reducteur()
    res = _equilibre_reducteur(etude, 3.0)
    nom = etude.couplages[0].nom
    assert np.abs(res.vitesses_angulaires["Roue2"][:, 2] + 10.0).max() < 1e-4
    assert abs(res.efforts_couplages[nom][-1, 1]) == pytest.approx(3.0, rel=TOL)
    assert abs(res.efforts_couplages[nom][-1, 0]) == pytest.approx(1.0, rel=TOL)


def test_ex16_reducteur_rendement() -> None:
    """η = 0,95, Ce = 1 N·m en régime établi : Cs = 2,85 N·m à 1e-3 près ; le chargement sans perte
    (3 N·m) n'est plus en équilibre."""
    etude = _reducteur()
    ancien = etude.couplages[0]
    assert isinstance(ancien, Engrenage)
    etude.couplages = [
        Engrenage(ancien.nom, ancien.liaison_1, ancien.liaison_2, ancien.k, ancien.sens, 0.95)
    ]
    res = _equilibre_reducteur(etude, 2.85)
    nom = etude.couplages[0].nom
    assert np.abs(res.vitesses_angulaires["Roue2"][:, 2] + 10.0).max() < 1e-4
    assert abs(res.efforts_couplages[nom][-1, 1]) == pytest.approx(2.85, rel=TOL)
    res = _equilibre_reducteur(etude, 3.0)
    assert abs(res.vitesses_angulaires["Roue2"][-1, 2] + 10.0) > 5.0


# ---------------------------------------------------------------------------- vis-écrou
COUPLE = 2.0  # N·m (SPEC EX-14)
EFFORT_SPEC = 2513.27  # N (SPEC EX-14)
EFFORT = 2.0 * math.pi * COUPLE / PAS  # 2 513,2741 N, valeur analytique 2π·C/p


def _vis_ecrou() -> Etude:
    etude = valider_tout(etude_enregistree("vis_ecrou", "pose0"))
    etude.pesanteur.actif = False
    return etude


def test_ex14_vis_ecrou_import() -> None:
    etude = _vis_ecrou()
    assert [x.type for x in etude.liaisons] == [TypeLiaison.PIVOT, TypeLiaison.GLISSIERE]
    assert len(etude.couplages) == 1
    c = etude.couplages[0]
    assert isinstance(c, VisEcrou)
    assert (c.liaison_1, c.liaison_2) == ("L_vis_pivot", "L_ecrou_glissiere")
    assert c.p == pytest.approx(PAS, rel=1e-12)


def test_ex14_vis_ecrou_vitesse() -> None:
    """p = 5 mm, ω = 10 rad/s : v = 7,9577 mm/s (axe de la vis, vers +z de SolidCraft)."""
    etude = _vis_ecrou()
    etude.pilotes = [pilote("L_vis_pivot", 10.0)]
    etude.reglages = reglages(1.0, 1000, 0.001)
    res = simuler_etude(etude, Mode.DYNAMIQUE)
    assert res.vitesses_angulaires["Vis"][-1, 2] == pytest.approx(10.0, rel=TOL)
    assert res.vitesses["Ecrou"][-1, 2] == pytest.approx(7.9577e-3, rel=1e-4)
    assert np.abs(res.vitesses["Ecrou"][-1, :2]).max() < 1e-9


def test_ex14_vis_ecrou_effort_axial() -> None:
    """Couple moteur 2 N·m sur la vis, effort résistant sur l'écrou : équilibre, effort axial
    transmis 2 513,27 N à 1e-3 près (le chargement vaut 2π·C/p, valeur analytique)."""
    assert EFFORT == pytest.approx(EFFORT_SPEC, abs=5e-3)
    etude = _vis_ecrou()
    etude.actions = [
        action("C", "Vis", NatureAction.COUPLE, (0.0, 0.0, COUPLE)),
        action("Fr", "Ecrou", NatureAction.FORCE, (0.0, 0.0, -EFFORT)),
    ]
    etude.reglages = reglages(0.5, 500, 0.001)
    res = MoteurExudynDyn().simuler(etude)
    nom = etude.couplages[0].nom
    assert np.abs(res.positions["Ecrou"][:, 2] - res.positions["Ecrou"][0, 2]).max() < 1e-4
    assert abs(res.efforts_couplages[nom][-1, 1]) == pytest.approx(EFFORT_SPEC, rel=TOL)
    assert abs(res.efforts_couplages[nom][-1, 0]) == pytest.approx(COUPLE, rel=TOL)


# ---------------------------------------------------------------------------- EX-44


# marqueur `perf` absent de cette branche (créé par le lot de finitions) : `slow` en attendant
@pytest.mark.slow
def test_ex44_bielle_moins_de_10_s() -> None:
    """Bielle-manivelle de référence, 1 s, 4 000 pas : moins de 10 s de calcul (EX-44), étude
    validée, garde-fou et traduction Exudyn compris."""
    etude = etude_bielle("00")
    debut = time.perf_counter()
    res = simuler_etude(etude, Mode.DYNAMIQUE)
    duree = time.perf_counter() - debut
    assert len(res.t) == 501
    assert duree < 10.0, f"{duree:.2f} s"
