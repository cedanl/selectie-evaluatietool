"""
Tests voor het PDF-rapport. De grafieken (kaleido, een Chromium per figuur)
worden weggestubd; het gaat hier om de tekst en de tabellen.
"""

import pytest

import rapport
from helpers import _laad_demodata, df_from_store, scores_df_from_store


@pytest.fixture(autouse=True)
def geen_grafieken(monkeypatch):
    monkeypatch.setattr(rapport, "_render_figures", lambda figures: {})


@pytest.fixture
def radboud():
    data, scores = _laad_demodata("demo_radboud_2026")
    return df_from_store(data), scores_df_from_store(scores)


def test_rapport_wordt_gemaakt(radboud):
    df, scores_df = radboud
    pdf = rapport.genereer_rapport(df, scores_df)
    assert pdf.startswith(b"%PDF")


def test_unicode_in_namen(radboud):
    """Pitch #35: en-dash, typografische aanhalingstekens en '≥' lieten de
    kernfont Helvetica crashen."""
    df, scores_df = radboud
    df = df.assign(opleiding="Psychologie – ‘selectie’")
    scores_df = scores_df.assign(
        item=scores_df["item"].str.replace("Wiskunde", "Wiskunde ≥ 7 “B”")
    )
    pdf = rapport.genereer_rapport(df, scores_df)
    assert pdf.startswith(b"%PDF")
