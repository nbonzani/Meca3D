# Lot 1b — Levée des risques SolidCraft et exécutable

*Le 25 octobre 2026. SolidCraft 0.15.0 (portable, canal de contrôle TCP 7878), Exudyn 1.13.6, PyInstaller 6.22.3, Python 3.12.10, Windows 11.*

Ce lot produit des prototypes jetables et ce compte rendu. Aucun code n'entre dans `src/` ni `tests/`, et `docs/SPEC.md` et `docs/ARCHITECTURE.md` ne sont pas modifiés. Toutes les valeurs citées viennent de réponses réelles, enregistrées dans `reponses/` (chemins personnels anonymisés, aucun jeton). Les maquettes construites sont dans `maquettes/`.

| Question | Verdict |
|---|---|
| Q2 couplages | Lus intégralement par `joint.list` et l'export JSON. Rapports exacts. EX-14 est tenable en V1. |
| Q3 animation | Les deux modes tiennent plus de 55 images/s. Je recommande `occurrence.move` en attente (`capture: false`) par `engine.batch`. |
| Q4 trajectoires | `motion.trace.keep` fonctionne mais reste cinématique. Je recommande l'esquisse 3D (`sketch.spline3d`) alimentée par les points Exudyn. |
| Q5 exécutable | PyInstaller (mode dossier) embarque Exudyn, PyQt6 et un processus `spawn`. Résultat identique au bit près. Un seul import caché nécessaire. |
| Q6 sous-assemblages | Une liaison visant une sous-occurrence est ambiguë et perturbe les autres exemplaires. La règle de EX-04 (signaler, ne pas importer) est confirmée. |

---

## Prérequis découvert : la fenêtre SolidCraft doit être visible

Les requêtes du canal sont traitées **une par image affichée**. Fenêtre normale : 16,6 ms par `joint.drive` (60 images/s, plafond de la synchronisation verticale). **Fenêtre réduite** : toute requête coûte environ 115 ms (8,7 requêtes/s), et `ui.screenshot` répond `no frame was presented (window hidden?)`. C'est la cause du « 17 ms par image » de D2 mesuré fenêtre visible, et d'un premier essai de ce lot à 8,6 images/s.

`ui.window {"action": "maximize"}` ramène une fenêtre réduite (latence de `document.inspect` : 114 ms → 34 ms, `reponses/q3_fenetre.json`). Meca3D doit donc détecter une latence anormale ou l'erreur `hidden` et restaurer la fenêtre avant d'animer. Fichier : `q3_fenetre.py`.

---

## Q2 — Couplages (`joint.gear`, `joint.rack_pinion`, `joint.screw`)

Maquettes : `reducteur`, `vis_ecrou` (pivot + glissière), `vis_ecrou_cyl` (une seule liaison cylindrique), `cremaillere`. Scripts : `q2_reducteur.py`, `q2_vis_cremaillere.py`, `q2_gear_interne.py`.

### Forme dans `joint.list`

Les couplages sont dans `links` (la liste vide `[]` sans couplage) :

```json
{"a": 1, "b": 2, "ia": 0, "ib": 0, "offset": 0.0, "ratio": -0.3333333333333333, "unit": "deg",
 "coupling": {"type": "gear", "ra": 20.0, "rb": 60.0}}
```

| Commande | `coupling` | `ratio` (joint.list) | `unit` |
|---|---|---|---|
| `joint.gear {a, b, ra, rb}` | `{type: gear, ra, rb}` ; plus `internal: true` et/ou `reverse: true` quand demandés | −ra/rb (+ si `internal` ou `reverse`) | `deg` |
| `joint.screw {a, b, pitch}` | `{type: screw, pitch}` ; plus `reverse: true` pour un pas à gauche | pitch/360, soit 0,013889 mm/deg pour 5 mm | `mm` |
| `joint.rack_pinion {a: pignon, b: crémaillère, radius}` | `{type: rack_pinion, radius}` | radius·π/180 = 0,349066 mm/deg pour 20 mm | `mm` |
| `joint.rack_pinion {a: crémaillère, b: pignon}` | idem | 2,864789 deg/mm | `deg` |

