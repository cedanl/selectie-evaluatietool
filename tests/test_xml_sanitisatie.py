"""
Tests voor de XML-sanitisatie in transformatie.py en config_wizard.py.

Dekt twee scenario's:
- _repareer_xlsx: verwijdert illegale XML-tekens uit het ZIP-archief van
  een xlsx, zodat openpyxl het kan inlezen zonder ParseError.
- _saniteer: verwijdert illegale tekens uit celwaarden voordat de config
  wizard ze naar een xlsx schrijft.
"""

import base64
import io
import re
import zipfile

import pandas as pd
import pytest
from openpyxl import Workbook

from config_wizard import _saniteer, exporteer_config_excel
from transformatie import _repareer_xlsx, lees_config

_ILLEGALE_XML_TEKENS = re.compile(rb"[\x00-\x08\x0b\x0c\x0e-\x1f]")


# ---------------------------------------------------------------------------
# Hulpfuncties
# ---------------------------------------------------------------------------


def _maak_xlsx_met_cel(celwaarde) -> bytes:
    """Bouw een minimale xlsx met een header-rij en één datacel."""
    wb = Workbook()
    ws = wb.active
    ws["A1"] = "kolom"
    ws["A2"] = celwaarde
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _injecteer_teken_in_xlsx(raw: bytes, teken: bytes) -> bytes:
    """Injecteer een illegaal teken midden in het eerste XML-bestand in de ZIP.
    Werkt ongeacht de exacte tag-structuur of bestandsnaam."""
    src = zipfile.ZipFile(io.BytesIO(raw))
    buf = io.BytesIO()
    injected = False
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        for item in src.infolist():
            data = src.read(item.filename)
            if not injected and item.filename.endswith(".xml"):
                pos = len(data) // 2
                data = data[:pos] + teken + data[pos:]
                injected = True
            dst.writestr(item, data)
    return buf.getvalue()


def _xml_bevat_illegale_tekens(raw: bytes) -> bool:
    """Controleer of enig XML-bestand in de ZIP illegale tekens bevat
    (na decompressie)."""
    zf = zipfile.ZipFile(io.BytesIO(raw))
    for name in zf.namelist():
        if name.endswith(".xml") and _ILLEGALE_XML_TEKENS.search(zf.read(name)):
            return True
    return False


def _als_upload_uri(raw: bytes) -> str:
    return f"data:application/octet-stream;base64,{base64.b64encode(raw).decode()}"


def _maak_config_xlsx(kolomnaam: str) -> bytes:
    """Maak een minimale config.xlsx met één kolom in het kolommen-blad."""
    config = {
        "koppel_id_kolom": "studentnummer",
        "opleiding": "Test",
        "instellingscode": "",
        "jaar": "2026",
        "blad_naam": "",
        "header_rij": "1",
        "totaalscore_kolom": "",
        "kolommen": [
            {
                "meenemen": True,
                "kolom_naam": kolomnaam,
                "instrument": "Test",
                "item": "Item",
                "criterium": "",
                "schaal": "1-10",
            }
        ],
    }
    return exporteer_config_excel(config)


# ---------------------------------------------------------------------------
# Tests voor _repareer_xlsx
# ---------------------------------------------------------------------------


