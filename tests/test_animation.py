# SPDX-License-Identifier: GPL-3.0-or-later
"""Animation dans SolidCraft contre le faux serveur (EX-53) : séquences de commandes, poses,
restauration, vitesse et curseur. Poses de référence : cinématique analytique de la bielle-manivelle
(r = 100 mm, l = 300 mm, θ = 60° + 20·t), indépendante du code testé."""

import math
from collections.abc import Iterator

import numpy as np
import pytest
from faux_serveur import JETON_DE_TEST, FauxServeur
from outils_cinematique import etude_bielle_60

from meca3d.cao.animation import Animateur
from meca3d.cao.canal import CanalSolidCraft
from meca3d.modele.etude import Etude
from meca3d.moteur.base import ResultatsBruts
from meca3d.moteur.cinematique import MoteurCinematique

R_MM, L_MM = 100.0, 300.0
THETA0, OMEGA = math.radians(60.0), 20.0
IDENTIFIANTS = {"Manivelle": 5, "Bielle": 8, "Piston": 11}
TOLERANCE_ANGLE_DEG = 0.1  # SPEC EX-53


class Horloge:
    """Horloge injectable (frontière externe)."""

    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t


def _xb(theta: float) -> float:
    return R_MM * math.cos(theta) + math.sqrt(L_MM**2 - (R_MM * math.sin(theta)) ** 2)


def pose_analytique(t: float) -> dict[str, tuple[float, np.ndarray]]:
    """(angle autour de z en rad, origine du repère du composant en mm) de chaque solide mobile."""
    theta = THETA0 + OMEGA * t
    ax, ay = R_MM * math.cos(theta), R_MM * math.sin(theta)
    b = _xb(theta)
    phi = math.atan2(-ay, b - ax)
    origine_bielle = np.array([ax - R_MM * math.cos(phi), ay - R_MM * math.sin(phi), 0.0])
    return {
        "Manivelle": (theta, np.zeros(3)),
        "Bielle": (phi, origine_bielle),
        "Piston": (0.0, np.array([b - 400.0, 0.0, 0.0])),
    }


def ecart_angle_deg(a: float, b: float) -> float:
    return abs(math.degrees((a - b + math.pi) % (2 * math.pi) - math.pi))


def angle_z(pose: np.ndarray) -> float:
    return math.atan2(pose[1, 0], pose[0, 0])


@pytest.fixture(scope="module")
def etude() -> Etude:
    return etude_bielle_60(duree=0.6)


@pytest.fixture(scope="module")
def resultats(etude: Etude) -> ResultatsBruts:
    return MoteurCinematique().simuler(etude)


@pytest.fixture
def faux() -> Iterator[FauxServeur]:
    with FauxServeur(theta="60") as serveur:
        yield serveur


@pytest.fixture
def canal(faux: FauxServeur) -> Iterator[CanalSolidCraft]:
    with CanalSolidCraft(port=faux.port, jeton=JETON_DE_TEST) as c:
        yield c


def _verifier_poses(faux: FauxServeur, t: float, tolerance_mm: float = 1e-3) -> None:
    for nom, (angle, origine) in pose_analytique(t).items():
        pose = faux.pose(nom)
        assert ecart_angle_deg(angle_z(pose), angle) <= TOLERANCE_ANGLE_DEG, nom
        assert np.abs(pose[:3, 3] - origine).max() <= tolerance_mm, nom
        assert pose[2, 2] == pytest.approx(1.0, abs=1e-9), nom


def _poses_egales_aux_initiales(faux: FauxServeur) -> None:
    assert faux.poses_en_attente == {}
    for nom in IDENTIFIANTS:
        assert np.array_equal(faux.pose(nom), faux.pose_initiale(nom))


def test_ex53_pose_a_t_0_5_conforme_a_la_pose_simulee(
    faux: FauxServeur, canal: CanalSolidCraft, etude: Etude, resultats: ResultatsBruts
) -> None:
    animateur = Animateur(canal, etude, resultats)
    animateur.aller_a(0.5)
    _verifier_poses(faux, 0.5)
    animateur.terminer()