- `a` et `b` sont des **identifiants de liaisons** (`joints[].id`), `ia`/`ib` des indices de valeur. Le `ratio` est « unités de b par unité de a », l'unité de b étant `unit`. `ra`/`rb` sont conservés tels que saisis (un texte `"20"` reste un texte).
- **Vis-écrou sur une liaison cylindrique** : `a` et `b` désignent la même liaison, avec `ia: 0` (angle, deg) et `ib: 1` (distance, mm). Les `values` de cette liaison sont `[angle, distance]`.
- `ra`/`rb` : la documentation de la commande les donne « rayons primitifs (ou nombres de dents) » ; seul le rapport compte. Je n'ai testé que des rayons (20 et 60 mm, soit un rapport de 1/3 comme Z₁ = 20 et Z₂ = 60). Une face ronde `{circle, occurrence}` donne le même rapport (−0,3333333333333335).
- Le champ `dof` de `joint.list` **ne tient pas compte** des couplages (1 par roue du réducteur, 2 pour la liaison cylindrique avec pas).

### Forme dans l'export JSON

`assembly.links` reprend les mêmes champs (`a`, `ia`, `b`, `ib`, `ratio`, `offset`, `coupling`), **sans `unit`**, et avec le `ratio` **par radian** : 0,7957747 mm/rad pour le pas de 5 mm (= p/2π), 20,0 mm/rad pour la crémaillère (= rayon). L'export URDF **ne contient aucun couplage** (pas de `mimic`).

### Vérification du rapport par `joint.drive`

| Maquette | Commande | Lecture par `joint.list` |
|---|---|---|
| réducteur | L1 = 7,5° / 30° / 90° / −45° / 360° | L2 = −2,5° / −10° / −30° / +15° / −120°, rapport −0,333333 à 10⁻¹⁵ |
| vis-écrou | vis = 90° / 360° / 720° / −180° | écrou = 1,25 / 5,0 / 10,0 / −2,5 mm ; pas à gauche : −5,0 mm pour 360° |
| vis-écrou cylindrique | `values: [90, 0]` / `[360, 0]` | `[90, 1,25]` / `[360, 5,0]` |
| crémaillère | pignon = 30° / 90° / 180° / −57,2958° | crémaillère = 10,4720 / 31,4159 / 62,8319 / −20,0000 mm |

L'engrenage satisfait EX-14 (ω₂ = −k·ω₁ avec k = ra/rb ; intérieur : +k), le pas v = p·ω/2π et le pignon-crémaillère v = r·ω, avec les signes ci-dessus (rotation positive autour de z, déplacement positif selon le z de la glissière).

### Pièges relevés

1. **`joint.drive` sur la liaison menée est ignoré** (`moved: false`, valeur inchangée). Il faut piloter la liaison `a`. Pour la vis-écrou cylindrique, `values: [0, 10]` ramène la distance à 0 : seul l'angle pilote.
2. **Valeurs de l'export JSON de la liaison menée : non fiables.** Observé deux fois : après un `joint.drive` refusé sur l'écrou (12 mm demandés, pose réelle à 0), le JSON donne `values: [12.0]` ; pour le réducteur, −0,349 rad (−20°) alors que la pose et `joint.list` donnent −10°. Le JSON garde la dernière valeur demandée. La pose réelle est dans `joint.list` ou dans les transformations.

### Recommandation pour le code produit

