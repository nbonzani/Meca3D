# SPDX-License-Identifier: GPL-3.0-or-later
"""Thème de la fenêtre (R12) : feuille de style QSS claire ou sombre aux couleurs méca ia,
couleurs des figures matplotlib et icônes Tabler (MIT, `ihm/icones/`) recolorées.

Charte (MIA-CG-001) : fonds neutres, Bleu Blueprint réservé à la structure (titres de section,
sélection, onglet actif), Cyan Signal et Orange Cuivre réservés aux états et à l'action
principale, jamais en aplat large. Aptos pour le texte, Cascadia Mono pour les valeurs.
"""

from dataclasses import dataclass
from enum import Enum
from functools import cache
from pathlib import Path

from PyQt6.QtCore import QByteArray, QRectF, Qt
from PyQt6.QtGui import QColor, QIcon, QPainter, QPalette, QPixmap
from PyQt6.QtSvg import QSvgRenderer

DOSSIER_ICONES = Path(__file__).resolve().parent / "icones"
TAILLES_ICONES = (16, 20, 24, 32, 48)  # px, rendus à l'avance pour un affichage net

# Charte méca ia (MIA-CG-001 v1.1)
BLUEPRINT = "#1B3A6B"
CYAN_SIGNAL = "#00B4D8"
ORANGE_CUIVRE = "#E07A2C"
PAPIER = "#FAFAF7"
GRAPHITE = "#2B2B2B"
GRIS_TRAME = "#E4E2DC"
GRIS_COTE = "#8A8A8A"

TEXTE_ACTION_PRINCIPALE = "#FFFFFF"  # sur fond cuivre

POLICE_TEXTE = '"Aptos", "Segoe UI", sans-serif'
POLICE_VALEURS = '"Cascadia Mono", "Consolas", monospace'

# États portés par la propriété dynamique « etat » des pastilles de la barre d'état
ETAT_NEUTRE = "neutre"
ETAT_OK = "ok"
ETAT_ALERTE = "alerte"


class Theme(Enum):
    CLAIR = "clair"
    SOMBRE = "sombre"


@dataclass(frozen=True)
class Couleurs:
    """Couleurs d'un thème : interface (QSS, palette) et figures matplotlib."""

    fond: str  # fond de la fenêtre et des barres
    panneau: str  # fond des zones de travail (arbre, onglets, saisies)
    bordure: str
    texte: str
    texte_secondaire: str
    structure: str  # Blueprint (ou sa déclinaison lisible sur fond sombre)
    selection: str  # fond d'un élément sélectionné
    ok: str
    alerte: str
    incomplet: str  # texte d'un élément incomplet de l'arbre (cuivre lisible sur le fond)
    # figures
    trace: str
    grille: str
    noeud: str
    bati: str
    isole: str
    arete: str


COULEURS: dict[Theme, Couleurs] = {
    Theme.CLAIR: Couleurs(
        fond="#EFEEEA",
        panneau=PAPIER,
        bordure="#CFCDC6",
        texte=GRAPHITE,
        texte_secondaire="#6E6E6E",
        structure=BLUEPRINT,
        selection="#D5DEEB",
        ok=CYAN_SIGNAL,
        alerte=ORANGE_CUIVRE,
        incomplet="#B4561A",
        trace=BLUEPRINT,
        grille=GRIS_TRAME,
        noeud="#D5DEEB",
        bati=GRIS_TRAME,
        isole="#F3C9A6",
        arete=GRIS_COTE,
    ),
    Theme.SOMBRE: Couleurs(
        fond="#1E1F22",
        panneau="#26282C",
        bordure="#3B3E44",
        texte="#E4E3DF",
        texte_secondaire="#9A9A9A",
        structure="#7F9CCB",
        selection="#2F4466",
        ok=CYAN_SIGNAL,
        alerte=ORANGE_CUIVRE,
        incomplet="#EE9A5C",
        trace="#8FB4E8",
        grille="#3B3E44",
        noeud="#2F4466",
        bati="#4A4D53",
        isole="#7A4A2A",
        arete="#9A9A9A",
    ),
}


def couleurs(theme: Theme) -> Couleurs:
    return COULEURS[theme]


def etat_m(m: int | None) -> str:
    return ETAT_NEUTRE if m is None else ETAT_OK


