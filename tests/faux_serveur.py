# SPDX-License-Identifier: GPL-3.0-or-later
"""Faux serveur du canal de contrôle SolidCraft (frontière externe, D2).

Rejoue les réponses enregistrées de `tests/fixtures/bielle/solidcraft/` : une ligne JSON par
message, port éphémère, jeton attendu sur la première requête de chaque connexion. Les scénarios
(jeton refusé, busy, timeout puis control.pending, coupure, structure modifiée, poses modifiées
seules, format différent, liaison sur sous-occurrence) s'injectent par `Scenario` ou par les
attributs du serveur. `file.export` écrit réellement les fichiers (copie des exports enregistrés),
dans un dossier qui doit exister.

Animation et trajectoires (lot 10, EX-53, EX-52) : `occurrence.move` (relatif, cumulatif, en
attente avec `capture: false`, comme le vrai SolidCraft : `component.list` ne montre pas les poses
en attente, seul `pending_moves` les liste), `engine.batch`, `component.revert_position`,
`sketch.create` / `sketch.options` / `sketch.spline3d` / `sketch.finish`, `timeline.delete`.
`sequences_batch` garde les séquences reçues, `commandes_recues()` toutes les commandes dans
l'ordre (lots compris), `pose(nom)` la pose courante (en attente comprise) d'une occurrence.
"""

import copy
import json
import shutil
import socket
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

DOSSIER = Path(__file__).parent / "fixtures" / "bielle" / "solidcraft"
JETON_DE_TEST = "0123456789abcdef0123456789abcdef"  # valeur fictive, sans lien avec un vrai jeton

# Sous-occurrence ajoutée par le scénario `sous_occurrence` (enfant du composant Manivelle)
ID_SOUS_OCCURRENCE = 14
NOM_SOUS_OCCURRENCE = "Goupille:1"
NOM_LIAISON_SOUS_OCCURRENCE = "L_goupille"


@dataclass
class Esquisse:
    """Esquisse créée par `sketch.create` (trajectoires, EX-52)."""

    identifiant: int
    nom: str
    sketch_3d: bool = False
    termine: bool = False
    points: list[list[float]] = field(default_factory=list)


@dataclass
class Scenario:
    """Comportements anormaux du faux serveur ; tout à sa valeur par défaut = serveur sain.

    `jeton_attendu` : jeton exigé sur la première requête (None : aucun contrôle).
    `occupe_sur` : méthode (ou commande de engine.execute) à laquelle le serveur répond busy.
    `timeout_sur` : méthode (ou commande) dont la première occurrence répond « timeout » ; la
    vraie réponse est ensuite livrée par control.pending après `pending_attentes` réponses
    `done: false`.
    `coupure_sur` : méthode (ou commande) qui provoque la fermeture de la connexion sans réponse.
    `revision` : remplace la révision de document.inspect (None : valeur de la fixture).
    `format_export` : remplace le champ `format` de l'export JSON.
    `sous_occurrence` : ajoute une liaison visant une sous-occurrence.
    `fenetre_reduite` : la fenêtre est réduite : chaque requête coûte `latence_reduite` s (115 ms
    mesurés, RESULTATS_1b § Q3) jusqu'à un `ui.window {"action": "maximize"}`.
    """

    jeton_attendu: str | None = JETON_DE_TEST
    occupe_sur: str | None = None
    timeout_sur: str | None = None
    pending_attentes: int = 1
    coupure_sur: str | None = None
    revision: int | None = None
    format_export: str | None = None
    sous_occurrence: bool = False
    fenetre_reduite: bool = False
    latence_reduite: float = 0.12


def _lire(nom: str) -> Any:
    return json.loads((DOSSIER / nom).read_text(encoding="utf-8"))


