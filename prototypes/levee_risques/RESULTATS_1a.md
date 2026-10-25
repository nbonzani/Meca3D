# Lot 1a — Levée des risques du moteur Exudyn (Q1, D9)

Exudyn 1.13.6, generalized-α `spectralRadius = 0.9`, Windows. Toutes les valeurs ci-dessous sortent de l'exécution des scripts de ce dossier ; les sorties brutes sont dans `sortie_*.txt`.
Lancement : `uv run python prototypes/levee_risques/<script>.py` (`moteur_processus.py` accepte `a`, `b`, `bq`).
Briques communes : `commun.py` (couplage au niveau vitesse, lecture du multiplicateur de Lagrange, réglages).

## 1. Synthèse

| Risque | Formulation retenue | Obtenu / attendu | Verdict |
|---|---|---|---|
| EX-14 engrenage (Z₁ = 20, Z₂ = 60) | `ObjectConnectorCoordinateVector` au niveau vitesse, `constraintUserFunction` + `jacobianUserFunction`, sur les paramètres d'Euler des deux corps : g = ω₂ + k·ω₁ = 0 | rapport ω_s/ω_e exact à 1,5·10⁻¹³ ; ω_e imposé à 30 rad/s au niveau vitesse → ω_s = −10,000000000 (écart 7·10⁻¹⁵) ; Ce = 1 N·m → Cs = 3,000000 N·m (multiplicateur lu : 3,000000) | **Conforme avec réserve** (dérive angulaire, voir 2.1) |
| EX-14 vis-écrou / hélicoïdale (p = 5 mm) | pivot glissant [0,1,1,0,1,1] + même contrainte vitesse sur un seul corps : v_x − (p/2π)·ω_x = 0 | v = 7,957747 mm/s (écart relatif 0) ; équilibre à C = 2 N·m, F = 2 513,2741 N (a = 1,5·10⁻¹² m/s²) ; effort axial lu dans le multiplicateur = 2 513,2741 N (écart relatif 2·10⁻¹⁶) ; F×1,001 → α = −162 rad/s² (déséquilibre détecté) | **Conforme** |
| EX-15 Coulomb, glissement f = 0,2 | `ObjectConnectorRigidBodySpringDamper` + `springForceTorqueUserFunction` : F = f·\|N\|·tanh(v/v_ε), N lu dans `ForceLocal` de la liaison parfaite (configuration courante) | a = 3,20586 m/s² (écart relatif ≤ 5·10⁻⁹) ; x(1 s) = 1,60378 m (h = 1 ms, écart 5,3·10⁻⁴) contre 1,60293 | **Conforme** |
| EX-15 adhérence f = 0,7 | idem | x_max(1 s) = 1,2·10⁻⁴ m (h = 1 ms, v_ε = 10⁻⁴ m/s) ; critère < 10⁻³ m ; **échoue pour v_ε ≥ 10⁻³ m/s** (1,17·10⁻³ m) | **Conforme avec réserve** (v_ε ≤ 10⁻⁴ m/s imposé) |
| EX-15 pivot (disque) | idem, couple C = f·r·\|R_rad\|·tanh(ω/ω_ε) | arrêt (\|ω\| < 0,01 rad/s) à 10,186 s (h = 1 ms, ω_ε = 10⁻² rad/s) contre 10,194 s : écart 0,08 % (critère 2 %) | **Conforme** |
| EX-16 rendement | deux `LoadTorqueVector` à `loadVectorUserFunction` calculant le couple de perte à partir du multiplicateur λ et du signe de la puissance | η = 0,95, Ce = 1 N·m → Cs = 2,850000 N·m (écart 6·10⁻¹⁰) ; deux phases : couple d'entrée 1,05263 (moteur) puis 0,95000 N·m (frein), attendus 1,05263 et 0,95000 | **Conforme** |
| D9 / EX-42 processus séparé | `multiprocessing` spawn, file de progression, annulation | progression ≈ 20 messages/s ; annulation dure 0,007 s, douce 0,088 s (critère < 1 s) | **Conforme** |
| D9 thread (information) | `threading.Thread` / `QThread` | fil principal à 15,5 ms d'écart moyen avec fonctions Python ; **gelé** (1 tick en 6 s) sans fonction Python | **D9 confirmé** |

