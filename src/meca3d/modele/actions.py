# SPDX-License-Identifier: GPL-3.0-or-later
"""Données d'entrée : lois d'entrée (EX-30, D5), pilotes, pesanteur (EX-31), actions extérieures
(EX-32) et ressorts-amortisseurs (EX-33).

Le texte d'une loi est analysé par `ast` sur liste blanche, puis converti en expression sympy
par un parcours de l'arbre : ni `eval`, ni `exec`, ni `sympify` ne touchent le texte saisi.
"""

import ast
import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

import numpy as np
import sympy

LONGUEUR_MAX_TEXTE = 2000
NOEUDS_MAX = 500
GRANDEURS = ("angle", "position")

_T = sympy.Symbol("t", real=True)

# Grandeurs imposables par une loi d'entrée selon le type de liaison (EX-30) : pivot : angle ;
# glissière : position ; pivot glissant : l'un ou l'autre ; hélicoïdale : angle.
_GRANDEURS_PILOTABLES: dict[str, tuple[str, ...]] = {
    "pivot": ("angle",),
    "glissiere": ("position",),
    "pivot_glissant": ("angle", "position"),
    "helicoidale": ("angle",),
}


def grandeurs_pilotables(type_liaison: str | None) -> tuple[str, ...]:
    """Grandeurs qu'une loi d'entrée peut imposer à une liaison de ce type (vide : aucune)."""
    if type_liaison is None:
        return ()
    return _GRANDEURS_PILOTABLES.get(str(type_liaison), ())


_FONCTIONS: dict[str, Callable[..., Any]] = {
    "sin": sympy.sin,
    "cos": sympy.cos,
    "tan": sympy.tan,
    "exp": sympy.exp,
    "log": sympy.log,
    "sqrt": sympy.sqrt,
    "abs": sympy.Abs,
    "min": sympy.Min,
    "max": sympy.Max,
}
_CONSTANTES_FIXES: dict[str, Any] = {"pi": sympy.pi}
_OPERATEURS_BINAIRES: dict[type, Callable[[Any, Any], Any]] = {
    ast.Add: lambda a, b: a + b,
    ast.Sub: lambda a, b: a - b,
    ast.Mult: lambda a, b: a * b,
    ast.Div: lambda a, b: a / b,
}
_COMPARAISONS: dict[type, Callable[[Any, Any], Any]] = {
    ast.Lt: lambda a, b: a < b,
    ast.LtE: lambda a, b: a <= b,
    ast.Gt: lambda a, b: a > b,
    ast.GtE: lambda a, b: a >= b,
}


# Dérivées de abs/min/max : sign, Heaviside, DiracDelta (distribution, prise nulle hors du saut)
_MODULES: list[Any] = [
    {
        "DiracDelta": lambda x: 0.0,
        "Heaviside": lambda x, h=0.5: 0.0 if x < 0 else (1.0 if x > 0 else h),
    },
    "numpy",
]


class ErreurLoi(ValueError):
    """Expression de loi d'entrée refusée ; le message est destiné à l'élève."""


