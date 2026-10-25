# SPDX-License-Identifier: GPL-3.0-or-later
"""Animation de la bielle-manivelle dans le vrai SolidCraft lancé avec `--control 7878`, maquette
`bielle_manivelle.solidcraft` ouverte à θ = 60° (manuel : `uv run pytest -m solidcraft`). La
maquette n'est jamais enregistrée ; sa pose, son état `dirty` et sa pile d'annulation doivent être
rendus identiques. La fenêtre de SolidCraft doit rester visible (sinon ~115 ms par requête)."""

import math
import tempfile
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from meca3d.cao.animation import Animateur
from test_animation import angle_z, ecart_angle_deg, pose_analytique

from meca3d.cao.canal import CanalSolidCraft
from meca3d.cao.solidcraft import importer
from meca3d.modele.actions import LoiEntree, Pesanteur, Pilote
from meca3d.modele.etude import Etude, Reglages
from meca3d.modele.liaison import TypeLiaison
from meca3d.moteur.base import ResultatsBruts
from meca3d.moteur.cinematique import MoteurCinematique

pytestmark = pytest.mark.solidcraft

THETA0_RAD = math.radians(60.0)
OMEGA = 20.0
CADENCE_MIN = 20.0  # images/s (SPEC EX-53)
IDENTIFIANTS = {"Manivelle": 5, "Bielle": 8, "Piston": 11}


@pytest.fixture(scope="module")
def canal() -> Iterator[CanalSolidCraft]:
    c = CanalSolidCraft(port=7878)
    yield c
    c.fermer()


def etat_document(canal: CanalSolidCraft) -> dict[str, Any]:
    d = canal.requete("document.inspect")
    return {k: d[k] for k in ("name", "dirty", "undo", "marker")}


def instantane(canal: CanalSolidCraft) -> dict[str, Any]:
    """Poses (component.list), valeurs articulaires (joint.list) et état du document."""
    composants = canal.executer("component.list")
    racine = next(c for c in composants["components"] if c.get("parent") is None)
    poses = {o["name"]: np.array(o["transform"], dtype=float) for o in racine["children"]}
    liaisons = {
        j["name"]: [v["value"] for v in j["values"]] for j in canal.executer("joint.list")["joints"]
    }
    return {
        "poses": poses,
        "liaisons": liaisons,
        "en_attente": composants.get("pending_moves", []),
        "document": etat_document(canal),
    }


@pytest.fixture(scope="module")
def etude(canal: CanalSolidCraft) -> Etude:
    with tempfile.TemporaryDirectory(prefix="meca3d_test_") as dossier:
        e = importer(canal, Path(dossier))
    angle = e.liaison("L01_pivot").valeur_pose
    if angle is None or abs(angle - THETA0_RAD) > 1e-6:
        pytest.skip("la maquette ouverte doit être la bielle-manivelle à θ = 60°")
    e.maquette = "bielle_manivelle.solidcraft"
    e.liaison("L23_rotule").type = TypeLiaison.LINEAIRE_ANNULAIRE
    e.liaison("L23_rotule").reorienter_axe((0.0, 0.0, 1.0))
    for liaison in e.liaisons:
        liaison.valider()
    e.pilotes = [Pilote("L01_pivot", LoiEntree(f"{THETA0_RAD!r} + {OMEGA!r}*t"))]
    e.pesanteur = Pesanteur(actif=False)
    e.reglages = Reglages(duree=1.0, nb_pas=4000, periode_ecriture=0.002)
    return e


@pytest.fixture(scope="module")
def resultats(etude: Etude) -> ResultatsBruts:
    return MoteurCinematique().simuler(etude)


def _pose_relue(canal: CanalSolidCraft, identifiant: int) -> np.ndarray:
    """Pose réelle, en attente comprise : un déplacement nul rend la transformation effective
    (`component.list` ne montre pas les déplacements en attente)."""
    reponse = canal.executer(
        "occurrence.move",
        {"occurrence": identifiant, "space": "world", "translate": [0, 0, 0], "capture": False},
    )
    return np.array(reponse["transform"], dtype=float).T


