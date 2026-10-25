# ARCHITECTURE — Meca3D v1

*Le 24 octobre 2026. Référence : [SPEC.md](SPEC.md).*

## 1. Vue d'ensemble et flux de données

    SolidCraft (application, --control PORT)
        │  TCP 127.0.0.1, lignes JSON, jeton            (cao/canal.py)
        ▼
    cao/solidcraft.py ── joint.list, component.list, component.properties,
        │                file.export urdf/json (dossier temporaire)
        ▼
    modele/  Etude = solides + liaisons proposées (modèle neutre, SI)
        │  l'élève valide les liaisons, saisit lois, actions, capteurs   (ihm/)
        ▼
    graphe/  μ, cycles, Ic, rc, m, h, ddl redondants
        │  garde-fou (EX-22, EX-23)
        ▼
    moteur/  traduction du modèle neutre vers Exudyn, dans un processus séparé
        │  Resultats bruts : temps, poses, vitesses, accélérations, réactions locales
        ▼
    resultats/  torseurs {i→j} au centre de la liaison, capteurs de point, CSV, statistiques
        │
        ├──► ihm/ : courbes, tableaux
        └──► cao/animation.py : joint.drive image par image, trajectoires, restauration de la pose

Le **modèle neutre** (`modele/`) est le pivot. Il ne dépend ni d'Exudyn, ni de SolidCraft, ni de Qt. Les adaptateurs `cao/` et `moteur/` le produisent ou le consomment.

## 2. Modules

| Module | Rôle | Dépend de |
|---|---|---|
| `unites` | conversions mm↔m, g↔kg, deg↔rad ; matrices par colonnes ; axe SolidCraft vers base de liaison | numpy |
| `modele.solide` | solide : nom, fixe, masse, CdG, inertie au CdG en repère monde, points nommés | unites |
| `modele.liaison` | catalogue des 11 liaisons (ddl bloqués), centre, base de liaison, statut proposée/validée, frottement f et r | unites |
| `modele.couplage` | engrenage, pignon-crémaillère, vis-écrou : liaisons couplées, rapport, rendement η | modele.liaison |
| `modele.actions` | lois d'entrée (expressions sympy et leurs dérivées), pesanteur, forces, couples, ressorts | sympy |
| `modele.capteurs` | définitions des capteurs : liaison, point / solide de référence, base d'expression | modele.solide |
| `modele.etude` | agrégat Etude ; lecture et écriture `.meca3d` (JSON versionné) | modele.* |
| `graphe.graphe` | graphe networkx, μ, cycles indépendants, composantes, solides isolés | networkx, modele |
| `graphe.mobilite` | système cinématique, rang (SVD), m, h, choix des ddl redondants à libérer | numpy, graphe.graphe |
| `moteur.base` | interface `Moteur` (Protocol), `Reglages`, `ResultatsBruts`, erreurs typées | modele |
| `moteur.exudyn_dyn` | construction Exudyn : corps, `GenericJoint`, pilotes, efforts, ressorts ; résolution | exudyn, moteur.base |
| `moteur.couplages` | contraintes utilisateur pour les couplages et l'hélicoïdale ; frottement ; rendement (selon le lot 1) | exudyn |
| `moteur.cinematique` | mode cinématique : m pilotes, ddl redondants libérés (EX-23) ; s'appuie sur exudyn_dyn | moteur.exudyn_dyn |
| `moteur.processus` | exécution dans un processus séparé : progression, annulation, remontée des erreurs | multiprocessing, moteur.base |
| `cao.canal` | client du canal de contrôle : jeton, port, requêtes, `busy`, `timeout`, `control.pending` | socket, json |
| `cao.solidcraft` | lecture de la maquette vers une Etude ; vérification du format ; révision | cao.canal, cao.urdf, modele |
| `cao.urdf` | lecture des inerties URDF, recomposition le long de l'arbre | xml, unites |
| `cao.animation` | animation (`joint.drive` ou `occurrence.move`, selon Q3), trajectoires, restauration de la pose | cao.canal |
| `resultats.torseurs` | torseurs {i→j} ou {j→i}, base locale ou monde ; torseur cinématique | numpy, modele, moteur.base |
| `resultats.capteurs` | capteurs de point relatifs à un solide de référence | numpy |
| `resultats.export` | CSV au format Excel français, statistiques min / max / moyenne | csv |
| `ihm.*` | fenêtre, arbre, propriétés, vues graphe / courbes / torseurs, menu Enseignant ; dialogue avec `moteur.processus` | PyQt6, matplotlib |
| `cli` | `meca3d` (IHM) et `meca3d simuler` (sans interface) | tout sauf ihm, pour `simuler` |

## 3. Arborescence

