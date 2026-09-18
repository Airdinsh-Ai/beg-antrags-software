# BEG-Antrags-Software – Protokoll

## 2026-09-18

### Ausgangsstand (noch nicht committet)
- Letzter Commit `32e46b9`: Grundgerüst FastAPI, Docker, eigenständiges uv-Projekt.
- Seitdem lokal aufgebaut, aber ungesichert:
  - Alembic-Setup (`alembic.ini`, `alembic/`).
  - Auth/Access-Schicht: `app/core/auth.py`, `app/core/access.py`, `app/core/security.py`.
  - Models: `app/models/` (building, case, document, funding, ownership, person, user).
  - Modul `app/modules/property/` (routes, service).
  - Schemas: `app/schemas/` (auth, property).
  - Seed-Script: `scripts/seed_demo_data.py`.
  - Tests: `tests/conftest.py`, test_access, test_auth, test_models, test_property, test_health.
  - Angepasst: `.env.example`, `Dockerfile`, `README.md`, `app/core/config.py`, `app/core/db.py`, `app/main.py`, `pyproject.toml`, `uv.lock`.

### Offen
- Nichts von alledem ist bisher committet.
- PROTOKOLL.md für dieses Projekt fehlte bisher komplett – hiermit angelegt.
