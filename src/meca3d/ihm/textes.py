# SPDX-License-Identifier: GPL-3.0-or-later
"""Tous les textes de l'interface, en français (règle IHM). Unités toujours indiquées."""

from meca3d.modele.liaison import Statut, TypeLiaison

TITRE_FENETRE = "Meca3D"

# --- arbre de l'étude (EX-61) ---------------------------------------------------------------
BRANCHE_MODELE = "Modèle cinématique"
BRANCHE_DONNEES = "Données d'entrée"
BRANCHE_RESULTATS = "Résultats"
RUBRIQUE_SOLIDES = "Solides"
RUBRIQUE_LIAISONS = "Liaisons"
RUBRIQUE_GRAPHE = "Graphe"
RUBRIQUE_PILOTES = "Pilotes"
RUBRIQUE_PESANTEUR = "Pesanteur"
RUBRIQUE_ACTIONS = "Actions"
RUBRIQUE_RESSORTS = "Ressorts"
RUBRIQUE_CAPTEURS = "Capteurs"
RUBRIQUE_COURBES = "Courbes"
RUBRIQUE_ANIMATION = "Animation"
MARQUE_INCOMPLET = "⚠ "

LIBELLES_TYPE: dict[TypeLiaison, str] = {
    TypeLiaison.ENCASTREMENT: "encastrement",
    TypeLiaison.PIVOT: "pivot",
    TypeLiaison.GLISSIERE: "glissière",
    TypeLiaison.PIVOT_GLISSANT: "pivot glissant",
    TypeLiaison.ROTULE_A_DOIGT: "rotule à doigt",
    TypeLiaison.ROTULE: "rotule",
    TypeLiaison.APPUI_PLAN: "appui plan",
    TypeLiaison.LINEAIRE_ANNULAIRE: "linéaire annulaire",
    TypeLiaison.LINEAIRE_RECTILIGNE: "linéaire rectiligne",
    TypeLiaison.PONCTUELLE: "ponctuelle",
    TypeLiaison.HELICOIDALE: "hélicoïdale",
}
LIBELLES_STATUT: dict[Statut, str] = {Statut.PROPOSEE: "proposée", Statut.VALIDEE: "validée"}
TYPE_A_CHOISIR = "type à choisir"
AUCUN_ELEMENT = "aucun"


def libelle_liaison(nom: str, type_: TypeLiaison | None, statut: Statut) -> str:
    libelle_type = TYPE_A_CHOISIR if type_ is None else LIBELLES_TYPE[type_]
    return f"{nom} — {libelle_type} ({LIBELLES_STATUT[statut]})"


# --- barre d'état ---------------------------------------------------------------------------
CONNEXION_ABSENTE = "SolidCraft : déconnecté"
CONNEXION_EN_COURS = "SolidCraft : connexion…"


def connexion_etablie(port: int) -> str:
    return f"SolidCraft : connecté (port {port})"


def etiquette_m(m: int | None) -> str:
    return f"m = {'—' if m is None else m}"


def etiquette_h(h: int | None) -> str:
    return f"h = {'—' if h is None else h}"


# --- commandes ------------------------------------------------------------------------------
MENU_FICHIER = "&Fichier"
MENU_SOLIDCRAFT = "&SolidCraft"
MENU_SIMULATION = "S&imulation"
MENU_ENSEIGNANT = "&Enseignant"
ACTION_QUITTER = "&Quitter"
ACTION_CONNECTER = "Connecter"
ACTION_IMPORTER = "Importer la maquette"
ACTION_SIMULER = "Simuler (dynamique)"
ACTION_SIMULER_CINEMATIQUE = "Simuler (cinématique)"
ACTION_ANNULER = "Annuler le calcul"
ACTION_VALIDER_TOUTES = "Valider toutes les propositions"
ACTION_VALIDATION_EN_BLOC = "Validation en bloc"
ACTION_HYPERSTATIQUE = "Hyperstatique autorisé"
INFO_VALIDATION_EN_BLOC = (
    "Ajoute le bouton « Valider toutes les propositions » (choix d'ergonomie, sans mot de passe)."
)
INFO_HYPERSTATIQUE = (
    "Autorise la simulation cinématique d'un mécanisme hyperstatique (h > 0). "
    "Le mode dynamique reste refusé."
)
INFO_SIMULER = "Lance la simulation dynamique dans un processus séparé."
INFO_CINEMATIQUE_INDISPONIBLE = (
    "Mode cinématique non disponible dans cette version (en cours de développement)."
)
INFO_SIMULER_INACTIF = "Valider d'abord chacune des liaisons du mécanisme."
TITRE_CONFIRMATION_BLOC = "Valider toutes les propositions"
TEXTE_CONFIRMATION_BLOC = (
    "Toutes les liaisons proposées vont être validées telles quelles. "
    "Vérifier que chaque proposition correspond bien au mécanisme réel. Continuer ?"
)

