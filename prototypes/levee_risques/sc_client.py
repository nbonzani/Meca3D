"""Client minimal du canal de contrôle SolidCraft (TCP, une ligne JSON par message)."""

from __future__ import annotations

import json
import os
import re
import socket
from pathlib import Path

RACINE = Path(__file__).parent


def lire_jeton(port: int = 7878) -> str:
    chemin = Path(os.environ["LOCALAPPDATA"]) / "SolidCraft" / "control" / f"{port}.token"
    return chemin.read_text(encoding="utf-8").strip()


def anonymiser(texte: str) -> str:
    """Remplace les chemins personnels (C:\\Users\\...) par un marqueur."""
    texte = re.sub(r"[A-Za-z]:(\\\\|\\|/)Users(\\\\|\\|/)[^\\/\"]+", "<UTILISATEUR>", texte)
    return texte


class Client:
    def __init__(self, port: int = 7878, timeout: float = 60.0):
        self.sock = socket.create_connection(("127.0.0.1", port), timeout=timeout)
        self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.f = self.sock.makefile("rwb")
        self.token = lire_jeton(port)
        self.n = 0
        self.premier = True

    def appel(self, methode: str, params: dict | None = None) -> dict:
        self.n += 1
        msg: dict = {"id": self.n, "method": methode, "params": params or {}}
        if self.premier:
            msg["token"] = self.token
            self.premier = False
        self.f.write((json.dumps(msg) + "\n").encode("utf-8"))
        self.f.flush()
        ligne = self.f.readline()
        return json.loads(ligne.decode("utf-8"))

    def cmd(self, commande: str, params: dict | None = None) -> dict:
        return self.appel("engine.execute", {"command": commande, "params": params or {}})

    def close(self) -> None:
        self.f.close()
        self.sock.close()


def sauver(nom: str, data: object) -> Path:
    """Enregistre une réponse brute (anonymisée) dans reponses/."""
    dossier = RACINE / "reponses"
    dossier.mkdir(exist_ok=True)
    p = dossier / nom
    p.write_text(anonymiser(json.dumps(data, indent=1, ensure_ascii=False)), encoding="utf-8")
    return p
