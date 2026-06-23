import pandas as pd
import pytest

from helpers import koppel_data
from shared import GROEP_NIET_GESTART, GROEP_DOORGESTROOMD, GROEP_GESTART_GEEN_VERVOLG


@pytest.fixture
def scores_df():
    return pd.DataFrame(
        {
            "studentnummer": [1, 1, 2, 2, 3, 3],
            "item": ["a", "b", "a", "b", "a", "b"],
            "score": [80, 70, 60, 50, 90, 85],
            "instrument": ["Test", "Test", "Test", "Test", "Test", "Test"],
            "criterium": ["c1", "c1", "c1", "c1", "c1", "c1"],
        }
    )


@pytest.fixture
def cho_df():
    return pd.DataFrame(
        {
            "studentnummer": [1, 2],
            "selectiejaar": [2024, 2024],
            "groep": [GROEP_DOORGESTROOMD, GROEP_GESTART_GEEN_VERVOLG],
        }
    )


class TestKoppelData:
    def test_niet_gestart_voor_ontbrekende(self, cho_df, scores_df):
        df = koppel_data(cho_df, scores_df)
        student3 = df[df["studentnummer"] == 3].iloc[0]
        assert student3["groep"] == GROEP_NIET_GESTART

    def test_groep_behouden(self, cho_df, scores_df):
        df = koppel_data(cho_df, scores_df)
        student1 = df[df["studentnummer"] == 1].iloc[0]
        assert student1["groep"] == GROEP_DOORGESTROOMD

    def test_totaalscore_berekend(self, cho_df, scores_df):
        df = koppel_data(cho_df, scores_df)
        assert "totaalscore" in df.columns
        assert df["totaalscore"].notna().all()

    def test_zscore_scalar_bug_fixed(self):
        cho_df = pd.DataFrame(
            {
                "studentnummer": [1, 2],
                "selectiejaar": [2024, 2024],
                "groep": [GROEP_DOORGESTROOMD, GROEP_GESTART_GEEN_VERVOLG],
            }
        )
        scores_df = pd.DataFrame(
            {
                "studentnummer": [1, 2],
                "item": ["a", "a"],
                "score": [50, 50],
                "instrument": ["Test", "Test"],
                "criterium": ["c1", "c1"],
            }
        )
        df = koppel_data(cho_df, scores_df)
        assert "totaalscore" in df.columns
        assert df["totaalscore"].notna().all()
