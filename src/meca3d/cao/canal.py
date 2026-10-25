# SPDX-License-Identifier: GPL-3.0-or-later
"""Client du canal de contrôle de SolidCraft (D2, EX-01, EX-02).

TCP 127.0.0.1, une ligne JSON UTF-8 par message, une requête à la fois par connexion. Le jeton
est porté par la première requête de chaque connexion. Après un `timeout`, la requête n'est jamais
renvoyée : sa réponse est relue par `control.pending` (ARCHITECTURE § 5).
"""

import json
import os
import socket
import threading
import time
from pathlib import Path
from typing import Any

HOTE = "127.0.0.1"
PORT_PAR_DEFAUT = 27878  # port de SolidCraft sans --control ni current.port (EX-01)
DELAI_CONNEXION = 2.0  # s ; le message d'absence doit sortir en moins de 3 s (EX-01)
DELAI_REPONSE = 70.0  # s ; au-delà du timeout serveur de 60 s (3600 s pour engine.batch)
INTERVALLE_PENDING = 0.2  # s entre deux relectures par control.pending
ATTENTE_PENDING_MAX = 3700.0  # s ; au-delà du timeout serveur de engine.batch
NOM_VARIABLE_DOSSIER = "SOLIDCRAFT_CONTROL_DIR"


class ErreurCanal(Exception):
    """Erreur du canal de contrôle ; le message est destiné à l'élève, en français."""


class SolidCraftAbsent(ErreurCanal):
    """Aucun serveur n'accepte la connexion."""


class JetonRefuse(ErreurCanal):
    """Jeton absent, illisible ou refusé par SolidCraft."""


class Occupe(ErreurCanal):
    """Réponse `busy` : une autre requête est en cours sur la connexion."""


class DelaiDepasse(ErreurCanal):
    """La requête n'a pas abouti dans le délai ; elle peut encore s'exécuter dans SolidCraft."""


class ConnexionPerdue(ErreurCanal):
    """SolidCraft a fermé la connexion ou ne répond plus."""


class ErreurSolidCraft(ErreurCanal):
    """SolidCraft a répondu `ok: false` ; le message reprend l'erreur reçue."""


def dossier_de_controle() -> Path:
    """`SOLIDCRAFT_CONTROL_DIR`, sinon `%LOCALAPPDATA%\\SolidCraft\\control`."""
    force = os.environ.get(NOM_VARIABLE_DOSSIER)
    if force:
        return Path(force)
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(base) / "SolidCraft" / "control"


