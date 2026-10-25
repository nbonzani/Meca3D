# Analyse d'architecture de Decade 1.4 et transposition vers SolidCraft

*Analyse du code source de Decade 1.4 (T. Paviot, C. Faury, GPL v2, décembre 2008), extrait dans `decade_archive/extract_14/app/`. Rédigée le 22 octobre 2026.*

Légende : **[code]** = constaté dans le source ; **[doc]** = constaté dans la documentation livrée ; **[à vérifier]** = hypothèse non testée.

---

## 1. Vue d'ensemble

Decade est une application **wxPython autonome** qui pilote la CAO de l'extérieur. Elle ne s'intègre pas à CATIA ni à SolidWorks. La CAO sert de **source de données** (pièces, masses, inerties, contraintes d'assemblage) et de **visualiseur** (animation des pièces, tracé des trajectoires).

```
┌──────────── CAO (CATIA V5 / SolidWorks) ────────────┐
│ assemblage = classes d'équivalence (sous-ensembles) │
└───────▲──────────────────────────────┬──────────────┘
        │ COM (pywin32 + proxy VB6)     │ positions, trajectoires,
        │ masses, inerties, CdG,        │ paramètres DECADE_*
        │ contraintes d'assemblage      ▼
┌───────┴────────────── Decade (Python 2.5) ─────────────────────┐
│ cad_interface.py  BASE / STANDALONE / CATIA / SOLIDWORKS        │
│ base.py           Solid, Liaison, Spring, Couple, Glisseur,     │
│                   VelocityLaw, Trajectoire, capteurs            │
│ project.py        modèle, boucle de simulation, rejeu, export   │
│ graph.py          graphe des liaisons (networkx) : μ, cycles    │
│ tree.py / gui.py  arbre modèle / entrées / résultats            │
│ plot.py           courbes (matplotlib), CSV, DSP                │
└────────────────────────────┬────────────────────────────────────┘
                             │ PyODE
                       Open Dynamics Engine
```

Volume : environ 20 200 lignes. Les plus gros modules sont `tree.py` (188 Ko), `project.py` (148 Ko), `base.py` (95 Ko) et `cad_interface.py` (58 Ko) **[code]**.

---

## 2. Modèle mécanique (`base.py`)

### 2.1 Solide

`Solid` porte **[code]** :
- la masse, le centre de gravité et la matrice d'inertie (Ixx…Iyz), lus dans la CAO ou saisis à la main (`mass_given_by_cad`) ;
- un indicateur `bati` (solide fixe) ;
- des **points** et des **vecteurs** nommés, attachés au solide. G (centre de gravité) et O (origine) sont créés par défaut, et l'élève en ajoute ;
- les vitesses initiales (linéaire et angulaire, exprimées en G) ;
- l'historique des positions et rotations, pour le rejeu sans recalcul ;
- la position du solide dans le diagramme du graphe des liaisons.

La **géométrie de collision** n'est qu'une ébauche : la forme est choisie d'après le *nom* de la pièce (« Sp », « Box », « Bille »…). La détection de collisions est désactivée par défaut (`COLLISION_DETECTION=False`) **[code]**.

### 2.2 Liaisons normalisées et traduction dans ODE

L'élève **choisit lui-même le type de liaison**. Decade ne le déduit pas des contraintes ; il en tire seulement la géométrie (point, axe, normale). Le modèle mécanique reste donc l'œuvre de l'élève **[code + doc]**.

| Liaison (globdef) | Traduction dans ODE | Remarque |
|---|---|---|
| Pivot | `HingeJoint` | exact |
| Glissière | `SliderJoint` | exact |
| Pivot glissant | `PistonJoint` | exact |
| Rotule | `BallJoint` | exact |
| Cardan (rotule à doigt) | `UniversalJoint` | exact |
| Encastrement | `FixedJoint` | exact |
| Appui plan | 2 corps fictifs : glissière + glissière + pivot | **approximation** |
| Ponctuelle | 2 corps fictifs : glissière + glissière + rotule | **approximation** |
| Linéaire annulaire | 1 corps fictif : glissière + rotule | **approximation** |
| Hélicoïdale | pivot + glissière couplés à chaque pas (`Liaison.Update`) | couplage explicite |
| TPR (transmission de puissance en rotation) | `CogWheelsJoint` | joint ajouté à une version modifiée de PyODE **[à vérifier]** |

Les **corps fictifs** ont une masse égale à 1/50 de la moyenne des masses des deux solides, sans gravité **[code]**. Ce bricolage était nécessaire parce qu'ODE n'a pas de joints point-plan ou point-droite. Il introduit une inertie parasite : les efforts calculés dans ces liaisons sont donc **approchés**.

Chaque liaison accepte aussi des **butées** (lostop/histop avec rebond), un **frottement visqueux** et un **frottement sec**. Le frottement sec est déclaré mais je n'en ai pas vu l'usage **[code]**.

### 2.3 Actions mécaniques et pilotage

- `Spring` (ressort linéaire entre deux points de deux solides : k, L0) et `TorsionalSpring` (ressort de torsion sur une liaison : C, a0). Les deux appliquent leurs forces avant chaque pas de calcul.
- `Glisseur` (force) et `Couple`. Leurs composantes sont des **expressions de t** évaluées à chaque pas, dans la base d'un solide donné.
- `VelocityLaw` : loi de vitesse imposée à un pivot ou à une glissière, sous forme linéaire, trapèze, échelon ou expression libre (« 10*sin(50*t) »). Elle est réalisée comme un **moteur ODE** (`paramVel` plus un effort maximal `MOTOR_FMAX` = 10 000 N ou N·m). Une alerte se déclenche si l'effort moteur dépasse ce plafond, et un détecteur de « points durs » (butées) existe **[code]**.

### 2.4 Capteurs (résultats)

**Capteurs de liaison** **[code]** :
- position, vitesse et accélération articulaires. L'angle est déroulé au-delà de 2π. L'accélération est obtenue par **différence finie** ;
- efforts **Fx, Fy, Fz, |F|, Mx, My, Mz, |M|**, lus par `joint.getFeedback()`.

**Capteurs de point** : position, vitesse et accélération (composantes et norme) d'un point, **par rapport à un solide de référence** choisi. C'est le mouvement relatif, une notion centrale en cinématique **[code]**.

**Post-traitement** : min, max, moyenne, amplitude, densité spectrale (DSP), export CSV. Les valeurs peuvent aussi être **écrites dans CATIA** sous forme de paramètres `DECADE_<capteur>_MIN/MAX/AVERAGE/INSTANT` **[code]**.

**Limite importante pour l'enseignement.** Le retour d'effort d'ODE donne la force et le moment appliqués à chaque corps **en son centre de gravité, dans le repère global**. Decade affiche F1 − F2, dans le repère global. Ce n'est **pas** le torseur d'action mécanique transmissible réduit au centre de la liaison et exprimé dans la base locale, qui est la grandeur enseignée **[code]**.

### 2.5 Trajectoires

`Trajectoire` enregistre le chemin d'un point par rapport à un solide de référence. Le chemin est **retracé dans la CAO** : un set géométrique dans CATIA, une esquisse dans SolidWorks **[code]**.

---

## 3. Interface CAO (`cad_interface.py`)

Il y a une classe abstraite `BASE_Interface` et quatre implémentations : `STANDALONE`, `CATIA`, `SOLIDWORKS`, et `INVENTOR` (ébauche) **[code]**. Les services fournis :

| Service | Côté CATIA V5 |
|---|---|
| Liste des pièces = solides | parcours du Product. **Chaque sous-assemblage est une classe d'équivalence** **[doc]** |
| Masse, CdG, inertie | `Analyze.GetInertia` via un proxy VB6 (`cad_proxy.dll`) ; contrôle que la matrice d'inertie est définie positive |
| Contraintes d'assemblage | `Connections("CATIAConstraints")` ; les éléments géométriques (droite, plan, point) sont mesurés avec `SPAWorkbench` |
| Animation | `PositionRotation2CAD` : la matrice de position de chaque pièce est réécrite à chaque image |
| Retour dans la CAO | trajectoires, paramètres `DECADE_*`, annotations 3D, capture vidéo |
| Lancement | macro `Start_Decade.catvba` |

La traduction des contraintes en géométrie de liaison (`LiaisonFromConstraint`) suit le type choisi par l'élève **[code]** :
- pivot, glissière ou pivot glissant : on cherche une **droite** (axe et point) ;
- rotule : on cherche un **point** ;
- appui plan : on cherche un **plan** (normale et point) ;
- ponctuelle ou linéaire annulaire : on cherche un couple point-plan ou point-droite.

Le **mode autonome** utilise la même interface, sans CAO : l'élève saisit les masses, les inerties et les positions. Le tutoriel le présente comme un atout : « un simple schéma peut suffire » **[doc]**.

---

## 4. Moteur de dynamique (ODE)

- Monde ODE, gravité désactivée par défaut, `ERP=0.8`, `CFM=1e-4`, **30 sous-pas** par image, `world.step` (solveur direct) plutôt que `quickStep` **[code]**.
- **Coordonnées maximales.** Chaque solide a 6 ddl et les liaisons sont des contraintes. Les **boucles fermées** passent donc naturellement, ce qui est un vrai atout pour les mécanismes enseignés (bielle-manivelle, Sinusmatic, hexapode).
- Mais les contraintes sont **pénalisées** (ERP et CFM). Elles dérivent légèrement et les efforts de liaison dépendent de ces réglages. ODE est conçu pour le jeu vidéo et ne garantit pas la précision attendue en ingénierie.
- Il n'existe pas de mode cinématique pur : même en cinématique, on simule la dynamique avec des moteurs à effort plafonné. Le drapeau `ANALYSE_CINEMATIQUE` existe mais semble inachevé **[code]**.
- La boucle de simulation à chaque image **[code]** :
  1. lire les capteurs ;
  2. enregistrer les positions et animer la CAO ;
  3. pour chaque sous-pas : ressorts, glisseurs et couples (fonctions de t), lois de vitesse, couplage hélicoïdal, collisions, `world.step` ;
  4. stocker les trajectoires.

  Le calcul, l'animation et l'interface tournent dans **un seul fil d'exécution**.

---

## 5. Graphe des liaisons (`graph.py`, `diagram.py`)

**[code]** :
- `Graph` hérite de `networkx.Graph` : les solides sont les sommets, les liaisons les arêtes ;
- **nombre cyclomatique** μ = L − S + 1 ;
- **cycles indépendants** : pour chaque liaison, on retire l'arête et on cherche le plus court chemin entre ses deux solides. On en déduit pour chaque liaison et chaque solide s'il est « dans un cycle » ou « hors cycle » ;
- `diagram.py` dessine le graphe (wx.lib.ogl), imprimable, avec mise en évidence d'un cycle choisi.

Je n'ai **trouvé aucun calcul de degré de mobilité ni d'hyperstatisme** dans le code (recherche de « hyperstat » et « mobilit » sans résultat). Le graphe s'arrête à μ et aux cycles.

---

## 6. Démarche pédagogique

D'après le tutoriel (pendule double, 17 pages) et la fiche méthode de F. Vitte (4 pages) **[doc]** :

1. **Préparer la maquette** : l'assemblage CAO est organisé en **sous-assemblages rigides correspondant aux classes d'équivalence cinématique**. Ce travail de modélisation est fait en amont, par l'élève.
2. **Construire le modèle Decade** : importer la maquette (solides reconnus automatiquement), puis pour chaque liaison :
   - choisir les deux solides et le **type de liaison** ;
   - renseigner la géométrie, à la main ou « issue des contraintes d'assemblage » (le bouton passe au vert si l'interprétation réussit) ;
   - consulter le **graphe des liaisons**.
