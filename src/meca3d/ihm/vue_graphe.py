# SPDX-License-Identifier: GPL-3.0-or-later
"""Vue du graphe des liaisons (EX-20) : matplotlib (QtAgg), μ, m, h, cycle mis en évidence."""

from typing import Any

import networkx as nx
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from matplotlib.patches import FancyArrowPatch
from PyQt6.QtWidgets import QComboBox, QLabel, QVBoxLayout, QWidget

from meca3d.graphe.mobilite import ResultatMobilite
from meca3d.ihm import textes
from meca3d.modele.couplage import Couplage, Engrenage, PignonCremaillere
from meca3d.modele.etude import Etude

COULEUR_ARETE = "#6b7280"
COULEUR_CYCLE = "#dc2626"
COULEUR_NOEUD = "#dbeafe"
COULEUR_BATI = "#d1d5db"
COULEUR_ISOLE = "#fca5a5"
COULEUR_COUPLAGE = "#0891b2"
COURBURE_PARALLELES = 0.25  # écart d'arc entre deux liaisons en parallèle


class VueGraphe(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._etude: Etude | None = None
        self._mobilite: ResultatMobilite | None = None
        disposition = QVBoxLayout(self)
        self.etiquette_resume = QLabel(textes.resume_graphe(None, None, None))
        self.choix_cycle = QComboBox()
        self.figure = Figure(figsize=(6, 4))
        self.canevas = FigureCanvasQTAgg(self.figure)
        disposition.addWidget(self.etiquette_resume)
        disposition.addWidget(self.choix_cycle)
        disposition.addWidget(self.canevas, 1)
        self.choix_cycle.currentIndexChanged.connect(self._sur_choix_cycle)

    # --- interrogation -----------------------------------------------------------------------
    def resume(self) -> str:
        return self.etiquette_resume.text()

    def liaisons_en_evidence(self) -> list[str]:
        """Noms des liaisons du cycle choisi (vide s'il n'y a aucun cycle)."""
        m = self._mobilite
        k = self.choix_cycle.currentIndex()
        if m is None or not 0 <= k < len(m.graphe.cycles):
            return []
        return [nom for nom, _ in m.graphe.cycles[k].liaisons]

    # --- mise à jour -------------------------------------------------------------------------
    def afficher(self, etude: Etude | None, mobilite: ResultatMobilite | None) -> None:
        self._etude, self._mobilite = etude, mobilite
        self.choix_cycle.blockSignals(True)
        self.choix_cycle.clear()
        if mobilite is not None:
            for i, cycle in enumerate(mobilite.graphe.cycles, 1):
                self.choix_cycle.addItem(
                    textes.libelle_cycle(i, [nom for nom, _ in cycle.liaisons])
                )
            if not mobilite.graphe.cycles:
                self.choix_cycle.addItem(textes.CYCLE_AUCUN)
        self.choix_cycle.blockSignals(False)
        if mobilite is None:
            self.etiquette_resume.setText(textes.resume_graphe(None, None, None))
        else:
            self.etiquette_resume.setText(textes.resume_graphe(mobilite.mu, mobilite.m, mobilite.h))
        self._dessiner()

    def _sur_choix_cycle(self, _: int) -> None:
        self._dessiner()

    def _dessiner(self) -> None:
        self.figure.clear()
        ax: Any = self.figure.add_subplot(111)
        ax.set_axis_off()
        etude, mobilite = self._etude, self._mobilite
        if etude is None or mobilite is None:
            message = textes.GRAPHE_VIDE if etude is None else textes.GRAPHE_INDISPONIBLE
            ax.text(0.5, 0.5, message, ha="center", va="center", wrap=True, transform=ax.transAxes)
            self.canevas.draw_idle()
            return
        g: nx.MultiGraph = mobilite.graphe.graphe
        pos = nx.circular_layout(g)
        en_evidence = set(self.liaisons_en_evidence())
        # arêtes (arcs distincts pour les liaisons en parallèle)
        vues: dict[frozenset[str], int] = {}
        for u, v, cle in g.edges(keys=True):
            rang = vues.get(frozenset((u, v)), 0)
            vues[frozenset((u, v))] = rang + 1
            courbure = COURBURE_PARALLELES * ((rang + 1) // 2) * (1 if rang % 2 else -1)
            if u == v:
                courbure = 0.0
            cycle = cle in en_evidence
            fleche = FancyArrowPatch(
                (float(pos[u][0]), float(pos[u][1])),
                (float(pos[v][0]), float(pos[v][1])),
                arrowstyle="-",
                connectionstyle=f"arc3,rad={courbure}",
                color=COULEUR_CYCLE if cycle else COULEUR_ARETE,
                linewidth=3.0 if cycle else 1.5,
                shrinkA=14,
                shrinkB=14,
            )
            ax.add_patch(fleche)
            milieu = (pos[u] + pos[v]) / 2
            decalage = courbure * 0.5 * (pos[v] - pos[u])
            normale = [-decalage[1], decalage[0]]
            type_ = etude.liaison(cle).type
            libelle = cle + ("" if type_ is None else f"\n{textes.LIBELLES_TYPE[type_]}")
            ax.text(
                milieu[0] + normale[0],
                milieu[1] + normale[1],
                libelle,
                ha="center",
                va="center",
                fontsize=8,
                color=COULEUR_CYCLE if cycle else "black",
                bbox={"boxstyle": "round,pad=0.2", "fc": "white", "ec": "none", "alpha": 0.9},
            )
        for couplage in etude.couplages:
            self._dessiner_couplage(ax, etude, couplage, pos)
        for n in g.nodes:
            bati = n == mobilite.graphe.bati
            isole = n in mobilite.graphe.isoles
            ax.text(
                pos[n][0],
                pos[n][1],
                textes.BATI if bati else g.nodes[n]["nom"],
                ha="center",
                va="center",
                fontsize=10,
                fontweight="bold",
                bbox={
                    "boxstyle": "square,pad=0.4" if bati else "round,pad=0.4",
                    "fc": COULEUR_ISOLE if isole else COULEUR_BATI if bati else COULEUR_NOEUD,
                    "ec": "black",
                },
            )
        ax.set_xlim(-1.5, 1.5)
        ax.set_ylim(-1.5, 1.5)
        ax.set_aspect("equal")
        self.canevas.draw_idle()

    @staticmethod
    def _dessiner_couplage(ax: Any, etude: Etude, couplage: Couplage, pos: dict) -> None:
        """Couplage (EX-14) : tireté entre les deux solides menés par ses liaisons. Il n'est pas
        une arête du graphe (il ne crée pas de cycle) mais ajoute une équation à Ec (EX-21)."""
        try:
            l1, l2 = etude.liaison(couplage.liaison_1), etude.liaison(couplage.liaison_2)
        except KeyError:
            return
        s1, s2 = {l1.solide_a, l1.solide_b}, {l2.solide_a, l2.solide_b}
        commun = s1 & s2
        u = next(iter(s1 - commun), l1.solide_b)
        v = next(iter(s2 - commun), l2.solide_b)
        if u not in pos or v not in pos or u == v:
            return
        ax.add_patch(
            FancyArrowPatch(
                (float(pos[u][0]), float(pos[u][1])),
                (float(pos[v][0]), float(pos[v][1])),
                arrowstyle="-",
                linestyle="--",
                color=COULEUR_COUPLAGE,
                linewidth=1.5,
                shrinkA=14,
                shrinkB=14,
            )
        )
        if isinstance(couplage, Engrenage):
            valeur = couplage.k
        elif isinstance(couplage, PignonCremaillere):
            valeur = couplage.r
        else:
            valeur = couplage.p
        milieu = (pos[u] + pos[v]) / 2
        ax.text(
            milieu[0],
            milieu[1],
            textes.libelle_couplage(couplage.GENRE, valeur, couplage.rendement),
            ha="center",
            va="center",
            fontsize=8,
            color=COULEUR_COUPLAGE,
            bbox={"boxstyle": "round,pad=0.2", "fc": "white", "ec": "none", "alpha": 0.9},
        )
