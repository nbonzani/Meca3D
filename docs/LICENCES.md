# Licences (EX-64)

Meca3D est publié sous **GNU GPL version 3 ou ultérieure** (fichier `LICENSE`, `license = "GPL-3.0-or-later"` dans `pyproject.toml`, en-tête `# SPDX-License-Identifier: GPL-3.0-or-later` dans chaque module de `src/`, vérifié par `tests/test_licences.py`).

## Dépendances d'exécution

Tableau produit par `uv run python tests/outils_licences.py` à partir des métadonnées installées (`importlib.metadata`) : dépendances directes et transitives de `meca3d`, extras exclus. Le test `test_ex64_licences_des_dependances_compatibles_gpl3` échoue si une licence n'est pas reconnue comme compatible.

| Paquet | Version | Licence déclarée | Compatible GPL v3 |
|---|---|---|---|
| contourpy | 1.4.0 | BSD-3-Clause | oui |
| cycler | 0.12.1 | BSD | oui |
| exudyn | 1.13.6 | « EXUDYN General License » : texte BSD à trois clauses (LicenseRef) | oui |
| fonttools | 4.67.0 | MIT | oui |
| kiwisolver | 1.5.1 | BSD | oui |
| matplotlib | 3.11.2 | licence PSF/Matplotlib (permissive) | oui |
| mpmath | 1.3.0 | BSD | oui |
| networkx | 3.7 | BSD-3-Clause | oui |
| numpy | 2.5.4 | BSD-3-Clause et licences permissives (0BSD, MIT, Zlib, CC0) | oui |
| packaging | 26.3 | Apache-2.0 ou BSD-2-Clause | oui |
| pillow | 13.0.0 | MIT-CMU (type HPND, permissive) | oui |
| pyparsing | 3.3.3 | MIT | oui |
| pyqt6 | 6.11.0 | GPL-3.0-only | oui, voir remarque |
| pyqt6-qt6 | 6.11.2 | LGPL v3 (bibliothèques Qt) | oui |
| pyqt6-sip | 13.13.0 | BSD-2-Clause | oui |
| python-dateutil | 3.0.0 | BSD et Apache-2.0 | oui |
| six | 1.17.0 | MIT | oui |
| sympy | 1.14.0 | BSD | oui |
| tzdata | 2026.5 | Apache-2.0 | oui |

## Analyse de compatibilité

- **Licences permissives** (MIT, BSD, PSF, Apache-2.0, HPND) : compatibles avec la GPL v3 (Apache-2.0 l'est avec la v3, pas avec la v2).
- **Exudyn** : le texte de `LICENSE.txt` est une BSD à trois clauses (copyright Johannes Gerstmayr, Université d'Innsbruck). L'identifiant SPDX déclaré est un `LicenseRef` propre, d'où une lecture du texte plutôt qu'une simple correspondance de nom. Obligation : reproduire l'avis et la clause de non-garantie dans la documentation d'une distribution binaire ; l'exécutable embarque ce fichier dans `licences/exudyn/`.
- **PyQt6** : GPL-3.0-only. Meca3D, qui l'importe, ne peut être distribué que sous GPL v3 : la mention « ou ultérieure » de notre propre code reste vraie pour nos fichiers, mais l'ensemble distribué avec PyQt6 relève de la v3. Compatible, aucune action requise.
- **Qt (pyqt6-qt6)** : LGPL v3, liaison dynamique (DLL séparées dans le dossier de l'exécutable, remplaçables) ; le code source de Qt est disponible sur qt.io.
- **Icônes Tabler** (`src/meca3d/ihm/icones/`, version 3.19.0, copiées au lot 13) : MIT, avis reproduit dans `src/meca3d/ihm/icones/LICENSE`, embarqué avec les icônes dans l'exécutable. Compatible, aucune action requise.
- **PyInstaller** (outil de construction, non distribué comme dépendance d'exécution) : GPL v2 ou ultérieure avec exception pour les programmes produits ; l'exécutable obtenu n'est pas soumis à une autre contrainte que celles ci-dessus.

Limite : la reconnaissance est automatique (motifs sur les métadonnées) et s'appuie sur les déclarations des paquets ; elle ne remplace pas un avis juridique. À refaire à chaque changement de dépendance.

## Distribution binaire

Le dossier de l'exécutable (EX-63) contient `licences/` : `LICENSE`, ce fichier et les fichiers de licence d'Exudyn, NumPy, Matplotlib, PyQt6, NetworkX et SymPy.