3. **Définir les entrées** : lois de vitesse sur les liaisons pilotes (les « pilotes »), efforts extérieurs, ressorts, gravité.
4. **Définir les sorties** : points supplémentaires, puis **capteurs** (de liaison ou de point, relatifs à un solide de référence) et trajectoires.
5. **Simuler et analyser** : la maquette s'anime dans la CAO, puis on dispose des courbes, du CSV et des trajectoires tracées dans la maquette.

Les choix pédagogiques forts :
- **le même vocabulaire que le cours** : classes d'équivalence, liaisons normalisées, graphe, torseurs, lois d'entrée ;
- **un arbre en trois branches qui suit la démarche** : modèle cinématique (solides, liaisons, graphe), données d'entrée (efforts, lois), résultats (capteurs, trajectoires) ;
- **l'élève modélise** : le logiciel ne devine pas les liaisons ;
- **une interface identique quelle que soit la CAO**, avec un mode autonome ;
- **un logiciel libre**, que les élèves installent chez eux. C'était un argument explicite de l'auteur ;
- **une bibliothèque d'exemples** : 12 maquettes CATIA et 10 maquettes SolidWorks, du pendule simple au réducteur.

---

## 7. Bilan : ce qu'il faut garder, corriger ou abandonner

| Garder | Corriger | Abandonner |
|---|---|---|
| Séparation CAO / simulateur, avec la CAO comme source et comme visualiseur | Efforts de liaison : donner le **torseur au centre de la liaison, en base locale** | Corps fictifs de masse arbitraire |
| Type de liaison choisi par l'élève, géométrie tirée de la CAO | Accélérations : les calculer directement, pas par différence finie | ODE et ses contraintes pénalisées |
| Graphe des liaisons, μ, cycles | Ajouter le **degré de mobilité et d'hyperstatisme** (rang du système cinématique) | Pilotage COM propre à Windows et proxy VB6 |
| Capteurs relatifs à un solide de référence | Vrai **mode cinématique** (mouvement imposé, sans dynamique) | Python 2, Numeric, PyODE, pymedia |
| Lois d'entrée sous forme d'expressions de t | Calcul dans un fil séparé de l'interface | Géométrie de collision choisie d'après le nom des pièces |
| Trajectoires retracées dans la CAO | | |
| Arbre modèle / entrées / résultats ; mode autonome | | |
| Bibliothèque d'exemples et fiches méthode | | |

