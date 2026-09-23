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
(Modul 1), Maßnahmenplanung (Modul 2), Fördersatz-Engine für KfW 458 (nach
KfW-Merkblatt 07/2026) + BEG EM mit Typprüfung und „ein Programm pro Maßnahme“ (Modul 3), LLM-Extraktion aus Energieausweisen
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
POST /cases/{id}/measures              {"typ": "waermepumpe_luft", "jaz": "3.5", "alte_heizung_art": "oel", "alte_heizung_inbetriebnahme": "2001-05-01", "alte_heizung_funktionstuechtig": true}
POST /cases/{id}/measures              {"typ": "daemmung"}
POST /cases/{id}/funding/kfw-458       {"foerderfaehige_kosten": "...", "ist_selbstnutzer": true, "haushaltsjahreseinkommen": ..., "kind_im_haushalt": false, "measure_id": "<Waermepumpe>"}
POST /cases/{id}/funding/beg-em        {"foerderfaehige_kosten": "...", "hat_isfp": false, "measure_id": "<Daemmung>"}
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

**Förderberechnung (Stand Merkblatt KfW 458, 07/2026):** `measure_id` ist Pflicht.
KfW 458 nur für Wärmeerzeuger, BEG EM nur für Dämmung/Fenster/Lüftung (Liste
`zulaessige_massnahmen` im Regelsatz), sonst `422`. Für Selbstnutzer sind
`haushaltsjahreseinkommen` und die `alte_heizung_*`-Angaben an der Maßnahme Pflicht
(`422`), für Nicht-Selbstnutzer nicht. Der KfW-Regelsatz gilt bis 31.01.2027
(Degression) — ab 01.02.2027 antwortet die Engine bewusst mit `422`, bis ein
Nachfolger-Regelsatz angelegt ist.

## Tests

```
uv run pytest
```

## Golden Path mit echtem LLM (`scripts/golden_path.py`)

End-to-End-Nachweis gegen einen **laufenden** Server, **ohne Mock**:
login → property → case → document upload → extract → measure → kfw-458 →
texts/generate → texts/review → export/pdf. Gibt je Schritt HTTP-Status und relevante
Werte aus (extrahierte Gebäudedaten, Förderquote/-betrag, Textentwurf) und bricht beim
ersten unerwarteten Status mit klarer Meldung und Exit-Code 1 ab.

```
docker compose up --build -d
docker compose exec api uv run --no-sync python -m scripts.seed_demo_data
uv run python -m scripts.erzeuge_test_energieausweis energieausweis_test.pdf
uv run python -m scripts.golden_path --pdf energieausweis_test.pdf
```

Optionen: `--basis-url` (Standard `http://127.0.0.1:8000`), `--email`/`--passwort`
(Standard: Demo-Nutzer), `--ausgabe` (Ziel des PDF-Exports), `--timeout`.

- **Kein API-Schlüssel im Skript.** Es spricht nur mit der eigenen API; den OpenAI- und
  Langfuse-Zugang hat ausschließlich der Server über `.env`. Die Schritte `extract` und
  `texts/generate` lösen dort **echte, kostenpflichtige** LLM-Aufrufe aus.
- Das Test-PDF ist **synthetisch** (fiktive Daten). Sollwerte der Extraktion: Baujahr
  1978, 1 Wohneinheit, 182 kWh/(m²a), Klasse F.
- Schritt 9 reicht den Entwurf unverändert als Endfassung ein. Das belegt nur den
  technischen Ablauf, **keinen** inhaltlichen Review.
- `tests/test_golden_path_script.py` prüft die Ablauflogik des Skripts mit **gemocktem**
  LLM. Das ersetzt nicht den echten Lauf.

---

## License

Copyright (c) 2026 Erdinç Arslan. All rights reserved.
This repository and its contents are published publicly for showcase and
evaluation purposes only. No license is granted to use, copy, modify, merge,
publish, distribute, sublicense, or sell any part of this software or its
documentation. Viewing the source for evaluation is permitted; all other
rights are reserved by the copyright holder.
For licensing inquiries, contact the copyright holder.