class TestRepareerXlsx:
    def test_schoon_bestand_blijft_leesbaar(self):
        raw = _maak_xlsx_met_cel("gewone tekst")
        gerepareerd = _repareer_xlsx(raw)
        df = pd.read_excel(io.BytesIO(gerepareerd))
        assert df.iloc[0, 0] == "gewone tekst"

    def test_schoon_bestand_bevat_geen_illegale_tekens(self):
        raw = _maak_xlsx_met_cel("gewone tekst")
        assert not _xml_bevat_illegale_tekens(_repareer_xlsx(raw))

    @pytest.mark.parametrize("teken", [b"\x0b", b"\x0c", b"\x01", b"\x1f"])
    def test_injectie_voegt_illegaal_teken_toe(self, teken):
        """Bevestigt dat _injecteer_teken_in_xlsx daadwerkelijk een illegaal
        teken in de gedecomprimeerde XML plaatst (precondition voor de andere tests)."""
        raw = _maak_xlsx_met_cel("waarde")
        besmet = _injecteer_teken_in_xlsx(raw, teken)
        assert _xml_bevat_illegale_tekens(besmet)

    @pytest.mark.parametrize("teken", [b"\x0b", b"\x0c", b"\x01", b"\x1f"])
    def test_repareer_verwijdert_illegale_tekens(self, teken):
        raw = _maak_xlsx_met_cel("waarde")
        besmet = _injecteer_teken_in_xlsx(raw, teken)
        assert not _xml_bevat_illegale_tekens(_repareer_xlsx(besmet))

    @pytest.mark.parametrize("teken", [b"\x0b", b"\x0c", b"\x01", b"\x1f"])
    def test_gerepareerd_bestand_is_leesbaar(self, teken):
        raw = _maak_xlsx_met_cel("waarde")
        besmet = _injecteer_teken_in_xlsx(raw, teken)
        gerepareerd = _repareer_xlsx(besmet)
        df = pd.read_excel(io.BytesIO(gerepareerd))
        assert len(df) > 0

    def test_normale_unicode_tekens_blijven_intact(self):
        raw = _maak_xlsx_met_cel("café naïve Üniversität")
        df = pd.read_excel(io.BytesIO(_repareer_xlsx(raw)))
        assert df.iloc[0, 0] == "café naïve Üniversität"

    def test_numerieke_celwaarde_blijft_intact(self):
        raw = _maak_xlsx_met_cel(42)
        df = pd.read_excel(io.BytesIO(_repareer_xlsx(raw)))
        assert df.iloc[0, 0] == 42

    def test_geldige_xml_tekens_worden_niet_gestript(self):
        # \t (0x09) en \n (0x0a) zijn geldige XML-tekens en mogen niet verdwijnen
        for teken in [b"\x09", b"\x0a"]:
            raw = _maak_xlsx_met_cel("tekst")
            besmet = _injecteer_teken_in_xlsx(raw, teken)
            gerepareerd = _repareer_xlsx(besmet)
            zf = zipfile.ZipFile(io.BytesIO(gerepareerd))
            xml_bytes = b"".join(
                zf.read(n) for n in zf.namelist() if n.endswith(".xml")
            )
            assert teken in xml_bytes


# ---------------------------------------------------------------------------
# Tests voor _saniteer (config wizard)
# ---------------------------------------------------------------------------


class TestSaniteer:
    @pytest.mark.parametrize("teken", ["\x0b", "\x0c", "\x01", "\x07", "\x1f"])
    def test_illegaal_teken_wordt_gestript(self, teken):
        assert _saniteer(f"kolom{teken}naam") == "kolomnaam"

    def test_schone_string_blijft_ongewijzigd(self):
        assert _saniteer("Motivatiebrief score") == "Motivatiebrief score"

    def test_geen_string_wordt_teruggegeven_als_is(self):
        assert _saniteer(42) == 42
        assert _saniteer(True) is True
        assert _saniteer(None) is None

    def test_tab_en_newline_blijven_intact(self):
        assert _saniteer("a\tb") == "a\tb"
        assert _saniteer("a\nb") == "a\nb"

    def test_meerdere_tekens_in_een_string(self):
        assert _saniteer("\x01score\x0b\x0c") == "score"


# ---------------------------------------------------------------------------
# Integratietests: rondreis via wizard + lees_config
# ---------------------------------------------------------------------------


class TestRondreis:
    def test_wizard_schrijft_geen_illegale_tekens(self):
        """Wizard sanitiseert bij schrijven: de gegenereerde config bevat
        geen illegale tekens, ook niet als de kolomnaam een illegaal teken had."""
        raw = _maak_config_xlsx("score\x0bkolom")
        assert not _xml_bevat_illegale_tekens(raw)

    def test_config_met_gesaniteerde_kolomnaam_is_leesbaar(self):
        raw = _maak_config_xlsx("score\x0bkolom")
        config = lees_config(_als_upload_uri(raw))
        namen = [k["kolom_naam"] for k in config["kolommen"]]
        assert "scorekolom" in namen

    def test_handmatig_besmette_xlsx_overleeft_lees_config(self):
        """lees_config repareert transparant een xlsx met een illegaal teken
        dat openpyxl anders niet kan lezen."""
        raw = _maak_xlsx_met_cel("waarde")
        besmet = _injecteer_teken_in_xlsx(raw, b"\x0c")
        assert _xml_bevat_illegale_tekens(besmet)
        gerepareerd = _repareer_xlsx(
            base64.b64decode(_als_upload_uri(besmet).split(",", 1)[1])
        )
        assert not _xml_bevat_illegale_tekens(gerepareerd)
        assert pd.read_excel(io.BytesIO(gerepareerd)) is not None
