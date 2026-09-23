"""Golden Path gegen einen laufenden Server - echter End-to-End-Durchlauf inkl. LLM.

Ablauf: login -> property -> case -> document upload -> extract -> measure ->
kfw-458 -> texts/generate -> texts/review -> export/pdf. Gibt je Schritt den
HTTP-Status und die relevanten Werte aus und bricht beim ersten unerwarteten
Status mit klarer Meldung ab (Exit-Code 1).

Enthaelt bewusst KEINEN API-Schluessel: Das Skript spricht nur mit der eigenen
API. Den OpenAI-/Langfuse-Zugang hat ausschliesslich der Server (.env). Die
Schritte extract und texts/generate kosten dort echte LLM-Aufrufe.

Aufruf (Server laeuft, Demo-Nutzer per scripts.seed_demo_data angelegt):
    uv run python -m scripts.golden_path --pdf pfad/zum/energieausweis.pdf
Synthetisches Test-PDF erzeugen:
    uv run python -m scripts.erzeuge_test_energieausweis energieausweis_test.pdf
"""

import argparse
import sys
from pathlib import Path

import httpx


class SchrittFehler(Exception):
    pass


def _pruefe(nr: int, name: str, response: httpx.Response, erwartet: int) -> httpx.Response:
    if response.status_code != erwartet:
        try:
            detail = response.json().get("detail", response.text)
        except ValueError:
            detail = response.text
        raise SchrittFehler(
            f"Schritt {nr} ({name}) fehlgeschlagen: HTTP {response.status_code}, "
            f"erwartet {erwartet}.\n  Detail: {str(detail)[:600]}"
        )
    print(f"[{nr:>2}] {name:<38} HTTP {response.status_code}  OK")
    return response


def _kurz(text: str, laenge: int = 160) -> str:
    text = " ".join(text.split())
    return text if len(text) <= laenge else text[:laenge] + " ..."


def durchlauf(args: argparse.Namespace, http: httpx.Client | None = None) -> None:
    """`http` nur fuer Tests (FastAPI-TestClient), sonst echter Client gegen --basis-url."""
    pdf = Path(args.pdf)
    if not pdf.is_file():
        raise SchrittFehler(f"Test-PDF nicht gefunden: {pdf}")

    if http is None:
        # LLM-Schritte koennen mit Retry/Backoff laenger dauern.
        with httpx.Client(base_url=args.basis_url, timeout=args.timeout) as client:
            _schritte(args, pdf, client)
    else:
        _schritte(args, pdf, http)

    print("\nGolden Path vollstaendig durchlaufen (10/10).")