Aucun risque n'est en échec. Deux réserves portent sur le choix des réglages (v_ε, mode de pilotage) et une sur la dérive angulaire des couplages.

## 2. Détail par risque

### 2.1 EX-14 — Engrenage (`moteur_engrenage.py`)

**Formulation.** Les corps portent des nœuds `RigidBodyEP` (7 coordonnées : x, y, z, e₀…e₃). La vitesse angulaire locale vaut ω_loc = 2·G(e)·ė avec G 3×4 linéaire en e. La contrainte vitesse g = coef_a·s_a + coef_b·s_b (s = vitesses de translation et de rotation locale) est linéaire en ė, avec la ligne de jacobien ∂g/∂ė = 2·aᵀG(e). Deux marqueurs `MarkerNodeCoordinates`, `velocityLevel=True`, `scalingMarker0/1 = zeros((1, 7))` (fixe nAE = 1). Code : `commun.couplage_vitesse`.

**API vérifiée par essai** (non documentée dans l'aide installée) :
- `constraintUserFunction(mbs, t, itemNumber, q, q_t, velocityLevel)` avec q et q_t de longueur 14 (les deux marqueurs concaténés), renvoie un tableau de nAE valeurs ;
- `jacobianUserFunction(mbs, t, itemNumber, q, q_t, velocityLevel)` renvoie la matrice nAE×14 = ∂g/∂q_t quand `velocityLevel=True`. C'est la seule matrice demandée : la solution converge avec elle seule (le terme ∂g/∂q n'est pas nécessaire) ;
- le multiplicateur est lu par `mbs.systemData.GetAECoordinates()[mbs.systemData.GetObjectLTGAE(obj)[0]]` ; pour g = ω₂ + k·ω₁, le couple exercé par la contrainte vaut −λ sur la sortie et −k·λ sur l'entrée.

**Résultats.**

| Essai | Obtenu | Attendu |
|---|---|---|
| ω_e imposé par pivot motorisé (`offsetUserFunction`, position), h = 1 ms | ω_e = 30,000567, ω_s = −10,000189 ; \|ω_s\| − 10 = 1,9·10⁻⁴ ; **ω_s + k·ω_e = 1,5·10⁻¹³** | 10⁻⁶ sur ω_s |
| idem, h = 2 ms / 0,5 ms | \|ω_s\| − 10 = 7,6·10⁻⁴ / 4,7·10⁻⁵ (∝ h²) | |
| ω_e imposé au niveau vitesse (contrainte g₂ = ω₁ − ω(t), `terme_t`) | ω_s = −10,000000000 ; écart 7·10⁻¹⁵ | 10⁻⁶ |
| Ce = 1 N·m, charge visqueuse 0,3 N·m·s/rad, régime établi | ω_e = 30,0000, ω_s = −10,0000 rad/s ; Cs = 3,000000 N·m ; λ = 3,000000 ; accélération 6·10⁻⁶ rad/s² | 3 N·m à 10⁻³ |
| Réaction du pivot de sortie | 0 N | — |

