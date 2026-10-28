# SPDX-License-Identifier: GPL-3.0-or-later
"""Lancement de SolidCraft et ouverture de la maquette (EX-07, lot 15).

SolidCraft 0.15.0 est livré en version portable : pas d'installation, pas d'entrée de registre.
L'exécutable est cherché à côté de Meca3D ; l'IHM demande et mémorise le chemin à défaut.
Constats du 28/10 (PC portable Polytech) : 22,7 s entre le lancement et la première réponse du
canal ; chaque instance réécrit `current.port`, d'où une connexion au port passé à `--control` ;
`doc.open` remplace la maquette ouverte sans rien demander, même modifiée (`dirty`) ;
`document.inspect` rend toujours `path: null` : seule la réponse de `doc.open` donne le chemin.
"""

import os
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

from meca3d.cao.canal import CanalSolidCraft, JetonIntrouvable, SolidCraftAbsent

NOM_EXECUTABLE = "solidcraft.exe"
PORT_LANCEMENT = 7878  # port du canal de contrôle passé à --control (EX-01, EX-07)
DELAI_LANCEMENT = 90.0  # s ; démarrage mesuré : 22,7 s (EX-07)
INTERVALLE_ATTENTE = 0.2  # s entre deux essais de connexion pendant le démarrage
PROFONDEUR_RECHERCHE = 2  # niveaux de sous-dossiers explorés sous chaque dossier de recherche


def dossiers_de_recherche() -> list[Path]:
    """Dossier de l'application (de l'exécutable, ou racine du dépôt en mode source) et son
    parent : une version portable de SolidCraft dézippée à côté de Meca3D y est trouvée."""
    if getattr(sys, "frozen", False):
        application = Path(sys.executable).resolve().parent
    else:
        application = Path(__file__).resolve().parents[3]
    return [application, application.parent]


def chercher_solidcraft(dossiers: Iterable[Path]) -> Path | None:
    """Premier `solidcraft.exe` des dossiers, à `PROFONDEUR_RECHERCHE` niveaux au plus."""
    for dossier in dossiers:
        if not dossier.is_dir():
            continue
        for profondeur in range(PROFONDEUR_RECHERCHE + 1):
            motif = "/".join(["*"] * profondeur + [NOM_EXECUTABLE])
            trouves = sorted(c for c in dossier.glob(motif) if c.is_file())
            if trouves:
                return trouves[0]
    return None


def lancer_solidcraft(executable: Path, port: int = PORT_LANCEMENT) -> subprocess.Popen[bytes]:
    """Lance SolidCraft avec son canal de contrôle, détaché : il survit à la fermeture de
    Meca3D (EX-07)."""
    options = 0
    if os.name == "nt":
        options = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    return subprocess.Popen(
        [str(executable), "--control", str(port)],
        cwd=executable.parent,
        creationflags=options,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def sonder_solidcraft(fabrique: Callable[[], CanalSolidCraft]) -> CanalSolidCraft | None:
    """Canal connecté si SolidCraft répond ; None s'il n'est pas lancé (pas de serveur, ou pas de
    fichier de jeton). Les autres erreurs (jeton refusé, occupé…) sont propagées."""
    canal = fabrique()
    try:
        canal.connecter()
        canal.requete("document.inspect")  # vérifie le jeton et la réponse (EX-01, EX-02)
    except (SolidCraftAbsent, JetonIntrouvable):
        canal.fermer()
        return None
    except BaseException:
        canal.fermer()
        raise
    return canal


def attendre_solidcraft(
    port: int,
    delai: float = DELAI_LANCEMENT,
    dossier_controle: Path | None = None,
    intervalle: float = INTERVALLE_ATTENTE,
    arret: threading.Event | None = None,
) -> CanalSolidCraft:
    """Attend que SolidCraft, tout juste lancé, réponde sur `port` ; rend le canal connecté.
    `arret` (fermeture de Meca3D) interrompt l'attente."""
    limite = time.monotonic() + delai
    arret = arret if arret is not None else threading.Event()
    while True:
        if arret.is_set():
            raise SolidCraftAbsent("Attente du démarrage de SolidCraft interrompue.")
        canal = sonder_solidcraft(
            lambda: CanalSolidCraft(port=port, dossier_controle=dossier_controle)
        )
        if canal is not None:
            return canal
        if time.monotonic() >= limite:
            duree = f"{delai:g}".replace(".", ",")
            raise SolidCraftAbsent(
                f"SolidCraft ne répond pas {duree} s après son lancement (port {port}) : "
                "vérifiez qu'il a démarré, puis utilisez SolidCraft > Connecter."
            )
        arret.wait(intervalle)


@dataclass(frozen=True)
class EtatMaquette:
    """Maquette ouverte dans SolidCraft : nom, modifications non enregistrées, document vide
    (SolidCraft tout juste lancé : ni corps ni historique, rien à perdre)."""

    nom: str
    modifiee: bool
    vide: bool


def etat_maquette(canal: CanalSolidCraft) -> EtatMaquette:
    inspection = canal.requete("document.inspect")
    return EtatMaquette(
        nom=str(inspection.get("name", "")),
        modifiee=bool(inspection.get("dirty", False)),
        vide=not inspection.get("bodies") and not inspection.get("timeline"),
    )


def meme_maquette(etat: EtatMaquette, chemin: Path) -> bool:
    """La maquette ouverte porte le nom du fichier `chemin`, sans tenir compte de la casse : le
    chemin de la maquette ouverte n'est pas lisible dans SolidCraft 0.15.0."""
    return not etat.vide and etat.nom.casefold() == chemin.stem.casefold()


def ouvrir_maquette(canal: CanalSolidCraft, chemin: Path) -> Path:
    """`doc.open` : remplace la maquette ouverte, SANS confirmation côté SolidCraft (EX-07).
    Rend le chemin du fichier ouvert, tel que SolidCraft le donne."""
    resultat = canal.executer("doc.open", {"path": str(chemin.resolve())})
    ouvert = resultat.get("path") if isinstance(resultat, dict) else None
    return Path(ouvert) if ouvert else chemin.resolve()
