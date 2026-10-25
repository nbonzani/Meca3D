# SPDX-License-Identifier: GPL-3.0-or-later
"""Affichage lisible d'une loi d'entrée (EX-30) : le texte saisi par l'élève est relu par `ast`
(sans jamais l'évaluer) et réécrit en notation mathématique : `2*pi*t**2` devient `2·π·t^2`,
`Piecewise((a, t < 0.2), (b, True))` devient `si t < 0,2 : a ; sinon : b`.

Texte illisible (non analysable) : repli sur une substitution simple, sans erreur.
"""

import ast
import re

_PREC_SOMME, _PREC_PRODUIT, _PREC_UNAIRE, _PREC_PUISSANCE, _PREC_ATOME = 1, 2, 3, 4, 5
_COMPARAISONS: dict[type[ast.cmpop], str] = {
    ast.Lt: "<",
    ast.LtE: "≤",
    ast.Gt: ">",
    ast.GtE: "≥",
    ast.Eq: "=",
    ast.NotEq: "≠",
}


def _nombre(valeur: float) -> str:
    return f"{valeur:g}".replace(".", ",")


def _rendre(noeud: ast.expr) -> tuple[str, int]:
    """Texte du nœud et sa précédence."""
    if isinstance(noeud, ast.Constant):
        if isinstance(noeud.value, bool):
            return ("vrai" if noeud.value else "faux"), _PREC_ATOME
        if isinstance(noeud.value, (int, float)):
            return _nombre(noeud.value), _PREC_ATOME
        raise ValueError("constante non numérique")
    if isinstance(noeud, ast.Name):
        return ("π" if noeud.id == "pi" else noeud.id), _PREC_ATOME
    if isinstance(noeud, ast.UnaryOp) and isinstance(noeud.op, (ast.USub, ast.UAdd)):
        signe = "-" if isinstance(noeud.op, ast.USub) else "+"
        return signe + _entre(noeud.operand, _PREC_UNAIRE), _PREC_UNAIRE
    if isinstance(noeud, ast.BinOp):
        return _binaire(noeud)
    if isinstance(noeud, ast.Compare) and len(noeud.ops) == 1:
        symbole = _COMPARAISONS.get(type(noeud.ops[0]))
        if symbole is None:
            raise ValueError("comparaison inconnue")
        gauche, _ = _rendre(noeud.left)
        droite, _ = _rendre(noeud.comparators[0])
        return f"{gauche} {symbole} {droite}", _PREC_SOMME - 1
    if isinstance(noeud, ast.Call) and isinstance(noeud.func, ast.Name):
        return _appel(noeud), _PREC_ATOME
    raise ValueError("nœud non géré")


def _entre(noeud: ast.expr, minimum: int) -> str:
    texte, precedence = _rendre(noeud)
    return f"({texte})" if precedence < minimum else texte


def _binaire(noeud: ast.BinOp) -> tuple[str, int]:
    op = noeud.op
    if isinstance(op, (ast.Add, ast.Sub)):
        signe = " + " if isinstance(op, ast.Add) else " - "
        droite_min = _PREC_SOMME if isinstance(op, ast.Add) else _PREC_PRODUIT
        return (
            _entre(noeud.left, _PREC_SOMME) + signe + _entre(noeud.right, droite_min),
            _PREC_SOMME,
        )
    if isinstance(op, (ast.Mult, ast.Div)):
        signe = "·" if isinstance(op, ast.Mult) else "/"
        droite_min = _PREC_PRODUIT if isinstance(op, ast.Mult) else _PREC_UNAIRE
        return (
            _entre(noeud.left, _PREC_PRODUIT) + signe + _entre(noeud.right, droite_min),
            _PREC_PRODUIT,
        )
    if isinstance(op, ast.Pow):
        return (
            _entre(noeud.left, _PREC_ATOME) + "^" + _entre(noeud.right, _PREC_ATOME),
            _PREC_PUISSANCE,
        )
    raise ValueError("opérateur non géré")


def _piecewise(noeud: ast.Call) -> str:
    morceaux: list[str] = []
    for i, argument in enumerate(noeud.args):
        if not (isinstance(argument, ast.Tuple) and len(argument.elts) == 2):
            raise ValueError("Piecewise mal formé")
        expression, condition = argument.elts
        texte = _rendre(expression)[0]
        vraie = isinstance(condition, ast.Constant) and condition.value is True
        if vraie and i == len(noeud.args) - 1 and i > 0:
            morceaux.append(f"sinon : {texte}")
        else:
            morceaux.append(f"si {_rendre(condition)[0]} : {texte}")
    return " ; ".join(morceaux)


def _appel(noeud: ast.Call) -> str:
    assert isinstance(noeud.func, ast.Name)
    nom = noeud.func.id
    if nom == "Piecewise":
        return _piecewise(noeud)
    arguments = ", ".join(_rendre(a)[0] for a in noeud.args)
    return f"√({arguments})" if nom == "sqrt" else f"{nom}({arguments})"


def _repli(texte: str) -> str:
    resultat = texte.strip().replace("**", "^").replace("*", "·")
    resultat = re.sub(r"\bpi\b", "π", resultat)
    return resultat.replace("sqrt(", "√(")


def loi_lisible(texte: str) -> str:
    """Texte saisi -> écriture mathématique lisible (jamais d'évaluation du texte)."""
    try:
        arbre = ast.parse(texte.strip(), mode="eval")
        return _rendre(arbre.body)[0]
    except (SyntaxError, ValueError, RecursionError):
        return _repli(texte)
