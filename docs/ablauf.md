# Ablauf der BEG-Antrags-Software (Phase 0)

Vom Gebäude bis zum freigegebenen Antragstext. Grün = deterministischer Code,
Orange = LLM-Aufruf (über Langfuse beobachtet), Rot = Prüfung, die abbrechen kann.

```mermaid
flowchart TD
    start(["Berater:in meldet sich an"]) --> prop

    subgraph M1["Modul 1 – Objekt & Fall"]
        prop["POST /property<br/>Gebäude + Eigentümer anlegen"]
        caseN["POST /cases<br/>Förderfall anlegen"]
        prop --> caseN
    end

    subgraph DOK["Dokumente"]
        upload["POST /cases/{id}/documents<br/>Energieausweis-PDF hochladen"]
        extract["POST /cases/{id}/extract<br/>Energieausweis auslesen<br/>→ Baujahr/Wohneinheiten ins Gebäude"]
        upload --> extract
    end

    subgraph M2["Modul 2 – Maßnahmenplanung"]
        catalog["GET /measures/catalog<br/>Maßnahmenkatalog"]
        measure["POST /cases/{id}/measures<br/>Maßnahme anlegen → measure_id<br/>(Wärmeerzeuger: + Altheizung)"]
        catalog --> measure
    end

    subgraph M3["Modul 3 – Fördersatz-Engine (kein LLM)"]
        kfw["POST /cases/{id}/funding/kfw-458<br/>Heizungsförderung"]
        begem["POST /cases/{id}/funding/beg-em<br/>Einzelmaßnahmen"]
        kumul{"Typ passt zum Programm?<br/>Nur ein Programm pro Maßnahme?"}
        kumulFail["422 / 409 – abgelehnt"]
        kfw --> kumul
        begem --> kumul
        kumul -- nein --> kumulFail
    end

    subgraph M4["Modul 4 – Antragstext"]
        gen["POST /cases/{id}/texts/generate<br/>LLM-Entwurf, freigegeben = false"]
        review["POST /cases/{id}/texts/review<br/>Mensch prüft/bearbeitet → freigegeben = true"]
        check{"freigegeben?"}
        blocked["409 – Pflicht-Review steht aus"]
        export["GET /cases/{id}/texts/export<br/>GET …/export/pdf"]
        gen --> review --> check
        check -- ja --> export
        check -- nein --> blocked
    end

    caseN --> upload
    caseN --> catalog
    extract -. "Gebäudedaten" .-> gen
    measure -- "measure_id" --> kfw
    measure -- "measure_id" --> begem
    kumul -. "ja: case_funding gespeichert,<br/>Programm fließt optional in den Text" .-> gen
    measure -- "measure_id" --> gen
    export --> ende(["Text per Copy-Paste ins Förderportal"])

    classDef det fill:#d4edda,stroke:#2e7d32,color:#1b1b1b
    classDef llm fill:#ffe0b2,stroke:#e65100,color:#1b1b1b
    classDef stop fill:#f8d7da,stroke:#c62828,color:#1b1b1b
    class prop,caseN,upload,catalog,measure,kfw,begem,kumul,review,check,export det
    class extract,gen llm
    class kumulFail,blocked stop
```

## Die zwei Kernideen

- **Geld rechnet nie das LLM.** Fördersätze, Boni, Deckel und die Programmzuordnung
  laufen komplett in `app/modules/funding/` (deterministisch, testbar).
- **Kein LLM-Text ohne Mensch.** Jeder Entwurf startet mit `freigegeben = false`;
  Export gibt `409`, bis jemand ihn über `/texts/review` aktiv freigibt
  (`app/modules/documents/antrags_text_service.py`).

Die `measure_id` verbindet beides: Förderberechnung und Antragstext beziehen sich
immer auf dieselbe Maßnahme.
