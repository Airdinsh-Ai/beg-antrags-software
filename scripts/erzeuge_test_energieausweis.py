"""Erzeugt einen SYNTHETISCHEN Energieausweis als PDF (fiktive Daten, kein echtes
Gebaeude) fuer scripts.golden_path.

Sollwerte fuer die Extraktion: Baujahr 1978, 1 Wohneinheit, 182 kWh/(m2a), Klasse F.

    uv run python -m scripts.erzeuge_test_energieausweis energieausweis_test.pdf
"""

import sys

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table

SOLLWERTE = {
    "baujahr": 1978,
    "wohneinheiten": 1,
    "energieverbrauch_kwh_pro_m2a": 182,
    "energieeffizienzklasse": "F",
}


def erzeuge(ziel: str) -> None:
    st = getSampleStyleSheet()
    breiten = [7 * cm, 8 * cm]
    story = [
        Paragraph("ENERGIEAUSWEIS für Wohngebäude", st["Title"]),
        Paragraph("gemäß den §§ 79 ff. Gebäudeenergiegesetz (GEG) – Verbrauchsausweis", st["Normal"]),
        Paragraph("<i>Synthetisches Testdokument – fiktive Daten, kein echtes Gebäude.</i>", st["Normal"]),
        Spacer(1, 0.6 * cm),
        Paragraph("Gebäude", st["Heading2"]),
        Table([
            ["Gebäudetyp", "freistehendes Einfamilienhaus"],
            ["Adresse", "Musterweg 12, 12345 Beispielstadt"],
            ["Baujahr Gebäude", str(SOLLWERTE["baujahr"])],
            ["Baujahr Wärmeerzeuger", "2001"],
            ["Anzahl Wohnungen", str(SOLLWERTE["wohneinheiten"])],
            ["Gebäudenutzfläche (AN)", "164 m²"],
            ["Wesentliche Energieträger für Heizung", "Heizöl EL"],
        ], colWidths=breiten),
        Spacer(1, 0.6 * cm),
        Paragraph("Energieverbrauch", st["Heading2"]),
        Table([
            ["Endenergieverbrauch dieses Gebäudes", f"{SOLLWERTE['energieverbrauch_kwh_pro_m2a']} kWh/(m²·a)"],
            ["Primärenergieverbrauch dieses Gebäudes", "200 kWh/(m²·a)"],
            ["Energieeffizienzklasse", SOLLWERTE["energieeffizienzklasse"]],
        ], colWidths=breiten),
    ]
    SimpleDocTemplate(ziel, pagesize=A4, topMargin=2 * cm).build(story)


def main() -> None:
    ziel = sys.argv[1] if len(sys.argv) > 1 else "energieausweis_test.pdf"
    erzeuge(ziel)
    print(f"{ziel} erzeugt. Sollwerte: {SOLLWERTE}")


if __name__ == "__main__":
    main()
