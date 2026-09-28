"""Benjamini-Hochberg-correctie op de per-item toetsen (pitch #38)."""

import math

import numpy as np
import pandas as pd
import pytest
from statsmodels.stats.multitest import multipletests

from shared import (
    P_GECORRIGEERD,
    bh_correctie,
    genereer_bevindingen,
    toets_verschil_per_item,
    vergelijk_succes_per_item,
    GROEP_DOORGESTROOMD,
    GROEP_GESTART_GEEN_VERVOLG,
)


@pytest.mark.parametrize(
    "p", [[0.01, 0.04, 0.03, 0.5], [0.001, 0.2, 0.9], [0.049], [0.02, 0.02, 0.02]]
)
def test_bh_gelijk_aan_statsmodels(p):
    verwacht = multipletests(p, method="fdr_bh")[1]
    assert np.allclose(bh_correctie(p), verwacht)


def test_bh_laat_nan_staan_en_telt_die_niet_mee():
    uit = bh_correctie([0.01, float("nan"), 0.04])
    assert math.isnan(uit[1])
    assert np.allclose(
        [uit[0], uit[2]], multipletests([0.01, 0.04], method="fdr_bh")[1]
    )


def _scores(n_items=10, n=12, seed=0):
    """Eén item met een echt verschil, de rest ruis."""
    rng = np.random.default_rng(seed)
    rijen = []
    for i in range(n_items):
        for s in range(2 * n):
            succes = s < n
            basis = 5 + (3 if (i == 0 and succes) else 0)
            rijen.append(
                {
                    "studentnummer": s,
                    "item_kort": f"item{i}",
                    "score": basis + rng.normal(),
                    "groep": GROEP_DOORGESTROOMD
                    if succes
                    else GROEP_GESTART_GEEN_VERVOLG,
                    "geslacht": "M" if s % 2 else "V",
                }
            )
    return pd.DataFrame(rijen)


def test_vergelijking_heeft_gecorrigeerde_kolom():
    tabel = vergelijk_succes_per_item(_scores())
    assert P_GECORRIGEERD in tabel.columns
    getoetst = tabel[tabel["_r"].notna()]
    assert (getoetst["_p_bh"] >= getoetst["_p"] - 1e-12).all()
    assert "*" not in "".join(tabel["p"])  # sterretjes alleen bij gecorrigeerd


def test_verschil_richting_volgt_gecorrigeerde_p():
    tabel = toets_verschil_per_item(_scores(), "geslacht")
    for _, r in tabel.iterrows():
        if r["_p_bh"] >= 0.05:
            assert r["Verschil"] == "vergelijkbaar"


def test_bevindingen_gebruiken_gecorrigeerde_p():
    tabel = vergelijk_succes_per_item(_scores())
    # Forceer een item dat ruw wel en gecorrigeerd niet significant is.
    tabel.loc[1, ["_p", "_p_bh", "_r"]] = [0.04, 0.2, 0.3]
    bev = genereer_bevindingen(tabel, {})
    tekst = " ".join(bev["validiteit"])
    assert "'item1'" not in tekst
    assert "Benjamini-Hochberg" in bev["samenvatting"][0]
    assert "zonder die correctie" in bev["samenvatting"][0]
