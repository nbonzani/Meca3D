# PLAN — Meca3D v1

*Le 24 octobre 2026. Chaque lot tient en une session. Tests d'abord, commités avant le code. Sortie commune à tous les lots : pytest vert, ruff 0, pyright 0, PROGRESS.md à jour.*

| Lot | Exigences | Fichiers | Tests d'abord | Critère de sortie | Statut |
|---|---|---|---|---|---|
| 0 | — | squelette `src/meca3d/`, pyproject, CI, kit dépôt | `test_fumee.py` | `uv run pytest`, `ruff check`, `pyright` verts ; CI GitHub verte | fait (CI à vérifier après le premier push) |
| 1a | Q1, D9 | `prototypes/levee_risques/moteur_*.py`, RESULTATS.md | essais chiffrés de EX-14, EX-15, EX-16 (valeurs de la SPEC) | engrenage, vis-écrou, hélicoïdale, Coulomb (glissière et pivot) et rendement : chacun conforme à son critère ou déclaré en échec ; annulation d'un `SolveDynamic` dans un processus en < 1 s ; décision écrite dans ARCHITECTURE.md | à faire |
| 1b | Q2 à Q6 | `prototypes/levee_risques/solidcraft_*.py`, `exe_*`, RESULTATS.md | réponses `joint.list` enregistrées (couplages, sous-assemblages) ; exécutable de test | forme des couplages et des sous-occurrences connue ; animation `joint.drive` / `occurrence.move` comparée (cadence, fidélité) ; `motion.trace.keep` éprouvé ; exécutable PyInstaller avec Exudyn, PyQt6 et un processus `spawn` lancé sur le runner windows-latest | à faire |
| 2 | EX-04 (fixtures), EX-05, EX-30, EX-31, EX-40, EX-62 (partiel), EX-52 (CSV) | `unites.py`, `modele/solide.py`, `modele/liaison.py` (pivot, glissière, linéaire annulaire), `modele/actions.py`, `moteur/base.py`, `moteur/exudyn_dyn.py`, `cao/urdf.py`, `cli.py` | `test_unites.py`, `test_lois.py`, `test_bielle_dyn.py` (référence Newton-Euler) | **tranche verticale** : `meca3d simuler` sur la fixture bielle → CSV, écart ≤ 5·10⁻³ | fait |
| 3 | EX-10, EX-11 (modèle), EX-12, EX-13, EX-60 | `modele/liaison.py`, `modele/couplage.py` (données), `modele/capteurs.py`, `modele/etude.py`, `moteur/exudyn_dyn.py` | `test_catalogue_liaisons.py` (invariants des 11 liaisons), `test_base_liaison.py`, `test_etude_fichier.py` | 11 liaisons conformes (hélicoïdale selon le lot 1a) ; aller-retour `.meca3d` identique | fait sauf 2 tests à corriger (cf. PROGRESS) |
| 4 | EX-20, EX-21, EX-22, EX-23 (calcul) | `graphe/graphe.py`, `graphe/mobilite.py` | `test_graphe.py`, `test_mobilite.py` (5 cas du tableau EX-21) | Ic, rc, m et h exacts ; ddl redondants désignés pour h = 3 | à faire |
| 5 | EX-01 à EX-06 | `cao/canal.py`, `cao/solidcraft.py`, `tests/faux_serveur.py`, fixtures de réponses | `test_canal.py`, `test_import_solidcraft.py` ; test `@solidcraft` réel | import depuis le faux serveur conforme ; messages d'erreur d'EX-01 et EX-02 ; test réel passé à la main | à faire |
| 6 | EX-32, EX-33, EX-41, EX-23 (simulation), EX-50, EX-51 | `moteur/exudyn_dyn.py`, `moteur/cinematique.py`, `resultats/torseurs.py`, `resultats/capteurs.py` | `test_ressort.py`, `test_cinematique.py`, `test_torseurs.py`, `test_capteurs_point.py` | critères chiffrés d'EX-32, EX-33, EX-41, EX-50 et EX-51 ; `test_bout_en_bout.py` vert | à faire |
| 7 | EX-14, EX-15, EX-16, hélicoïdale | `moteur/couplages.py`, `moteur/exudyn_dyn.py`, `modele/couplage.py`, `cao/solidcraft.py` (lecture des couplages) | `test_reducteur.py`, `test_vis_ecrou.py`, `test_coulomb.py`, `test_rendement.py` | critères chiffrés d'EX-14 à EX-16 (ou report en V2, décidé au lot 1a) | à faire |
| 8 | EX-11 (IHM), EX-42, EX-43, EX-61 | `ihm/fenetre.py`, `ihm/arbre.py`, `ihm/proprietes.py`, `ihm/vue_graphe.py`, `moteur/processus.py`, `__main__.py` | `test_ihm_arbre.py` (pytest-qt), `test_processus.py` (annulation < 1 s, erreur remontée) | import → validation → graphe → simulation lancée depuis l'IHM, annulable | à faire |
| 9 | EX-52 (courbes, CSV), EX-30 à EX-33 (saisie), EX-50, EX-60 (IHM) | `ihm/vue_courbes.py`, `ihm/vue_torseurs.py`, `ihm/proprietes.py`, `resultats/export.py` | `test_export_csv.py`, `test_ihm_saisie.py` | scénario EX-52 relu par Excel en français ; étude enregistrée puis rouverte depuis l'IHM | à faire |
| 10 | EX-53, EX-52 (trajectoires) | `cao/animation.py`, `ihm/fenetre.py` | `test_animation.py` (faux serveur : séquence de commandes, restauration de la pose) | cadence ≥ 20 images/s et pose restaurée, mesurées sur le vrai SolidCraft | à faire |
| 11 | EX-44, cas tests de la SPEC | `tests/fixtures/{pendule_simple,pendule_double,reducteur,vis_ecrou}/`, `tests/test_cas_reference.py` | tests des cas de référence (T₀ = 1,03625 s, T(30°) = 1,05429 s, ω_bas = 3,13863 rad/s, réducteur, vis-écrou) | les quatre maquettes construites dans SolidCraft, exportées en fixtures, conformes ; temps de la bielle < 10 s | à faire |
| 12 | EX-63, EX-64 | `.github/workflows/release.yml`, `meca3d.spec`, LICENSE, en-têtes SPDX | `test_exe.py` (CSV identique au mode source) | exécutable construit par la CI ; release de test publiée **après accord explicite** | à faire |

## Parallélisation (worktrees)

- **1a ∥ 1b** : aucun fichier commun.
- **4 ∥ 5** : après le lot 3, qui gèle `modele/`.
- **10 ∥ 11** : après le lot 9.
- Les lots 6 et 7 touchent tous deux `moteur/exudyn_dyn.py` : ils se font l'un après l'autre.

## Décisions à valider pendant la réalisation

- **Fin du lot 1a** : maintien ou report en V2 d'EX-14, EX-15 et EX-16, selon les essais.
- **Fin du lot 1b** : mode d'animation (Q3) et traitement des sous-assemblages (Q6).
- **Lot 12** : publication de la première release.