- Lire les couplages dans `joint.list.links` (unités par degré) et traduire : `gear` → engrenage (k = ra/rb, signe selon `internal`/`reverse`), `screw` → vis-écrou (`pitch`, `reverse`), `rack_pinion` → pignon-crémaillère (`radius`). Convertir mm → m et les rapports par degré en rapports par radian dans `unites.py`.
- Ne jamais utiliser `values` du JSON pour une liaison menée : prendre `joint.list`.
- Garder la saisie manuelle des couplages dans Meca3D (EX-14), pour une maquette sans couplage.
- Limites : seul le sens `a → b` est piloté ; pas testé : `joint.motion_link` (couplage générique), `joint.cam`, `pin_slot`, `planar`.

---

## Q3 — Animation : `joint.drive` ou `occurrence.move`

Scripts : `q3_animation.py` (comparaison, 200 images, tour complet de la manivelle), `q3_latences.py`, `q3_restauration.py`, `q3_cadence_boucle.py`, `q3_pending_groupe.py`. Les poses « calculées » viennent de la cinématique analytique (r = 100 mm, l = 300 mm), pas de SolidCraft.

### Ce que fait `occurrence.move`

`occurrence {occurrence, space, translate, axis, angle, origin, capture}` est **relatif et cumulatif** : rotation de `angle` autour de l'axe passant par `origin`, puis translation, dans l'espace `world`, appliquées à la pose courante. La réponse renvoie la nouvelle `transform` effective.

- `capture: true` (défaut) sur une occurrence **liée** : la liaison la remet en place au calcul suivant, et un pas d'annulation est créé. Inutilisable.
- **`capture: false`** : le déplacement reste « en attente » (`component.list.pending_moves` liste les identifiants). Il est **affiché dans la vue 3D** (captures d'écran vérifiées), `joint.list` ne bouge pas, et `component.list.transform` non plus : la pose se relit par `occurrence.properties` (centre de gravité, boîte englobante en repère monde) ou dans la réponse de `occurrence.move`.
- Une pose absolue s'obtient par `D = T_cible · T_courante⁻¹`, convertie en axe-angle (`delta_deplacement` dans `q3_animation.py`).
- Un déplacement en attente d'une occurrence de premier niveau **emporte ses sous-occurrences** rigidement, exemplaire par exemplaire (`q3_pending_groupe.json`).

### Résultats (fenêtre visible, une seule connexion persistante)

| Mesure | `joint.drive` | `occurrence.move` en attente |
|---|---|---|
| 200 images, une requête par commande | **57 images/s** (1 requête/image) | 19,9 images/s (3 requêtes/image : trois solides) |
| 200 images, une requête `engine.batch` **par image** | 54 images/s (latence médiane 17,4 ms) | **58 images/s** (3 commandes/requête, 16,5 ms) |
| 200 images en une seule requête `engine.batch` | 132 images/s (527 ms de calcul SolidCraft) | 102 images/s (600 commandes) |
| Fidélité (pose lue vs demandée) | θ : 5,7·10⁻⁹ deg ; x_B : 4,0·10⁻⁸ mm vs analytique | pose renvoyée : 1,8·10⁻¹⁴ ; x_B relu par `occurrence.properties` : 5,7·10⁻¹⁴ mm |
| Relecture de l'état à chaque image (`joint.list` + `component.list`) | +117 ms par image : à réserver à la vérification | — |

La cadence est bornée par l'affichage (1 requête par image, 60 Hz) : il faut **regrouper les commandes d'une image en un `engine.batch`**. Le maillon limitant est l'envoi, pas le calcul.

### Effet sur le document (maquette enregistrée, `document.inspect`)

| Indicateur | `joint.drive` | `occurrence.move` en attente |
|---|---|---|
| `dirty` | passe à `true` ; redevient `false` si la pose finale égale la pose enregistrée | **reste `false`** |
| Pile d'annulation (`undo`) | +1 par commande, plafonnée à 200 : **évince l'historique de l'utilisateur** (24 → 200 sur la maquette d'origine) | **inchangée** |
| `revision` | augmente à chaque commande | augmente aussi (+1 par déplacement, +1 par restauration) |

### Restauration de la pose initiale

