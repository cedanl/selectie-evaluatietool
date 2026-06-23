"""End-to-end pipeline test using demo data as fixtures."""

import pandas as pd

from helpers import koppel_data
from shared import GROEP_VOLGORDE, UITKOMST_PERSPECTIEVEN, vergelijk_succes_per_item


class TestEndToEnd:
    def test_koppel_data_succeeds(self, demo_dataset):
        df = koppel_data(demo_dataset["cho_df"], demo_dataset["scores_df"])
        assert len(df) > 0
        assert "groep" in df.columns
        assert "totaalscore" in df.columns

    def test_alle_groepen_geldig(self, demo_dataset):
        df = koppel_data(demo_dataset["cho_df"], demo_dataset["scores_df"])
        for groep in df["groep"].unique():
            assert groep in GROEP_VOLGORDE

    def test_scores_df_lang_formaat(self, demo_dataset):
        scores = demo_dataset["scores_df"]
        assert "studentnummer" in scores.columns
        assert "item" in scores.columns
        assert "score" in scores.columns
        assert "instrument" in scores.columns

    def test_verschiltoets_per_perspectief(self, demo_dataset):
        df = koppel_data(demo_dataset["cho_df"], demo_dataset["scores_df"])
        scores = demo_dataset["scores_df"].merge(
            df[["studentnummer", "groep"]].drop_duplicates(),
            on="studentnummer",
            how="inner",
        )
        from shared import shorten_item

        scores["item_kort"] = scores["item"].apply(shorten_item)

        for key, perspectief in UITKOMST_PERSPECTIEVEN.items():
            pop = scores[scores["groep"].isin(perspectief["populatie"])]
            if pop.empty:
                continue
            tabel = vergelijk_succes_per_item(pop, perspectief=perspectief)
            assert isinstance(tabel, pd.DataFrame)
