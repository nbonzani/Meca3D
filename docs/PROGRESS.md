# Journal de progression

## 2026-10-25 — Lot 4, graphe, mobilité, hyperstatisme (fait)
- Fait : `graphe/graphe.py` (description minimale figée, graphe networkx multigraphe, μ, base de cycles, isolés, bâti fusionné, `depuis_etude`), `graphe/mobilite.py` (Kc par torseurs, rang SVD 1e-9, m, h, `verifier_avant_simulation`, `designer_ddl_redondants`, `liberer`).
- Résultats (Ic, rc, m, h) : bielle pivot/pivot/rotule/glissière 6/5/1/1 ; annulaire z 7/6/1/0 ; annulaire x 7/5/2/1 ; 3 pivots + glissière 4/3/1/3 ; pendule double 2/0/2/0 ; engrenage sur bâti Ic = 2, Ec = 1, m = 1, h = 0.
- Décisions : ddl redondants désignés côté statique (Gram-Schmidt à pivot sur la matrice d'équilibre, couplages retenus d'abord), h statique recoupé avec h cinématique ; hélicoïdale : couplage interne ajouté par `depuis_etude` (rapport nominal) ; style : tri des imports des tests commités (aucune assertion modifiée).
- Vigilance : `depuis_etude` ne lit pas de couplages dans l'étude (paramètre `couplages`), raccord à faire avec le lot 3 ; la fixture bielle est à θ = 0 (position singulière), seuls Ic et Ec y sont testés.
- Prochaine action : lot 5 (IHM du graphe) et raccord avec le lot 3.

## 2026-10-25 — Lot 2, tranche verticale (fait)
- Fait : `unites`, `modele/{solide,liaison,actions,etude}`, `cao/{urdf,solidcraft}` (fonction pure `etude_depuis_reponses`), `moteur/{base,exudyn_dyn}`, `resultats/{torseurs,export}`, `cli simuler`. Fixture `tests/fixtures/bielle/bielle.meca3d` (générée par `generer_etude.py`).
- Résultats : écarts relatifs vs Newton-Euler : O 2,8e-3, A 2,8e-3, B 2,4e-3, couple 4,8e-3, normale 2,4e-3 (seuil 5e-3) ; simulation 1,1 s ; x_B(0) à 60° = 0,3372281 m.
- Décisions : pilote = loi(t) − valeur à l'import (offset relatif à la pose) ; inertie recomposée via l'origine `visual` de l'URDF (URDF écrit à valeurs articulaires nulles) ; `Reglages` défini dans `modele/etude.py`, réexporté par `moteur/base.py` ; CSV : couple moteur `C (N·m)` + torseurs {a→b} en base monde.
- Vigilance : marge de 4 % sur le couple (4,8e-3 pour 5e-3) ; corrections de style (ruff) appliquées aux tests commités, sans changement d'assertion.
- Prochaine action : lots 3 puis 4 ∥ 5.

## 2026-10-24 — Cadrage (fait)
- Fait : SPEC.md (EX-01 à EX-64), ARCHITECTURE.md (D1 à D12), PLAN.md (lots 0 à 12) ; kit dépôt (CLAUDE.md, .claude/, pyproject.toml).
- Décisions : canal de contrôle SolidCraft vérifié en direct (jeton, joint.list en 35 ms, joint.drive en 17 ms) ; couplages, Coulomb et rendements en V1, sous réserve du lot 1a.
- Prochaine action : lot 0.
