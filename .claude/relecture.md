# Contrôles propres au projet
- Aucun import d'exudyn hors de `src/meca3d/moteur/`, de PyQt6 hors de `src/meca3d/ihm/`, ni de socket hors de `src/meca3d/cao/`.
- Aucune conversion d'unités (`/ 1000`, `radians`, `degrees`) hors de `unites.py`.
- Les valeurs de référence des tests sont celles de SPEC.md (EX-xx), avec une tolérance égale ou plus stricte.
- La solution de référence Newton-Euler (`tests/reference_bielle.py`) est indépendante d'Exudyn.
- Le réglage `spectralRadius` reste à 0.9 ; tout changement est justifié par un test.
- Les lois d'entrée ne passent jamais par `eval`, `exec` ni `sympify` sur du texte non vérifié par la liste blanche `ast`.
- Les fixtures ne contiennent ni jeton, ni chemin personnel, ni fichier de `decade_archive/`.
- L'animation restaure toujours la pose initiale de la maquette (bloc `finally`) et n'enregistre jamais la maquette.