def etat_h(h: int | None) -> str:
    """h > 0 interdit la simulation (EX-22) : la pastille passe en alerte."""
    if h is None:
        return ETAT_NEUTRE
    return ETAT_OK if h == 0 else ETAT_ALERTE


def palette(theme: Theme) -> QPalette:
    """Palette Qt cohérente avec la feuille de style (utilisée par les widgets non stylés)."""
    c = COULEURS[theme]
    p = QPalette()
    R = QPalette.ColorRole
    for role, valeur in (
        (R.Window, c.fond),
        (R.WindowText, c.texte),
        (R.Base, c.panneau),
        (R.AlternateBase, c.fond),
        (R.Text, c.texte),
        (R.Button, c.fond),
        (R.ButtonText, c.texte),
        (R.Highlight, c.selection),
        (R.HighlightedText, c.texte),
        (R.ToolTipBase, c.panneau),
        (R.ToolTipText, c.texte),
        (R.PlaceholderText, c.texte_secondaire),
    ):
        p.setColor(role, QColor(valeur))
    inactif = QPalette.ColorGroup.Disabled
    for role in (R.Text, R.ButtonText, R.WindowText):
        p.setColor(inactif, role, QColor(c.texte_secondaire))
    for role in (R.Base, R.Button, R.Window):
        p.setColor(inactif, role, QColor(c.fond))
    return p


