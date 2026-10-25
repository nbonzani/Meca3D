# Meca3D

Outil pédagogique de mécanique des solides indéformables. L'élève part d'une maquette
[SolidCraft](https://solidcraft.io), choisit les liaisons normalisées, obtient le graphe des liaisons,
la mobilité et l'hyperstatisme, simule le mécanisme avec [Exudyn](https://github.com/jgerstmayr/EXUDYN)
et lit les torseurs de liaison. La démarche s'inspire de Decade (Thomas Paviot).

Statut : en développement (voir `docs/PLAN.md`). Licence : GPL v3 ou ultérieure.

    uv sync
    uv run pytest -q
    uv run python -m meca3d
