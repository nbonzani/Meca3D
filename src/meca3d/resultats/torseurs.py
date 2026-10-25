# SPDX-License-Identifier: GPL-3.0-or-later
"""Torseurs de liaison {i→j} au centre de la liaison (EX-50, minimal au lot 2).

Seul endroit où la convention Exudyn (action du solide b sur le solide a, en base de liaison
liée à a) est convertie en {i→j} (ARCHITECTURE § 5).
"""

import numpy as np

from meca3d.modele.etude import Etude
from meca3d.moteur.base import ResultatsBruts


def torseur_statique(
    etude: Etude,
    resultats: ResultatsBruts,
    liaison: str,
    de: str | None = None,
    base: str = "monde",
) -> np.ndarray:
    """Torseur {de → autre solide} au centre, (n, 6) = [Fx Fy Fz Mx My Mz].

    `de` : solide agissant (défaut : solide a). `base` : « monde » ou « liaison » (base de
    liaison liée au solide a).
    """
    lia = etude.liaison(liaison)
    de = lia.solide_a if de is None else de
    if de not in (lia.solide_a, lia.solide_b):
        raise ValueError(f"{de} n'est pas un solide de la liaison {liaison}.")
    if base not in ("monde", "liaison"):
        raise ValueError("base : « monde » ou « liaison » attendu.")
    signe = -1.0 if de == lia.solide_a else 1.0  # brut = action de b sur a
    force = signe * resultats.forces[liaison]
    moment = signe * resultats.moments[liaison]
    if base == "monde":
        r_liaison = lia.base()
        n = len(resultats.t)
        r_a = resultats.rotations.get(lia.solide_a, np.broadcast_to(np.eye(3), (n, 3, 3)))
        r = r_a @ r_liaison  # (n, 3, 3)
        force = np.einsum("nij,nj->ni", r, force)
        moment = np.einsum("nij,nj->ni", r, moment)
    return np.hstack([force, moment])
