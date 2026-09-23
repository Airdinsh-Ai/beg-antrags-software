"""Regelwerk-Versionierung (Systemarchitektur Abschnitt 6): Auswahl am Stichtag,
Ueberlappungs-/Lueckenpruefung, strikte Dateien, Regel-Hash.

Die Regelwechsel-Tests arbeiten mit Test-Regelsaetzen in tmp_path, nicht mit
echten Altwerten - die Foerdersaetze vor dem 21.07.2026 sind nicht geprueft.
"""

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
import yaml

from app.models.funding import ProgrammTyp
from app.modules.funding import ruleset
from app.modules.funding.service import calculate_kfw458
from tests.test_funding import _create_case


def _echte_datei(name: str) -> dict:
    return yaml.safe_load((ruleset.RULES_DIR / name).read_text(encoding="utf-8"))


def _schreibe(pfad: Path, daten: dict) -> None:
    pfad.write_text(yaml.safe_dump(daten, allow_unicode=True), encoding="utf-8")


@pytest.fixture()
def regelwechsel_dir(tmp_path) -> Path:
    """Echte Regelsaetze plus ein fiktiver KfW-458-Vorgaenger (01.01.-20.07.2026)
    mit abweichender Grundfoerderung, damit die Auswahl im Ergebnis sichtbar ist."""
    _schreibe(tmp_path / "beg_em.yaml", _echte_datei("beg_em_2026-07-21.yaml"))

    neu = _echte_datei("kfw458_2026-07-21.yaml")
    _schreibe(tmp_path / "kfw458_neu.yaml", neu)

    alt = yaml.safe_load(yaml.safe_dump(neu))
    alt["regelwerk"].update(
        version="kfw458-test-alt", gueltig_ab=date(2026, 1, 1), gueltig_bis=date(2026, 7, 20)
    )
    alt["regeln"]["grundfoerderung"] = "0.25"
    _schreibe(tmp_path / "kfw458_alt.yaml", alt)
    return tmp_path


def _aendere_alt(verzeichnis: Path, **kopf) -> None:
    pfad = verzeichnis / "kfw458_alt.yaml"
    daten = yaml.safe_load(pfad.read_text(encoding="utf-8"))
    daten["regelwerk"].update(kopf)
    _schreibe(pfad, daten)


# --- Echtes Regelwerk ---------------------------------------------------------


def test_echtes_regelwerk_laedt_beide_programme():
    regelwerk = ruleset.lade_regelwerk()
    assert set(regelwerk) == {ProgrammTyp.KFW_458, ProgrammTyp.BEG_EM}


def test_stichtag_vor_der_reform_hat_keinen_regelsatz():
    with pytest.raises(ruleset.KeinRegelsatzFehler, match="20.07.2026"):
        ruleset.waehle_regelsatz(ProgrammTyp.BEG_EM, date(2026, 7, 20))


# --- Auswahl am Stichtag ------------------------------------------------------


def test_auswahl_nach_stichtag_nicht_nach_neuester_datei(regelwechsel_dir):
    regelwerk = ruleset.lade_regelwerk(regelwechsel_dir)

    letzter_alter_tag = ruleset.waehle_regelsatz(ProgrammTyp.KFW_458, date(2026, 7, 20), regelwerk)
    erster_neuer_tag = ruleset.waehle_regelsatz(ProgrammTyp.KFW_458, date(2026, 7, 21), regelwerk)

    assert letzter_alter_tag.kopf.version == "kfw458-test-alt"
    assert erster_neuer_tag.kopf.version == "kfw458-2026-07-21"


def test_stichtag_vor_erstem_regelsatz_wirft_fehler(regelwechsel_dir):
    regelwerk = ruleset.lade_regelwerk(regelwechsel_dir)
    with pytest.raises(ruleset.KeinRegelsatzFehler):
        ruleset.waehle_regelsatz(ProgrammTyp.KFW_458, date(2025, 12, 31), regelwerk)


def test_berechnung_nutzt_regelsatz_des_stichtags(regelwechsel_dir, monkeypatch):
    regelwerk = ruleset.lade_regelwerk(regelwechsel_dir)
    monkeypatch.setattr(ruleset, "aktuelles_regelwerk", lambda: regelwerk)

    kwargs = dict(
        foerderfaehige_kosten=Decimal("10000"), haushaltsjahreseinkommen=100_000, ist_selbstnutzer=True
    )
    alt = calculate_kfw458(**kwargs, stichtag=date(2026, 7, 20))
    neu = calculate_kfw458(**kwargs, stichtag=date(2026, 7, 21))

    assert alt["foerderquote"] == Decimal("0.41")  # 25 + 16, fiktiver Vorgaenger
    assert neu["foerderquote"] == Decimal("0.46")  # 30 + 16, echter Regelsatz
    assert alt["regel_hash"] != neu["regel_hash"]


# --- Pruefung beim Laden (Startabbruch) ---------------------------------------