---

## 8. Transposition vers SolidCraft et un moteur moderne

### 8.1 Ce que SolidCraft apporte déjà

Relevé dans le catalogue de commandes de la version installée **[code SolidCraft]** :

| Besoin Decade | Équivalent SolidCraft | Écart |
|---|---|---|
| Classes d'équivalence | occurrences et `joint.rigid_group` | aucun |
| Masse, CdG | `occurrence.properties` (masse et CdG en repère monde, selon le matériau) | **la matrice d'inertie** n'apparaît pas dans la description ; l'export URDF la calcule **[à vérifier]** |
| Matériaux | `material.assign` / `material.create` (masse volumique) | aucun |
| Liaisons | `joint.create` : rigid, revolute, slider, cylindrical, pin_slot, planar, ball | il manque **ponctuelle, linéaire annulaire, linéaire rectiligne et rotule à doigt** |
| Hélicoïdale, TPR | `joint.screw`, `joint.gear`, `joint.rack_pinion`, `joint.cam` | couplages cinématiques seulement, pas d'effort |
| Animation de la maquette | `joint.drive` (boucles fermées suivies), `motion.study` / `motion.play` | aucun : c'est l'équivalent de `PositionRotation2CAD` |
| Trajectoires dans la CAO | `motion.trace.keep` (spline 3D dans une esquisse) | aucun |
| Cinématique | `motion.plot` (positions, vitesses et accélérations par différence finie), `motion.interference` | **pas de dynamique ni d'efforts** |
| Mobilité | `joint.list` renvoie les ddl et les conflits | à confronter au calcul pédagogique |
| Interface de pilotage | MCP, `solidcraft-cli`, export `json` (conception complète) et `urdf` (arbre seulement, boucles omises) | multiplateforme, sans COM |