**Lecture de ces résultats.**
- L'écart de 1,9·10⁻⁴ rad/s sur ω_s avec le pilotage en position n'est pas dû au couplage : c'est la vitesse de la manivelle motorisée par la loi θ(t) qui s'écarte de ω_e (erreur de schéma en h²). Le rapport entre ω_s et ω_e reste exact. Le critère « ω_s = 10 à 10⁻⁶ » n'est tenu au sens strict que si l'entrée est pilotée au niveau vitesse, ou s'il est formulé sur le rapport ω_s/ω_e. À signaler dans la SPEC.
- Signe : engrenage extérieur → ω_s = −10 rad/s (la SPEC dit « 10 rad/s » : valeur absolue).
- **Dérive angulaire** : φ₂ + k·φ₁ s'écarte de 0 à cause de l'intégration des paramètres d'Euler par le schéma (la contrainte vitesse n'est pas stabilisée au niveau position) : −1,4·10⁻⁴ rad à 1 s, −8,2·10⁻⁴ rad à 5 s, −3,3·10⁻³ rad (0,19°) à 20 s pour h = 1 ms ; ∝ h² (−3,6·10⁻⁵ rad à 1 s pour h = 0,5 ms). Négligeable pour un outil pédagogique (le déphasage des dents n'est pas modélisé).
- **Effort de contact denture** : le multiplicateur λ est exploitable comme **couple transmis** (Cs lu exactement) et donc comme effort tangentiel au cercle primitif F_t = Cs/R₂. Il ne donne **pas** l'effort total de denture : aucune poussée radiale n'apparaît (réaction de pivot nulle). La composante radiale F_t·tan α n'est pas modélisée (contrainte idéale) ; à calculer en post-traitement avec l'angle de pression si on la veut.
- Limite structurelle : `ObjectConnectorCoordinateVector` n'a que deux marqueurs, donc un couplage porte sur **au plus deux corps** (bâti compris, un seul corps pour la vis-écrou). Un train planétaire (porte-satellites mobile, trois corps) n'est pas couvert : non testé, hors périmètre de la V1 si le couplage est toujours entre deux liaisons dont l'une est avec le bâti. Pour deux liaisons entre corps mobiles, les coefficients dépendent de l'orientation : non testé.

**Formulation recommandée (lot 7).** `couplages.py` : une fonction qui, pour un couplage {liaison i → liaison j, rapport k, signe}, ajoute la contrainte vitesse avec des coefficients locaux calculés à partir de l'axe de chaque liaison (repère local du corps, axe fixe dans le corps puisque la liaison est avec le bâti). Le couple de contact se lit par le multiplicateur. Réglages : mêmes que le reste (ρ∞ = 0,9, h = 1 ms). Prévoir un message « dérive angulaire » inutile en V1.

### 2.2 EX-14 — Hélicoïdale et vis-écrou (`moteur_helicoidale.py`)

Pivot glissant [0,1,1,0,1,1] (axe x) + `couplage_vitesse` à un seul corps (les deux marqueurs sont sur le même nœud) avec les coefficients [1,0,0, −p/2π,0,0] ; l'écrou est le bâti.

| Essai | Obtenu | Attendu |
|---|---|---|
| ω = 10 rad/s imposé (contrainte vitesse) | v = 7,957747 mm/s ; x(1 s) = 7,161972 mm (écart relatif 6·10⁻¹⁵) | 7,9577 mm/s |
| C = 2 N·m, F₀ = 2 513,2741 N, départ au repos | x_max = 7,6·10⁻¹³ m ; \|α\| = 1,9·10⁻⁹ rad/s² ; effort axial lu dans le couplage = 2 513,2741 N (écart relatif 1,8·10⁻¹⁶) | 2 513,27 N à 10⁻³ |
| sensibilité : F₀×1,001 / ×0,999 | α = −161,9 / +160,4 rad/s² | non nul (le test discrimine à 10⁻³) |
| ω imposé, mêmes charges : multiplicateur de pilotage | −2·10⁻⁶ N·m (nul à l'équilibre) ; avec F₀×1,001 : −0,0020 N·m (= 2·10⁻³ attendu) | |

L'hélicoïdale entre deux corps mobiles n'est pas testée (voir limite 2.1) ; le pignon-crémaillère (v = r·ω) relève de la même contrainte à un coefficient près : non exécuté séparément.

### 2.3 EX-15 — Frottement de Coulomb (`moteur_coulomb.py`)

**Formulation.** Un `ObjectConnectorRigidBodySpringDamper` relie le bâti et le corps ; les deux marqueurs `MarkerBodyRigid` portent le repère de la liaison (axe = x) par `localHT=exu.HT(rotation=A, ...)`. La `springForceTorqueUserFunction(mbs, t, itemNumber, u, rot, v, w, k, d, rotJ0, rotJ1, offset)` renvoie un 6-vecteur (force, couple) exprimé dans le repère du marqueur 0 ; la convention de signe est celle d'un ressort-amortisseur : elle renvoie **+f·|N|·tanh(v_x/v_ε)** (le connecteur applique l'opposé au corps 1). Nœud `NodeGenericData` obligatoire (`nodeNumber`). La réaction |N| est lue par `mbs.GetObjectOutput(liaison, ForceLocal)` : norme (F_y, F_z) pour une glissière d'axe x, norme radiale pour un pivot.

Deux lectures de la réaction :
- **`courant`** : lecture dans la configuration courante, donc la valeur de l'itération de Newton en cours : la boucle implicite est résolue par le point fixe de Newton. **Recommandée.**
- **`pas_prec`** : valeur lue dans un `PreStepUserFunction` (réaction du pas précédent) : explicite, retard d'un pas.

Le jacobien du connecteur est calculé par différences finies par Exudyn : renseigner `damping` à la pente d = f·N/v_ε est inutile (résultats identiques à 10⁻¹³ avec et sans, cas b′).

**Résultats (a), glissement f = 0,2** (attendu a = 3,20586 m/s², x(1 s) = 1,60293 m) :

| mode | h | v_ε (m/s) | a | écart relatif sur x(1 s) |
|---|---|---|---|---|
| courant, pas_prec | 10 ms | 10⁻² … 10⁻⁴ | 3,20586 (écart ≤ 10⁻⁸) | 5,3·10⁻³ |
| courant, pas_prec | 2 ms | 10⁻² / ≤ 10⁻³ | 3,20586 | 1,9·10⁻³ / 1,06·10⁻³ |
| courant, pas_prec | 1 ms | 10⁻² / ≤ 10⁻³ | 3,20586 | 1,8·10⁻³ / 5,3·10⁻⁴ |

L'écart sur x(1 s) vient du pas de temps (démarrage du schéma), pas de v_ε dès que v_ε ≤ 10⁻³ ; l'accélération est exacte. Critère 10⁻² : tenu partout, avec marge ≥ 2.

**Résultats (b), adhérence f = 0,7** (critère x_max < 10⁻³ m sur 1 s) : le bloc fluage à la vitesse v = v_ε·atanh(tan 30°/0,7) = 1,17·v_ε. Avec h = 1 ms : v_ε = 10⁻² → 1,2·10⁻² m (KO) ; 10⁻³ → 1,17·10⁻³ m (KO, limite) ; **10⁻⁴ → 1,2·10⁻⁴ m (OK)** ; 10⁻⁵ → 1,4·10⁻⁵ m (OK). À h = 2 ms : 1,3·10⁻⁴ m ; à h = 10 ms : 3,9·10⁻⁴ m (toujours OK). Accélération résiduelle ≤ 10⁻¹⁰ m/s² : l'état est stationnaire. Aucune instabilité ni chatter, même à v_ε = 10⁻⁵ m/s et h = 10 ms (le jacobien numérique suffit).

**Résultats (c), disque** (attendu t_arrêt = 10,194 s, 2 %) ; t_arrêt = premier instant avec |ω| < 0,01 rad/s :

| h | ω_ε = 0,1 rad/s | 10⁻² | 10⁻³ |
|---|---|---|---|
| 20 ms | 2,02 % | 0,45 % | 0,26 % |
| 5 ms | 1,68 % | 0,04 % | 0,04 % |
| 1 ms | 1,62 % | 0,08 % | 0,09 % |

(identiques pour `courant` et `pas_prec`). ω(5 s) vaut 5,0955 rad/s à h = 1 ms (linéaire attendu : 5,0950) ; l'écart de ω(5 s) croît en h² (5,1267 à 20 ms). Avec ω_ε = 0,1 rad/s la queue exponentielle de la loi régularisée repousse l'arrêt de 1,6 %, à la limite des 2 %.

**Cas (d), pendule** (réaction couplée au frottement : la réaction du pivot dépend du couple de frottement, donc la boucle est réellement implicite). Angle à 3 s, référence `courant` à h = 0,1 ms :

| mode | h = 10 ms | 5 ms | 1 ms |
|---|---|---|---|
| courant | 1,0·10⁻² rad | 2,1·10⁻³ | 8,3·10⁻⁵ (converge) |
| pas_prec | 1,8·10⁻³ | 3,3·10⁻³ | 1,1·10⁻³ (ne converge pas monotonement) |

La lecture `courant` converge avec h, la lecture `pas_prec` plafonne à ~10⁻³ rad (retard d'un pas) : plus lente à raffiner, mais stable.

**Limites non testées** : appui plan (frottement 2D, direction du glissement), rotule, hélicoïdale avec frottement, plusieurs frottements dans le même mécanisme (boucles à plusieurs contacts). La composante de moment de la glissière est ignorée dans |N|. Chaque connecteur de frottement ajoute des appels Python par itération (avertissements « memory allocations » d'Exudyn, sans conséquence sur les résultats ; coût non mesuré).

**Formulation recommandée (lot 7).** Lecture `courant`, loi tanh, repère du connecteur = repère de la liaison. Réglages par défaut : **v_ε = 10⁻⁴ m/s pour la translation** (adhérence tenue, fluage 1,2·10⁻⁴ m/s au maximum), **ω_ε = 10⁻² rad/s pour la rotation** ; h ≤ 2 ms (h ≤ 5 ms acceptable pour les pivots). Le fluage v = v_ε·atanh(F_t/(f·N)) est l'écart à signaler dans les résultats (EX-15) : le calculer à partir de v_ε et de la valeur de |v| aux instants d'adhérence.

### 2.4 EX-16 — Rendement (`moteur_rendement.py`)

**Formulation.** À partir du multiplicateur λ du couplage (g = ω₂ + k·ω₁) : couple exercé par la contrainte sur la sortie T_s = −λ, sur l'entrée T_e = −k·λ, puissance entrante P_e = −T_e·ω_e = k·λ·ω_e. Deux couples de perte, par `LoadTorqueVector` à `loadVectorUserFunction` :
- sens direct (P_e > 0) : −(1−η)·T_s sur la sortie → P_s = η·P_e ;
- sens inverse (P_e < 0) : −(1−η)·T_e sur l'entrée → |P_e| = η·|P_s| ;
pondérés par w = ½(1 + tanh(P_e/P_eps)) et 1 − w (P_eps = 0,5 W) pour une transition continue. Le multiplicateur est lu dans la configuration courante (point fixe de Newton) ; la lecture du pas précédent donne les mêmes valeurs à 10⁻⁹ près.

| Essai | Obtenu | Attendu |
|---|---|---|
| η = 0,95, Ce = 1 N·m, régime établi | ω_e = 28,5000, ω_s = −9,5000 ; Cs = 2,850000 N·m (écart 6,4·10⁻¹⁰) ; P_s/P_e = 0,950000 | 2,85 à 10⁻³ |
| η = 1 / 0,5 | Cs = 3,000000 / 1,500000 | 3 / 1,5 |
| deux phases, entrée imposée 30 rad/s, phase 1 : charge résistante 3 N·m | couple d'entrée 1,05263 N·m (signe −) | 3/(3·0,95) = 1,05263 |
| phase 2 : couple entraînant 3 N·m sur la sortie (frein) | couple d'entrée 0,95000 N·m (signe +, inversé) | η·3/3 = 0,95000 |
| contre-exemple « perte toujours sur la sortie » en phase 2 | 1,05263 N·m | 0,95 attendu : ≠, l'essai discrimine bien le sens |

**Limites** : la pondération par tanh(P_e/P_eps) applique une perte partielle près de P_e = 0 (la puissance perdue y est de l'ordre de P_eps·(1−η), négligeable) ; P_eps doit être mis à l'échelle des puissances du mécanisme (réglage, défaut 0,5 W à confirmer). Le rendement de la vis-écrou (couple/effort) et de la crémaillère n'a pas été exécuté : même construction avec T_s remplacé par l'effort de la contrainte et P_e = v·F (non testé). Un rendement est appliqué pour un couplage à deux corps seulement (limite 2.1).

**Formulation recommandée (lot 7).** Fonction `ajouter_rendement(mbs, couplage, eta)` qui ajoute les deux charges ci-dessus, lecture `courant`.

### 2.5 D9 / EX-42 — Processus et annulation (`moteur_processus.py`)

Modèle : bielle-manivelle de `prototypes/exudyn_bielle` (pilotage par `offsetUserFunction`), 240 000 pas, ≈ 29 s de calcul.

**Partie A, processus `spawn`.**
- La progression sort d'un `PostStepUserFunction` limité à 20 messages/s par une `multiprocessing.Queue` : intervalle moyen 0,050 s sur 60 messages en 3 s (écart maximal 0,3 s, autour du démarrage).
- **Annulation dure** `Process.terminate()` : processus terminé en **0,007 s**. **Annulation douce** (`Event` lu par le `PostStepUserFunction` qui renvoie `False`) : solveur arrêté proprement en **0,088 s**, `SolveDynamic` renvoie `True`, `t` atteint = 6,38 s (résultats partiels récupérables).
- Coût de démarrage : construction + import d'Exudyn dans le fils = 0,70 s ; premier message de progression d'un nouveau calcul après 1,16 s depuis le lancement. Pour qu'un nouveau calcul ne soit pas retardé, on peut précharger un travailleur (non testé) ; le critère « retour à l'état prêt < 1 s » porte sur l'annulation, atteint.

**Partie B, thread (information).** Compteur `sleep(1 ms)` dans le fil principal :
- référence sans calcul : 1,6 ms en moyenne ;
- `threading.Thread` + bielle (fonctions Python) : **15,5 ms en moyenne** (max 16,7 ms) : le fil principal reste vivant (≈ 65 Hz), grâce aux appels Python du solveur qui relâchent le GIL ; le calcul dure autant (4,0 s) ;
- `threading.Thread` + modèle **sans** fonction Python : **un seul tick en 6 s**, calcul de 10,5 s : le solveur C++ **ne libère pas** le GIL, le fil principal est gelé ;
- `QThread` (PyQt6) + bielle : 214 ticks en 6 s (≈ 17 ms), max 19 ms.

**Conclusion D9 : confirmé.** Un thread n'est fluide que si le modèle contient des fonctions utilisateur Python (le cas d'une loi d'entrée, mais pas d'un modèle gravitaire seul) ; encore à 15 ms de latence, et sans annulation brutale possible. Le processus donne une annulation en 7 à 90 ms.

## 3. Décision proposée

- **EX-14 : maintenir en V1** (engrenage, vis-écrou, hélicoïdale ; pignon-crémaillère par même construction, à exécuter au lot 7). Réserves à inscrire : un couplage porte sur deux corps (bâti compris) ; critère « ω_s = 10 rad/s à 10⁻⁶ » à reformuler en rapport ω_s/ω_e = −k (exact à 10⁻¹³), le pilotage par loi de position introduisant 2·10⁻⁴ rad/s à h = 1 ms ; dérive angulaire ≈ 2·10⁻⁴ rad/s à h = 1 ms, non corrigée.
- **EX-15 : maintenir en V1** avec v_ε = 10⁻⁴ m/s (translation) et 10⁻² rad/s (rotation) par défaut, et le fluage affiché dans les résultats ; appui plan et frottements multiples à valider au lot 7 (cas 2D non essayés).
- **EX-16 : maintenir en V1** sous la formulation à deux couples de perte pondérés par le sens de la puissance ; rendement de la vis-écrou à valider au lot 7.
- **D9 : confirmé** ; l'annulation s'implémente par `terminate()` (dure, 7 ms) avec arrêt doux optionnel par `Event` + `PostStepUserFunction` ; prévoir `freeze_support` pour PyInstaller (Q5 reste ouvert).
- À reporter dans ARCHITECTURE.md (D1) : le moteur doit exposer des contraintes utilisateur au niveau vitesse (`ObjectConnectorCoordinateVector`) et des connecteurs `ObjectConnectorRigidBodySpringDamper` ; lecture des multiplicateurs par `GetAECoordinates`/`GetObjectLTGAE`, signatures des fonctions utilisateur notées en 2.1 et 2.3.