def test_ueberlappende_zeitraeume_werden_abgelehnt(regelwechsel_dir):
    _aendere_alt(regelwechsel_dir, gueltig_bis=date(2026, 7, 21))
    with pytest.raises(ruleset.RegelwerkFehler, match="Ueberlappung"):
        ruleset.lade_regelwerk(regelwechsel_dir)


def test_offener_vorgaenger_gilt_als_ueberlappung(regelwechsel_dir):
    # Vorgaenger ohne gueltig_bis = nicht abgeloest -> zwei gleichzeitig gueltig
    _aendere_alt(regelwechsel_dir, gueltig_bis=None)
    with pytest.raises(ruleset.RegelwerkFehler, match="Ueberlappung"):
        ruleset.lade_regelwerk(regelwechsel_dir)


def test_luecke_zwischen_regelsaetzen_wird_abgelehnt(regelwechsel_dir):
    _aendere_alt(regelwechsel_dir, gueltig_bis=date(2026, 7, 10))
    with pytest.raises(ruleset.RegelwerkFehler, match="Luecke"):
        ruleset.lade_regelwerk(regelwechsel_dir)


def test_gueltig_bis_vor_gueltig_ab_wird_abgelehnt(regelwechsel_dir):
    _aendere_alt(regelwechsel_dir, gueltig_ab=date(2026, 7, 20), gueltig_bis=date(2026, 7, 1))
    with pytest.raises(ruleset.RegelwerkFehler, match="vor gueltig_ab"):
        ruleset.lade_regelwerk(regelwechsel_dir)


def test_vertippter_schluessel_wird_abgelehnt(regelwechsel_dir):
    pfad = regelwechsel_dir / "kfw458_alt.yaml"
    daten = yaml.safe_load(pfad.read_text(encoding="utf-8"))
    daten["regeln"]["grundfoerdrung"] = daten["regeln"].pop("grundfoerderung")
    _schreibe(pfad, daten)
    with pytest.raises(ruleset.RegelwerkFehler, match="kfw458_alt.yaml"):
        ruleset.lade_regelwerk(regelwechsel_dir)


def test_fehlendes_gueltig_ab_wird_abgelehnt(regelwechsel_dir):
    pfad = regelwechsel_dir / "kfw458_alt.yaml"
    daten = yaml.safe_load(pfad.read_text(encoding="utf-8"))
    del daten["regelwerk"]["gueltig_ab"]
    _schreibe(pfad, daten)
    with pytest.raises(ruleset.RegelwerkFehler, match="gueltig_ab"):
        ruleset.lade_regelwerk(regelwechsel_dir)


def test_programm_ohne_regelsatz_wird_abgelehnt(regelwechsel_dir):
    (regelwechsel_dir / "beg_em.yaml").unlink()
    with pytest.raises(ruleset.RegelwerkFehler, match="beg_em"):
        ruleset.lade_regelwerk(regelwechsel_dir)


# --- Regel-Hash ---------------------------------------------------------------


def test_geaenderte_datei_ergibt_anderen_hash(tmp_path):
    pfad = tmp_path / "kfw.yaml"
    daten = _echte_datei("kfw458_2026-07-21.yaml")
    _schreibe(pfad, daten)
    vorher = ruleset._lade_datei(pfad).regel_hash

    daten["regeln"]["klimabonus"] = "0.17"
    _schreibe(pfad, daten)
    assert ruleset._lade_datei(pfad).regel_hash != vorher


def test_hash_unabhaengig_von_zeilenenden(tmp_path):
    inhalt = (ruleset.RULES_DIR / "kfw458_2026-07-21.yaml").read_bytes().replace(b"\r\n", b"\n")
    lf, crlf = tmp_path / "lf.yaml", tmp_path / "crlf.yaml"
    lf.write_bytes(inhalt)
    crlf.write_bytes(inhalt.replace(b"\n", b"\r\n"))
    assert ruleset._lade_datei(lf).regel_hash == ruleset._lade_datei(crlf).regel_hash


# --- API ----------------------------------------------------------------------


def test_api_stichtag_ohne_regelsatz_gibt_422(client, auth_headers):
    case = _create_case(client, auth_headers)
    response = client.post(
        f"/cases/{case['id']}/funding/kfw-458",
        json={"foerderfaehige_kosten": "10000", "haushaltsjahreseinkommen": 100000, "stichtag": "2026-07-15"},
        headers=auth_headers,
    )
    assert response.status_code == 422
    assert "Kein gueltiger Regelsatz" in response.json()["detail"]


def test_api_ohne_stichtag_gilt_anlagedatum_des_falls(client, auth_headers):
    case = _create_case(client, auth_headers)
    response = client.post(
        f"/cases/{case['id']}/funding/beg-em",
        json={"foerderfaehige_kosten": "10000"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["stichtag"] == case["created_at"][:10]


def test_rulesets_endpoint_zeigt_gueltigkeitszeitraum(client, auth_headers):
    body = client.get("/funding/rulesets", headers=auth_headers).json()
    kfw = next(r for r in body if r["programm"] == "kfw_458")
    assert kfw["gueltig_ab"] == "2026-07-21"
    assert kfw["gueltig_bis"] is None