**Conclusion** : SolidCraft joue parfaitement le rôle que CATIA tenait pour Decade (source et visualiseur), avec en plus une cinématique à boucles fermées. Il manque exactement ce que Decade apportait : **la dynamique, les efforts de liaison, le graphe et les liaisons à contact ponctuel ou linéique**.

### 8.2 Choix du moteur

Le critère décisif pour un usage pédagogique est de pouvoir déclarer **chaque liaison normalisée par la liste de ses ddl bloqués** (la dualité torseur cinématique / torseur statique), avec des boucles fermées et une **réaction exprimée dans le repère de la liaison**.

| Moteur | Liaisons normalisées | Boucles | Torseur de liaison | Verdict |
|---|---|---|---|---|
| **Exudyn** | `GenericJoint` : 6 indicateurs de ddl bloqués, donc les 11 liaisons sans corps fictif **[à vérifier par un test]** | oui (coordonnées redondantes) | sortie force et moment de la liaison **[à vérifier : repère local]** | **recommandé** |
| Project Chrono (PyChrono) | famille `ChLinkLock*`, dont point-plan et point-droite | oui | réaction dans le repère de la liaison | solide mais lourd (installation via conda) |
| MuJoCo | arbre plus contraintes d'égalité pour fermer les boucles | partiellement | `efc_force` à reconstruire | orienté robotique ; ponctuelle et linéaire annulaire mal adaptées |
| Pinocchio | arbre seulement | non | couples articulaires | inadapté aux boucles |