def test_ex53_pose_a_t_0_5_conforme_et_restauration_exacte(
    canal: CanalSolidCraft, etude: Etude, resultats: ResultatsBruts
) -> None:
    avant = instantane(canal)
    assert avant["document"]["dirty"] is False
    animateur = Animateur(canal, etude, resultats)
    try:
        animateur.aller_a(0.5)
        for nom, (angle, origine) in pose_analytique(0.5).items():
            pose = _pose_relue(canal, IDENTIFIANTS[nom])
            assert ecart_angle_deg(angle_z(pose), angle) <= 0.1, nom
            assert np.abs(pose[:3, 3] - origine).max() <= 1e-3, nom  # mm
        # centre de gravité du piston relu indépendamment (monde, mm) : x_B
        cdg = canal.executer("occurrence.properties", {"occurrence": 11})["total"]["center_of_mass"]
        assert cdg[0] == pytest.approx(pose_analytique(0.5)["Piston"][1][0] + 400.0, abs=1e-3)
        assert etat_document(canal)["dirty"] is False  # aucun salissement pendant l'animation
    finally:
        animateur.terminer()
    apres = instantane(canal)
    assert apres["en_attente"] == []
    for nom, pose in avant["poses"].items():
        assert np.abs(apres["poses"][nom] - pose).max() <= 1e-9, nom
    for nom, valeurs in avant["liaisons"].items():
        assert np.abs(np.array(apres["liaisons"][nom]) - np.array(valeurs)).max() <= 1e-9, nom
    assert apres["document"] == avant["document"]
    assert apres["document"]["dirty"] is False


def test_ex53_cadence_mesuree_au_moins_20_images_par_seconde(
    canal: CanalSolidCraft, etude: Etude, resultats: ResultatsBruts
) -> None:
    avant = instantane(canal)
    animateur = Animateur(canal, etude, resultats)
    debut = time.perf_counter()
    images = animateur.jouer()  # lecture en temps réel, vitesse ×1, restauration en fin
    duree = time.perf_counter() - debut
    cadence_lecture = images / duree
    # débit brut : 100 images consécutives, une requête engine.batch chacune
    animateur2 = Animateur(canal, etude, resultats)
    instants = np.linspace(0.0, animateur2.duree, 100)
    debut = time.perf_counter()
    try:
        for t in instants:
            animateur2.aller_a(float(t))
    finally:
        cadence_brute = len(instants) / (time.perf_counter() - debut)
        animateur2.terminer()
    print(
        f"\ncadence : lecture temps réel {cadence_lecture:.1f} images/s ({images} images en "
        f"{duree:.2f} s), débit brut {cadence_brute:.1f} images/s"
    )
    assert cadence_lecture >= CADENCE_MIN
    assert cadence_brute >= CADENCE_MIN
    apres = instantane(canal)
    assert apres["en_attente"] == []
    assert apres["document"] == avant["document"]
    for nom, pose in avant["poses"].items():
        assert np.abs(apres["poses"][nom] - pose).max() <= 1e-9, nom


def test_ex52_trajectoire_reelle_tracee_puis_effacee(
    canal: CanalSolidCraft, etude: Etude, resultats: ResultatsBruts
) -> None:
    """La trajectoire modifie la maquette (esquisse 3D) : on encadre par un point de contrôle
    d'édition pour rendre `dirty` et la pile d'annulation exactement comme avant."""
    avant = etat_document(canal)
    point = canal.executer("edit.checkpoint")
    identifiant = point["checkpoint"]
    animateur = Animateur(canal, etude, resultats)
    try:
        b_import = (0.05 + math.sqrt(0.09 - 0.0075), 0.0, 0.0)
        nom = animateur.tracer_trajectoire(b_import, "Piston", nom="Trajectoire_B")
        esquisses = canal.requete("document.inspect")["sketches"]
        assert nom in [e["name"] if isinstance(e, dict) else e for e in esquisses]
        assert animateur.effacer_trajectoires() == 1
        esquisses = canal.requete("document.inspect")["sketches"]
        assert nom not in [e["name"] if isinstance(e, dict) else e for e in esquisses]
    finally:
        animateur.terminer()
        canal.executer("edit.restore_checkpoint", {"checkpoint": identifiant})
        canal.executer("edit.restore_checkpoint", {"checkpoint": identifiant, "forget": True})
    assert etat_document(canal) == avant
