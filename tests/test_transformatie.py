import base64
from pathlib import Path

import pandas as pd
import pytest

from transformatie import lees_config, parse_selectiedata, transformeer_naar_lang

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