**Recommandation : Exudyn**, encapsulé derrière une interface `Moteur`, comme Decade le faisait implicitement avec ODE, pour garder Chrono comme solution de repli.

> **Mise à jour du 22 octobre 2026 : prototype réalisé** ([prototypes/exudyn_bielle/RESULTATS.md](../prototypes/exudyn_bielle/RESULTATS.md)).
> - 10 liaisons sur 11 sont exactes directement par `GenericJoint`. La linéaire rectiligne est exacte par association de deux ponctuelles.
> - Torseur : action {1→0}, réduite au centre de la liaison, en base de liaison liée au solide 0.
> - Bielle-manivelle : écart maximal de 0,5 % (0,08 % en régime établi) avec une solution Newton-Euler indépendante.
> - Le cas hyperstatique est refusé par le solveur.
>
> Ces points, marqués « à vérifier » ci-dessus, sont confirmés.

### 8.3 Architecture proposée (Python 3)

```
meca3d/
├── cao/            adaptateurs CAO (équivalent de cad_interface.py)
│   ├── base.py         interface : solides, inerties, liaisons, animation, traces
│   ├── solidcraft.py   via MCP / solidcraft-cli : occurrences, properties,
│   │                   joint.list, export json/urdf ; retour : joint.drive, motion.trace.keep
│   └── autonome.py     saisie manuelle (mode « simple schéma »)
├── modele/         modèle pédagogique (équivalent de base.py, sans dépendance au moteur)
│   ├── solide.py       masse, CdG, inertie, points et vecteurs nommés
│   ├── liaison.py      11 liaisons normalisées : ddl bloqués, centre, base locale
│   ├── actions.py      ressorts, glisseurs, couples, lois d'entrée (expressions de t)
│   └── capteurs.py     liaison (torseurs cinématique et statique), point / solide de référence
├── graphe/         networkx : μ, cycles, mobilité et hyperstatisme (rang)
├── moteur/         interface Moteur ; exudyn.py (dynamique) ; cinematique.py (mouvement imposé)
├── resultats/      courbes, CSV, post-traitement (min, max, moyenne, DSP)
└── ihm/            PyQt6 : arbre modèle / entrées / résultats, graphe, courbes
```

