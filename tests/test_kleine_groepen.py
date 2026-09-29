"""Kleine groepen (< MIN_CEL) worden in Selectiescores afgeschermd (issue #60)."""

import pandas as pd
import pytest

from helpers import (
    _aantallen_per_groep,
    _laad_demodata,
    _scherm_kleine_groepen,
    df_from_store,
    scores_df_from_store,
)
from shared import AFGESCHERMD, MIN_CEL
from tabs.scores import update_scores_tab


def _figuur_groepen(fig) -> set[str]:
    """Alle groepsnamen die in de figuur terechtkomen: tracenamen, en bij één
    item ook de x-waarden (dan staan de groepen op de x-as)."""
    groepen = set()
    for trace in fig.data:
        groepen.add(trace.name)
        groepen.update(str(x) for x in (trace.x if trace.x is not None else []))
    return groepen


def test_scherm_kleine_groepen_laat_groep_van_een_weg():
    scores = pd.DataFrame(
        {
            "studentnummer": [f"s{i}" for i in range(11)],
            "groep": ["a"] * 5 + ["b"] * 5 + ["c"],
            "item": ["x"] * 11,
            "score": range(11),
        }
    )
    over, volgorde, afgeschermd = _scherm_kleine_groepen(scores, ["a", "b", "c"])
    assert set(over["groep"]) == {"a", "b"}
    assert volgorde == ["a", "b"]
    assert afgeschermd == ["c"]


def test_scherm_kleine_groepen_telt_per_item_en_zonder_lege_scores():
    # Groep b heeft 5 studenten, maar bij item y maar 4 met een score.
    scores = pd.DataFrame(
        {
            "studentnummer": [f"s{i}" for i in range(10)] * 2,
            "groep": (["a"] * 5 + ["b"] * 5) * 2,
            "item": ["x"] * 10 + ["y"] * 10,
            "score": list(range(10)) + list(range(9)) + [None],
        }
    )
    over, volgorde, afgeschermd = _scherm_kleine_groepen(scores, ["a", "b"])
    assert not ((over["groep"] == "b") & (over["item"] == "y")).any()
    assert ((over["groep"] == "b") & (over["item"] == "x")).sum() == 5
    assert volgorde == ["a", "b"]
    assert afgeschermd == ["b"]


@pytest.fixture(scope="module")
def radboud():
    return _laad_demodata("demo_radboud_2026")


def test_aantallen_schermen_kleine_groep_af(radboud):
    df = df_from_store(radboud[0])
    tabel = _aantallen_per_groep(df, "geslacht").set_index("Groep")
    assert tabel.loc["anders", "n"] == AFGESCHERMD
    assert tabel.loc["anders", "%"] == "-"
    # Percentages over de getoonde groepen, zodat de 1 niet terug te rekenen is.
    n_getoond = int(tabel.loc["vrouw", "n"]) + int(tabel.loc["man", "n"])
    assert (
        tabel.loc["vrouw", "%"]
        == f"{int(tabel.loc['vrouw', 'n']) / n_getoond * 100:.0f}%"
    )


@pytest.mark.parametrize("item_filter", ["Alle", "enkel"])
def test_selectiescores_tonen_groep_van_een_niet(radboud, item_filter):
    data, scores = radboud
    if item_filter == "enkel":
        item_filter = scores_df_from_store(scores)["item"].iloc[0]
    fig, aant, _, _, gem, _, _, melding = update_scores_tab(
        "geslacht", "Alle", "Alle", item_filter, "Alle", data, scores
    )
    assert "anders" not in _figuur_groepen(fig)
    assert {"vrouw", "man"} <= _figuur_groepen(fig)
    assert "anders" not in {rij["Groep"] for rij in gem}
    assert {rij["Groep"]: rij["n"] for rij in aant}["anders"] == AFGESCHERMD
    assert "anders" in melding and str(MIN_CEL) in melding


def test_selectiescores_zonder_kleine_groep_geen_melding(radboud):
    data, scores = radboud
    *_, melding = update_scores_tab(
        "doorstroom", "Alle", "Alle", "Alle", "Alle", data, scores
    )
    assert melding is None
