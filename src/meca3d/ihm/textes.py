# SPDX-License-Identifier: GPL-3.0-or-later
"""Tous les textes de l'interface, en français (règle IHM). Unités toujours indiquées."""

import re

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
ACTION_NOUVEAU = "&Nouvelle étude"
ACTION_OUVRIR = "&Ouvrir une étude…"
ACTION_ENREGISTRER = "&Enregistrer"
ACTION_ENREGISTRER_SOUS = "Enregistrer &sous…"
ACTION_EXPORTER_CSV = "Exporter les résultats en CSV…"
FILTRE_ETUDE = "Étude Meca3D (*.meca3d)"
FILTRE_CSV = "Fichier CSV (*.csv)"
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
INFO_SIMULER_CINEMATIQUE = (
    "Lance la simulation cinématique : une loi d'entrée par mobilité, aucun effort affiché."
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
ONGLET_COURBES = "Courbes"
ONGLET_TORSEURS = "Torseurs"

# --- étude, fichiers, bandeau (EX-60, EX-06) -------------------------------------------------
TITRE_CONFIRMATION_ABANDON = "Abandonner l'étude en cours"
TEXTE_CONFIRMATION_ABANDON = "L'étude en cours a des modifications non enregistrées. Continuer ?"
MSG_ETUDE_ENREGISTREE = "Étude enregistrée : "
MSG_ETUDE_OUVERTE = "Étude ouverte : "
MSG_PAS_DE_RESULTAT = "Aucun résultat à exporter : lancer d'abord une simulation."
MSG_CSV_ECRIT = "Résultats exportés : "
BANDEAU_MODIFIEE = "Maquette modifiée — réimporter pour mettre l'étude à jour."
BOUTON_REIMPORTER = "Réimporter"
MSG_VERIFICATION_IMPOSSIBLE = "Vérification de la maquette impossible : "


def titre_fenetre(chemin: str | None, modifiee: bool) -> str:
    nom = "sans titre" if chemin is None else chemin
    return f"{TITRE_FENETRE} — {nom}{' *' if modifiee else ''}"


# --- loi d'entrée : affichage lisible (R8) -------------------------------------------------
SYMBOLES_GRANDEUR = {"angle": "θ", "position": "x"}
UNITES_GRANDEUR = {
    "angle": ("rad", "rad/s", "rad/s²"),
    "position": ("m", "m/s", "m/s²"),
}


def loi_lisible(texte: str) -> str:
    """Expression saisie -> écriture mathématique : `2*pi*t**2` devient `2·π·t^2`."""
    resultat = texte.strip().replace("**", "^").replace("*", "·")
    resultat = re.sub(r"\bpi\b", "π", resultat)
    return resultat.replace("sqrt(", "√(")


def loi_pilote(texte: str, grandeur: str) -> str:
    symbole = SYMBOLES_GRANDEUR.get(grandeur, "f")
    unite = UNITES_GRANDEUR.get(grandeur, ("",))[0]
    return f"{symbole}(t) = {loi_lisible(texte)}  ({unite})"


# --- saisie des entrées -----------------------------------------------------------------------
GROUPE_PILOTE = "Loi d'entrée (pilote)"
LOI_ACTUELLE = "Loi actuelle : "
AUCUNE_LOI = "aucune loi d'entrée sur cette liaison"
CHAMP_LOI = "f(t) ="
CHAMP_T_APERCU = "Aperçu à t ="
BOUTON_APPLIQUER_LOI = "Appliquer la loi"
BOUTON_RETIRER_LOI = "Retirer la loi"
GRANDEURS = (("Angle imposé (rad)", "angle"), ("Position imposée (m)", "position"))
MSG_LOI_A_SAISIR = "Saisir d'abord une loi d'entrée valide."
MSG_POSE_INCONNUE = "Pilote impossible : la pose initiale de cette liaison est inconnue."


def apercu_loi(valeur: float, vitesse: float, acceleration: float, u: tuple[str, str, str]) -> str:
    return (
        f"valeur = {valeur:.6g} {u[0]} ; vitesse = {vitesse:.6g} {u[1]} ; "
        f"accélération = {acceleration:.6g} {u[2]}"
    )


def loi_non_evaluable(t: float, detail: str) -> str:
    return f"Loi non évaluable à t = {t:g} s ({detail})."


TITRE_PESANTEUR = "Pesanteur"
CASE_PESANTEUR = "Pesanteur active"
BOUTON_PESANTEUR = "Appliquer la pesanteur"
GROUPE_PESANTEUR = "Vecteur g (repère monde, m/s²)"

TITRE_ACTION = "Action extérieure"
CHAMP_NOM = "Nom"
CHAMP_SOLIDE = "Solide"
CHAMP_NATURE = "Nature"
CHAMP_REPERE = "Repère d'expression"
NATURES = (("Force (N)", "force"), ("Couple (N·m)", "couple"))
REPERES = (("Repère monde", "monde"), ("Repère du solide", "solide"))
GROUPE_POINT_PIECE = "Point d'application (coordonnées pièce, mm)"
GROUPE_COMPOSANTES_FORCE = "Composantes de la force (N), fonctions de t"
GROUPE_COMPOSANTES_COUPLE = "Composantes du couple (N·m), fonctions de t"
BOUTON_AJOUTER = "Ajouter"
BOUTON_APPLIQUER = "Appliquer les modifications"
BOUTON_SUPPRIMER = "Supprimer"

TITRE_RESSORT = "Ressort-amortisseur"
GROUPE_POINT_1 = "Point 1 (coordonnées pièce du solide 1, mm)"
GROUPE_POINT_2 = "Point 2 (coordonnées pièce du solide 2, mm)"
CHAMP_SOLIDE_1 = "Solide 1"
CHAMP_SOLIDE_2 = "Solide 2"
CHAMP_RAIDEUR = "Raideur k"
CHAMP_LONGUEUR_LIBRE = "Longueur libre l₀"
CHAMP_AMORTISSEMENT = "Amortissement c"

TITRE_CAPTEUR = "Capteur"
GENRES_CAPTEUR = (("Capteur de liaison (torseur)", "liaison"), ("Capteur de point", "point"))
CHAMP_LIAISON = "Liaison"
CHAMP_SENS = "Sens du torseur"
SENS = (("i → j (action du solide a sur b)", "i_vers_j"), ("j → i", "j_vers_i"))
CHAMP_BASE = "Base d'expression"
BASES_LIAISON = (("Base de liaison", "liaison"), ("Base monde", "monde"))
BASES_POINT = (("Base du solide de référence", "reference"), ("Base monde", "monde"))
CHAMP_REFERENCE = "Solide de référence"
GROUPE_POINT_CAPTEUR = "Point du solide (coordonnées pièce, mm)"

MSG_NOM_EXISTE = "Ce nom existe déjà : en choisir un autre."


def libelle_action(nom: str, nature: str, solide: str) -> str:
    return f"{nom} — {'force' if nature == 'force' else 'couple'} sur {solide}"


def libelle_ressort(nom: str, solide_1: str, solide_2: str) -> str:
    return f"{nom} — {solide_1} / {solide_2}"


def libelle_capteur(nom: str, genre: str, detail: str) -> str:
    return f"{nom} — {'torseur' if genre == 'liaison' else 'point'} {detail}"


# --- résultats (EX-50, EX-52) -------------------------------------------------------------------
COURBE_X = "Abscisse"
COURBE_Y = "Ordonnée"
COURBE_VIDE = "Aucun résultat : lancer une simulation."
CHAMP_TORSEUR = "Torseur"
TORSEURS = (("Statique {i→j}", "statique"), ("Cinématique {V j/i}", "cinematique"))
TORSEUR_VIDE = "Aucun résultat : lancer une simulation."
TORSEUR_STATIQUE_ABSENT = "Aucun effort en mode cinématique : torseur cinématique seul."
COLONNE_LIAISON = "Liaison"


def etiquette_instant(t: float) -> str:
    return f"t = {t:.6g} s"


def etiquette_statistiques(minimum: float, maximum: float, moyenne: float, unite: str) -> str:
    u = f" {unite}" if unite else ""
    return f"min = {minimum:.6g}{u} ; max = {maximum:.6g}{u} ; moyenne = {moyenne:.6g}{u}"


def unite_de(grandeur: str) -> str:
    """Unité entre parenthèses à la fin d'un nom de colonne : `C (N·m)` -> `N·m`."""
    if grandeur.endswith(")") and "(" in grandeur:
        return grandeur[grandeur.rindex("(") + 1 : -1]
    return ""


# --- animation dans SolidCraft et trajectoires (EX-53, EX-52) ----------------------------------
ONGLET_ANIMATION = "Animation"
ANIMATION_LECTURE = "Lecture"
ANIMATION_PAUSE = "Pause"
ANIMATION_ARRET = "Arrêter (restaurer la pose)"
ANIMATION_VITESSE = "Vitesse :"
ANIMATION_VITESSES: tuple[tuple[str, float], ...] = (
    ("×0,1", 0.1),
    ("×0,25", 0.25),
    ("×0,5", 0.5),
    ("×1", 1.0),
    ("×2", 2.0),
)
ANIMATION_TRAJECTOIRE_CAPTEUR = "Capteur de point :"
ANIMATION_TRACER = "Tracer la trajectoire"
ANIMATION_EFFACER = "Effacer les trajectoires"
ANIMATION_AIDE = (
    "Rejoue dans SolidCraft le mouvement simulé : lecture, pause, vitesse de ×0,1 à ×2 et curseur "
    "temporel. La pose initiale de la maquette est restaurée à l'arrêt, en fin de lecture et à la "
    "fermeture ; la maquette n'est jamais enregistrée. Garder la fenêtre de SolidCraft visible."
)
ANIMATION_INACTIVE = "Animation indisponible : "
ANIMATION_SANS_RESULTAT = "lancer d'abord une simulation."
ANIMATION_SANS_CONNEXION = "connecter SolidCraft."
ANIMATION_OCCUPEE = "une opération est en cours."
ANIMATION_PAS_DE_CAPTEUR = "Aucun capteur de point : en ajouter un (branche Capteurs)."
MSG_TRAJECTOIRE_TRACEE = (
    "Trajectoire tracée dans SolidCraft (esquisse 3D « {nom} »). La maquette est modifiée : "
    "l'enregistrer dans SolidCraft pour conserver la trajectoire."
)
MSG_TRAJECTOIRES_EFFACEES = "Trajectoires effacées de la maquette SolidCraft : {nombre}."
MSG_AUCUNE_TRAJECTOIRE = "Aucune trajectoire à effacer."


def animation_temps(t: float, duree: float) -> str:
    return f"t = {t:.3f} s / {duree:.3f} s".replace(".", ",")
