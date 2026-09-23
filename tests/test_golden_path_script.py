"""scripts/golden_path.py gegen die App im TestClient - mit GEMOCKTEM LLM.

Prueft nur die Ablauflogik des Skripts (alle 10 Schritte, Abbruch beim ersten
Fehler), nicht die echte LLM-Anbindung. Die belegt nur ein Lauf gegen den
laufenden Server mit gueltigem OpenAI-Zugang.
"""

import argparse

import pytest

from app.llm.client import Antragstexte, EnergieausweisDaten, LLMAufrufFehler
from scripts.erzeuge_test_energieausweis import erzeuge
from scripts.golden_path import SchrittFehler, durchlauf


@pytest.fixture()
def args(tmp_path, berater_user) -> argparse.Namespace:
    pdf = tmp_path / "energieausweis.pdf"
    erzeuge(str(pdf))
    return argparse.Namespace(
        pdf=str(pdf),
        basis_url="http://testserver",
        email=berater_user.email,
        passwort="test-passwort-123",
        adresse="Musterweg 12, 12345 Beispielstadt",
        ausgabe=str(tmp_path / "export.pdf"),
        timeout=10.0,
    )


@pytest.fixture()
def upload_in_tmp(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.config.settings.upload_verzeichnis", str(tmp_path / "uploads"))


def test_skript_durchlaeuft_alle_zehn_schritte(client, args, upload_in_tmp, monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(
        "app.modules.documents.service.extract_energieausweis",
        lambda pdf: EnergieausweisDaten(
            baujahr=1978, wohneinheiten=1, energieverbrauch_kwh_pro_m2a=182, energieeffizienzklasse="F"
        ),
    )
    monkeypatch.setattr(
        "app.modules.documents.antrags_text_service.generate_antragstexte",
        lambda fall: Antragstexte(massnahmenbeschreibung="Beschreibung", energetischer_mehrwert="Mehrwert"),
    )

    durchlauf(args, http=client)

    ausgabe = capsys.readouterr().out
    assert "[10] GET /cases/{id}/texts/export/pdf" in ausgabe
    assert "baujahr=1978" in ausgabe
    assert "betrag=22400.00 EUR" in ausgabe  # 86 % -> 80 % von 28.000
    assert "vollstaendig durchlaufen (10/10)" in ausgabe
    assert (tmp_path / "export.pdf").read_bytes().startswith(b"%PDF-")


def test_skript_bricht_beim_ersten_fehler_mit_klarer_meldung_ab(client, args, upload_in_tmp, monkeypatch, capsys):
    def _kein_guthaben(pdf):
        raise LLMAufrufFehler("Error code: 429 - insufficient_quota")

    monkeypatch.setattr("app.modules.documents.service.extract_energieausweis", _kein_guthaben)

    with pytest.raises(SchrittFehler, match=r"(?s)Schritt 5 .*HTTP 502, erwartet 200.*insufficient_quota"):
        durchlauf(args, http=client)
    assert "[ 6]" not in capsys.readouterr().out  # nach dem Fehler kein weiterer Schritt


def test_fehlendes_pdf_bricht_vor_dem_ersten_aufruf_ab(args):
    args.pdf = "gibt-es-nicht.pdf"
    with pytest.raises(SchrittFehler, match="Test-PDF nicht gefunden"):
        durchlauf(args)
