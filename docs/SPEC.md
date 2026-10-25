# SPEC — Meca3D v1

*Rédigée le 24 octobre 2026. Sources : [analyse_decade.md](analyse_decade.md), [prototypes/exudyn_bielle/RESULTATS.md](../prototypes/exudyn_bielle/RESULTATS.md), [prototypes/sonde_solidcraft/RESULTATS.md](../prototypes/sonde_solidcraft/RESULTATS.md).*

## 1. Objectif et utilisateurs

**Objectif.** Faire passer l'élève d'une maquette 3D SolidCraft à une étude de mécanique des solides indéformables : choix des liaisons normalisées, graphe des liaisons, mobilité et hyperstatisme, lois d'entrée, simulation cinématique ou dynamique, torseurs de liaison. La démarche reprend celle de Decade (T. Paviot) : **l'élève modélise, le logiciel ne devine pas les liaisons**.

**Utilisateurs.**
- Élèves ingénieurs de Polytech Nancy, en TP encadré et chez eux (installation libre sur leur PC Windows).
- Enseignants : préparation des maquettes, démonstrations, corrigés.

**Contexte d'usage.** SolidCraft (application de bureau) est lancé avec la maquette ouverte. Meca3D, lancé à côté, s'y connecte, lit le mécanisme, puis renvoie le mouvement simulé dans la maquette.

**Vocabulaire.** Classe d'équivalence = occurrence SolidCraft (sous-assemblage rigide). Liaison SolidCraft = joint. Liaison Meca3D = liaison normalisée (NF EN ISO 3952). Liaison pilote = liaison dont le mouvement est imposé par une loi d'entrée.

## 2. Hors périmètre

En V1, Meca3D ne fait pas :
- **Mode autonome** : la saisie d'un mécanisme sans SolidCraft est prévue en V2.
- **Contact unilatéral** : pas de décollement ni de choc. Toutes les liaisons sont bilatérales, parfaites ou avec le frottement de Coulomb d'EX-15.
- **Frottement visqueux dans les liaisons, résistance au roulement, lubrification** : non traités. Seuls le frottement de Coulomb (EX-15) et les rendements de couplage (EX-16) sont modélisés.
- **Solides déformables** : pas de jeu ni de flexibilité.
- **Liaisons détectées automatiquement** : seule une *proposition* est faite à partir du type SolidCraft, et l'élève la valide toujours.
- **Autres CAO** : ni CATIA ni SolidWorks, et aucune autre version de SolidCraft que celle déclarée supportée (EX-03).
- **Plateformes** : ni macOS, ni Linux, ni navigateur. Le code reste portable, mais seul Windows est livré et testé.
- **Calcul inverse** : pas d'optimisation ni de dimensionnement automatique.
- **Post-traitement avancé** : ni DSP ni FFT. Seuls min, max et moyenne sont fournis.
- **Langue** : l'interface est uniquement en français.
- **Modification de la géométrie SolidCraft** : Meca3D ne fait que lire et animer. Il n'écrit dans la maquette que les trajectoires (EX-52).

## 3. Exigences

Conventions de toutes les exigences : unités SI en interne (m, kg, s, rad, N, N·m). Les longueurs saisies ou affichées peuvent être en mm et les angles en degrés, avec l'unité toujours indiquée. Tolérances relatives rapportées au maximum de la grandeur de référence sur l'intervalle étudié.

### 3.1 Liaison avec SolidCraft

- **EX-01 Connexion.** Meca3D se connecte au canal de contrôle de SolidCraft (TCP 127.0.0.1, lignes JSON, jeton lu dans `%LOCALAPPDATA%\SolidCraft\control\<port>.token`). Le port est lu dans `control\current.port` ou saisi.
  - *Acceptation* : SolidCraft lancé avec `--control 7878` → connexion établie et `document.inspect` répond `ok: true` en moins de 1 s.
  - *Acceptation* : SolidCraft absent → message « SolidCraft n'est pas lancé ou n'accepte pas les connexions (port N) » en moins de 3 s, sans plantage.