class FauxServeur:
    """Serveur TCP en thread. `requetes` : toutes les requêtes reçues (dicts), dans l'ordre."""

    def __init__(self, theta: str = "00", scenario: Scenario | None = None) -> None:
        self.theta = theta
        self.scenario = scenario or Scenario()
        self.requetes: list[dict[str, Any]] = []
        # Modifications de STRUCTURE de la maquette (EX-06), changeables en cours de test :
        # type SolidCraft imposé à des liaisons (nom -> type) et couplages de joint.list `links`.
        # Modification de POSE seule : changer `theta` ("00" -> "60"), la structure est identique.
        self.types_modifies: dict[str, str] = {}
        self.links: list[dict[str, Any]] | None = None
        self.connexions = 0
        # Animation (lot 10) : poses en attente (matrices 4×4 usuelles, mm) par identifiant
        # d'occurrence, séquences d'engine.batch, esquisses de trajectoires
        self.poses_en_attente: dict[int, np.ndarray] = {}
        self.sequences_batch: list[list[dict[str, Any]]] = []
        self.esquisses: list[Esquisse] = []
        self._verrou = threading.Lock()
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._socket.bind(("127.0.0.1", 0))
        self._socket.listen(8)
        self.port: int = self._socket.getsockname()[1]
        self._actif = True
        self._clients: list[socket.socket] = []
        self._thread = threading.Thread(target=self._accepter, daemon=True)
        self._thread.start()

    # --- cycle de vie ---------------------------------------------------------------------
    def __enter__(self) -> "FauxServeur":
        return self

    def __exit__(self, *_: object) -> None:
        self.arreter()

    def arreter(self) -> None:
        self._actif = False
        try:
            self._socket.close()
        except OSError:
            pass
        for client in list(self._clients):
            try:
                client.close()
            except OSError:
                pass

    @property
    def revision(self) -> int:
        if self.scenario.revision is not None:
            return self.scenario.revision
        return int(_lire(f"document_inspect_theta{self.theta}.json")["revision"])

    @revision.setter
    def revision(self, valeur: int) -> None:
        """Simule une modification de la maquette entre deux lectures."""
        self.scenario.revision = valeur

    def commandes_recues(self) -> list[str]:
        """Noms de toutes les commandes reçues dans l'ordre, les lots d'engine.batch dépliés."""
        noms: list[str] = []
        for r in self.requetes:
            if r.get("method") == "engine.batch":
                noms.extend(str(c["command"]) for c in (r.get("params") or {})["commands"])
            else:
                noms.append(_nom(r))
        return noms

    def _occurrences(self) -> dict[int, tuple[str, np.ndarray]]:
        """Occurrences de premier niveau : identifiant -> (nom, pose initiale 4×4, mm)."""
        liste = _lire(f"component_list_theta{self.theta}.json")
        racine = next(c for c in liste["components"] if c.get("parent") is None)
        return {
            o["id"]: (o["name"], np.array(o["transform"], dtype=float).T)
            for o in racine["children"]
        }

    def pose(self, nom: str) -> np.ndarray:
        """Pose courante 4×4 (mm, en attente comprise) de l'occurrence « Manivelle:1 » ou
        « Manivelle »."""
        for ident, (n, initiale) in self._occurrences().items():
            if n == nom or n.rsplit(":", 1)[0] == nom:
                return self.poses_en_attente.get(ident, initiale)
        raise KeyError(nom)

    def pose_initiale(self, nom: str) -> np.ndarray:
        for n, initiale in self._occurrences().values():
            if n == nom or n.rsplit(":", 1)[0] == nom:
                return initiale
        raise KeyError(nom)

    def methodes_recues(self) -> list[str]:
        """Noms des requêtes reçues : la commande pour engine.execute, sinon la méthode."""
        return [_nom(r) for r in self.requetes]

    # --- réseau ---------------------------------------------------------------------------
    def _accepter(self) -> None:
        while self._actif:
            try:
                client, _ = self._socket.accept()
            except OSError:
                return
            self._clients.append(client)
            with self._verrou:
                self.connexions += 1
            threading.Thread(target=self._servir, args=(client,), daemon=True).start()

    def _servir(self, client: socket.socket) -> None:
        etat: dict[str, Any] = {"authentifie": False, "pending": None}
        tampon = b""
        try:
            while self._actif:
                while b"\n" not in tampon:
                    morceau = client.recv(65536)
                    if not morceau:
                        return
                    tampon += morceau
                ligne, tampon = tampon.split(b"\n", 1)
                requete = json.loads(ligne.decode("utf-8"))
                with self._verrou:
                    self.requetes.append(requete)
                reponse = self._traiter(requete, etat)
                if reponse is None:  # coupure
                    return
                client.sendall((json.dumps(reponse) + "\n").encode("utf-8"))
                if reponse.get("error", "").startswith("unauthorized:"):
                    return
        except (OSError, ValueError):
            pass
        finally:
            try:
                client.close()
            except OSError:
                pass

    # --- logique de protocole -------------------------------------------------------------
    def _traiter(self, requete: dict[str, Any], etat: dict[str, Any]) -> dict[str, Any] | None:
        ident = requete.get("id")
        sc = self.scenario
        if not etat["authentifie"]:
            if sc.jeton_attendu is not None and requete.get("token") != sc.jeton_attendu:
                return {"id": ident, "ok": False, "error": "unauthorized: jeton absent ou faux"}
            etat["authentifie"] = True
        methode = requete.get("method")
        nom = _nom(requete)
        if methode == "control.pending":
            return self._pending(ident, etat)
        if etat["pending"] is not None:
            return {"id": ident, "ok": False, "busy": True, "error": "busy: requête en cours"}
        if sc.coupure_sur == nom:
            return None
        if sc.occupe_sur == nom:
            return {"id": ident, "ok": False, "busy": True, "error": "busy: occupé"}
        reponse = self._repondre(requete)
        if sc.timeout_sur == nom:
            sc.timeout_sur = None  # une seule fois
            etat["pending"] = {"reponse": reponse, "attentes": sc.pending_attentes, "id": ident}
            return {
                "id": ident,
                "ok": False,
                "running": True,
                "error": f"timeout: {nom} is still running, do not resend",
            }
        return reponse

    def _pending(self, ident: Any, etat: dict[str, Any]) -> dict[str, Any]:
        attente = etat["pending"]
        if attente is None:
            return {"id": ident, "ok": True, "result": {"pending": None}}
        if attente["attentes"] > 0:
            attente["attentes"] -= 1
            resultat: dict[str, Any] = {
                "pending": attente["id"],
                "method": "engine.execute",
                "done": False,
            }
        else:
            etat["pending"] = None
            resultat = {
                "pending": attente["id"],
                "method": "engine.execute",
                "done": True,
                "reply": attente["reponse"],
            }
        return {"id": ident, "ok": True, "result": resultat}

    def _repondre(self, requete: dict[str, Any]) -> dict[str, Any]:
        ident = requete.get("id")
        methode = requete.get("method")
        if self.scenario.fenetre_reduite and methode != "ui.window":
            time.sleep(self.scenario.latence_reduite)
        if methode == "ui.window":
            action = (requete.get("params") or {}).get("action")
            etat = {"custom_titlebar": True, "maximized": not self.scenario.fenetre_reduite}
            if action == "maximize":  # seule action qui ramène une fenêtre réduite (mesuré)
                self.scenario.fenetre_reduite = False
            return {"id": ident, "ok": True, "result": etat}
        if methode == "document.inspect":
            inspection = _lire(f"document_inspect_theta{self.theta}.json")
            inspection["revision"] = self.revision
            return {"id": ident, "ok": True, "result": inspection}
        if methode == "engine.batch":
            return self._lot(ident, requete.get("params") or {})
        if methode == "engine.execute":
            params = requete.get("params") or {}
            return self._commande(ident, params.get("command"), params.get("params") or {})
        return {"id": ident, "ok": False, "error": f"unknown method: {methode}"}

    def _commande(self, ident: Any, commande: str | None, params: dict[str, Any]) -> dict[str, Any]:
        theta = self.theta
        if commande == "joint.list":
            return {"id": ident, "ok": True, "result": self._joint_list()}
        if commande == "component.list":
            return {"id": ident, "ok": True, "result": self._component_list()}
        if commande == "component.properties":
            propriete = _lire(f"component_properties_theta{theta}.json").get(
                str(params.get("component"))
            )
            if propriete is None:
                return {"id": ident, "ok": False, "error": "component introuvable"}
            return {"id": ident, "ok": True, "result": propriete}
        if commande == "file.export":
            return self._exporter(ident, params)
        if commande == "occurrence.move":
            return self._deplacer(ident, params)
        if commande == "component.revert_position":
            return self._revenir(ident, params)
        if commande in ("sketch.create", "sketch.options", "sketch.spline3d", "sketch.finish"):
            return self._esquisse(ident, commande, params)
        if commande == "timeline.delete":
            return self._supprimer(ident, params)
        return {"id": ident, "ok": False, "error": f"unknown command: {commande}"}

    # --- animation et trajectoires (lot 10) -----------------------------------------------
    def _lot(self, ident: Any, params: dict[str, Any]) -> dict[str, Any]:
        commandes = list(params.get("commands") or [])
        self.sequences_batch.append(commandes)
        resultats: list[Any] = []
        for commande in commandes:
            reponse = self._commande(ident, commande.get("command"), commande.get("params") or {})
            if not reponse.get("ok"):
                return {
                    "id": ident,
                    "ok": False,
                    "error": f"batch: {commande.get('command')}: {reponse.get('error')}",
                }
            resultats.append(reponse["result"])
        return {
            "id": ident,
            "ok": True,
            "result": {"completed": len(resultats), "undone": 0, "results": resultats},
        }

    def _deplacer(self, ident: Any, params: dict[str, Any]) -> dict[str, Any]:
        occurrence = params.get("occurrence")
        if occurrence not in self._occurrences():
            return {"id": ident, "ok": False, "error": f"occurrence inconnue : {occurrence}"}
        if params.get("space") != "world":
            return {"id": ident, "ok": False, "error": "le faux serveur ne gère que space=world"}
        if params.get("capture", True):
            return {"id": ident, "ok": False, "error": "le faux serveur exige capture=false"}
        courante = self.poses_en_attente.get(occurrence, self._occurrences()[occurrence][1])
        delta = np.eye(4)
        if params.get("axis") is not None:
            axe = np.array(params["axis"], dtype=float)
            axe /= np.linalg.norm(axe)
            angle = float(params["angle"])
            k = np.array([[0, -axe[2], axe[1]], [axe[2], 0, -axe[0]], [-axe[1], axe[0], 0]])
            rotation = np.eye(3) + np.sin(angle) * k + (1 - np.cos(angle)) * (k @ k)
            origine = np.array(params.get("origin") or [0.0, 0.0, 0.0], dtype=float)
            delta[:3, :3] = rotation
            delta[:3, 3] = origine - rotation @ origine
        delta[:3, 3] += np.array(params.get("translate") or [0.0, 0.0, 0.0], dtype=float)
        nouvelle = delta @ courante
        self.poses_en_attente[occurrence] = nouvelle
        resultat = {"occurrence": occurrence, "pending": True, "transform": nouvelle.T.tolist()}
        return {"id": ident, "ok": True, "result": resultat}

    def _revenir(self, ident: Any, params: dict[str, Any]) -> dict[str, Any]:
        visees = params.get("occurrences")
        ids = list(self.poses_en_attente) if visees is None else list(visees)
        retirees = [i for i in ids if self.poses_en_attente.pop(i, None) is not None]
        return {"id": ident, "ok": True, "result": {"reverted": len(retirees)}}

    def _esquisse(self, ident: Any, commande: str, params: dict[str, Any]) -> dict[str, Any]:
        if commande == "sketch.create":
            nom = str(params.get("name") or f"Esquisse{len(self.esquisses) + 1}")
            if any(e.nom == nom for e in self.esquisses):
                nom = f"{nom}_{len(self.esquisses) + 1}"
            esquisse = Esquisse(identifiant=100 + len(self.esquisses), nom=nom)
            self.esquisses.append(esquisse)
            resultat = {"name": nom, "sketch": esquisse.identifiant}
            return {"id": ident, "ok": True, "result": resultat}
        if not self.esquisses:
            return {"id": ident, "ok": False, "error": "aucune esquisse active"}
        courante = self.esquisses[-1]
        if commande == "sketch.options":
            courante.sketch_3d = bool(params.get("sketch_3d", courante.sketch_3d))
            resultat = {"options": {"sketch_3d": courante.sketch_3d}}
            return {"id": ident, "ok": True, "result": resultat}
        if commande == "sketch.spline3d":
            if not courante.sketch_3d:
                return {"id": ident, "ok": False, "error": "3D Sketch required"}
            points = [[float(x) for x in p] for p in params.get("points") or []]
            if len(points) < 2:
                return {"id": ident, "ok": False, "error": "2 points au moins"}
            courante.points = points
            return {"id": ident, "ok": True, "result": {"created": {"curves": ["w1"]}}}
        courante.termine = True
        return {"id": ident, "ok": True, "result": {"sketch": courante.identifiant, "profiles": 0}}

    def _supprimer(self, ident: Any, params: dict[str, Any]) -> dict[str, Any]:
        visees = [str(f) for f in params.get("features") or []]
        supprimees = [e for e in self.esquisses if e.nom in visees or str(e.identifiant) in visees]
        if not supprimees:
            return {"id": ident, "ok": False, "error": f"feature inconnue : {visees}"}
        self.esquisses = [e for e in self.esquisses if e not in supprimees]
        return {"id": ident, "ok": True, "result": {"deleted": [e.identifiant for e in supprimees]}}

    def _joint_list(self) -> dict[str, Any]:
        joints = _lire(f"joint_list_theta{self.theta}.json")
        if self.scenario.sous_occurrence:
            modele = copy.deepcopy(joints["joints"][-1])
            modele.update({"id": 99, "name": NOM_LIAISON_SOUS_OCCURRENCE, "a": ID_SOUS_OCCURRENCE})
            joints["joints"].append(modele)
        for joint in joints["joints"]:
            if joint["name"] in self.types_modifies:
                joint["type"] = self.types_modifies[joint["name"]]
        if self.links is not None:
            joints["links"] = copy.deepcopy(self.links)
        return joints

    def _component_list(self) -> dict[str, Any]:
        liste = _lire(f"component_list_theta{self.theta}.json")
        if self.scenario.sous_occurrence:
            identite = [[1.0 if i == j else 0.0 for j in range(4)] for i in range(4)]
            sous = {
                "component": 13,
                "grounded": False,
                "id": ID_SOUS_OCCURRENCE,
                "name": NOM_SOUS_OCCURRENCE,
                "parent": 4,
                "transform": identite,
            }
            manivelle = next(c for c in liste["components"] if c["id"] == 4)
            manivelle["children"].append(sous)
        # les poses en attente ne modifient pas `transform` (constaté sur le vrai SolidCraft)
        liste["pending_moves"] = sorted(self.poses_en_attente)
        return liste

    def _exporter(self, ident: Any, params: dict[str, Any]) -> dict[str, Any]:
        chemin = Path(str(params.get("path", "")))
        format_ = params.get("format")
        if not chemin.parent.is_dir():
            return {"id": ident, "ok": False, "error": f"dossier inexistant : {chemin.parent}"}
        source = DOSSIER / f"export_theta{self.theta}"
        if format_ == "urdf":
            shutil.copyfile(source / "bielle.urdf", chemin)
            for stl in source.glob("bielle-*.stl"):
                destination = chemin.parent / f"{chemin.stem}-{stl.name.split('-', 1)[1]}"
                shutil.copyfile(stl, destination)
        elif format_ == "json":
            contenu = json.loads((source / "bielle.json").read_text(encoding="utf-8"))
            if self.scenario.format_export is not None:
                contenu["format"] = self.scenario.format_export
            chemin.write_text(json.dumps(contenu), encoding="utf-8")
        else:
            return {"id": ident, "ok": False, "error": f"format inconnu : {format_}"}
        return {"id": ident, "ok": True, "result": {"path": str(chemin), "format": format_}}


def _nom(requete: dict[str, Any]) -> str:
    if requete.get("method") == "engine.execute":
        return str((requete.get("params") or {}).get("command"))
    return str(requete.get("method"))
