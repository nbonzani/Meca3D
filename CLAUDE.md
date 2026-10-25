# Meca3D — instructions pour Claude
Outil pédagogique de mécanique des solides indéformables : maquette SolidCraft → liaisons normalisées choisies par l'élève → graphe, m, h → simulation Exudyn → torseurs. Spécification : @docs/SPEC.md
Plan et état : docs/PLAN.md, docs/PROGRESS.md. Décisions : docs/ARCHITECTURE.md. Origine : docs/analyse_decade.md

## Commandes
- Environnement : `uv sync` (jamais pip directement)
- Tests : `uv run pytest -q`. Un fichier : `uv run pytest tests/test_x.py -q`. SolidCraft réel : `uv run pytest -m solidcraft` (application lancée avec `--control 7878`)
- Qualité : `uv run ruff check --fix . ; uv run ruff format . ; uv run pyright`
- Lancer : `uv run python -m meca3d`. Sans IHM : `uv run meca3d simuler <etude.meca3d> --csv <sortie.csv>`

## Architecture (ne pas contourner)
- `modele/` et `graphe/` : purs, sans exudyn, PyQt6, socket ni accès disque (sauf `modele/etude.py` pour le `.meca3d`).
- `moteur/` est la seule couche qui importe exudyn. `cao/` est la seule couche qui parle à SolidCraft. `ihm/` est la seule couche qui importe PyQt6.
- Unités SI en interne. Les conversions mm/g/deg passent toutes par `unites.py`, et uniquement à l'entrée dans `cao/`.
- Le torseur Exudyn (action du corps 1 sur le corps 0, en base de liaison liée au corps 0) n'est converti en {i→j} que dans `resultats/torseurs.py`.
- Les simulations tournent dans un processus séparé (`moteur/processus.py`), jamais dans le fil IHM.

## Méthode
- Travail par lots de docs/PLAN.md, via /methode-dev:lot N. Tests d'abord, commités avant le code.
- IMPORTANT : ne jamais modifier un test commité sans l'accord explicite de l'utilisateur.
- Exception accordée le 25/10/2026 : retouches purement formelles d'un test commité (ordre des imports, typage pour pyright, marqueurs comme slow, mise en forme) autorisées sans accord, si aucune assertion, valeur ou tolérance ne change ; commit `style:` séparé et signalé dans le compte rendu.
- Aucune affirmation de réussite sans preuve (sortie de commande).
- Aucune nouvelle dépendance sans accord (liste autorisée : SPEC § 6). Ambiguïté de la spec : demander, ne pas trancher.
- Toute valeur de référence d'un test vient de SPEC.md ou d'un calcul analytique indépendant, jamais du code testé.
- Commits : "test(EX-xx): …", "feat(EX-xx): …", "fix: …", "docs: …". Dépôt public : aucun jeton, chemin personnel ou fichier de `decade_archive/` dans un commit.
- Fin de session : /methode-dev:passation.
- Lors d'une compaction : conserver le lot en cours, les fichiers modifiés et les commandes de test.

## Pièges connus
- Windows : pathlib partout, encodage UTF-8 explicite pour les fichiers texte, CSV en UTF-8 avec BOM.
- Exudyn : generalized-α avec `spectralRadius = 0.9` (avec 1.0, les réactions divergent) ; `ss.solution.sensors.writePeriod` explicite ; noms de réglages récents (`ss.solution.file.write`).
- Exudyn : la linéaire rectiligne directe est fausse en grandes rotations, il faut deux ponctuelles. Un modèle hyperstatique donne « System Jacobian seems to be singular ».
- Liaisons : axe = x local, normale = z local. L'axe z de SolidCraft devient x local pour les liaisons à axe (`unites.py`).
- SolidCraft : `transform` est stockée par colonnes (à transposer), les longueurs sont en mm, les masses en g ; angles en deg dans l'API, en rad dans le JSON. L'URDF omet la liaison qui ferme une boucle et ne sert qu'aux inerties. `file.export` exige un dossier existant.
- Canal de contrôle : une requête à la fois par connexion. Après un `timeout`, ne pas renvoyer la requête : la relire avec `control.pending`.
- Prototypes de référence : `prototypes/exudyn_bielle` (solution Newton-Euler) et `prototypes/sonde_solidcraft` (chaîne SolidCraft → Exudyn).
- SolidCraft : fenêtre réduite → ~115 ms par requête (une requête par image affichée) ; la garder visible (`ui.window {"action":"maximize"}`). `revision` change à chaque animation : ne pas s'en servir pour détecter une modification.
- PyInstaller : `--hidden-import exudyn.exudynCPP` indispensable ; `multiprocessing.freeze_support()` dans le point d'entrée.