- **EX-02 Jeton invalide ou refus.** Une réponse `unauthorized`, `busy`, `timeout` ou une fermeture de connexion est traduite en message explicite, et l'étude en cours n'est pas perdue.
  - *Acceptation* : un faux serveur qui répond `unauthorized` → message « jeton refusé » et état « déconnecté ».
- **EX-03 Version supportée.** Meca3D déclare le format SolidCraft qu'il supporte, `solidcraft/26` (SolidCraft 0.15.0), et lit le champ `format` de l'export JSON.
  - *Acceptation* : format différent → avertissement non bloquant, qui nomme le format attendu et le format reçu.
- **EX-04 Lecture du mécanisme.** Depuis la maquette ouverte, Meca3D lit les données suivantes, et les solides fixes sont identifiés :
  - occurrences : nom, statut fixe et pose ;
  - liaisons : nom, type, occurrences a et b, origine et axe z en repère monde ;
  - couplages de mouvement ;
  - pour chaque occurrence mobile : masse, centre de gravité et matrice d'inertie au centre de gravité, en repère monde.

  L'inertie provient de l'export URDF (`file.export`) écrit dans un dossier temporaire de Meca3D.

  Une classe d'équivalence est une occurrence de premier niveau de la maquette. Les sous-occurrences en font partie rigidement. Une liaison qui vise une sous-occurrence est signalée et n'est pas importée. Ce comportement est à vérifier au lot 1 (Q6).
  - *Acceptation (sous-occurrence)* : liaison sur une sous-occurrence (faux serveur) → message nommant la liaison, et import des autres liaisons.
  - *Acceptation* : bielle-manivelle de référence (fixture) → masses et I_zz identiques à 10⁻⁹ près aux valeurs du prototype (manivelle I_zz = 2,704·10⁻⁴ kg·m², bielle I_zz = 7,0512·10⁻³ kg·m²), et 4 liaisons lues.
- **EX-05 Configuration de référence.** Le modèle est construit dans la pose courante de la maquette au moment de l'import. Cette pose est mémorisée dans l'étude.
  - *Acceptation* : import à θ = 60° puis simulation à partir de θ₀ = 60° → x_B(0) = 0,3372281 m à 10⁻⁶ près.
- **EX-06 Maquette modifiée.** Meca3D mémorise le numéro `revision` de `document.inspect` lors de l'import. Si la révision change, un bandeau propose de réimporter, et les choix de l'élève sont conservés pour les liaisons de même nom.
  - *Acceptation* : révision changée (faux serveur) → bandeau affiché ; après réimport, les types de liaison choisis sont conservés.

### 3.2 Modèle cinématique

- **EX-10 Catalogue de liaisons.** Les 11 liaisons normalisées sont définies par leurs ddl bloqués, dans la base de liaison (axe = x local, normale = z local) :

  | Liaison | ddl bloqués [Tx Ty Tz Rx Ry Rz] |
  |---|---|
  | encastrement | [1 1 1 1 1 1] |
  | pivot | [1 1 1 0 1 1] |
  | glissière | [0 1 1 1 1 1] |
  | pivot glissant | [0 1 1 0 1 1] |
  | rotule à doigt | [1 1 1 0 0 1] |
  | rotule | [1 1 1 0 0 0] |
  | appui plan | [0 0 1 1 1 0] |
  | linéaire annulaire | [0 1 1 0 0 0] |
  | linéaire rectiligne | [0 0 1 0 1 0] |
  | ponctuelle | [0 0 1 0 0 0] |
  | hélicoïdale | [0 1 1 0 1 1], plus le couplage Tx = p·Rx / 2π |

  - *Acceptation* : pour chaque liaison, essai en grands déplacements (rotation de 0,3 rad au moins) → invariants géométriques respectés à 10⁻⁹ près et efforts nuls sur les ddl libres. La linéaire rectiligne est réalisée par deux ponctuelles (cf. prototype).
