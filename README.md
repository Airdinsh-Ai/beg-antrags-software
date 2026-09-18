# BEG-Antrags-Software

Phase 0: FastAPI-Backend mit Datenmodell (Systemarchitektur Abschnitt 7), Alembic-
Migrationen, Auth + Rollen (Modul 10) und CRUD für Objekt/Fall (Modul 1). Noch ohne
LLM-Anbindung, Fördersatz-Engine oder Antragstext-Generator.

**Eigenständiges Projekt** — eigene `.venv`, eigenes `uv.lock`, kein Member des
uv-Workspace im Repo-Root. Bewusst isoliert, siehe `Basics/Documente Projekt/sitzungen/`.

## Setup

1. `.env.example` nach `.env` kopieren
2. In diesem Ordner: `uv sync` (erstellt `.venv` lokal, unabhängig von der Root-venv)
3. Datenbank-Schema anlegen: `uv run alembic upgrade head`
4. Demo-Nutzer für den manuellen Test anlegen (Phase 0 hat keinen
   Registrierungs-Endpunkt, siehe Systemarchitektur Abschnitt 11):
   `uv run python -m scripts.seed_demo_data` → `berater@example.com` /
   `demo-passwort-123`
5. Starten:
   - lokal: `uv run python -m uvicorn app.main:app --reload`
     (`uv run uvicorn ...` kann unter Windows von einer
     Anwendungssteuerungsrichtlinie blockiert werden — `python -m uvicorn` umgeht das)
   - oder mit Docker: `docker compose up --build` (führt die Alembic-Migration beim
     Start automatisch aus; Demo-Nutzer danach einmalig per
     `docker compose exec api uv run --no-sync python -m scripts.seed_demo_data`)

## Manueller Test (Postman/curl)

```
POST /auth/login          {"email": "berater@example.com", "password": "demo-passwort-123"}
POST /property             {"person": {...}, "building": {...}, "ownership": {...}}
POST /cases                {"building_id": "...", "ownership_id": "..."}
GET  /cases/{id}
```

`Authorization: Bearer <access_token>` aus dem Login-Response bei allen Endpunkten außer
`/health` und `/auth/login`.

## Tests

```
uv run pytest
```
