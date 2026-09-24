"""
Tests voor robuuste invoer bij upload (pitch #34): tekstcellen in
scorekolommen, oude .xls-bestanden, hoofdletterextensies, jaartallen als
'2025-2026' en de volgorde van de encoding-fallback.
"""

import base64
import io

import pandas as pd
import pytest

from transformatie import (
    _repareer_xlsx,
    parse_csv_or_excel,
    parse_header_rij,
    parse_jaar,
    transformeer_naar_lang,
    valideer_config,
)


def _uri(raw: bytes) -> str:
    return "data:application/octet-stream;base64," + base64.b64encode(raw).decode()


def _xlsx(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    df.to_excel(buf, index=False)
    return buf.getvalue()


CONFIG = {
    "koppel_id_kolom": "studentnr",
    "kolommen": [
        {"kolom_naam": "A", "instrument": "I", "item": "A", "meenemen": True},
        {"kolom_naam": "B", "instrument": "I", "item": "B", "meenemen": True},
    ],
}
SELECTIE = pd.DataFrame(
    {"studentnr": [1, 2, 3, 4], "A": [5, "n.v.t.", 7, 6], "B": [1, 2, 3, 4]}
)


class TestTekstInScorekolom:
    def test_transformatie_crasht_niet(self):
        lang = transformeer_naar_lang(SELECTIE, CONFIG)
        a = lang[lang["item"] == "A"]
        assert len(a) == 3  # de 'n.v.t.'-cel valt weg
        assert a["score"].dtype == float

    def test_validatie_waarschuwt_zonder_te_blokkeren(self):
        checks = valideer_config(CONFIG, _uri(_xlsx(SELECTIE)))
        assert all(c["ok"] for c in checks)
        waarschuwingen = [c for c in checks if c.get("waarschuwing")]
        assert len(waarschuwingen) == 1
        assert "'A' (1)" in waarschuwingen[0]["check"]


class TestJaar:
    @pytest.mark.parametrize(
        "waarde, verwacht",
        [
            (2025, 2025),
            ("2025", 2025),
            ("2025.0", 2025),
            (2025.0, 2025),
            ("2025-2026", 2025),
            ("studiejaar 2025/2026", 2025),
            ("", None),
            (None, None),
            ("onbekend", None),
        ],
    )
    def test_parse_jaar(self, waarde, verwacht):
        assert parse_jaar(waarde) == verwacht

    def test_transformatie_met_studiejaar(self):
        lang = transformeer_naar_lang(SELECTIE, {**CONFIG, "jaar": "2025-2026"})
        assert set(lang["selectiejaar"]) == {2025}

    def test_validatie_blokkeert_onleesbaar_jaar(self):
        checks = valideer_config(
            {**CONFIG, "jaar": "vorig jaar"}, _uri(_xlsx(SELECTIE))
        )
        assert any(not c["ok"] and "Jaar" in c["check"] for c in checks)


class TestHeaderRij:
    @pytest.mark.parametrize(
        "waarde, verwacht", [("3", 3), ("3.0", 3), (3, 3), ("", 1), (None, 1), ("x", 1)]
    )
    def test_parse_header_rij(self, waarde, verwacht):
        assert parse_header_rij(waarde) == verwacht


class TestBestandsformaat:
    def test_niet_zip_wordt_ongewijzigd_doorgegeven(self):
        # Een oud .xls-bestand is een OLE-bestand, geen ZIP.
        xls_achtig = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 64
        assert _repareer_xlsx(xls_achtig) == xls_achtig

    def test_hoofdletterextensie_wordt_als_excel_gelezen(self):
        df = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
        gelezen = parse_csv_or_excel(_uri(_xlsx(df)), "CHO_DATA.XLSX")
        assert gelezen.shape == (2, 2)


class TestEncoding:
    def test_cp1252_tekens_blijven_heel(self):
        tekst = "naam;bedrag\n‘José’;€ 5\n"
        gelezen = parse_csv_or_excel(_uri(tekst.encode("cp1252")), "data.csv")
        assert gelezen.iloc[0, 0] == "‘José’"
        assert gelezen.iloc[0, 1] == "€ 5"

    def test_utf8_blijft_voorrang_hebben(self):
        tekst = "naam;x\nJosé;1\n"
        gelezen = parse_csv_or_excel(_uri(tekst.encode("utf-8")), "data.csv")
        assert gelezen.iloc[0, 0] == "José"


class TestKolomMatching:
    """Pitch #33: configkolommen exact matchen, niet via de eerste substring."""

    def test_exacte_match_wint_van_substring(self):
        from transformatie import _find_col

        assert _find_col(["Item 10", "Item 1"], "Item 1") == "Item 1"
        assert _find_col(["studentnr_oud", "studentnr"], "studentnr") == "studentnr"

    def test_hoofdletterongevoelig_exact(self):
        from transformatie import _find_col

        assert _find_col(["Studentnummer", "studentnummer_oud"], "studentnummer") == (
            "Studentnummer"
        )

    def test_unieke_substring_blijft_werken(self):
        from transformatie import _find_col

        assert _find_col(["C_Sc_Totaal (punten)"], "C_Sc_Totaal") == (
            "C_Sc_Totaal (punten)"
        )

    def test_dubbelzinnige_substring_geeft_geen_match(self):
        from transformatie import _find_col

        assert _find_col(["studentnr_oud", "studentnr_nieuw"], "studentnr") is None

    def test_validatie_meldt_dubbelzinnige_naam(self):
        df = pd.DataFrame({"studentnr_oud": [1], "studentnr_nieuw": [2], "A": [3]})
        config = {**CONFIG, "kolommen": CONFIG["kolommen"][:1]}
        checks = valideer_config(config, _uri(_xlsx(df)))
        assert any(
            not c["ok"] and "past op meerdere kolommen" in c["check"] for c in checks
        )

    def test_validatie_meldt_twee_regels_op_een_kolom(self):
        df = pd.DataFrame({"studentnr": [1], "Score A": [3]})
        config = {
            "koppel_id_kolom": "studentnr",
            "kolommen": [
                {"kolom_naam": "Score A", "instrument": "I", "item": "x"},
                {"kolom_naam": "score a", "instrument": "I", "item": "y"},
            ],
        }
        checks = valideer_config(config, _uri(_xlsx(df)))
        assert any(not c["ok"] and "wijzen allemaal" in c["check"] for c in checks)
        lang = transformeer_naar_lang(df, config)
        assert len(lang) == 1