| Méthode | Écart (valeurs articulaires, poses) |
|---|---|
| Retour par `joint.drive` à la valeur initiale | chaîne ouverte (crémaillère) : 0,0 ; **boucle fermée (bielle-manivelle) : 6·10⁻⁸ à 8·10⁻⁸ (deg ou mm)**, donc au-dessus de 10⁻⁹ |
| `edit.checkpoint` avant, `edit.restore_checkpoint` après | **0,0 exactement**, pile d'annulation et `dirty` restaurés. Annule aussi toute modification faite par l'utilisateur entre-temps |
| `component.revert_position` après des déplacements en attente | **0,0 exactement**, pile d'annulation intacte, sans effet sur les modifications de l'utilisateur |

Attention : `edit.restore_checkpoint` avec `forget: true` n'applique **pas** la restauration, il oublie seulement le point (erreur commise une fois en cours de lot, réparée en rouvrant la maquette).

### Recommandation

**`occurrence.move` en attente**, avec les poses issues d'Exudyn, une requête `engine.batch` par image, et `component.revert_position` en fin d'animation ou à l'interruption.

- Il ne salit pas le document (ni `dirty`, ni annulation), la restauration est exacte quelle que soit la topologie, et il montre exactement ce qu'Exudyn a calculé, sans dépendre de la convergence du solveur de boucle de SolidCraft ni du choix du mode d'assemblage entre deux images éloignées.
- Contreparties : conversion pose absolue → déplacement relatif (axe-angle 3D général, à coder), suivi de la pose courante côté Meca3D, et la relecture « par `joint.list` » de EX-53 n'est plus possible : voir « Décisions proposées ».
- Repli : `joint.drive` des m liaisons pilotes (par `engine.batch`) encadré par `edit.checkpoint`/`edit.restore_checkpoint`, tant qu'aucune modification utilisateur n'est possible pendant l'animation. À ne pas utiliser avec un retour par `joint.drive` (boucle fermée).
- Si Meca3D est interrompu en cours d'animation, les déplacements en attente restent dans SolidCraft jusqu'à `component.revert_position` : prévoir un nettoyage à la reconnexion (si `pending_moves` est non vide et que Meca3D l'avait provoqué).

### EX-06 : `revision` ne convient pas

`revision` augmente à chaque animation (dans les deux modes) et prend à la réouverture une valeur de compteur propre à l'application (1061 pour une maquette enregistrée à 39). `marker` (nombre de fonctions de la chronologie) ne bouge pas quand on modifie ou renomme une liaison (`q3_marker_revision.json`). `dirty` ne bouge pas avec les déplacements en attente. Proposition : une **signature de structure** (condensé de `joint.list` sans `values`, plus la structure de `component.list` sans `transform`, plus `marker`), comparée à celle de l'import. À valider : non testé pour une modification de paramètre de cotation.

---

## Q4 — Trajectoires (`motion.trace`, `motion.trace.keep`)

Script : `q4_trajectoires.py`, `q4_suppression.py` (sur une **copie** de la bielle, jamais sur l'original).

- **`motion.trace {occurrence, point, joint, from, to, samples}`** : sans étude, sans modifier le document (`revision` inchangée, `dirty: false`). `point` est un point monde (mm) pris sur l'occurrence **dans sa pose actuelle** ; la liaison parcourt `from → to` (deg ou mm, `index` pour la valeur), les boucles fermées suivent. Réponse : `points` (monde, mm), `samples` (2 à 500), `stopped_at`, `stopped_by_loop`, `stopped_by_contact`. 200 points en 0,27 s ; écart à l'analytique 1,5·10⁻⁸ mm (point de bielle) et 4,1·10⁻⁸ mm (piston).
- **Étude** : `motion.study {name, steps, keys: [{joint, points: [[pas, valeur]…]}]}` crée une étude **qui modifie le document** (`dirty`, une annulation) ; `motion.trace {study}` la rejoue (écart 1,5·10⁻⁸ mm). `motion.plot` fournit en plus positions, vitesses et accélérations par différences finies. Une étude n'est nécessaire que pour plusieurs liaisons ou une loi non linéaire ; `motion.delete {study}` la supprime.
- **`motion.trace.keep`** : mêmes paramètres plus `name`. Crée une esquisse 3D contenant une courbe `w1` (`curves: ["w1"]`, `sketch: 13`), ajoutée à la chronologie (`marker` 4 → 5) et au document (`dirty: true`). La courbe est **fixe**, elle ne suit pas les changements ultérieurs. Visible dans la vue 3D. L'effacement : `timeline.delete {features: ["Trace_P"]}`.
- **Alternative testée** : `sketch.create {plane: XY, name}`, `sketch.options {sketch_3d: true}`, `sketch.spline3d {points: [[x,y,z]…]}` (points monde, mm, 2 ou plus), `sketch.finish`. **200 points en 93 ms**, aucune étude, **points quelconques**. Effacement par `timeline.delete`. `sketch.line3d` (polyligne) est annoncé par le registre, non essayé. L'interpolation exacte aux points n'est pas mesurée.

### Recommandation

Utiliser l'**esquisse 3D `sketch.spline3d`** alimentée par les positions du capteur Exudyn. `motion.trace.keep` est purement cinématique (une liaison de `from` à `to`) : il ne retrace pas une simulation dont les ddl libres sont mus par des efforts, ni l'ordre temporel. Les deux laissent une esquisse dans la maquette, donc le document devient « modifié » : c'est l'unique écriture de Meca3D (EX-52), et l'élève doit enregistrer s'il veut la conserver.

---

## Q5 — Exécutable (PyInstaller, mode dossier)

Dossier : `exe/` (venv local `exe/.venv`, ni le `pyproject.toml` ni le `uv.lock` racine ne sont touchés). Versions : Exudyn 1.13.6, PyQt6 6.11.0, numpy 2.5.4, PyInstaller 6.22.3, pyinstaller-hooks-contrib 2026.9.

Programme : `mini_meca3d.py` (fenêtre PyQt6, `--sans-fenetre` pour l'essai automatique, `--fermer-apres` en ms pour une vraie fenêtre fermée seule) et `calcul_exudyn.py` (pendule à pivot `GenericJoint`, 1 s, généralisé-α ρ∞ = 0,9, 1 000 pas), lancé dans un processus `spawn` après `multiprocessing.freeze_support()`. Construction : `exe/construire.py`.

| Mesure | Valeur |
|---|---|
| Écart exe / source (θ(1 s), somme de θ, norme max de la force, force locale, 1 001 points) | **0,0** (identique au bit près, attendu < 10⁻¹²) ; θ(1 s) = −3,1334442619018894 rad |
| Processus | parent et calcul distincts (PID différents), `code_sortie_fils = 0`, méthode `spawn` |
| Fenêtre | `--sans-fenetre` : plateforme Qt `offscreen` ; sinon plateforme `windows`, fenêtre affichée puis fermée seule |
| Taille de `dist/mini_meca3d` | **136,1 Mo** (233 fichiers). Sans `--exclude-module tkinter` : 140 Mo |
| Plus gros fichiers | OpenBLAS de numpy 20,6 Mo, `opengl32sw.dll` 20,6 Mo, Qt6Core 10,4 Mo, Qt6Gui 9,5 Mo, exudynCPP 8,6 Mo |
| Temps de construction | environ 100 s |
| Temps d'exécution (exe, sans fenêtre) | environ 2,6 s au total, dont 1,9 s pour le processus fils (démarrage, import d'Exudyn et de numpy) et 30 ms de calcul (mode source : 2,2 s et 19 ms) |

### Options et hooks nécessaires

- **`--hidden-import exudyn.exudynCPP` : indispensable.** Exudyn charge son module compilé par `importlib`, l'analyse de PyInstaller ne le voit pas. Sans lui, le fils répond `ImportError("Exudyn could not import its compiled module…")`. Aucun autre import caché, aucun fichier de données, aucun hook personnalisé n'a été nécessaire ; les plugins Qt (`windows`, `offscreen`) et les DLL sont collectés par le hook PyQt6 fourni.
- `--exclude-module tkinter` : facultatif (tkinter est tiré par `exudyn.utilities`, 8 Mo de tcl/tk).
- `multiprocessing.freeze_support()` en premier dans `if __name__ == "__main__"` : indispensable. La fonction cible du processus doit être dans un module importable (ici `calcul_exudyn.fils`) ; PyInstaller la trouve car l'import est dans le corps d'une fonction. Le fils est la même exe relancée avec les arguments de `multiprocessing`.
- **Allègement testé** : supprimer `opengl32sw.dll`, `Qt6Pdf.dll` et `Qt6Network.dll` de `_internal/PyQt6/Qt6/bin` ramène le dossier à **105 Mo** sans gêner la fenêtre ni le calcul. Non testé avec matplotlib (QtAgg).
- Exécutable lancé depuis un autre dossier courant : fonctionne.

### Limites

Reste à faire sur le runner GitHub Actions `windows-latest` (consigne : local seulement). Non testé : `--onefile`, matplotlib, chemin avec accents ou espaces, antivirus (faux positifs possibles sur les exécutables PyInstaller non signés), moteur graphique d'Exudyn (non utilisé). Le démarrage du processus fils coûte environ 2 s : à prévoir pour EX-42 (annulation en moins de 1 s : il s'agit d'arrêter un fils déjà lancé, pas d'en démarrer un). Le choix D9 (processus `spawn`) est **validé** avec PyInstaller.

---

## Q6 — Sous-assemblages et occurrences multiples

Maquettes : `sous_assemblage` (liaisons sur des sous-occurrences), `sous_assemblage_propre` (cas géré). Scripts : `q6_sous_assemblages.py`, `q6_liaisons.py`, `q6_poses.py`, `q6_propre.py`. Structure : `Bati` (fixe), composants `Barre` et `Axe`, composant `Groupe` contenant une occurrence de chacun, `Groupe` placé deux fois (`Groupe:1`, `Groupe:2`), `Barre:1` et `Axe:1` au premier niveau.

### Ce que renvoie SolidCraft

- `component.list` : chaque composant a `occurrences` ; chaque occurrence `{id, name, component, parent, grounded, transform}`. **`parent` est l'identifiant du composant contenant** : 0 (racine) pour le premier niveau, 10 (`Groupe`) pour `Barre:2` (id 12) et `Axe:2` (id 13). Les deux exemplaires de `Groupe` (ids 11 et 14) **partagent** les sous-occurrences 12 et 13 : une occurrence imbriquée n'a pas d'identifiant par exemplaire.
- `transform` d'une sous-occurrence : **relative** au composant parent (identité au repos). La pose monde est `transform(Groupe:i) · transform(sous-occurrence)`.
- `occurrence.properties {occurrence: 12}` échoue (`occurrence has multiple placements; supply its path`) ; avec `path: [11, 12]` ou `[14, 12]` : masse et centre de gravité en repère monde, par exemplaire. Pour une occurrence de premier niveau (`descendants: true` par défaut), **les sous-occurrences sont agrégées** : `Groupe:1` = 14,942 g = 12,9 + 2,042.
- `joint.list` : `a` et `b` sont de simples identifiants d'occurrence (12, 13…), **sans chemin**. `joint.origin` accepte et ignore silencieusement un paramètre `path`. Une liaison sur 12/13 ne dit donc pas de quel exemplaire de `Groupe` il s'agit.
- **Effet constaté d'une liaison sur sous-occurrence** (maquette `sous_assemblage`, qui porte les liaisons Bati/`Axe:2` et `Barre:2`/`Axe:2` en plus de Bati/`Groupe:1`) : SolidCraft les résout en modifiant la transformation **locale partagée**, donc les **deux** exemplaires de `Groupe` bougent. Exemple : après `joint.drive` de Bati/`Groupe:1` à 30°, le centre de gravité de `Barre:2` dans `Groupe:2` passe de (50, 150) à (43,3 ; 125,0), alors que `Groupe:2` n'a aucune liaison au premier niveau. `joint.list.dof` ne le signale pas (aucun conflit, `floating: []`).
- **Export URDF** : chaque occurrence est un lien (`Barre_2` pour `Barre:2` ; second exemplaire `Barre_2_2`, `Axe_2_2`). Le lien d'une occurrence de premier niveau qui contient des sous-occurrences est un lien « vide » (masse 10⁻⁶ kg), et ses sous-occurrences sont rattachées par des joints `fixed` (`Barre_2_fixed`, parent `Groupe_1`, avec `origin` relative). Dans la maquette à liaisons sur sous-occurrences, l'arbre est réorganisé selon les liaisons et cet agrégat n'est plus lisible. L'URDF **ne donne pas l'inertie agrégée** du groupe.
- **Export JSON** : `occurrences[]` plat avec `parent` ; `assembly.joints[].a|b.occurrence` sans chemin ; transformations locales aux composants.

### Cas géré (`sous_assemblage_propre` : liaisons seulement au premier niveau)

`Groupe:1` et `Groupe:2` ont chacun une pivot avec le bâti, pilotées à 30° et −50° : les sous-occurrences suivent rigidement, indépendamment, et `occurrence.properties` donne par exemplaire la masse agrégée (14,942 g) et le centre de gravité monde. La sous-occurrence reste à l'identité locale. C'est exactement le modèle « une classe d'équivalence est une occurrence de premier niveau ».

### Recommandation pour le code produit

1. **Confirmer EX-04.** Une occurrence est de premier niveau si `parent == 0` (racine) dans `component.list`. Toute liaison dont `a` ou `b` a `parent != 0` est signalée (nom de la liaison, message à l'élève) et **n'est pas importée**. Les autres liaisons sont importées. Les sous-occurrences font partie rigidement de leur occurrence de premier niveau.
2. **Masse et centre de gravité** d'un groupe : `occurrence.properties` de l'occurrence de premier niveau (agrégat).
3. **Inertie d'un groupe** : l'URDF ne la donne pas ; il faut sommer les inerties des liens enfants rattachés par des joints `fixed`, en composant les `origin` (Huygens). À écrire et à tester au lot suivant ; identification des liens par la structure de l'arbre plutôt que par le nom (suffixes `_2_2` des seconds exemplaires).
4. **Avertir** si une liaison vise une sous-occurrence, car SolidCraft a alors déjà déplacé les deux exemplaires dans la maquette : la pose lue est incohérente pour l'autre exemplaire.
5. **Écrans de test (faux serveur)** : prévoir une réponse où `a` ou `b` a `parent != 0`.

### Observation annexe sur les masses

Pour un cylindre de rayon 6 mm et de 14 mm de haut à 1,29 g/cm³ (masse exacte 2,04253 g) : `occurrence.properties` donne 2,04231 g (−1,1·10⁻⁴) et l'URDF 2,04162 g (−4,5·10⁻⁴). Les surfaces courbes sont tessellées. Pour des pièces prismatiques (la bielle-manivelle), les masses sont exactes. EX-04 (10⁻⁹) reste réaliste pour la bielle-manivelle, mais une pièce ronde (roues, vis) s'écarte de l'ordre de 10⁻⁴ à 10⁻³ en relatif entre les deux canaux : en V1, prendre masse et inertie dans le même canal (URDF) pour qu'elles soient cohérentes entre elles.

---

## Décisions proposées

*(À valider par l'utilisateur ; je n'ai pas modifié SPEC.md ni ARCHITECTURE.md.)*

### Mode d'animation (Q3)

- **Retenir `occurrence.move` en attente (`capture: false`)**, poses issues d'Exudyn, un `engine.batch` par image (jusqu'à 58 images/s mesurés), restauration par `component.revert_position`. Raison : aucun effet sur `dirty` ni sur l'historique d'annulation, restauration exacte (0,0), fidélité à la simulation.
- **Amender EX-53** : « relu par `joint.list` » devient « relu par `occurrence.properties` (centre de gravité d'un solide) à 0,1° ou 10⁻⁶ m près » ; la restauration est vérifiée sur `joint.list` et `component.list` à 10⁻⁹ près (obtenu : 0,0). La cadence de 20 images/s est tenue (58 mesurés) à condition de grouper en `engine.batch`.
- **Ajouter une exigence** : détecter une fenêtre SolidCraft réduite (latence > 80 ms ou `ui.screenshot` en erreur `hidden`) et la restaurer par `ui.window {"action": "maximize"}`, sinon la cadence tombe à 8 images/s.
- **EX-06** : remplacer le critère `revision` par une signature de structure (voir Q3).
- **Repli** à garder dans ARCHITECTURE : `joint.drive` en `engine.batch` des liaisons pilotes, avec `edit.checkpoint`/`restore_checkpoint`.

### Sous-assemblages (Q6)

- **Garder EX-04 tel que rédigé** (liaison sur sous-occurrence signalée, non importée) et ajouter le critère de détection (`parent != 0`) et le motif : SolidCraft déplace alors tous les exemplaires du sous-assemblage. Le test « faux serveur » de EX-04 devient réalisable avec des `component.list` et `joint.list` fixture (les réponses enregistrées dans `reponses/q6_*` peuvent servir de fixture, après relecture).
- Masse et centre de gravité d'un groupe par `occurrence.properties` ; **inertie agrégée à calculer** depuis l'URDF (lot ultérieur).

### Trajectoires (Q4)

- **Utiliser l'esquisse 3D `sketch.spline3d`** avec les positions du capteur Exudyn (EX-52 « Trajectoire d'un point »), nommée par Meca3D pour pouvoir être effacée (`timeline.delete`) avant un nouveau tracé. `motion.trace` (lecture seule, 0,27 s pour 200 points) sert éventuellement d'aperçu cinématique sans écriture.
- **Préciser EX-52** : la trajectoire rend la maquette « modifiée » (esquisse ajoutée) et n'est pas enregistrée par Meca3D.

### Couplages (Q2) et exécutable (Q5)

- EX-14 : maintenu en V1, lecture par `joint.list.links` ; interdit de lire les `values` du JSON pour une liaison menée.
- EX-63 / D9 : PyInstaller + Exudyn + PyQt6 + `spawn` validés en local avec `--hidden-import exudyn.exudynCPP` ; reste à les rejouer sur `windows-latest`.

## État laissé

- SolidCraft : maquette d'origine `bielle_manivelle.solidcraft` rouverte depuis le disque (jamais enregistrée par ce lot, fichier inchangé), propre (`dirty: false`, historique vide), θ = 60°, seul document ouvert, fenêtre restaurée (elle était réduite au départ). Le document ouvert au départ portait des modifications non enregistrées et un historique d'annulation que ce lot n'a pas pu conserver.
- Les maquettes de test sont dans `maquettes/` (enregistrées par `file.save_as`).

## Fichiers

Scripts : `sc_client.py` (client TCP), `sc_maquette.py` (aides de construction), `q2_*.py`, `q3_*.py`, `q4_*.py`, `q6_*.py`, `extraire_commandes.py`, `exe/*.py`. Réponses brutes : `reponses/` ; exports JSON et URDF : `reponses/export_*/`. Registre des commandes utilisées : `reponses/commandes_utilisees.json`.
