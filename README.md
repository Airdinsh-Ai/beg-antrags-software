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
Abschnitt 7), Alembic-Migrationen, Auth + Rollen (Modul 10), CRUD für Objekt/Fall
(Modul 1), Maßnahmenplanung (Modul 2), Fördersatz-Engine für KfW 458 + BEG EM
inkl. 60%-Kumulierungsprüfung (Modul 3), LLM-Extraktion aus Energieausweisen
(Modul 1) und Antragstext-Generator mit Pflicht-Review (Modul 4). Beide
LLM-Aufrufe über OpenAI, instrumentiert mit Langfuse (Systemarchitektur
Abschnitt 4/5). Umsetzung als Capstone-Projekt der Masterschool
AI-Engineering-Ausbildung.

**Eigenständiges Projekt** — eigene `.venv`, eigenes `uv.lock`.

## Setup

1. `.env.example` nach `.env` kopieren, `OPENAI_API_KEY` sowie
   `LANGFUSE_PUBLIC_KEY`/`LANGFUSE_SECRET_KEY`/`LANGFUSE_HOST` eintragen (für
   die LLM-Endpunkte aus Modul 1/4 nötig; ohne gültigen OpenAI-Key
   funktionieren nur die übrigen Endpunkte)
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

## Manueller Test (Postman/curl) — kompletter Ablauf

```
POST /auth/login                       {"email": "berater@example.com", "password": "demo-passwort-123"}
POST /property                         {"person": {...}, "building": {...}, "ownership": {...}}
POST /cases                            {"building_id": "...", "ownership_id": "..."}
POST /cases/{id}/measures              {"typ": "waermepumpe_luft", "jaz": "3.5"}
POST /cases/{id}/funding/kfw-458       {"foerderfaehige_kosten": "...", "haushaltsjahreseinkommen": ..., "ist_selbstnutzer": true, "measure_id": "..."}
POST /cases/{id}/funding/beg-em        {"foerderfaehige_kosten": "...", "hat_isfp": false, "measure_id": "..."}
POST /cases/{id}/documents             multipart: datei=<PDF>, typ=energieausweis, retention_class=...
POST /cases/{id}/extract               (kein Body - liest das zuletzt hochgeladene Energieausweis-Dokument)
POST /cases/{id}/texts/generate        {"measure_id": "..."}
POST /cases/{id}/texts/review          {"measure_id": "...", "massnahmenbeschreibung": "...", "energetischer_mehrwert": "..."}
GET  /cases/{id}/texts/export          ?measure_id=...
GET  /cases/{id}/texts/export/pdf      ?measure_id=...
GET  /cases/{id}
GET  /funding/rulesets
GET  /measures/catalog
```

`Authorization: Bearer <access_token>` aus dem Login-Response bei allen Endpunkten außer
`/health` und `/auth/login`. `funding/kfw-458` und `funding/beg-em` sind reiner
deterministischer Code, brauchen keinen LLM-Zugang. Nur `extract` und `texts/generate`
rufen OpenAI auf — dafür `OPENAI_API_KEY`/`LANGFUSE_*` in `.env` nötig. Interaktive Doku
unter `/docs` (Swagger UI), sobald der Server läuft.

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