Le dépôt a pour racine `D:\CLAUDE\dev\Meca3D` :

    Meca3D/
      CLAUDE.md
      LICENSE
      pyproject.toml
      .gitignore
      .claude/
      .github/
        workflows/
          ci.yml
          release.yml
      docs/
        SPEC.md
        ARCHITECTURE.md
        PLAN.md
        PROGRESS.md
        analyse_decade.md
      prototypes/
        exudyn_bielle/
        sonde_solidcraft/
        levee_risques/
      src/
        meca3d/
          __init__.py
          __main__.py
          cli.py
          unites.py
          modele/
            solide.py
            liaison.py
            couplage.py
            actions.py
            capteurs.py
            etude.py
          graphe/
            graphe.py
            mobilite.py
          moteur/
            base.py
            exudyn_dyn.py
            couplages.py
            cinematique.py
            processus.py
          cao/
            canal.py
            solidcraft.py
            urdf.py
            animation.py
          resultats/
            torseurs.py
            capteurs.py
            export.py
          ihm/
            fenetre.py
            arbre.py
            proprietes.py
            vue_graphe.py
            vue_courbes.py
            vue_torseurs.py
      tests/
        fixtures/
          bielle/
        faux_serveur.py
        reference_bielle.py
        test_fumee.py
        test_bout_en_bout.py
      decade_archive/

`decade_archive/` reste local et ignoré par Git : ce sont des sources et des binaires tiers, dont un exécutable de 31,8 Mo. Les `.venv/` des prototypes sont également ignorés.

## 4. Décisions structurantes

- **D1 — Moteur Exudyn 1.13.6, derrière une interface `Moteur`.**
  - *Alternatives* : Project Chrono, MuJoCo.
  - *Raison* : les 11 liaisons se déclarent par leurs ddl bloqués, et le torseur sort au centre de la liaison, en base locale. Validé le 22 octobre 2026, avec 0,5 % d'écart au plus. Version figée, car le comportement de l'intégrateur en dépend (ρ∞ = 0,9).
  - *Date* : 24 octobre 2026.