- **EX-11 Proposition puis choix.** Chaque liaison SolidCraft reçoit une proposition :

  | SolidCraft | Proposition |
  |---|---|
  | revolute | pivot |
  | slider | glissière |
  | cylindrical | pivot glissant |
  | planar | appui plan |
  | ball | rotule |
  | rigid | encastrement |
  | cylindrical couplé par `joint.screw` | hélicoïdale |
  | pin_slot | aucune proposition, choix imposé |

  L'élève peut choisir n'importe laquelle des 11 liaisons. Chaque liaison se valide une par une, et aucune simulation n'est possible tant qu'une liaison n'est pas validée.

  Un réglage de l'étude, « validation en bloc », accessible par le menu Enseignant, ajoute un bouton « Valider toutes les propositions » (avec confirmation). Il est désactivé par défaut. Il s'agit d'un choix d'ergonomie, pas d'une protection : il n'y a pas de mot de passe.
  - *Acceptation* : le statut « proposée / validée » est visible, et le bouton Simuler est inactif tant qu'une liaison n'est pas validée.
  - *Acceptation* : validation en bloc désactivée → bouton absent ; activée → toutes les liaisons passent à « validée » après confirmation.
- **EX-12 Base de liaison.** L'axe z de la liaison SolidCraft devient l'axe de la liaison (x local) pour pivot, glissière, pivot glissant, linéaire annulaire et hélicoïdale, et la normale (z local) pour appui plan et ponctuelle. Pour la rotule à doigt et la linéaire rectiligne, l'élève saisit une seconde direction (vecteur en repère monde), projetée orthogonalement à z.
  - *Acceptation* : direction colinéaire à z (angle < 1°) → refus avec message.
  - *Acceptation* : direction (1, 1, 0) pour z = (0, 0, 1) → base orthonormée directe à 10⁻¹² près.
- **EX-13 Changement d'orientation.** L'élève peut basculer l'axe d'une liaison vers l'un des axes x, y ou z du repère monde, ou vers un vecteur saisi, et son centre vers un point saisi. C'est nécessaire quand l'axe issu de SolidCraft ne convient pas : par exemple, une linéaire annulaire tirée d'une rotule.
  - *Acceptation* : linéaire annulaire en B réorientée selon z → la bielle-manivelle devient isostatique (cf. EX-21).
- **EX-14 Couplages.** Trois couplages entre deux liaisons :
  - engrenage : ω₂ = −k·ω₁ pour un engrenage extérieur, +k pour un engrenage intérieur ;
  - pignon-crémaillère : v = r·ω ;
  - vis-écrou : v = p·ω / 2π.

  Ils sont lus dans SolidCraft quand ils y sont définis, ou saisis dans Meca3D.
  - *Acceptation (réducteur)* : Z₁ = 20, Z₂ = 60, ω_e = 30 rad/s → ω_s = 10 rad/s à 10⁻⁶ près ; en régime établi sans perte, Ce = 1 N·m → Cs = 3 N·m à 10⁻³ près.
  - *Acceptation (vis-écrou)* : p = 5 mm, ω = 10 rad/s → v = 7,9577 mm/s ; couple moteur 2 N·m en équilibre → effort axial 2 513,27 N à 10⁻³ près.
