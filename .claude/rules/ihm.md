---
paths:
  - "src/meca3d/ihm/**"
---
# Règles IHM PyQt6
- Aucune logique métier dans les widgets : appeler modele/, graphe/, resultats/, et moteur/processus.py pour simuler.
- Une simulation passe toujours par moteur/processus.py (processus séparé) ; toute autre opération de plus de 200 ms passe par QThreadPool.
- Signaux et slots typés ; pas de lambda capturant self dans une boucle.
- Textes utilisateur en français, centralisés dans ihm/textes.py ; vocabulaire du cours (classe d'équivalence, liaison normalisée, torseur, loi d'entrée).
- Unités toujours affichées à côté des valeurs.
