# Sonde de l'API SolidCraft et chaîne SolidCraft → Exudyn

*Le 23 octobre 2026. SolidCraft 0.15.0 (portable, piloté par MCP), Exudyn 1.13.6.*

## Objet

Vérifier qu'un assemblage modélisé dans SolidCraft fournit tout ce qu'il faut à Exudyn, sans ressaisie : masses, centres de gravité, inerties, liaisons et leurs repères. On le vérifie en refaisant, depuis SolidCraft, la bielle-manivelle déjà validée dans [../exudyn_bielle](../exudyn_bielle/RESULTATS.md).

## Modèle construit dans SolidCraft

Fichier : `export/bielle_manivelle.solidcraft` (copie de `D:\CLAUDE\dev\Solidcraft\meca3d_sonde\`).

- **Quatre composants** : Bâti (fixé), Manivelle (100×20×20 mm), Bielle (300×20×20 mm), Piston (cube de 30 mm). Les matériaux sont créés pour l'occasion : `Acier7800` à 7,8 g/cm³ et `PistonDense`, réglé pour que le piston pèse 0,5 kg.
- **Liaisons** créées avec `joint.origin` puis `joint.create` (`flip: true` pour garder les pièces en place) :
  - L01 : revolute (pivot) en O ;
  - L12 : revolute (pivot) en A ;
  - L23 : ball (rotule) en B ;
  - L30 : slider (glissière) selon x.
- SolidCraft compte **1 ddl** et aucun conflit.

## Ce que fournit chaque canal

| Besoin | Canal SolidCraft | Résultat |
|---|---|---|
| Masse, CdG | `occurrence.properties` | exacts : 936 g pour la bielle, CdG en repère monde |
| **Matrice d'inertie** | `occurrence.properties` | **absente** |
| **Matrice d'inertie** | export **URDF** (`<inertial>`) | **exacte** : I_zz manivelle 2,704·10⁻⁴ kg·m², bielle 7,0512·10⁻³ kg·m². Donnée au CdG, dans le repère du lien URDF (tourné), donc à recomposer le long de l'arbre URDF |
| Liaisons : type, occurrences | `joint.list`, export **JSON** (`assembly.joints`) | complets |
| Repère de liaison | `joint.list` (`frame_a`, `frame_b`) ; JSON (`snap`) | **origine et axe z seulement**. JSON : en **repère local de l'occurrence** ; plus un `angle` autour de z |
| Pose des occurrences | JSON `occurrences[].transform` | 4×4 **stockée par colonnes** (translation dans la 4ᵉ ligne), en mm |
| Valeurs articulaires | JSON (rad) ; API `joint.drive` (deg) | unités différentes selon le canal |
| Boucle fermée | URDF | **la liaison qui ferme la boucle est omise** (L23). Inutile pour la topologie, l'URDF ne sert qu'aux inerties |
| Cinématique | `joint.drive` | **exacte** : x_B(60°) = 337,22813232690 mm, comme le calcul analytique (écart de 4·10⁻¹²) |
| Écriture de fichiers | `export`, `save`, `file.export` | **limitée** à `D:\CLAUDE\dev\Solidcraft` et aux dossiers temporaires, sauf si l'agent est lancé avec `--allow-path` |

## Chaîne automatique : `chaine_solidcraft_exudyn.py`

1. Lecture du JSON : occurrences, poses et liaisons. Les points et les axes sont ramenés en repère monde.
2. Lecture de l'URDF : pose des liens, puis CdG et inertie en repère monde.
3. Proposition de liaison normalisée par type SolidCraft (revolute → pivot, slider → glissière, ball → rotule…), puis **choix de l'élève** : ici, rotule → linéaire annulaire en B.
4. Construction du modèle Exudyn, loi d'entrée sur L01, simulation, comparaison à la référence Newton-Euler.

```bash
../exudyn_bielle/.venv/Scripts/python chaine_solidcraft_exudyn.py
```

| Grandeur | max \|réf.\| | écart relatif |
|---|---|---|
| réaction en O | 76,6 N | 2,8·10⁻³ |
| réaction en A | 70,3 N | 2,8·10⁻³ |
| réaction en B | 26,7 N | 2,4·10⁻³ |
| couple moteur | 3,68 N·m | 4,8·10⁻³ |
| normale piston | 20,6 N | 2,4·10⁻³ |

Ces écarts sont **identiques** à ceux du modèle saisi à la main : la chaîne n'introduit aucune erreur.

**Si l'élève garde la rotule proposée en B** (pivot, pivot, rotule, glissière, soit h = 1 dans l'espace), Exudyn refuse le calcul (Jacobien singulier), alors que **SolidCraft avait accepté l'assemblage sans conflit**. La modélisation CAO et la modélisation mécanique ne coïncident donc pas : c'est précisément l'étape que Meca3D doit faire réaliser à l'élève, avec un calcul de h avant la simulation.

## Conséquences pour Meca3D (adaptateur SolidCraft)

- **Sources à combiner** : le JSON pour la topologie et la géométrie des liaisons, l'URDF pour les inerties. L'API MCP sert pour le pilotage (`joint.drive`, `motion.study`) et le retour visuel.
- **Repères de liaison incomplets** : seul l'axe z est donné. Il suffit pour pivot, glissière, pivot glissant, linéaire annulaire, appui plan et ponctuelle (symétries de révolution autour de z). Pour la rotule à doigt et la linéaire rectiligne, il faudra faire **désigner la seconde direction** à l'élève dans Meca3D (ou utiliser `angle`, à vérifier).
- **Conversions à centraliser** : mm → m, deg ↔ rad, matrice par colonnes, axe z SolidCraft → axe x de notre convention pour les liaisons à axe.
- **Dossier d'échange** : configurer SolidCraft avec `--allow-path` vers le dossier de travail de Meca3D, ou travailler dans `D:\CLAUDE\dev\Solidcraft`.
- **Limites non testées** : sous-assemblages imbriqués, occurrences multiples d'un même composant, pièces importées en STEP, `pin_slot` et `planar`.
