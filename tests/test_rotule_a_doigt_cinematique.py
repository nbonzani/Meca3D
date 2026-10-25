# SPDX-License-Identifier: GPL-3.0-or-later
"""Rotule à doigt : équation de liaison au niveau vitesse du mode cinématique.

Exudyn contraint Rz de la rotule à doigt par (x local du solide a)·(y local du solide b) = 0 : la
vitesse angulaire relative n'est donc pas orthogonale à z local (seulement à l'instant initial).
Les vitesses d'un mouvement simulé doivent annuler les équations de liaison du mode cinématique.
"""

import numpy as np
import pytest

from meca3d.modele.actions import Pesanteur
from meca3d.modele.etude import Etude, Reglages
from meca3d.modele.liaison import Liaison, TypeLiaison
from meca3d.modele.solide import Solide
from meca3d.moteur.base import ResultatsBruts
from meca3d.moteur.cinematique import residu_vitesses
from meca3d.moteur.exudyn_dyn import MoteurExudynDyn

OMEGA_0 = np.array([1.3, 0.9, 0.0])  # rad/s : rotation libre autour de x et y


@pytest.fixture(scope="module")
def etude() -> Etude:
    bati = Solide("Bati", True, 1.0, np.zeros(3), np.eye(3))
    corps = Solide("C", False, 1.0, np.array([0.0, 0.0, -0.3]), np.diag([0.01, 0.02, 0.03]))
    liaison = Liaison("L", "ball", "Bati", "C", np.zeros(3), np.array([0.0, 0.0, 1.0]), None)
    liaison.choisir(TypeLiaison.ROTULE_A_DOIGT)
    liaison.definir_direction((1.0, 0.0, 0.0))
    liaison.valider()
    return Etude(
        [bati, corps],
        [liaison],
        pesanteur=Pesanteur(vecteur=(0.0, 0.0, -9.81)),
        reglages=Reglages(duree=0.8, nb_pas=4000, periode_ecriture=0.002),
    )


@pytest.fixture(scope="module")
def resultats(etude: Etude) -> ResultatsBruts:
    vitesse = np.cross(OMEGA_0, [0.0, 0.0, -0.3])
    return MoteurExudynDyn().simuler(etude, vitesses_initiales={"C": (vitesse, OMEGA_0)})


def test_rotule_a_doigt_mouvement_de_grande_amplitude(resultats: ResultatsBruts) -> None:
    rotation = resultats.rotations["C"]
    angle = np.degrees(np.arccos((np.trace(rotation, axis1=1, axis2=2) - 1.0) / 2.0))
    assert angle.max() > 10.0  # le test sort du voisinage de l'import
    # le doigt : R[0, 1] = (x local de a)·(y local de b) reste nul, alors que R[1, 0] ne l'est pas
    assert np.abs(rotation[:, 0, 1]).max() < 1e-9
    assert np.abs(rotation[:, 1, 0]).max() > 1e-2


def test_rotule_a_doigt_vitesses_compatibles_avec_les_equations_de_liaison(
    etude: Etude, resultats: ResultatsBruts
) -> None:
    # vitesses des capteurs d'Exudyn (erreur en O(h), de l'ordre de 1e-5) : le résidu est faible ;
    # avec la condition ω_rel·z = 0 (premier ordre), il atteindrait 1e-1
    residu = residu_vitesses(etude, resultats)
    assert residu.shape[1] == 4  # trois translations bloquées et le doigt
    assert np.abs(residu).max() < 1e-3