Ce qu'on transpose de Decade, module par module :
- **`cao/solidcraft.py`** reprend `BASE_Interface` sans COM. Les liaisons SolidCraft sont **proposées** comme point de départ (revolute → pivot, slider → glissière, cylindrical → pivot glissant, planar → appui plan, ball → rotule, rigid → encastrement), mais **l'élève valide ou change le type**, conformément au principe de Decade. Les liaisons absentes de SolidCraft (ponctuelle, linéaire annulaire, linéaire rectiligne, rotule à doigt) sont définies dans Meca3D à partir d'une origine de liaison SolidCraft (`joint.origin`).
- **`modele/liaison.py`** remplace la table de traduction ODE (et ses corps fictifs) par la **définition de chaque liaison par ses ddl**. C'est à la fois plus juste et plus pédagogique.
- **`modele/capteurs.py`** corrige le défaut majeur de Decade : les efforts sont donnés comme **torseur au centre de la liaison, dans sa base locale**, avec en plus le torseur cinématique.
- **`graphe/`** reprend `graph.py` (μ, cycles) et ajoute le **calcul de mobilité et d'hyperstatisme** par l'approche cinématique : avec Ic le nombre d'inconnues cinématiques, Ec = 6μ le nombre d'équations et rc le rang du système, on a m = Ic − rc et h = Ec − rc. Ce calcul est faisable à chaque configuration avec numpy.
- **`moteur/cinematique.py`** fournit le mode cinématique qui manquait à Decade. Il peut s'appuyer sur `joint.drive` et `motion.plot` de SolidCraft comme référence croisée.
- **Retour dans la CAO** : `joint.drive` image par image, ou `motion.study` (keys) puis `motion.export_animation` en GIF, et `motion.trace.keep` pour les trajectoires.

> **Mise à jour du 23 octobre 2026 : chaîne SolidCraft → Exudyn validée** ([prototypes/sonde_solidcraft/RESULTATS.md](../prototypes/sonde_solidcraft/RESULTATS.md)).
> - L'inertie n'est pas donnée par l'API, mais elle est exacte dans l'export URDF.
> - Les liaisons et leurs repères (origine et axe z, en repère local) se lisent dans l'export JSON.
> - Une bielle-manivelle modélisée dans SolidCraft donne, sans ressaisie, les mêmes torseurs que le modèle saisi à la main (écart de 0,5 % au plus avec la référence).
> - Le risque 1 ci-dessous est levé.

### 8.4 Risques identifiés

1. **Matrice d'inertie** : il faut confirmer qu'elle est accessible par l'API de SolidCraft. Sinon, la lire dans l'export URDF (`<inertial>`), qui la fournit par lien.
2. **Repère des réactions dans Exudyn** : à confirmer par un test avant toute conception de l'interface.
3. **Stabilité de l'API SolidCraft** : le projet en est à la version 0.15 et se dit « early ». Il faut isoler l'adaptateur et figer une version.
4. **Liaisons à contact** (ponctuelle, linéique) avec perte de contact : les modéliser comme des liaisons bilatérales (contact permanent, comme Decade), sans gérer le décollement dans un premier temps.

---

## 9. Suites proposées

1. **Prototype de validation du moteur**, avant tout cadrage : une bielle-manivelle modélisée à la main dans Exudyn, avec la vérification des 11 liaisons par `GenericJoint` et du repère des réactions.
2. **Sonde de l'API SolidCraft** : vérifier ce que `occurrence.properties`, `joint.list` et l'export `json` renvoient réellement (inertie, repères des liaisons).
3. Puis **cadrage** de Meca3D avec la méthode dev-1-cadrage, en reprenant comme exigences les points « garder » et « corriger » du § 7.

*Matériel de référence : `decade_archive/extract_14/app/doc/` (tutoriel, fiches méthode) et `app/samples/` (22 maquettes), réutilisables comme cas tests sous réserve de les reconstruire dans SolidCraft. Les formats CATProduct et SLDASM ne s'y ouvrent pas directement.*
