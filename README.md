# BEG-Antrags-Software

Software, die Immobilienbesitzer und eine begleitende Beraterfirma durch den
BEG-Förderantragsprozess für energetische Sanierungen führt: Gebäudedaten per KI
erfassen, Fördersätze regelbasiert (nicht per KI) berechnen und die beiden
anspruchsvollsten Freitextfelder des Antrags automatisiert generieren.

**Kein Formular-Ausfüller** — die strukturierten Antragsdaten trägt der Antragsteller
weiterhin selbst ein. Die Plattform übernimmt gezielt den Teil, an dem Antragsteller
tatsächlich scheitern: die technisch-bürokratischen Beschreibungstexte.

**Stack:** Python, FastAPI, PostgreSQL/SQLite, SQLAlchemy · LLM-gestützte
Datenextraktion & Textgenerierung (OpenAI, Ziel Claude) · Langfuse-Observability

**Projektstand:** Phase 0: FastAPI-Backend mit Datenmodell (Systemarchitektur
Abschnitt 7), Alembic-Migrationen, Auth + Rollen (Modul 10) und CRUD für Objekt/Fall
(Modul 1). Noch ohne LLM-Anbindung, Fördersatz-Engine oder Antragstext-Generator.
Umsetzung als Capstone-Projekt der Masterschool AI-Engineering-Ausbildung.

**Eigenständiges Projekt** — eigene `.venv`, eigenes `uv.lock`.

## Setup

1. `.env.example` nach `.env` kopieren
2. In diesem Ordner: `uv sync` (erstellt `.venv` lokal)
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

---

## License

Copyright (c) 2026 Erdinç Arslan. All rights reserved.
This repository and its contents are published publicly for showcase and
evaluation purposes only. No license is granted to use, copy, modify, merge,
publish, distribute, sublicense, or sell any part of this software or its
documentation. Viewing the source for evaluation is permitted; all other
rights are reserved by the copyright holder.
For licensing inquiries, contact the copyright holder.
