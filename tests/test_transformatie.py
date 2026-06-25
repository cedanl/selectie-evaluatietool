import base64
from pathlib import Path

import pandas as pd
import pytest

from transformatie import (
    lees_config,
    parse_selectiedata,
    transformeer_naar_lang,
    parse_bool,
    meegenomen_kolommen,
    normaliseer_studentnummer,
)

DEMO_DIR = Path(__file__).parent.parent / "data" / "demo"


def _uri(path: Path) -> str:
    return f"data:application/octet-stream;base64,{base64.b64encode(path.read_bytes()).decode()}"


@pytest.fixture
def gezondheidskunde():
    d = DEMO_DIR / "gezondheidskunde_univ_noordstad_2026"
    if not d.exists():
        pytest.skip("demo data not present")
    return d


@pytest.fixture
def sportkunde():
    d = DEMO_DIR / "sportkunde_hs_westland_2026"
    if not d.exists():
        pytest.skip("demo data not present")
    return d


class TestParseBool:
    @pytest.mark.parametrize("waar", [True, "TRUE", "true", "Waar", "Ja", "1", 1, "x"])
    def test_waar(self, waar):
        assert parse_bool(waar) is True

    @pytest.mark.parametrize(
        "onwaar", [False, "FALSE", "Nee", "0", "", None, float("nan")]
    )
    def test_onwaar(self, onwaar):
        assert parse_bool(onwaar) is False


class TestNormaliseerStudentnummer:
    def test_int_float_en_tekst_worden_gelijk(self):
        assert list(normaliseer_studentnummer(pd.Series([123]))) == ["123"]
        assert list(normaliseer_studentnummer(pd.Series([123.0]))) == ["123"]
        assert list(normaliseer_studentnummer(pd.Series([" 123 "]))) == ["123"]

    def test_int_en_string_bron_koppelen(self):
        # selectiedata int 123 en 1CHO tekst "123" moeten matchen
        sel = set(normaliseer_studentnummer(pd.Series([123, 124])).dropna())
        cho = set(normaliseer_studentnummer(pd.Series(["123", "124.0"])).dropna())
        assert sel & cho == {"123", "124"}

    def test_lege_waarden_worden_na(self):
        out = normaliseer_studentnummer(pd.Series(["", None]))
        assert out.isna().all()


class TestMeegenomenKolommen:
    def test_filtert_op_meenemen(self):
        config = {
            "kolommen": [
                {"kolom_naam": "a", "meenemen": True},
                {"kolom_naam": "b", "meenemen": False},
                {"kolom_naam": "c", "meenemen": True},
            ]
        }
        namen = [k["kolom_naam"] for k in meegenomen_kolommen(config)]
        assert namen == ["a", "c"]

    def test_zonder_meenemen_telt_alles_mee(self):
        config = {"kolommen": [{"kolom_naam": "a"}, {"kolom_naam": "b"}]}
        assert len(meegenomen_kolommen(config)) == 2


class TestLeesConfig:
    def test_returns_dict(self, gezondheidskunde):
        config = lees_config(_uri(gezondheidskunde / "config.xlsx"))
        assert isinstance(config, dict)
        assert "kolommen" in config
        assert "koppel_id_kolom" in config

    def test_kolommen_hebben_instrument(self, gezondheidskunde):
        config = lees_config(_uri(gezondheidskunde / "config.xlsx"))
        for kolom in config["kolommen"]:
            assert "instrument" in kolom
            assert "kolom_naam" in kolom


class TestParseSelectiedata:
    def test_returns_dataframe(self, gezondheidskunde):
        config = lees_config(_uri(gezondheidskunde / "config.xlsx"))
        df = parse_selectiedata(_uri(gezondheidskunde / "selectiedata.xlsx"), config)
        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0

    def test_id_kolom_aanwezig(self, gezondheidskunde):
        config = lees_config(_uri(gezondheidskunde / "config.xlsx"))
        df = parse_selectiedata(_uri(gezondheidskunde / "selectiedata.xlsx"), config)
        assert config["koppel_id_kolom"] in df.columns


class TestTransformeerNaarLang:
    def test_lang_formaat(self, gezondheidskunde):
        config = lees_config(_uri(gezondheidskunde / "config.xlsx"))
        raw = parse_selectiedata(_uri(gezondheidskunde / "selectiedata.xlsx"), config)
        scores = transformeer_naar_lang(raw, config)
        assert "studentnummer" in scores.columns
        assert "item" in scores.columns
        assert "score" in scores.columns
        assert "instrument" in scores.columns

    def test_header_rij_3(self, sportkunde):
        config = lees_config(_uri(sportkunde / "config.xlsx"))
        raw = parse_selectiedata(_uri(sportkunde / "selectiedata.xlsx"), config)
        scores = transformeer_naar_lang(raw, config)
        assert len(scores) > 0