- **EX-15 Frottement de Coulomb.** Coefficient f réglable par liaison (0 par défaut, liaison parfaite).
  - Pour une glissière ou un appui plan, l'effort tangent vaut f·|N| et s'oppose à la vitesse de glissement.
  - Pour un pivot, le couple résistant vaut f·r·|R_radiale|, avec r le rayon de l'axe saisi par l'élève.
  - Une loi régularisée près de la vitesse nulle (vitesse de régularisation v_ε réglable) est admise ; l'écart qu'elle introduit est signalé dans les résultats.
  - *Acceptation (glissement)* : bloc de 1 kg sur glissière inclinée de 30°, f = 0,2, départ au repos → accélération 3,20586 m/s² à 10⁻² près en relatif, soit x(1 s) = 1,60293 m.
  - *Acceptation (adhérence)* : même cas avec f = 0,7 > tan 30° = 0,577 → déplacement sur 1 s inférieur à 10⁻³ m.
  - *Acceptation (pivot)* : disque d'acier R = 0,1 m, e = 0,02 m, à axe horizontal (CdG sur l'axe), r = 5 mm, f = 0,1, ω₀ = 10 rad/s → arrêt à t = ω₀·R² / (2·f·r·g) = 10,194 s à 2 % près.
- **EX-16 Rendement des couplages.** Un rendement η ∈ ]0 ; 1] est réglable par couplage (1 par défaut). La puissance transmise de l'entrée vers la sortie vaut P_s = η·P_e ; dans le sens inverse, P_e = η·P_s. Le sens est déterminé à chaque instant par le signe de la puissance.
  - *Acceptation* : réducteur Z₁ = 20, Z₂ = 60, η = 0,95, Ce = 1 N·m en régime établi → Cs = 2,85 N·m à 10⁻³ près.
  - *Acceptation* : inversion du sens de la puissance → le rendement est appliqué dans le bon sens (cas test à deux phases, moteur puis frein).

### 3.3 Graphe, mobilité, hyperstatisme

- **EX-20 Graphe des liaisons.** Le graphe montre les solides (nœuds), les liaisons (arêtes nommées par leur type) et le bâti identifié. Meca3D calcule μ = L − S + 1 (par composante connexe) et les cycles indépendants, et met en évidence un cycle choisi.
  - *Acceptation* : bielle-manivelle (S = 4, L = 4) → μ = 1, et un cycle de 4 liaisons.
  - *Acceptation* : pendule double → μ = 0.
  - *Acceptation* : solide sans liaison → signalé comme isolé.
- **EX-21 Mobilité et hyperstatisme.** Le calcul se fait par la méthode cinématique : Ic inconnues cinématiques, Ec = 6μ, rc rang du système (SVD, tolérance relative 10⁻⁹), m = Ic − rc, h = Ec − rc. Chaque couplage (EX-14) ajoute une équation : Ec = 6μ + nombre de couplages. Il est effectué dans la configuration courante et mis à jour à chaque changement de liaison.

  | Cas | Ic | rc | m | h |
  |---|---|---|---|---|
  | bielle-manivelle, pivot / pivot / rotule / glissière | 6 | 5 | 1 | 1 |
  | linéaire annulaire d'axe z en B | 7 | 6 | 1 | 0 |
  | linéaire annulaire d'axe x en B | 7 | 5 | 2 | 1 |
  | trois pivots et une glissière | 4 | 3 | 1 | 3 |
  | pendule double | 2 | 0 | 2 | 0 |

  Valeurs vérifiées par calcul le 24 octobre 2026. *Acceptation* : chacun de ces cas → Ic, rc, m et h exactement comme indiqué.
- **EX-22 Garde-fou avant simulation.**
  - h > 0 : la simulation est refusée. Le message indique h et les liaisons du ou des cycles concernés, et propose de revoir les choix de liaison.
  - Nombre de lois d'entrée différent de m : la simulation cinématique est refusée avec un message, et la simulation dynamique avertit.
  - *Acceptation* : le cas h = 1 ci-dessus → refus, et aucun appel au moteur.
