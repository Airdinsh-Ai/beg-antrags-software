# BEG-Antrags-Software

Lauffähiges Grundgerüst (Phase 0, Schritt 1) — FastAPI-App mit einem `/health`-Endpunkt.
Noch ohne Datenmodell, Auth oder Fachmodule.

**Eigenständiges Projekt** — eigene `.venv`, eigenes `uv.lock`, kein Member des
uv-Workspace im Repo-Root. Bewusst isoliert, siehe `Basics/Documente Projekt/sitzungen/`.

## Setup

1. `.env.example` nach `.env` kopieren
2. In diesem Ordner: `uv sync` (erstellt `.venv` lokal, unabhängig von der Root-venv)
3. Starten:
   - lokal: `uv run python -m uvicorn app.main:app --reload`
     (`uv run uvicorn ...` kann unter Windows von einer
     Anwendungssteuerungsrichtlinie blockiert werden — `python -m uvicorn` umgeht das)
   - oder mit Docker: `docker compose up --build`

`GET /health` liefert `{"status": "ok"}`.

## Tests

```
uv run pytest
```