# --- messages -------------------------------------------------------------------------------
MSG_PAS_D_ETUDE = "Aucune étude : connecter SolidCraft puis importer la maquette."
MSG_IMPORT_EN_COURS = "Import de la maquette en cours…"
MSG_MOBILITE_INDISPONIBLE = (
    "Mobilité indisponible : choisir le type de chaque liaison (et la seconde direction "
    "des liaisons qui en demandent une)."
)
MSG_CALCUL_LANCE = "Calcul lancé dans un processus séparé (le démarrage prend quelques secondes)."
MSG_CALCUL_ANNULE = "Calcul annulé : aucun résultat."
MSG_CALCUL_ECHEC = "Échec du calcul. "
MSG_BLOC_FAIT = "Liaisons validées en bloc : "


def msg_calcul_termine(n_instants: int) -> str:
    return f"Simulation terminée : {n_instants} instants calculés."


def msg_import_termine(n_solides: int, n_liaisons: int) -> str:
    return f"Maquette importée : {n_solides} solides, {n_liaisons} liaisons proposées."


# --- propriétés -----------------------------------------------------------------------------
TITRE_PROPRIETES = "Propriétés"
PROPRIETES_VIDE = "Sélectionner un élément de l'arbre."
CHOIX_TYPE_VIDE = "— à choisir —"
BOUTON_VALIDER = "Valider cette liaison"
BOUTON_AXE = "Appliquer l'axe"
BOUTON_DIRECTION = "Appliquer la direction"
BOUTON_CENTRE = "Déplacer le centre"
GROUPE_AXE = "Orientation de l'axe (repère monde)"
GROUPE_DIRECTION = "Seconde direction (repère monde, projetée orthogonalement à l'axe)"
GROUPE_CENTRE = "Centre de la liaison (repère monde)"
AXES_MONDE = (
    ("Axe x du repère monde", "x"),
    ("Axe y du repère monde", "y"),
    ("Axe z du repère monde", "z"),
    ("Vecteur saisi", "vecteur"),
)


def etiquette_statut(statut: Statut) -> str:
    return f"Statut : {LIBELLES_STATUT[statut]}"


def etiquette_type_solidcraft(type_sc: str, proposition: TypeLiaison | None) -> str:
    texte = f"Type SolidCraft : {type_sc}"
    if proposition is None:
        return texte + " — aucune proposition, choix imposé."
    return texte + f" — proposition : {LIBELLES_TYPE[proposition]}."


# --- graphe ---------------------------------------------------------------------------------
GRAPHE_INDISPONIBLE = "Graphe indisponible : " + MSG_MOBILITE_INDISPONIBLE
GRAPHE_VIDE = "Aucune étude chargée."
CYCLE_AUCUN = "aucun cycle"
BATI = "Bâti"


def resume_graphe(mu: int | None, m: int | None, h: int | None) -> str:
    def v(x: int | None) -> str:
        return "—" if x is None else str(x)

    return f"μ = {v(mu)}   m = {v(m)}   h = {v(h)}"


def libelle_cycle(numero: int, liaisons: list[str]) -> str:
    return f"Cycle {numero} : " + " – ".join(liaisons)


ONGLET_GRAPHE = "Graphe des liaisons"
ONGLET_JOURNAL = "Journal"