- **D2 — Liaison SolidCraft par le canal de contrôle TCP en lignes JSON.**
  - *Alternatives* : serveur MCP (stdio, prévu pour les agents, avec une limite de dossiers d'écriture) ; fichiers exportés à la main.
  - *Raison* : choix de l'utilisateur. Vérifié le 24 octobre 2026 : jeton lu automatiquement, `joint.list` en 35 ms, `joint.drive` en 17 ms par image, `file.export` vers tout dossier existant.
  - *Date* : 24 octobre 2026.
- **D3 — Inertie lue dans un export URDF temporaire.**
  - *Alternative* : recalcul depuis les STL.
  - *Raison* : `component.properties` ne donne pas l'inertie, alors que l'URDF la donne exacte.
- **D4 — Modèle neutre indépendant de la CAO, du moteur et de l'IHM.**
  - *Raison* : il est testable sans SolidCraft ni Exudyn, il prépare le mode autonome de la V2, et le moteur reste remplaçable.
- **D5 — Lois d'entrée en sympy, analysées sur une liste blanche de l'arbre syntaxique.**
  - *Alternative* : un analyseur maison.
  - *Raison* : les dérivées sont exactes, ce que le pilotage Exudyn exige (`offsetUserFunction_t`), et l'accélération est obtenue sans différence finie. Le texte est vérifié par `ast` avant tout appel à sympy, ce qui exclut l'exécution de code.
- **D6 — PyQt6 et matplotlib (QtAgg), licence GPL v3.**
  - *Alternatives* : PySide6 avec une licence MIT ; pyqtgraph.
  - *Raison* : choix de l'utilisateur et outils déjà maîtrisés. matplotlib est déjà utilisé par le prototype.
- **D7 — Mode cinématique réalisé par Exudyn, avec m liaisons pilotées.**
  - *Alternative* : un solveur géométrique maison.
  - *Raison* : un seul jeu de traductions des liaisons. Pour l'option « Hyperstatique autorisé », les ddl redondants désignés par `graphe.mobilite` passent à 0 dans `constrainedAxes`.
  - *Révision du 25 octobre 2026 (lot 6)* : Exudyn ne fournit que les positions. Vitesses et accélérations sont obtenues par dérivation exacte des équations de liaison. Les capteurs Exudyn (generalized-α, ordre 1 en h) donnaient 3,9·10⁻³ d'écart relatif sur l'accélération et 2,9·10⁻⁷ sur une vitesse relative, hors des critères d'EX-41 et d'EX-51 ; la formulation d'indice 2 est refusée avec `offsetUserFunction_t`. En mode dynamique, les capteurs Exudyn restent utilisés.
- **D15 — Repère d'un solide = repère de son composant SolidCraft** (rotation et origine de la `transform` de l'occurrence à l'import), puis lié au solide.
  - *Alternative* : repère monde à l'import.
  - *Raison* : c'est la convention de la CAO, que Decade suivait avec les repères des pièces CATIA. L'élève lit et saisit les points en coordonnées pièce. Décision du 25 octobre 2026.
- **D8 — Pas de pint ; conversions centralisées dans `unites.py`.**
  - *Raison* : le calcul est vectorisé avec numpy et il n'y a que quatre conversions frontières, toutes testées. Les unités affichées sont portées par les en-têtes et les étiquettes.
- **D9 — Calcul dans un processus séparé (`multiprocessing`, démarrage `spawn`).**
  - *Alternative* : un QThread.
  - *Raison* : les lois d'entrée sont des fonctions Python appelées à chaque pas, donc sous le verrou global de Python (GIL). Je n'ai pas trouvé de documentation indiquant qu'Exudyn libère ce verrou pendant le calcul, ni de moyen d'interrompre `SolveDynamic` depuis un autre fil. Un processus garantit que l'IHM reste fluide et que l'annulation prend moins de 1 s (EX-42). Il faut appeler `freeze_support` pour PyInstaller ; à vérifier au lot 1.
- **D10 — Fichier `.meca3d` en JSON, avec un champ `version_etude`.**
  - *Raison* : fichier lisible et comparable par diff ; les migrations sont explicites.
- **D11 — Ligne de commande `meca3d simuler`.**
  - *Raison* : scénario de bout en bout et test de l'exécutable sans IHM, et préparation des corrigés.
- **D12 — Dépôt public `nbonzani/Meca3D` dès le départ.**
  - *Raison* : choix de l'utilisateur. Conséquences : aucun jeton ni chemin personnel dans les fixtures, et `decade_archive/` ignoré.

- **D13 — Couplages, frottement et rendement : formulations du lot 1a** ([RESULTATS_1a.md](../prototypes/levee_risques/RESULTATS_1a.md)).
  - *Couplages et hélicoïdale* : contrainte au niveau vitesse, par `ObjectConnectorCoordinateVector` avec `constraintUserFunction` et `jacobianUserFunction`, sur les paramètres d'Euler. Le couple ou l'effort transmis se lit dans le multiplicateur de Lagrange.
  - *Coulomb* : `ObjectConnectorRigidBodySpringDamper` à fonction utilisateur F = f·|N|·tanh(v/v_ε), avec N lu dans la configuration courante (point fixe de Newton).
  - *Rendement* : deux couples de perte (`LoadTorqueVector`), pondérés par le sens de la puissance.
  - *Résultats* : tous les critères sont tenus. EX-14, EX-15 et EX-16 restent en V1 (décision du 25 octobre 2026). D9 est confirmé : sans fonction Python, le solveur ne libère pas le GIL, et l'annulation par `terminate()` prend 7 ms.

- **D14 — Résultats du lot 1b** ([RESULTATS_1b.md](../prototypes/levee_risques/RESULTATS_1b.md)), décidés le 25 octobre 2026.
  - *Animation* : `occurrence.move` avec les poses Exudyn, un `engine.batch` par image (58 images/s), puis restauration par `component.revert_position` : retour exact, document non modifié, pile d'annulation intacte. Repli : `joint.drive` encadré par `edit.checkpoint` et `edit.restore_checkpoint`.
  - *Couplages* : ils se lisent dans `joint.list.links` (`a`, `b`, `ratio`, `unit`, `coupling{type, ra, rb, pitch, radius, internal, reverse}`). Ni le `ratio` ni les `values` de la liaison menée ne sont à lire dans le JSON.
  - *Sous-assemblages* : une sous-occurrence est repérée par `parent != 0`. La règle d'EX-04 est confirmée : la liaison est signalée et non importée.
  - *Trajectoires* : `sketch.spline3d`.
  - *Exécutable* : PyInstaller en mode dossier, avec `--hidden-import exudyn.exudynCPP` (indispensable). Le résultat est identique au bit près au mode source. Taille 105 à 136 Mo.
  - *Prérequis* : la fenêtre SolidCraft doit être visible pour garder la cadence.

Décisions coûteuses à défaire :
- D1 (moteur) ;
- D4 (modèle neutre) ;
- D9 (processus séparé) ;
- l'inclusion des couplages et du frottement dans la V1, suspendue au lot 1.

## 5. Points d'intégration critiques

- **Convention du torseur Exudyn** : `ForceLocal` et `TorqueLocal` donnent l'action du corps 1 sur le corps 0 (ordre de `itemNumbers`), réduite au centre de la liaison, en base de liaison liée au corps 0. Le passage à {i→j} se fait uniquement dans `resultats.torseurs`.
- **Base de liaison** : l'axe z de SolidCraft devient l'axe x local pour pivot, glissière, pivot glissant, linéaire annulaire et hélicoïdale, et le z local pour appui plan et ponctuelle. La liaison et la direction saisie (EX-12, EX-13) sont prioritaires.
- **Linéaire rectiligne** : elle est réalisée par deux ponctuelles. La liaison directe d'Exudyn est fausse en grandes rotations.
- **Intégrateur** : ρ∞ = 0,9 obligatoire, sinon les réactions divergent.
- **Unités et formats SolidCraft** : mm, g, deg ; transformations stockées par colonnes ; `flip` des liaisons. Une seule porte d'entrée : `cao.solidcraft` avec `unites`.
- **Canal de contrôle** : une requête à la fois par connexion (`busy`) ; une requête en `timeout` continue de s'exécuter, il faut donc relire avec `control.pending` sans la renvoyer. Requêtes servies par le fil IHM de SolidCraft, entre deux images.
- **Processus de calcul** : seules des données sérialisables traversent la frontière (Etude en dict, ResultatsBruts en tableaux numpy).
