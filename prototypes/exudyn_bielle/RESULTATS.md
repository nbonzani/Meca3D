# Prototype de validation du moteur Exudyn

*Le 22 octobre 2026. Exudyn 1.13.6, Python 3.12, Windows 11. Environnement isolé : `.venv` (uv).*

## Objet

Vérifier, avant tout cadrage de Meca3D, les deux hypothèses de [l'analyse Decade](../../docs/analyse_decade.md) § 8.2 :
1. `GenericJoint` réalise les 11 liaisons normalisées par la seule liste de leurs ddl bloqués ;
2. les efforts de liaison sont accessibles sous la forme du **torseur enseigné** : au centre de la liaison, dans sa base locale.

## Fichiers

| Fichier | Rôle |
|---|---|
| `liaisons.py` | catalogue des 11 liaisons : `constrainedAxes` [Tx Ty Tz Rx Ry Rz] |
| `test_liaisons.py` | essai de chaque liaison en grands déplacements (invariants physiques, ddl libres, efforts sur ddl libres) |
| `bielle_manivelle.py` | modèle Exudyn plus une solution de référence indépendante (Newton-Euler plan, système 9×9) |
| `comparer.py` | comparaison des torseurs sur 1 s, figure, essai de la variante hyperstatique |
| `comparaison_bielle.png` | courbes : couple moteur, réaction en A, réaction normale du piston |

Pour relancer les essais :

```bash
.venv/Scripts/python test_liaisons.py
```

```bash
.venv/Scripts/python comparer.py
```

## Résultats

### 1. Liaisons normalisées : 10 sur 11 exactes directement, la 11ᵉ par association

| Liaison | Résultat | Remarque |
|---|---|---|
| encastrement, pivot, glissière, pivot glissant, rotule, appui plan, linéaire annulaire, ponctuelle | **exactes** (invariants à 10⁻¹⁵ près) | |
| rotule à doigt | **exacte** | Exudyn maintient x₀ ⟂ y₁ : la condition du cardan |
| linéaire rectiligne directe | **inexacte en grandes rotations** (écart de 0,05 pour 0,27 rad) | Exudyn maintient x₀ ⟂ z₁ au lieu de z₀ ⟂ x₁ ; les deux coïncident en petites rotations |
| linéaire rectiligne = 2 ponctuelles en parallèle | **exacte** | c'est aussi l'illustration d'un résultat du cours (association de liaisons) |

Les efforts sur les ddl libres sont strictement nuls dans tous les cas : la dualité entre torseur cinématique et torseur statique est respectée.

### 2. Convention du torseur de liaison (établie numériquement)

`ForceLocal` et `TorqueLocal` donnent le **torseur de l'action du solide 1 sur le solide 0** (ordre de `itemNumbers`). Il est **réduit au centre de la liaison** et **exprimé dans la base de liaison liée au solide 0**, qui suit ce solide en mouvement (vérifié sur la liaison L12 portée par la manivelle). C'est la forme du torseur enseigné : il suffit de l'afficher au bon nom, {1→0} ou {0→1}.

### 3. Bielle-manivelle isostatique : écart maximal de 0,5 %

Mécanisme : manivelle de 0,1 m, bielle de 0,3 m, piston de 0,5 kg, gravité, montée en vitesse sur 0,2 s puis ω = 20 rad/s. Liaisons : pivot motorisé, pivot, linéaire annulaire d'axe z, glissière, soit h = 0.

| Grandeur | max \|réf.\| | écart relatif max |
|---|---|---|
| R(0→1) en O | 76,6 N | 2,8·10⁻³ |
| R(1→2) en A | 70,3 N | 2,8·10⁻³ |
| R(2→3) en B | 26,7 N | 2,4·10⁻³ |
| N(0→3) piston | 20,6 N | 2,4·10⁻³ |
| Couple moteur | 3,68 N·m | 4,8·10⁻³ |

La cinématique (θ, x_B) coïncide à 10⁻⁶ près. L'écart est concentré à la fin de la montée en vitesse (t = 0,204 s), où la dérivée de l'accélération imposée est discontinue. En régime établi, il est de l'ordre de 0,08 %.

**Réglage indispensable** : l'intégrateur generalized-α doit garder un amortissement numérique (ρ∞ = 0,9). Avec ρ∞ = 1, les efforts de liaison divergent (instabilité classique de la formulation à index 3) alors que la cinématique reste juste.

### 4. Bielle-manivelle hyperstatique : refus du calcul

Avec trois pivots et une glissière (h = 3 dans l'espace), Exudyn s'arrête sur « System Jacobian seems to be singular ». Ce comportement est **sain et exploitable en pédagogie** : l'outil refuse de fournir des efforts indéterminés. Meca3D devra détecter l'hyperstatisme **avant** la simulation (calcul de h sur le graphe) et l'expliquer à l'élève.

## Conséquences pour Meca3D

- **Exudyn est validé comme moteur.** Les liaisons se déclarent par leurs ddl bloqués, ce qui est directement le langage du cours. Les torseurs sont lisibles sans post-traitement lourd.
- **La linéaire rectiligne** est à construire par deux ponctuelles. Les autres liaisons sont des `GenericJoint` directs.
- **Le calcul de h avant simulation** est obligatoire, avec un message pédagogique.
- **Une loi d'entrée régulière** est nécessaire : départ au repos ou vitesses initiales cohérentes, et dérivées continues si l'on veut des efforts propres.
- **Il reste à valider** :
  - la liaison hélicoïdale (couplage Tx = p·Rx/2π) ;
  - un mode cinématique pur, sans dynamique ;
  - le passage des inerties lues dans SolidCraft ;
  - une boucle spatiale (non plane).