class _Convertisseur:
    def __init__(self, constantes: dict[str, float]) -> None:
        self.constantes = constantes

    def convertir(self, noeud: ast.AST) -> Any:
        if isinstance(noeud, ast.Constant):
            return self._constante(noeud.value)
        if isinstance(noeud, ast.Name):
            return self._nom(noeud.id)
        if isinstance(noeud, ast.UnaryOp):
            if isinstance(noeud.op, ast.USub):
                return -self.convertir(noeud.operand)
            if isinstance(noeud.op, ast.UAdd):
                return self.convertir(noeud.operand)
        if isinstance(noeud, ast.BinOp):
            a, b = self.convertir(noeud.left), self.convertir(noeud.right)
            if isinstance(noeud.op, ast.Pow):
                if getattr(a, "is_number", False) and getattr(b, "is_number", False):
                    a, b = sympy.Float(a), sympy.Float(b)  # évite les entiers géants
                return a**b
            operation = _OPERATEURS_BINAIRES.get(type(noeud.op))
            if operation is not None:
                return operation(a, b)
        if isinstance(noeud, ast.Compare):
            if len(noeud.ops) == 1 and type(noeud.ops[0]) in _COMPARAISONS:
                comparaison = _COMPARAISONS[type(noeud.ops[0])]
                return comparaison(self.convertir(noeud.left), self.convertir(noeud.comparators[0]))
        if isinstance(noeud, ast.Call):
            return self._appel(noeud)
        raise ErreurLoi(
            "Expression non autorisée : seules les opérations + − * / **, les fonctions "
            "sin, cos, tan, exp, log, sqrt, abs, min, max, Piecewise, la variable t, pi "
            "et les constantes de l'étude sont admises."
        )

    def _constante(self, valeur: object) -> Any:
        if isinstance(valeur, bool):
            return sympy.true if valeur else sympy.false
        if isinstance(valeur, int):
            return sympy.Integer(valeur) if abs(valeur) <= 10**6 else sympy.Float(valeur)
        if isinstance(valeur, float):
            return sympy.Float(valeur)
        raise ErreurLoi("Seuls les nombres sont admis comme constantes littérales.")

    def _nom(self, nom: str) -> Any:
        if nom == "t":
            return _T
        if nom in _CONSTANTES_FIXES:
            return _CONSTANTES_FIXES[nom]
        if nom in self.constantes:
            return sympy.Float(self.constantes[nom])
        raise ErreurLoi(
            f"Nom inconnu « {nom} » : seuls t, pi et les constantes de l'étude sont admis."
        )

    def _appel(self, noeud: ast.Call) -> Any:
        if not isinstance(noeud.func, ast.Name) or noeud.keywords:
            raise ErreurLoi("Appel de fonction non autorisé.")
        nom = noeud.func.id
        if nom == "Piecewise":
            morceaux = []
            for argument in noeud.args:
                if not (isinstance(argument, ast.Tuple) and len(argument.elts) == 2):
                    raise ErreurLoi("Piecewise attend des couples (expression, condition).")
                morceaux.append(
                    (self.convertir(argument.elts[0]), self.convertir(argument.elts[1]))
                )
            if not morceaux:
                raise ErreurLoi("Piecewise attend au moins un couple (expression, condition).")
            return sympy.Piecewise(*morceaux)
        fonction = _FONCTIONS.get(nom)
        if fonction is None:
            raise ErreurLoi(f"Fonction « {nom} » non autorisée.")
        if not noeud.args:
            raise ErreurLoi(f"La fonction {nom} attend au moins un argument.")
        return fonction(*[self.convertir(a) for a in noeud.args])


def analyser_expression(texte: str, constantes: dict[str, float] | None = None) -> Any:
    """Texte -> expression sympy de t, après contrôle par liste blanche `ast`."""
    if not texte or not texte.strip():
        raise ErreurLoi("La loi d'entrée est vide : saisir une expression de t.")
    if len(texte) > LONGUEUR_MAX_TEXTE:
        raise ErreurLoi("La loi d'entrée est trop longue.")
    try:
        arbre = ast.parse(texte.strip(), mode="eval")
    except SyntaxError as e:
        raise ErreurLoi(f"Expression illisible : {e.msg}.") from e
    if sum(1 for _ in ast.walk(arbre)) > NOEUDS_MAX:
        raise ErreurLoi("La loi d'entrée est trop complexe.")
    expression = _Convertisseur(constantes or {}).convertir(arbre.body)
    if not isinstance(expression, sympy.Expr):
        raise ErreurLoi("L'expression ne définit pas une valeur numérique.")
    return expression


class LoiEntree:
    """Loi d'entrée f(t) avec dérivées première et seconde exactes (dérivation symbolique)."""

    def __init__(self, texte: str, constantes: dict[str, float] | None = None) -> None:
        self.texte = texte
        self.constantes = dict(constantes or {})
        expression = analyser_expression(texte, self.constantes)
        self._f = sympy.lambdify(_T, expression, modules=_MODULES)
        self._df = sympy.lambdify(_T, sympy.diff(expression, _T), modules=_MODULES)
        self._ddf = sympy.lambdify(_T, sympy.diff(expression, _T, 2), modules=_MODULES)

    def valeur(self, t: float) -> float:
        return float(self._f(t))

    def vitesse(self, t: float) -> float:
        return float(self._df(t))

    def acceleration(self, t: float) -> float:
        return float(self._ddf(t))