- **EX-23 Option « Hyperstatique autorisé ».** Une case à cocher de l'étude, décochée par défaut, autorise le **mode cinématique** pour h > 0.
  - Meca3D retire alors h équations redondantes (choix automatique par la décomposition en rang) et affiche quels ddl ont été libérés.
  - Le mouvement obtenu est celui du mécanisme réel, si ses dimensions sont compatibles.
  - Le mode dynamique reste refusé pour h > 0, car les efforts de liaison sont indéterminés : le message le rappelle.
  - *Acceptation* : trois pivots et une glissière (h = 3), option cochée, ω = 20 rad/s → x_B(t) identique au cas isostatique à 10⁻⁶ m près, et 3 ddl libérés listés.
  - *Acceptation* : option cochée, mode dynamique → refus avec message.

### 3.4 Données d'entrée

- **EX-30 Lois d'entrée.** Une loi d'entrée porte sur une liaison pilote (pivot : angle ; glissière : position ; pivot glissant : l'un ou l'autre ; hélicoïdale : angle). C'est une expression de t ; les dérivées première et seconde sont obtenues par dérivation symbolique. Fonctions admises : `+ − * / **`, `sin`, `cos`, `tan`, `exp`, `log`, `sqrt`, `abs`, `pi`, `Piecewise` / `min` / `max`, et constantes nommées de l'étude. Tout autre nom est refusé.
  - *Acceptation* : `20*t` → valeur, vitesse et accélération à t = 0,5 s égales à 10, 20 et 0.
  - *Acceptation* : `__import__('os')` → refus.
  - *Acceptation* : l'expression vide → refus.
- **EX-31 Pesanteur.** Vecteur g réglable, par défaut (0, 0, −9,81) m/s² (z vers le haut, comme SolidCraft). Il peut être désactivé.
  - *Acceptation* : g désactivé, pendule lâché → aucun mouvement (angle constant à 10⁻⁹ près).
