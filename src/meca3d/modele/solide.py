# SPDX-License-Identifier: GPL-3.0-or-later
"""Solide indéformable du modèle neutre (SI, repère monde, configuration de référence)."""

from dataclasses import dataclass
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

    def vers_dict(self) -> dict[str, Any]:
        return {
            "nom": self.nom,
            "fixe": self.fixe,
            "masse": self.masse,
            "cdg": [float(x) for x in self.cdg],
            "inertie": [[float(x) for x in ligne] for ligne in self.inertie],
        }

    @classmethod
    def depuis_dict(cls, d: dict[str, Any]) -> "Solide":
        return cls(
            nom=str(d["nom"]),
            fixe=bool(d["fixe"]),
            masse=float(d["masse"]),
            cdg=np.array(d["cdg"], dtype=float),
            inertie=np.array(d["inertie"], dtype=float),
        )