@dataclass
class Pilote:
    """Liaison pilote et sa loi (EX-30). `grandeur` : angle ou position (selon le type si None)."""

    liaison: str
    loi: LoiEntree
    grandeur: str | None = None

    def vers_dict(self) -> dict[str, Any]:
        return {
            "liaison": self.liaison,
            "loi": self.loi.texte,
            "constantes": self.loi.constantes,
            "grandeur": self.grandeur,
        }

    @classmethod
    def depuis_dict(cls, d: dict[str, Any]) -> "Pilote":
        return cls(
            liaison=str(d["liaison"]),
            loi=LoiEntree(str(d["loi"]), {k: float(v) for k, v in d["constantes"].items()}),
            grandeur=d["grandeur"],
        )


@dataclass
class Pesanteur:
    """Pesanteur (EX-31) : vecteur en m/s², z vers le haut par défaut, désactivable."""

    vecteur: Sequence[float] = (0.0, 0.0, -9.81)
    actif: bool = True

    def effectif(self) -> np.ndarray:
        if not self.actif:
            return np.zeros(3)
        return np.array(self.vecteur, dtype=float)

    def vers_dict(self) -> dict[str, Any]:
        return {"vecteur": [float(x) for x in self.vecteur], "actif": self.actif}

    @classmethod
    def depuis_dict(cls, d: dict[str, Any]) -> "Pesanteur":
        return cls(vecteur=tuple(float(x) for x in d["vecteur"]), actif=bool(d["actif"]))


class ErreurAction(ValueError):
    """Définition d'action extérieure ou de ressort invalide ; le message est destiné à l'élève."""


class NatureAction(StrEnum):
    FORCE = "force"
    COUPLE = "couple"


class RepereAction(StrEnum):
    """Repère d'expression : monde, ou repère du solide (axes du monde à la pose d'import, liés au
    solide ensuite)."""

    MONDE = "monde"
    SOLIDE = "solide"


def _nom_non_vide(valeur: object, libelle: str) -> str:
    if not isinstance(valeur, str) or not valeur.strip():
        raise ErreurAction(f"Nom de {libelle} vide ou invalide : un nom est à saisir.")
    return valeur


def _point(valeur: Sequence[float], libelle: str) -> tuple[float, float, float]:
    try:
        coordonnees = tuple(float(x) for x in valeur)
    except (TypeError, ValueError) as e:
        raise ErreurAction(f"{libelle} : point invalide ({e}).") from e
    if len(coordonnees) != 3 or not all(math.isfinite(x) for x in coordonnees):
        raise ErreurAction(f"{libelle} : le point attendu a trois coordonnées finies (m).")
    return coordonnees[0], coordonnees[1], coordonnees[2]