def test_ex53_un_batch_par_image_de_trois_deplacements(
    faux: FauxServeur, canal: CanalSolidCraft, etude: Etude, resultats: ResultatsBruts
) -> None:
    animateur = Animateur(canal, etude, resultats)
    for t in (0.1, 0.2, 0.3, 0.4):
        animateur.aller_a(t)
    assert len(faux.sequences_batch) == 4
    for sequence in faux.sequences_batch:
        assert [c["command"] for c in sequence] == ["occurrence.move"] * 3
        assert sorted(c["params"]["occurrence"] for c in sequence) == [5, 8, 11]
        assert all(c["params"]["capture"] is False for c in sequence)
    # aucun déplacement envoyé hors d'un engine.batch
    assert len([r for r in faux.requetes if r.get("method") == "engine.batch"]) == 4
    assert faux.methodes_recues().count("occurrence.move") == 0
    _verifier_poses(faux, 0.4)
    animateur.terminer()


def test_ex53_le_solide_fixe_n_est_pas_deplace(
    faux: FauxServeur, canal: CanalSolidCraft, etude: Etude, resultats: ResultatsBruts
) -> None:
    animateur = Animateur(canal, etude, resultats)
    animateur.aller_a(0.3)
    deplacees = {c["params"]["occurrence"] for s in faux.sequences_batch for c in s}
    assert 2 not in deplacees  # Bati:1
    animateur.terminer()


def test_ex53_restauration_en_fin_d_animation(
    faux: FauxServeur, canal: CanalSolidCraft, etude: Etude, resultats: ResultatsBruts
) -> None:
    horloge = Horloge()
    animateur = Animateur(canal, etude, resultats, horloge=horloge)
    animateur.lire()
    images = 0
    while animateur.en_lecture:
        horloge.t += 0.05
        animateur.avancer()
        images += 1
        assert images < 100
    assert animateur.position == pytest.approx(animateur.duree, abs=1e-12)
    _poses_egales_aux_initiales(faux)
    assert faux.commandes_recues()[-1] == "component.revert_position"
    assert len(faux.sequences_batch) >= 5


def test_ex53_restauration_sur_exception(
    faux: FauxServeur, canal: CanalSolidCraft, etude: Etude, resultats: ResultatsBruts
) -> None:
    with pytest.raises(RuntimeError, match="boum"):
        with Animateur(canal, etude, resultats) as animateur:
            animateur.aller_a(0.35)
            assert faux.poses_en_attente  # des déplacements sont bien en attente
            raise RuntimeError("boum")
    _poses_egales_aux_initiales(faux)


def test_ex53_restauration_si_la_lecture_est_interrompue_par_une_erreur(
    faux: FauxServeur, canal: CanalSolidCraft, etude: Etude, resultats: ResultatsBruts
) -> None:
    appels = {"n": 0}

    def horloge_defaillante() -> float:
        appels["n"] += 1
        if appels["n"] > 6:
            raise RuntimeError("horloge en panne")
        return appels["n"] * 0.05

    animateur = Animateur(canal, etude, resultats, horloge=horloge_defaillante)
    with pytest.raises(RuntimeError, match="horloge"):
        animateur.jouer()
    assert faux.sequences_batch  # au moins une image a été jouée
    _poses_egales_aux_initiales(faux)


def test_ex53_jouer_rend_le_nombre_d_images_et_restaure(
    faux: FauxServeur, canal: CanalSolidCraft, etude: Etude, resultats: ResultatsBruts
) -> None:
    horloge = Horloge()

    def attente(duree: float) -> None:
        horloge.t += 0.1

    animateur = Animateur(canal, etude, resultats, horloge=horloge, attente=attente)
    images = animateur.jouer()
    assert images == len(faux.sequences_batch) >= 5
    _poses_egales_aux_initiales(faux)


def test_ex53_jamais_d_enregistrement_de_la_maquette(
    faux: FauxServeur, canal: CanalSolidCraft, etude: Etude, resultats: ResultatsBruts
) -> None:
    with Animateur(canal, etude, resultats) as animateur:
        animateur.aller_a(0.2)
        animateur.aller_a(0.5)
        animateur.tracer_trajectoire((0.0, 0.0, 0.0), "Piston")
        animateur.effacer_trajectoires()
    noms = faux.commandes_recues()
    assert noms  # l'animation a bien parlé à SolidCraft
    assert not [n for n in noms if "save" in n.lower() or n.startswith("doc.")]
    assert not [m for m in faux.methodes_recues() if "save" in m.lower()]


def test_ex53_vitesse_plage_et_message(
    canal: CanalSolidCraft, etude: Etude, resultats: ResultatsBruts
) -> None:
    animateur = Animateur(canal, etude, resultats)
    for valeur in (0.1, 0.5, 1.0, 2.0):
        animateur.vitesse = valeur
        assert animateur.vitesse == valeur
    for invalide in (0.05, 2.5, 0.0, -1.0):
        with pytest.raises(ValueError, match="0,1"):
            animateur.vitesse = invalide
    assert animateur.vitesse == 2.0