def _schritte(args: argparse.Namespace, pdf: Path, http: httpx.Client) -> None:
    r = _pruefe(1, "POST /auth/login", http.post(
        "/auth/login", json={"email": args.email, "password": args.passwort}), 200)
    http.headers["Authorization"] = f"Bearer {r.json()['access_token']}"

    prop = _pruefe(2, "POST /property", http.post("/property", json={
        "person": {"name": "Golden-Path-Testperson", "kontakt": "test@example.com"},
        "building": {"adresse": args.adresse},
        "ownership": {"von": "2015-01-01"},
    }), 201).json()

    case = _pruefe(3, "POST /cases", http.post("/cases", json={
        "building_id": prop["building_id"], "ownership_id": prop["ownership_id"],
    }), 201).json()
    cid = case["id"]
    print(f"     case_id = {cid}")

    _pruefe(4, "POST /cases/{id}/documents", http.post(
        f"/cases/{cid}/documents",
        data={"typ": "energieausweis", "retention_class": "foerderrechtlich"},
        files={"datei": (pdf.name, pdf.read_bytes(), "application/pdf")},
    ), 201)

    extrakt = _pruefe(5, "POST /cases/{id}/extract  [LLM]", http.post(
        f"/cases/{cid}/extract"), 200).json()
    print(f"     extrahiert: baujahr={extrakt['baujahr']}, wohneinheiten={extrakt['wohneinheiten']}, "
          f"verbrauch={extrakt['energieverbrauch_kwh_pro_m2a']} kWh/(m2a), "
          f"klasse={extrakt['energieeffizienzklasse']}")

    mid = _pruefe(6, "POST /cases/{id}/measures", http.post(f"/cases/{cid}/measures", json={
        "typ": "waermepumpe_luft", "jaz": "3.5",
        "alte_heizung_art": "oel", "alte_heizung_inbetriebnahme": "2001-05-01",
        "alte_heizung_funktionstuechtig": True,
    }), 201).json()["id"]

    f = _pruefe(7, "POST /cases/{id}/funding/kfw-458", http.post(
        f"/cases/{cid}/funding/kfw-458", json={
            "measure_id": mid, "foerderfaehige_kosten": "35000", "ist_selbstnutzer": True,
            "haushaltsjahreseinkommen": 25000, "kind_im_haushalt": False,
        }), 200).json()
    print(f"     quote={f['foerderquote']} (max {f['max_quote']}), klimabonus={f['klimabonus_angewendet']}, "
          f"einkommensbonus={f['einkommensbonus']}, betrag={f['foerderbetrag']} EUR, "
          f"regelversion={f['regelversion']}")

    entwurf = _pruefe(8, "POST /cases/{id}/texts/generate  [LLM]", http.post(
        f"/cases/{cid}/texts/generate", json={"measure_id": mid}), 201).json()
    print(f"     freigegeben={entwurf['freigegeben']}")
    print(f"     massnahmenbeschreibung: {_kurz(entwurf['massnahmenbeschreibung_entwurf'])}")
    print(f"     energetischer_mehrwert: {_kurz(entwurf['energetischer_mehrwert_entwurf'])}")

    # Hier reicht das Skript den Entwurf unveraendert als Endfassung ein. Das
    # belegt nur den technischen Ablauf - KEINEN inhaltlichen Review.
    review = _pruefe(9, "POST /cases/{id}/texts/review", http.post(
        f"/cases/{cid}/texts/review", json={
            "measure_id": mid,
            "massnahmenbeschreibung": entwurf["massnahmenbeschreibung_entwurf"],
            "energetischer_mehrwert": entwurf["energetischer_mehrwert_entwurf"],
        }), 200).json()
    print(f"     freigegeben={review['freigegeben']}, reviewed_at={review['reviewed_at']}")

    r = _pruefe(10, "GET /cases/{id}/texts/export/pdf", http.get(
        f"/cases/{cid}/texts/export/pdf", params={"measure_id": mid}), 200)
    if not r.content.startswith(b"%PDF-"):
        raise SchrittFehler("Schritt 10: Antwort ist kein PDF.")
    ausgabe = Path(args.ausgabe)
    ausgabe.write_bytes(r.content)
    print(f"     PDF gespeichert: {ausgabe} ({len(r.content)} Bytes)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Golden Path gegen einen laufenden Server (echtes LLM).")
    parser.add_argument("--pdf", required=True, help="Energieausweis-PDF fuer Upload und Extraktion")
    parser.add_argument("--basis-url", default="http://127.0.0.1:8000", help="Basis-URL des Servers")
    parser.add_argument("--email", default="berater@example.com", help="Login (Demo-Nutzer)")
    parser.add_argument("--passwort", default="demo-passwort-123", help="Passwort (Demo-Nutzer)")
    parser.add_argument("--adresse", default="Musterweg 12, 12345 Beispielstadt", help="Gebaeudeadresse")
    parser.add_argument("--ausgabe", default="antragstext_export.pdf", help="Zielpfad fuer den PDF-Export")
    parser.add_argument("--timeout", type=float, default=180.0, help="Timeout je Aufruf in Sekunden")
    args = parser.parse_args()

    try:
        durchlauf(args)
    except SchrittFehler as exc:
        print(f"\nABBRUCH - {exc}", file=sys.stderr)
        sys.exit(1)
    except httpx.TransportError as exc:
        print(f"\nABBRUCH - Server unter {args.basis_url} nicht erreichbar: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
