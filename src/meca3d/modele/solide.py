# SPDX-License-Identifier: GPL-3.0-or-later
"""Solide indéformable du modèle neutre (SI, repère monde, configuration de référence)."""

from dataclasses import dataclass, field
from typing import Any

import numpy as np


@dataclass
class Solide:
    """Classe d'équivalence : masse (kg), CdG (m) et inertie au CdG (kg·m², axes monde)."""

    nom: str
    fixe: bool
    masse: float
    cdg: np.ndarray
    inertie: np.ndarray
    # Repère du solide = repère de son composant CAO (SolidCraft : `transform` de l'occurrence),
    # en repère monde à la pose d'import, lié au solide ensuite. Identité par défaut.
    repere_rotation: np.ndarray = field(default_factory=lambda: np.eye(3))
    repere_origine: np.ndarray = field(default_factory=lambda: np.zeros(3))

    def repere_identite(self) -> bool:
        return bool(
            np.allclose(self.repere_rotation, np.eye(3), atol=1e-12, rtol=0.0)
            and np.allclose(self.repere_origine, 0.0, atol=1e-12, rtol=0.0)
        )

    def vers_monde(self, local: np.ndarray) -> np.ndarray:
        """Point donné en coordonnées du repère du solide -> repère monde à la pose d'import."""
        return self.repere_origine + self.repere_rotation @ np.asarray(local, dtype=float)

    def vers_local(self, monde: np.ndarray) -> np.ndarray:
        """Point en repère monde (pose d'import) -> coordonnées du repère du solide."""
        return self.repere_rotation.T @ (np.asarray(monde, dtype=float) - self.repere_origine)

    def vers_dict(self) -> dict[str, Any]:
        d = self._vers_dict_base()
        if not self.repere_identite():
            d["repere"] = {
                "rotation": [[float(x) for x in ligne] for ligne in self.repere_rotation],
                "origine": [float(x) for x in self.repere_origine],
            }
        return d

    def _vers_dict_base(self) -> dict[str, Any]:
        return {
            "nom": self.nom,
            "fixe": self.fixe,
            "masse": self.masse,
            "cdg": [float(x) for x in self.cdg],
            "inertie": [[float(x) for x in ligne] for ligne in self.inertie],
        }

    @classmethod
    def depuis_dict(cls, d: dict[str, Any]) -> "Solide":
        repere = d.get("repere")
        extra: dict[str, Any] = {}
        if repere is not None:
            extra = {
                "repere_rotation": np.array(repere["rotation"], dtype=float),
                "repere_origine": np.array(repere["origine"], dtype=float),
            }
            if extra["repere_rotation"].shape != (3, 3) or extra["repere_origine"].shape != (3,):
                raise ValueError("Repère de solide : rotation 3×3 et origine à trois composantes.")
        return cls(
            nom=str(d["nom"]),
            fixe=bool(d["fixe"]),
            masse=float(d["masse"]),
            cdg=np.array(d["cdg"], dtype=float),
            inertie=np.array(d["inertie"], dtype=float),
            **extra,
        )
