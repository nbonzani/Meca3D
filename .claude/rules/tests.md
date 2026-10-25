---
paths:
  - "tests/**"
---
# Règles de test
- Un test par critère d'acceptation, nommé test_exNN_<cas>.
- Valeurs de référence issues de SPEC.md, jamais recalculées avec le code testé.
- Données réelles dans tests/fixtures/ (exports SolidCraft, réponses enregistrées du canal de contrôle) ; pas de mocks sauf frontière externe (SolidCraft via tests/faux_serveur.py, horloge).
- Tolérances numériques explicites (pytest.approx(..., rel=...) ou abs=...), égales à celles de la SPEC.
- Tests longs : @pytest.mark.slow. Tests contre le vrai SolidCraft : @pytest.mark.solidcraft (lancés à la main).
- IHM : pytest-qt, qtbot.waitUntil, jamais time.sleep.