- **EX-32 Actions extérieures.** Une force ou un couple, constant ou fonction de t (même grammaire qu'EX-30), est appliqué en un point d'un solide. Il est exprimé en repère monde ou en repère du solide.
  - *Acceptation* : vis-écrou, couple 2 N·m sur la vis et effort résistant sur l'écrou → équilibre conforme à EX-14.
- **EX-33 Ressorts-amortisseurs.** Un ressort-amortisseur linéaire est défini entre deux points de deux solides : raideur k, longueur libre l₀, amortissement c.
  - *Acceptation* : masse de 1 kg sur glissière verticale, k = 1 000 N/m, c = 0 → période 2π·√(m/k) = 0,19869 s à 10⁻³ près.

### 3.5 Simulation

- **EX-40 Mode dynamique.** Le mode dynamique utilise Exudyn 1.13.6 (`GenericJoint`) avec l'intégrateur generalized-α (ρ∞ = 0,9), à pas fixe réglable (durée, nombre de pas).
  - *Acceptation* : bielle-manivelle de référence (r = 0,10 m, L = 0,30 m, piston de 0,5 kg, mouvement dans le plan XY, pesanteur g = (0, −9,81, 0) m/s² comme dans le prototype, montée en vitesse sur 0,2 s puis ω = 20 rad/s, 1 s, 4 000 pas) → écart relatif ≤ 5·10⁻³ sur les torseurs en O, A, B, le couple moteur et la normale du piston, par rapport à la solution Newton-Euler du prototype.
- **EX-41 Mode cinématique.** Le mouvement est imposé sur m liaisons pilotes. Meca3D calcule les positions, vitesses et accélérations de tous les solides sans afficher d'effort.
  - *Acceptation* : bielle-manivelle à ω constant = 20 rad/s → x_B(t) conforme à la formule analytique à 10⁻⁶ m près.
  - *Acceptation* : l'accélération du piston est conforme à la dérivée seconde analytique à 10⁻³ près, et elle est calculée directement, pas par différence finie.
- **EX-42 Calcul hors du fil de l'interface.** La simulation tourne hors du fil IHM. Elle affiche sa progression et peut être annulée.
  - *Acceptation* : annulation → retour à l'état prêt en moins de 1 s, sans résultat partiel présenté comme complet.
- **EX-43 Échec du solveur.** Un Jacobien singulier ou une non-convergence est traduit en message pédagogique, qui rappelle l'hyperstatisme et les configurations singulières (point mort) et donne l'instant de l'échec.
  - *Acceptation* : modèle hyperstatique transmis au moteur en contournant le garde-fou (test unitaire) → message avec t de l'échec, sans plantage.
- **EX-44 Performance.**
  - *Acceptation* : bielle-manivelle de référence (1 s, 4 000 pas) → moins de 10 s de calcul sur un PC de TP (base : 2,6 s pour le prototype complet, référence comprise, sur le PC portable Polytech le 24 octobre 2026).

### 3.6 Résultats

- **EX-50 Torseurs de liaison.** Pour chaque liaison, Meca3D donne le torseur statique {i→j}, au choix de l'élève (i→j ou j→i), réduit au centre de la liaison et exprimé dans la base de liaison ou en base monde, ainsi que le torseur cinématique {V j/i}. Les composantes nulles par construction sont affichées comme nulles.
  - *Acceptation* : pivot L01 de la bielle-manivelle → R(0→1) conforme à la référence (EX-40) ; composante de moment sur l'axe libre < 10⁻⁹ N·m (hors pilote).
- **EX-51 Capteurs de point.** Position, vitesse et accélération d'un point d'un solide, relativement à un solide de référence quelconque, exprimées dans la base du solide de référence ou en base monde.
  - *Acceptation* : point B du piston par rapport au bâti → conforme à EX-41.
  - *Acceptation* : point A de la bielle par rapport à la manivelle → vitesse nulle à 10⁻⁹ près.
- **EX-52 Courbes, CSV, trajectoires.**
  - Courbes : toute grandeur de capteur en fonction de t ou d'une autre grandeur.
  - Valeurs extrêmes : min, max et moyenne affichés.
  - Export CSV : séparateur `;`, décimale `,`, UTF-8 avec BOM, en-têtes avec unités.
  - Trajectoire d'un point : retracée dans SolidCraft.
  - *Acceptation* : le CSV de la bielle relu par Excel en français montre les colonnes `t (s)` et `C (N·m)`, avec 501 lignes pour une période d'échantillonnage de 2 ms sur 1 s.
- **EX-53 Animation dans SolidCraft.** Le mouvement simulé est rejoué dans la maquette (lecture, pause, vitesse ×0,1 à ×2, curseur temporel), à 20 images/s au moins.
  - *Acceptation* : bielle-manivelle → la pose SolidCraft à t = 0,5 s correspond à θ simulé à 0,1° près (relu par `joint.list`).
  - *Acceptation* : cadence mesurée ≥ 20 images/s.
  - *Acceptation* : en fin d'animation ou à l'interruption, la pose initiale de la maquette est restaurée (valeurs de `joint.list` identiques à 10⁻⁹ près), et Meca3D n'enregistre jamais la maquette.

### 3.7 Étude, interface, distribution

- **EX-60 Fichier d'étude.** Une étude `.meca3d` (JSON, UTF-8) contient :
  - le chemin de la maquette et la révision importée ;
  - les choix de liaisons, les couplages ;
  - les lois, les actions et les ressorts ;
  - les capteurs et les réglages de simulation.

  Elle ne contient pas les résultats, qui sont recalculés.
  - *Acceptation* : enregistrer, rouvrir, simuler → résultats identiques bit à bit.
  - *Acceptation* : fichier corrompu → message, aucune étude partielle.
- **EX-61 Arbre de l'étude.** La fenêtre principale suit la démarche de Decade avec un arbre en trois branches :
  - Modèle cinématique : solides, liaisons, graphe ;
  - Données d'entrée : pilotes, pesanteur, actions, ressorts ;
  - Résultats : capteurs, courbes, animation.

  Chaque élément incomplet est signalé.
  - *Acceptation* : test pytest-qt → les trois branches sont présentes, et une liaison non validée est marquée.
- **EX-62 Ligne de commande.** `meca3d simuler <etude.meca3d> --csv <sortie.csv>` exécute une étude sans interface, à partir des données mémorisées, sans SolidCraft. Il sert aux tests et aux corrigés.
  - *Acceptation* : étude bielle de la fixture → CSV produit, code de retour 0 ; h > 0 → code de retour 2 et message.
- **EX-63 Distribution.** Exécutable Windows (PyInstaller, mode dossier) construit par GitHub Actions (windows-latest) et publié dans les Releases à chaque étiquette `v*`. Il s'utilise sans Python installé. SolidCraft 0.15.0 s'installe séparément.
  - *Acceptation* : sur un runner propre, `meca3d.exe simuler` sur l'étude bielle → CSV identique à celui du mode source à 10⁻¹² près.
- **EX-64 Licence.** Le code est publié sous GPL v3 (fichier LICENSE, en-tête SPDX dans chaque module) et les dépendances sont compatibles.
  - *Acceptation* : `pip-licenses`, ou équivalent, ne liste aucune dépendance incompatible avec la GPL v3.

## 4. Données

- **Entrée SolidCraft** (canal de contrôle, vérifié le 24 octobre 2026 sur SolidCraft 0.15.0) :
  - `joint.list` : liaisons avec `frame_a` / `frame_b` (origine en mm et axe z en repère monde à la pose courante), `type`, `a`, `b`, `values` (en deg), `dof`, `conflicts` ;
  - `component.list` : occurrences, `grounded`, `transform` (4×4 stockée par colonnes, mm) ;
  - `component.properties` : masse (g) et CdG (mm, repère monde), **sans inertie** ;
  - `file.export` au format `urdf` : inertie (kg·m², au CdG, en repère du lien URDF, à recomposer). La liaison qui ferme une boucle est omise : l'URDF ne sert qu'aux inerties. L'export écrit dans tout dossier existant ; le serveur MCP impose une limite de dossiers, mais pas le canal de contrôle ;
  - `file.export` au format `json` : champ `format` (`solidcraft/26`), couplages.
- **Fixtures** (`tests/fixtures/`) :
  - exports réels de la bielle-manivelle : `bielle_export.json`, `bielle.urdf`, STL, et les réponses `joint.list` / `component.list` / `component.properties` enregistrées ;
  - études `.meca3d` de référence ;
  - plus tard, les maquettes du pendule simple, du pendule double, du réducteur et du système vis-écrou.
- **Pièges connus** :
  - unités : mm et g côté SolidCraft, deg dans l'API, rad dans le JSON ;
  - matrices stockées par colonnes ;
  - axe z de SolidCraft à faire correspondre à l'axe x de la liaison ;
  - `flip` des liaisons ;
  - pose de l'URDF à recomposer le long de l'arbre.
- **Volumes** : 2 à 20 solides et 1 à 30 liaisons par mécanisme. Simulations de 10³ à 10⁵ pas.

## 5. Interfaces

- **Fenêtre principale** (PyQt6) :
  - à gauche, l'arbre de l'étude (EX-61) ;
  - au centre, des onglets : graphe des liaisons (EX-20), courbes (EX-52), tableau des torseurs (EX-50) ;
  - à droite, les propriétés de l'élément sélectionné ;
  - une barre d'état : connexion SolidCraft, m, h.
- **Commandes** :
  - Connecter et Importer ;
  - Valider toutes les propositions, avec confirmation, liaison par liaison possible ;
  - Simuler en dynamique ou en cinématique ;
  - Animer ;
  - Exporter en CSV ;
  - Enregistrer et Ouvrir une étude.
- **Ligne de commande** : `meca3d` (IHM) ; `meca3d simuler …` (EX-62).
- **Fichiers produits** : `.meca3d` (EX-60), `.csv` (EX-52), trajectoires dans la maquette SolidCraft (EX-52).

## 6. Contraintes

- **Plateforme** : Windows 11 x64, Python 3.12.
- **Gestion du projet** : uv et pyproject.toml.
- **Dépendances autorisées** : exudyn==1.13.6, numpy, networkx, sympy, PyQt6, matplotlib ; pytest, pytest-qt, ruff, pyright et PyInstaller en développement. Toute autre dépendance demande un accord.
- **SolidCraft** : 0.15.0 (format `solidcraft/26`), piloté par le canal de contrôle uniquement : pas de MCP et pas de COM.
- **Séparation des couches** : la logique métier (modèle, graphe, moteur) est indépendante de l'IHM et de SolidCraft, et elle est testable sans eux.
- **Licence** : GPL v3. Le code de Decade (GPL v2 ou ultérieure) peut servir d'inspiration ; aucun fichier n'en est copié tel quel.

## 7. Scénario de bout en bout

Test `tests/test_bout_en_bout.py`, sans SolidCraft. Il s'appuie sur un faux serveur de contrôle qui rejoue les réponses enregistrées de la bielle-manivelle :
1. connexion au faux serveur et import → 4 solides et 4 liaisons proposées (pivot, pivot, rotule, glissière) ;
2. calcul du graphe → μ = 1, m = 1, h = 1 ; la simulation est refusée (EX-22) ;
3. L23 passe en linéaire annulaire, réorientée selon z → m = 1, h = 0 ;
4. loi d'entrée sur L01 (montée en vitesse puis 20 rad/s), pesanteur g = (0, −9,81, 0) ;
5. simulation dynamique sur 1 s et 4 000 pas → écart relatif ≤ 5·10⁻³ par rapport à la référence (EX-40) ;
6. export CSV (EX-52), enregistrement de l'étude, réouverture, nouvelle simulation → résultats identiques.

Un test du même scénario contre le vrai SolidCraft est marqué `@pytest.mark.solidcraft` et lancé à la main.

## 8. Questions ouvertes

- **Q1 Couplages, hélicoïdale, frottement et rendement dans Exudyn.** Ni engrenage ni vis-écrou n'y existent tout faits.
  - Couplages et hélicoïdale : la solution envisagée est une contrainte utilisateur `ObjectConnectorCoordinateVector`.
  - Frottement de Coulomb : il faudrait un effort fonction de la réaction de liaison, ce qui fait une boucle implicite. Une formulation explicite (réaction du pas précédent) ou une boucle implicite est à évaluer.
  - Rendement : il change selon le sens de la puissance.

  Ces quatre points sont à valider au lot 1. En cas d'échec, les exigences concernées (EX-14, EX-15, EX-16) passent en V2 : c'est une décision à reprendre avec l'utilisateur.
- **Q2 Lecture des couplages SolidCraft.** Il reste à vérifier sous quelle forme `joint.list` ou l'export JSON décrivent `joint.gear`, `joint.rack_pinion` et `joint.screw` (lot 1).
- **Q3 Animation.** Il faut choisir entre `joint.drive` sur les m liaisons pilotes (SolidCraft résout les boucles) et `occurrence.move` avec les poses Exudyn, en fonction de la cadence et de la fidélité (lot 1).
- **Q4 Trajectoires.** Il reste à préciser les paramètres de `motion.trace.keep`, qui suppose peut-être une étude de mouvement SolidCraft, ou à trouver une alternative (esquisse 3D) (lot 1).
- **Q5 Exécutable.** L'embarquement d'Exudyn et de PyQt6 par PyInstaller n'est pas vérifié (lot 1).
- **Q6 Sous-assemblages.** Il reste à vérifier ce que renvoient `component.list` et `joint.list` pour une maquette à sous-assemblages imbriqués et à occurrences multiples d'un même composant (lot 1).