def feuille_de_style(theme: Theme) -> str:
    """Feuille QSS de la fenêtre principale : sobre, dense, sans effet décoratif."""
    c = COULEURS[theme]
    return f"""
QWidget {{ font-family: {POLICE_TEXTE}; font-size: 9pt; color: {c.texte}; }}
QMainWindow, QStatusBar, QMenuBar, QToolBar {{ background: {c.fond}; }}
QMenuBar {{ border-bottom: 1px solid {c.bordure}; }}
QMenuBar::item:selected, QMenu::item:selected {{ background: {c.selection}; }}
QMenu {{ background: {c.panneau}; border: 1px solid {c.bordure}; }}
QToolBar {{ border-bottom: 1px solid {c.bordure}; spacing: 2px; padding: 2px 4px; }}
QToolBar::separator {{ background: {c.bordure}; width: 1px; margin: 4px 6px; }}
QToolButton {{ border: 1px solid transparent; border-radius: 2px; padding: 3px; }}
QToolButton:hover {{ border-color: {c.bordure}; background: {c.panneau}; }}
QToolButton:pressed, QToolButton:checked {{ background: {c.selection}; }}
QToolButton#actionPrincipale {{
    background: {c.alerte}; color: {TEXTE_ACTION_PRINCIPALE}; font-weight: 600; padding: 3px 8px;
}}
QToolButton#actionPrincipale:disabled {{ background: {c.bordure}; color: {c.texte_secondaire}; }}
QTreeWidget, QTableWidget, QTableView, QPlainTextEdit, QListWidget {{
    background: {c.panneau}; border: 1px solid {c.bordure};
    selection-background-color: {c.selection}; selection-color: {c.texte};
}}
QPlainTextEdit, QTableWidget, QTableView {{ font-family: {POLICE_VALEURS}; }}
QScrollArea, QScrollArea > QWidget > QWidget {{ background: {c.fond}; border: none; }}
QHeaderView::section {{
    background: {c.fond}; border: none; border-right: 1px solid {c.bordure};
    border-bottom: 1px solid {c.bordure}; padding: 2px 4px; color: {c.structure};
    font-weight: 600;
}}
QTabWidget::pane {{ border: 1px solid {c.bordure}; background: {c.panneau}; top: -1px; }}
QTabBar::tab {{
    background: {c.fond}; border: 1px solid {c.bordure}; border-bottom: none;
    padding: 4px 12px; margin-right: -1px; color: {c.texte_secondaire};
}}
QTabBar::tab:selected {{
    background: {c.panneau}; color: {c.texte}; border-top: 2px solid {c.structure};
}}
QGroupBox {{
    border: 1px solid {c.bordure}; margin-top: 14px; padding-top: 4px; font-weight: 600;
}}
QGroupBox::title {{
    subcontrol-origin: margin; left: 6px; padding: 0 3px; color: {c.structure};
}}
QLineEdit, QComboBox {{
    background: {c.panneau}; border: 1px solid {c.bordure}; border-radius: 2px;
    padding: 2px 4px; min-height: 18px;
}}
QLineEdit:focus, QComboBox:focus {{
    border-color: {c.structure};
}}
QAbstractSpinBox {{
    font-family: {POLICE_VALEURS}; background: {c.panneau}; border: 1px solid {c.bordure};
    border-radius: 2px; padding: 2px 16px 2px 4px; min-height: 18px;
}}
QAbstractSpinBox:focus {{ border-color: {c.structure}; }}
QAbstractSpinBox:disabled {{ background: {c.fond}; color: {c.texte_secondaire}; }}
QAbstractSpinBox::up-button, QAbstractSpinBox::down-button {{
    subcontrol-origin: border; width: 14px; border: none; border-left: 1px solid {c.bordure};
}}
QAbstractSpinBox::up-button {{ subcontrol-position: top right; }}
QAbstractSpinBox::down-button {{ subcontrol-position: bottom right; }}
QAbstractSpinBox::up-arrow, QAbstractSpinBox::down-arrow {{
    width: 0; height: 0; border-left: 4px solid transparent; border-right: 4px solid transparent;
}}
QAbstractSpinBox::up-arrow {{ border-bottom: 4px solid {c.texte_secondaire}; }}
QAbstractSpinBox::down-arrow {{ border-top: 4px solid {c.texte_secondaire}; }}
QComboBox QAbstractItemView {{ background: {c.panneau}; border: 1px solid {c.bordure}; }}
QPushButton {{
    background: {c.panneau}; border: 1px solid {c.bordure}; border-radius: 2px;
    padding: 3px 10px;
}}
QPushButton:hover {{ border-color: {c.structure}; }}
QPushButton:disabled {{ color: {c.texte_secondaire}; }}
QSplitter::handle {{ background: {c.fond}; }}
QProgressBar {{
    border: 1px solid {c.bordure}; border-radius: 2px; background: {c.panneau};
    text-align: center; max-height: 14px;
}}
QProgressBar::chunk {{ background: {c.ok}; }}
QFrame#bandeau {{ background: {c.panneau}; border: 1px solid {c.alerte};
    border-left: 4px solid {c.alerte}; }}
QStatusBar {{ border-top: 1px solid {c.bordure}; }}
QStatusBar::item {{ border: none; }}
QLabel[etat] {{
    font-family: {POLICE_VALEURS}; padding: 1px 8px; margin: 1px 2px;
    border: 1px solid {c.bordure}; border-left: 4px solid {c.bordure}; border-radius: 2px;
}}
QLabel[etat="{ETAT_OK}"] {{ border-left-color: {c.ok}; }}
QLabel[etat="{ETAT_ALERTE}"] {{ border-color: {c.alerte}; border-left-color: {c.alerte}; }}
QWidget#barreEtapes {{ background: {c.fond}; border-bottom: 1px solid {c.bordure}; }}
QToolButton[etape] {{
    border: none; border-bottom: 2px solid transparent; border-radius: 0;
    padding: 4px 14px; color: {c.texte_secondaire};
}}
QToolButton[etape]:hover {{ background: {c.panneau}; }}
QToolButton[etape][etat="incomplet"] {{ color: {c.texte}; border-bottom-color: {c.alerte}; }}
QToolButton[etape][etat="pret"] {{ color: {c.texte}; border-bottom-color: {c.ok}; }}
QToolButton[etape][etat="fait"] {{ color: {c.structure}; border-bottom-color: {c.structure}; }}
QLabel#flecheEtape {{ color: {c.texte_secondaire}; }}
QToolTip {{ background: {c.panneau}; color: {c.texte}; border: 1px solid {c.bordure}; }}
"""


@cache
def _svg(nom: str) -> str:
    return (DOSSIER_ICONES / f"{nom}.svg").read_text(encoding="utf-8")


def icone(nom: str, theme: Theme, couleur: str | None = None) -> QIcon:
    """Icône Tabler `nom` dessinée dans la couleur du texte du thème (ou `couleur`)."""
    trait = couleur or COULEURS[theme].texte
    donnees = QByteArray(_svg(nom).replace("currentColor", trait).encode("utf-8"))
    rendu = QSvgRenderer(donnees)
    resultat = QIcon()
    for taille in TAILLES_ICONES:
        image = QPixmap(taille, taille)
        image.fill(Qt.GlobalColor.transparent)
        peintre = QPainter(image)
        rendu.render(peintre, QRectF(0, 0, taille, taille))
        peintre.end()
        resultat.addPixmap(image)
    return resultat