class CanalSolidCraft:
    """Connexion au canal de contrôle. Port et jeton : arguments, sinon dossier de contrôle."""

    def __init__(
        self,
        port: int | None = None,
        jeton: str | None = None,
        dossier_controle: Path | None = None,
        delai_connexion: float = DELAI_CONNEXION,
        delai_reponse: float = DELAI_REPONSE,
        intervalle_pending: float = INTERVALLE_PENDING,
        attente_pending_max: float = ATTENTE_PENDING_MAX,
    ) -> None:
        self._dossier = dossier_controle
        self._jeton = jeton
        self.port = port if port is not None else self._lire_port()
        self.delai_connexion = delai_connexion
        self.delai_reponse = delai_reponse
        self.intervalle_pending = intervalle_pending
        self.attente_pending_max = attente_pending_max
        self._socket: socket.socket | None = None
        self._tampon = b""
        self._prochain_id = 1
        self._jeton_envoye = False
        self._verrou = threading.RLock()

    # --- découverte -----------------------------------------------------------------------
    def _dossier_controle(self) -> Path:
        return self._dossier if self._dossier is not None else dossier_de_controle()

    def _lire_port(self) -> int:
        fichier = self._dossier_controle() / "current.port"
        try:
            return int(fichier.read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            return PORT_PAR_DEFAUT

    def _lire_jeton(self) -> str:
        if self._jeton:
            return self._jeton
        fichier = self._dossier_controle() / f"{self.port}.token"
        try:
            jeton = fichier.read_text(encoding="utf-8").strip()
        except OSError as e:
            raise JetonRefuse(
                f"SolidCraft : jeton refusé, fichier de jeton introuvable pour le port {self.port}."
            ) from e
        if not jeton:
            raise JetonRefuse(
                f"SolidCraft : jeton refusé, fichier de jeton vide (port {self.port})."
            )
        return jeton

    # --- état -----------------------------------------------------------------------------
    @property
    def connecte(self) -> bool:
        return self._socket is not None

    def connecter(self) -> None:
        """Ouvre la connexion (le jeton est vérifié par SolidCraft à la première requête)."""
        with self._verrou:
            if self._socket is not None:
                return
            jeton = self._lire_jeton()
            try:
                s = socket.create_connection((HOTE, self.port), timeout=self.delai_connexion)
            except OSError as e:
                raise SolidCraftAbsent(
                    f"SolidCraft n'est pas lancé ou n'accepte pas les connexions (port {self.port})"
                ) from e
            s.settimeout(self.delai_reponse)
            self._socket = s
            self._jeton = jeton
            self._tampon = b""
            self._jeton_envoye = False

    def fermer(self) -> None:
        with self._verrou:
            if self._socket is not None:
                try:
                    self._socket.close()
                except OSError:
                    pass
            self._socket = None
            self._tampon = b""

    def __enter__(self) -> "CanalSolidCraft":
        return self

    def __exit__(self, *_: object) -> None:
        self.fermer()

    # --- requêtes -------------------------------------------------------------------------
    def requete(
        self, methode: str, params: dict[str, Any] | None = None, nom: str | None = None
    ) -> Any:
        """Envoie une requête et rend le champ `result` de la réponse."""
        with self._verrou:
            self.connecter()
            ident = self._envoyer(methode, params)
            reponse = self._recevoir(ident)
            return self._resultat(reponse, nom or methode)

    def executer(self, commande: str, params: dict[str, Any] | None = None) -> Any:
        """`engine.execute` : exécute une commande de SolidCraft et rend son résultat."""
        return self.requete(
            "engine.execute", {"command": commande, "params": params or {}}, nom=commande
        )

    def _envoyer(self, methode: str, params: dict[str, Any] | None) -> int:
        ident = self._prochain_id
        self._prochain_id += 1
        message: dict[str, Any] = {"id": ident, "method": methode, "params": params or {}}
        if not self._jeton_envoye:
            message["token"] = self._jeton
            self._jeton_envoye = True
        donnees = (json.dumps(message) + "\n").encode("utf-8")
        assert self._socket is not None
        try:
            self._socket.sendall(donnees)
        except OSError as e:
            self.fermer()
            raise self._perdue() from e
        return ident

    def _recevoir(self, ident: int) -> dict[str, Any]:
        assert self._socket is not None
        try:
            while b"\n" not in self._tampon:
                morceau = self._socket.recv(65536)
                if not morceau:
                    self.fermer()
                    raise self._perdue()
                self._tampon += morceau
        except TimeoutError as e:
            self.fermer()
            raise DelaiDepasse(
                "SolidCraft n'a pas répondu dans le délai imparti ; la connexion est fermée."
            ) from e
        except OSError as e:
            self.fermer()
            raise self._perdue() from e
        ligne, self._tampon = self._tampon.split(b"\n", 1)
        try:
            reponse = json.loads(ligne.decode("utf-8"))
        except ValueError as e:
            self.fermer()
            raise ErreurCanal("Réponse illisible de SolidCraft (JSON invalide).") from e
        if not isinstance(reponse, dict):
            self.fermer()
            raise ErreurCanal("Réponse illisible de SolidCraft (objet JSON attendu).")
        return reponse

    @staticmethod
    def _perdue() -> ConnexionPerdue:
        return ConnexionPerdue(
            "Connexion avec SolidCraft perdue : SolidCraft a fermé la connexion ou s'est arrêté. "
            "L'étude en cours est conservée ; relancez l'opération une fois SolidCraft relancé."
        )

    def _resultat(self, reponse: dict[str, Any], nom: str) -> Any:
        if reponse.get("ok"):
            return reponse.get("result")
        erreur = str(reponse.get("error", ""))
        if erreur.startswith("unauthorized:"):
            self.fermer()
            raise JetonRefuse(f"SolidCraft : jeton refusé ({erreur}).")
        if reponse.get("busy"):
            raise Occupe(
                "SolidCraft est occupé : une requête précédente n'est pas terminée. "
                "Réessayez dans un instant."
            )
        if reponse.get("running") and erreur.startswith("timeout:"):
            return self._relire_pending(nom)
        raise ErreurSolidCraft(f"SolidCraft a refusé la requête « {nom} » : {erreur}")

    def _relire_pending(self, nom: str) -> Any:
        """Attend la vraie réponse d'une requête en timeout, sans jamais la renvoyer."""
        limite = time.monotonic() + self.attente_pending_max
        while True:
            ident = self._envoyer("control.pending", None)
            reponse = self._recevoir(ident)
            etat = self._resultat(reponse, "control.pending")
            if not isinstance(etat, dict) or etat.get("pending") is None:
                raise ErreurSolidCraft(
                    f"SolidCraft : la réponse de « {nom} » n'est plus disponible."
                )
            if etat.get("done"):
                return self._resultat(etat["reply"], nom)
            if time.monotonic() >= limite:
                raise DelaiDepasse(
                    f"La requête « {nom} » est toujours en cours dans SolidCraft après "
                    f"{self.attente_pending_max:g} s ; elle n'a pas été renvoyée."
                )
            time.sleep(self.intervalle_pending)
