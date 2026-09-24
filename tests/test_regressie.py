"""
Tests voor het gezamenlijke regressiemodel (pitch #31): één implementatie
voor de tab Regressie, 'Wat valt op' en het rapport, met EPV-selectie op
univariate p-waarde.
"""

import math

import pandas as pd
import pytest

from helpers import koppel_data
from shared import (
    PERSPECTIEF_DOORSTROOM,
    bereken_gezamenlijk_model,
    bereken_univariaat,
    model_stats_uit,
)


class _FakeApp:
    """Vangt de callbackfunctie op zodat we hem direct kunnen aanroepen."""

    def __init__(self):
        self.functies = {}

    def callback(self, *args, **kwargs):
        def registreer(fn):
            self.functies[fn.__name__] = fn
            return fn

        return registreer


@pytest.fixture
def demo_df(demo_dataset):
    df = koppel_data(demo_dataset["cho_df"], demo_dataset["scores_df"])
    return df, demo_dataset["scores_df"]


def test_epv_selectie_houdt_laagste_p_waarden(demo_df):
    df, scores_df = demo_df
    model = bereken_gezamenlijk_model(df, scores_df, PERSPECTIEF_DOORSTROOM)
    assert model["status"] == "ok"
    if not model["verwijderd_epv"]:
        pytest.skip("geen EPV-selectie nodig in deze demo")
    p = {r["Item"]: r["_p"] for r in model["univariaat"]}
    behouden = max(p[r["Item"]] for r in model["coefficienten"])
    weggelaten = min(p[i] for i in model["verwijderd_epv"])
    assert behouden <= weggelaten


def test_tab_regressie_toont_zelfde_model_als_wat_valt_op(demo_df):
    import tabs.regressie

    df, scores_df = demo_df
    app = _FakeApp()
    tabs.regressie.registreer_callbacks(app)
    uitvoer = app.functies["update_regressie_tab"](
        df.to_json(orient="split"), scores_df.to_json(orient="split")
    )
    stats = model_stats_uit(
        bereken_gezamenlijk_model(df, scores_df, PERSPECTIEF_DOORSTROOM)
    )
    assert f"pseudo R²) = {stats['pseudo_r2']}" in str(uitvoer[0])
    tab_sig = [r["Item"] for r in uitvoer[4] if r["Sig."] not in ("ns", "-")]
    assert tab_sig == stats["sig_items"]


def test_univariaat_gelijk_aan_modelonderdeel(demo_df):
    df, scores_df = demo_df
    los = bereken_univariaat(df, scores_df, PERSPECTIEF_DOORSTROOM)
    model = bereken_gezamenlijk_model(df, scores_df, PERSPECTIEF_DOORSTROOM)
    assert [r["Item"] for r in los] == [r["Item"] for r in model["univariaat"]]
    for a, b in zip(los, model["univariaat"]):
        assert math.isclose(a["_p"], b["_p"]) or (
            math.isnan(a["_p"]) and math.isnan(b["_p"])
        )


def test_te_weinig_studenten():
    df = pd.DataFrame({"studentnummer": ["1"], "groep": ["Doorgestroomd naar jaar 2"]})
    scores = pd.DataFrame({"studentnummer": ["1"], "item": ["A"], "score": [1.0]})
    model = bereken_gezamenlijk_model(df, scores, PERSPECTIEF_DOORSTROOM)
    assert model["status"] == "te_weinig_studenten"
    assert model_stats_uit(model) is None