@pytest.mark.parametrize(("vitesse", "attendu"), [(0.1, 0.02), (0.5, 0.1), (1.0, 0.2), (2.0, 0.4)])
def test_ex53_vitesse_de_lecture(
    canal: CanalSolidCraft, etude: Etude, resultats: ResultatsBruts, vitesse: float, attendu: float
) -> None:
    horloge = Horloge()
    animateur = Animateur(canal, etude, resultats, horloge=horloge)
    animateur.vitesse = vitesse
    animateur.lire()
    horloge.t = 0.2
    assert animateur.avancer() is True
    assert animateur.position == pytest.approx(attendu, abs=1e-9)
    animateur.terminer()


def test_ex53_changer_de_vitesse_en_lecture_ne_fait_pas_de_saut(
    canal: CanalSolidCraft, etude: Etude, resultats: ResultatsBruts
) -> None:
    horloge = Horloge()
    animateur = Animateur(canal, etude, resultats, horloge=horloge)
    animateur.lire()
    horloge.t = 0.2
    animateur.avancer()
    assert animateur.position == pytest.approx(0.2, abs=1e-9)
    animateur.vitesse = 0.5
    horloge.t = 0.4
    animateur.avancer()
    assert animateur.position == pytest.approx(0.3, abs=1e-9)
    animateur.terminer()


def test_ex53_pause_fige_la_position_et_n_envoie_rien(
    faux: FauxServeur, canal: CanalSolidCraft, etude: Etude, resultats: ResultatsBruts
) -> None:
    horloge = Horloge()
    animateur = Animateur(canal, etude, resultats, horloge=horloge)
    animateur.lire()
    horloge.t = 0.1
    animateur.avancer()
    position = animateur.position
    envoyes = len(faux.sequences_batch)
    animateur.pause()
    assert animateur.en_lecture is False
    horloge.t = 0.5
    assert animateur.avancer() is False
    assert animateur.position == position
    assert len(faux.sequences_batch) == envoyes
    animateur.lire()  # reprise : repart de la position, sans saut
    horloge.t = 0.6
    animateur.avancer()
    assert animateur.position == pytest.approx(position + 0.1, abs=1e-9)
    animateur.terminer()


def test_ex53_curseur_temporel(
    faux: FauxServeur, canal: CanalSolidCraft, etude: Etude, resultats: ResultatsBruts
) -> None:
    animateur = Animateur(canal, etude, resultats)
    assert animateur.duree == pytest.approx(0.6, abs=1e-9)
    animateur.aller_a(0.25)
    assert animateur.position == pytest.approx(0.25, abs=1e-12)
    _verifier_poses(faux, 0.25)
    animateur.aller_a(0.05)  # retour en arrière
    _verifier_poses(faux, 0.05)
    animateur.aller_a(-3.0)  # bornes
    assert animateur.position == 0.0
    animateur.aller_a(99.0)
    assert animateur.position == pytest.approx(animateur.duree, abs=1e-12)
    _verifier_poses(faux, animateur.duree)
    animateur.terminer()


def test_ex53_curseur_entre_deux_echantillons_est_interpole(
    faux: FauxServeur, canal: CanalSolidCraft, etude: Etude, resultats: ResultatsBruts
) -> None:
    animateur = Animateur(canal, etude, resultats)
    animateur.aller_a(0.30037)  # entre deux points de la grille de 0,5 ms
    _verifier_poses(faux, 0.30037, tolerance_mm=5e-3)  # erreur de l'interpolation linéaire
    animateur.terminer()


def test_ex53_relecture_apres_restauration_puis_nouvelle_lecture(
    faux: FauxServeur, canal: CanalSolidCraft, etude: Etude, resultats: ResultatsBruts
) -> None:
    animateur = Animateur(canal, etude, resultats)
    animateur.aller_a(0.4)
    animateur.terminer()
    _poses_egales_aux_initiales(faux)
    animateur.terminer()  # idempotent : aucune requête de plus
    n = len(faux.requetes)
    animateur.terminer()
    assert len(faux.requetes) == n
    animateur.aller_a(0.5)  # on peut rejouer après la restauration
    _verifier_poses(faux, 0.5)
    animateur.terminer()
    _poses_egales_aux_initiales(faux)