@dataclass
class ActionExterieure:
    """Force (N) ou couple (N·m) appliqué en un point d'un solide (EX-32).

    `composantes` : trois expressions de t (grammaire d'EX-30), une par axe du repère choisi ;
    un nombre est une loi constante. `point` : point d'application en repère monde à la pose
    d'import, lié au solide ; sans objet pour un couple (vecteur libre).
    """

    nom: str
    solide: str
    nature: NatureAction
    composantes: Sequence[str | float]
    repere: RepereAction = RepereAction.MONDE
    point: tuple[float, float, float] = (0.0, 0.0, 0.0)
    constantes: dict[str, float] = field(default_factory=dict)
    lois: tuple[LoiEntree, LoiEntree, LoiEntree] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        _nom_non_vide(self.nom, "action")
        _nom_non_vide(self.solide, "solide d'action")
        try:
            self.nature = NatureAction(self.nature)
        except ValueError as e:
            raise ErreurAction(
                f"Action {self.nom} : nature « {self.nature} » inconnue (force ou couple)."
            ) from e
        try:
            self.repere = RepereAction(self.repere)
        except ValueError as e:
            raise ErreurAction(
                f"Action {self.nom} : repère « {self.repere} » inconnu (monde ou solide)."
            ) from e
        if not isinstance(self.composantes, Sequence) or len(self.composantes) != 3:
            raise ErreurAction(f"Action {self.nom} : trois composantes sont attendues.")
        textes = tuple(c if isinstance(c, str) else repr(float(c)) for c in self.composantes)
        self.composantes = (textes[0], textes[1], textes[2])
        self.point = _point(self.point, f"Action {self.nom}")
        self.constantes = {k: float(v) for k, v in self.constantes.items()}
        self.lois = (
            LoiEntree(textes[0], self.constantes),
            LoiEntree(textes[1], self.constantes),
            LoiEntree(textes[2], self.constantes),
        )

    def valeur(self, t: float) -> np.ndarray:
        """Vecteur force ou couple à l'instant t, dans le repère de l'action."""
        return np.array([loi.valeur(t) for loi in self.lois], dtype=float)

    def vers_dict(self) -> dict[str, Any]:
        return {
            "nom": self.nom,
            "solide": self.solide,
            "nature": self.nature.value,
            "composantes": list(self.composantes),
            "repere": self.repere.value,
            "point": list(self.point),
            "constantes": dict(self.constantes),
        }

    @classmethod
    def depuis_dict(cls, d: dict[str, Any]) -> "ActionExterieure":
        return cls(
            nom=d["nom"],
            solide=d["solide"],
            nature=d["nature"],
            composantes=tuple(d["composantes"]),
            repere=d["repere"],
            point=tuple(d["point"]),  # type: ignore[arg-type]
            constantes=dict(d["constantes"]),
        )


@dataclass
class RessortAmortisseur:
    """Ressort-amortisseur linéaire entre deux points de deux solides (EX-33).

    Raideur k (N/m), longueur libre l₀ (m), amortissement c (N·s/m). Les points sont donnés en
    repère monde à la pose d'import et liés à leur solide. Effort : k (l − l₀) + c·l̇ le long de
    la droite des deux points.
    """

    nom: str
    solide_1: str
    point_1: tuple[float, float, float]
    solide_2: str
    point_2: tuple[float, float, float]
    raideur: float
    longueur_libre: float
    amortissement: float = 0.0

    def __post_init__(self) -> None:
        _nom_non_vide(self.nom, "ressort")
        _nom_non_vide(self.solide_1, "solide de ressort")
        _nom_non_vide(self.solide_2, "solide de ressort")
        if self.solide_1 == self.solide_2:
            raise ErreurAction(
                f"Ressort {self.nom} : il doit relier deux solides distincts "
                f"(et non {self.solide_1} à lui-même)."
            )
        self.point_1 = _point(self.point_1, f"Ressort {self.nom}")
        self.point_2 = _point(self.point_2, f"Ressort {self.nom}")
        for libelle, valeur in (
            ("raideur k", self.raideur),
            ("longueur libre l₀", self.longueur_libre),
            ("amortissement c", self.amortissement),
        ):
            if not isinstance(valeur, int | float) or not math.isfinite(valeur) or valeur < 0.0:
                raise ErreurAction(
                    f"Ressort {self.nom} : {libelle} invalide (nombre fini positif ou nul)."
                )

    def vers_dict(self) -> dict[str, Any]:
        return {
            "nom": self.nom,
            "solide_1": self.solide_1,
            "point_1": list(self.point_1),
            "solide_2": self.solide_2,
            "point_2": list(self.point_2),
            "raideur": self.raideur,
            "longueur_libre": self.longueur_libre,
            "amortissement": self.amortissement,
        }

    @classmethod
    def depuis_dict(cls, d: dict[str, Any]) -> "RessortAmortisseur":
        return cls(
            nom=d["nom"],
            solide_1=d["solide_1"],
            point_1=tuple(d["point_1"]),  # type: ignore[arg-type]
            solide_2=d["solide_2"],
            point_2=tuple(d["point_2"]),  # type: ignore[arg-type]
            raideur=float(d["raideur"]),
            longueur_libre=float(d["longueur_libre"]),
            amortissement=float(d["amortissement"]),
        )
