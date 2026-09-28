"""Subtotalen naast hun onderdelen worden herkend en uitgevinkt (pitch #38)."""

import numpy as np
import pandas as pd

from config_wizard import (
    _SOM_WOORDEN,
    _naam_delen,
    detecteer_alle_kolommen,
    detecteer_somkolommen,
)


def _df():
    rng = np.random.default_rng(1)
    a = rng.integers(1, 6, 20)
    b = rng.integers(1, 6, 20)
    c = rng.integers(1, 6, 20)
    return pd.DataFrame(
        {"id": range(20), "a": a, "b": b, "c": c, "som_ab": a + b, "x": a * 2}
    )


def test_som_van_aaneengesloten_kolommen():
    gevonden = detecteer_somkolommen(_df(), ["a", "b", "c", "som_ab", "x"])
    assert gevonden["som_ab"] == ["a", "b"]
    assert "x" not in gevonden and "a" not in gevonden


def test_alleen_de_naam_verraadt_het():
    df = pd.DataFrame({"p": range(10), "C_B1_Sc_SubTotaal": range(10, 20)})
    assert detecteer_somkolommen(df, list(df.columns)) == {"C_B1_Sc_SubTotaal": []}


def test_geen_vals_alarm_op_woorddeel():
    assert not (_naam_delen("Somatisch_inzicht") & _SOM_WOORDEN)
    assert _naam_delen("C_B1_B2_Sc_SubTotaal") & _SOM_WOORDEN


def test_subtotaal_uitgevinkt_in_wizard():
    kols = {k["kolom_naam"]: k for k in detecteer_alle_kolommen(_df(), "id", None)}
    assert kols["som_ab"]["_meenemen"] is False
    assert kols["som_ab"]["item"]  # voorstel blijft, zodat aanvinken kan
    assert kols["a"]["_meenemen"] is True
