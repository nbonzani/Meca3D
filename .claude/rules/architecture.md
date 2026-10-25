---
paths:
  - "src/meca3d/**"
---
# Règles d'architecture
- modele/ et graphe/ n'importent ni exudyn, ni PyQt6, ni socket, ni cao/, ni moteur/.
- moteur/ n'importe ni PyQt6 ni cao/. cao/ n'importe ni exudyn ni PyQt6.
- Seules des données sérialisables (dict, listes, tableaux numpy) traversent la frontière du processus de calcul.
- Les erreurs du moteur sont typées (moteur/base.py) et porteuses d'un message pédagogique en français.
- Les nombres magiques physiques (ρ∞ = 0,9, tolérance de rang 1e-9) sont des constantes nommées, référencées à la SPEC ou à l'ARCHITECTURE.
- En-tête de chaque module : `# SPDX-License-Identifier: GPL-3.0-or-later`.
