"""
Tests voor de fixes uit de code-audit van 2026-09: gevallen waarin de analyses
stil een verkeerde uitkomst gaven (scheiding in de regressie, samenvallende
itemnamen, dubbele kandidaten, sterk overlappende items) en de randgevallen
eromheen (lege config, negatieve schalen, voorloopnullen, filter_query,
upload-route).
"""

import base64
import io
import os
import time
from contextlib import contextmanager
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest
from flask import Flask

import bestandsopslag
import uploads
from helpers import (
    df_from_store,
    gezamenlijk_model_uit_stores,
    koppel_data,
    query_tekst,
    scores_df_from_store,
)
from shared import (
    GROEP_DOORGESTROOMD,
    GROEP_GESTART_GEEN_VERVOLG,
    PERSPECTIEF_DOORSTROOM,
    _effect_met_bi,
    _verwijder_collineair,
    bereken_gezamenlijk_model,
    bereken_univariaat,
    genereer_bevindingen,
    grenzen_van_label,
    schaal_bucket,
)
from transformatie import (
    dubbele_itemnamen,
    transformeer_naar_lang,
    valideer_config,
)


def _uri(raw: bytes) -> str:
    return "data:application/octet-stream;base64," + base64.b64encode(raw).decode()


def _xlsx(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    df.to_excel(buf, index=False)
    return buf.getvalue()


def _kol(naam, item=None, instrument="I"):
    return {
        "kolom_naam": naam,
        "instrument": instrument,
        "item": naam if item is None else item,
        "meenemen": True,
    }


# ── Regressie: scheiding en overlap ──────────────────────────────────────────


def _regressiedata(n=60, seed=0):
    """Gestarte studenten met een item dat de uitkomst perfect scheidt en twee
    ruisitems."""
    rng = np.random.default_rng(seed)
    y = np.r_[np.zeros(n // 2), np.ones(n // 2)].astype(int)
    nummers = [str(1000 + i) for i in range(n)]
    df = pd.DataFrame(
        {
            "studentnummer": nummers,
            "groep": np.where(y == 1, GROEP_DOORGESTROOMD, GROEP_GESTART_GEEN_VERVOLG),
        }
    )
    items = {
        "Scheidend": y * 10 + rng.normal(0, 1, n),
        "Ruis A": rng.normal(0, 1, n),
        "Ruis B": rng.normal(0, 1, n),
    }
    scores = pd.concat(
        pd.DataFrame({"studentnummer": nummers, "item": naam, "score": waarden})
        for naam, waarden in items.items()
    )
    return df, scores


def test_scheidend_item_wordt_herkend_niet_als_niet_significant_getoond():
    df, scores = _regressiedata()
    rijen = {
        r["Item"]: r for r in bereken_univariaat(df, scores, PERSPECTIEF_DOORSTROOM)
    }
    scheidend = rijen["Scheidend"]
    assert scheidend["_probleem"] == "scheiding"
    assert scheidend["Sig."] == "scheidt volledig"  # niet 'ns'
    assert scheidend["Odds ratio"] == "-"
    assert scheidend["_p"] != scheidend["_p"]  # NaN: telt niet mee in BH
    assert rijen["Ruis A"].get("_probleem") is None


def test_gezamenlijk_model_zet_scheidend_item_apart_en_fit_de_rest():
    df, scores = _regressiedata()
    model = bereken_gezamenlijk_model(df, scores, PERSPECTIEF_DOORSTROOM)
    assert model["status"] == "ok"
    assert model["verwijderd_scheiding"] == ["Scheidend"]
    # Niet als 'zwakste' item bij de EPV-voorselectie weggegooid.
    assert "Scheidend" not in model["verwijderd_epv"]
    assert {r["Item"] for r in model["coefficienten"]} == {"Ruis A", "Ruis B"}


def test_bevindingen_melden_scheiding_als_sterk_signaal():
    df, scores = _regressiedata()
    uni = bereken_univariaat(df, scores, PERSPECTIEF_DOORSTROOM)
    regels = genereer_bevindingen(pd.DataFrame(), {}, univariaat_data=uni)["regressie"]
    tekst = " ".join(regels)
    assert "'Scheidend'" in tekst and "volledig" in tekst
    assert "Geen enkel item voorspelt" not in tekst


def test_afgeleid_gemiddelde_wordt_als_overlap_verwijderd():
    """Een gemiddelde van drie items heeft net volle rang, maar gaf absurde odds
    ratios (e^60). De VIF-stap haalt het eruit."""
    rng = np.random.default_rng(1)
    X = pd.DataFrame({k: rng.normal(0, 1, 80) for k in ("a", "b", "c")})
    X["gemiddelde"] = X[["a", "b", "c"]].mean(axis=1) + rng.normal(0, 0.01, 80)
    X["los"] = rng.normal(0, 1, 80)
    rest, verwijderd = _verwijder_collineair(X)
    assert verwijderd == ["gemiddelde"]
    assert list(rest.columns) == ["a", "b", "c", "los"]


def test_onafhankelijke_items_blijven_staan():
    rng = np.random.default_rng(2)
    X = pd.DataFrame({k: rng.normal(0, 1, 50) for k in ("a", "b", "c")})
    assert _verwijder_collineair(X)[1] == []


def test_demo_modellen_hebben_redelijke_odds_ratios(demo_dataset):
    df = koppel_data(demo_dataset["cho_df"], demo_dataset["scores_df"])
    model = bereken_gezamenlijk_model(
        df, demo_dataset["scores_df"], PERSPECTIEF_DOORSTROOM
    )
    assert model["status"] == "ok"
    for r in model["coefficienten"]:
        assert 0.01 < r["Odds ratio"] < 100, r


def test_gecachet_model_geeft_kopie():
    df, scores = _regressiedata()
    df["groep"] = pd.Categorical(df["groep"])
    store = df.to_json(orient="split")
    scores_store = scores.to_json(orient="split")
    eerste = gezamenlijk_model_uit_stores(store, scores_store)
    eerste["univariaat"].clear()
    tweede = gezamenlijk_model_uit_stores(store, scores_store)
    assert len(tweede["univariaat"]) == 3


# ── Samenvallende itemnamen ──────────────────────────────────────────────────


def test_dubbele_itemnamen_ook_na_inkorten():
    kolommen = [
        _kol("K1", "Gesprek schaalscore"),
        _kol("K2", "Gesprek", instrument="J"),
        _kol("K3", "Anders"),
    ]
    assert dubbele_itemnamen(kolommen) == {"Gesprek": ["K1", "K2"]}


def test_lege_itemnamen_vallen_terug_op_kolomnaam():
    kolommen = [_kol("A", ""), _kol("B", "")]
    assert dubbele_itemnamen(kolommen) == {}
    data = pd.DataFrame({"id": ["1", "2"], "A": [1, 2], "B": [3, 4]})
    lang = transformeer_naar_lang(data, {"koppel_id_kolom": "id", "kolommen": kolommen})
    assert sorted(lang["item"].unique()) == ["A", "B"]


def test_dubbele_itemnaam_wordt_niet_stil_samengevoegd():
    config = {
        "koppel_id_kolom": "id",
        "kolommen": [_kol("A", "Zelfde"), _kol("B", "Zelfde")],
    }
    data = pd.DataFrame({"id": ["1", "2"], "A": [1, 2], "B": [3, 4]})
    with pytest.raises(ValueError, match="Zelfde"):
        transformeer_naar_lang(data, config)
    checks = valideer_config(config, _uri(_xlsx(data)))
    assert any("Zelfde" in c["check"] and not c["ok"] for c in checks)


# ── Dubbele kandidaten ───────────────────────────────────────────────────────

_CONFIG_AB = {"koppel_id_kolom": "id", "kolommen": [_kol("A"), _kol("B")]}


def test_exact_dubbele_kandidaat_telt_een_keer_met_waarschuwing():
    data = pd.DataFrame({"id": ["1", "2", "2"], "A": [1, 2, 2], "B": [3, 4, 4]})
    lang = transformeer_naar_lang(data, _CONFIG_AB)
    assert len(lang) == 4
    checks = valideer_config(_CONFIG_AB, _uri(_xlsx(data)))
    assert all(c["ok"] for c in checks)
    assert any(c.get("waarschuwing") and "dubbele" in c["check"] for c in checks)


def test_tegenstrijdige_dubbele_kandidaat_blokkeert():
    # '2' en '2.0' zijn na normalisatie dezelfde student.
    data = pd.DataFrame({"id": ["1", "2", "2.0"], "A": [1, 2, 5], "B": [3, 4, 4]})
    with pytest.raises(ValueError, match="meerdere keren"):
        transformeer_naar_lang(data, _CONFIG_AB)
    checks = valideer_config(_CONFIG_AB, _uri(_xlsx(data)))
    assert any("meerdere keren" in c["check"] and not c["ok"] for c in checks)


# ── Lege config en duidelijke fouten ─────────────────────────────────────────


def test_config_zonder_items_blokkeert_bij_validatie():
    config = {"koppel_id_kolom": "id", "kolommen": [{**_kol("A"), "meenemen": False}]}
    data = pd.DataFrame({"id": ["1"], "A": [1]})
    checks = valideer_config(config, _uri(_xlsx(data)))
    assert not checks[-1]["ok"] and "Meenemen" in checks[-1]["check"]


def test_koppel_data_zonder_scores_geeft_begrijpelijke_fout():
    cho = pd.DataFrame({"studentnummer": ["1"], "groep": [GROEP_DOORGESTROOMD]})
    with pytest.raises(ValueError, match="geen selectiescores"):
        koppel_data(cho, pd.DataFrame())


# ── Schaallabels, store, filter_query, betrouwbaarheidsinterval ──────────────


@pytest.mark.parametrize(
    "label, verwacht",
    [
        ("0-5", (0.0, 5.0)),
        ("-5-5", (-5.0, 5.0)),
        ("-10--2", (-10.0, -2.0)),
        ("0-1e+06", (0.0, 1e6)),
        ("0.5-2.5", (0.5, 2.5)),
        ("onbekend", None),
    ],
)
def test_grenzen_van_label(label, verwacht):
    assert grenzen_van_label(label) == verwacht


def test_negatieve_schaal_rondreis():
    label = schaal_bucket([-3, 2, 5])
    assert grenzen_van_label(label) == (-5.0, 5.0)


def test_store_behoudt_voorloopnullen():
    df = pd.DataFrame(
        {"studentnummer": ["00123", "456"], "groep": ["Niet gestart"] * 2}
    )
    assert df_from_store(df.to_json(orient="split"))["studentnummer"].tolist() == [
        "00123",
        "456",
    ]
    scores = pd.DataFrame({"studentnummer": ["007"], "score": [1.0]})
    assert scores_df_from_store(scores.to_json(orient="split"))[
        "studentnummer"
    ].tolist() == ["007"]


def test_query_tekst_escapet_aanhalingstekens():
    assert query_tekst('Buitenlands "IB" diploma') == '"Buitenlands \\"IB\\" diploma"'
    assert query_tekst("a\\b") == '"a\\\\b"'


def test_bi_krimpt_niet_tot_een_punt_bij_volledige_scheiding():
    r, lo, hi = _effect_met_bi(1.0, 10, 10)
    assert r == 1.0 and hi == 1.0
    assert lo < 0.99


# ── Upload-route en laden ────────────────────────────────────────────────────


@pytest.fixture
def uploadmap(tmp_path, monkeypatch):
    monkeypatch.setattr(bestandsopslag, "UPLOAD_DIR", tmp_path)
    bestandsopslag._CACHE.clear()
    return tmp_path


@pytest.fixture
def client(uploadmap):
    server = Flask(__name__)
    bestandsopslag.registreer_upload_route(server)
    return server.test_client()


def _post(client, headers=None):
    return client.post(
        "/upload-bestand",
        data={"bestand": (io.BytesIO(b"a;b\n1;2\n"), "1cho.csv")},
        content_type="multipart/form-data",
        headers=headers or {},
    )


def test_upload_van_andere_site_wordt_geweigerd(client, uploadmap):
    antwoord = _post(client, {"Origin": "https://kwaadaardig.example"})
    assert antwoord.status_code == 403
    assert list(uploadmap.iterdir()) == []


def test_upload_van_de_app_zelf_mag(client):
    assert _post(client, {"Origin": "http://localhost"}).status_code == 200


def test_te_grote_upload_wordt_geweigerd(client, monkeypatch):
    monkeypatch.setattr(bestandsopslag, "MAX_UPLOAD_BYTES", 10)
    assert _post(client).status_code == 413


def test_verwijder_upload(client, uploadmap):
    token = _post(client).get_json()["token"]
    bestandsopslag.verwijder_upload(token)
    assert list(uploadmap.iterdir()) == []
    bestandsopslag.verwijder_upload(token)  # nogmaals: geen fout
    bestandsopslag.verwijder_upload("../../etc/passwd")  # ongeldig: geen fout


def test_verlopen_uploads_worden_bij_start_opgeruimd(uploadmap):
    oud = uploadmap / ("a" * 32 + ".csv")
    nieuw = uploadmap / ("b" * 32 + ".csv")
    oud.write_text("x")
    nieuw.write_text("x")
    twee_dagen = time.time() - 2 * 24 * 60 * 60
    os.utime(oud, (twee_dagen, twee_dagen))
    bestandsopslag.registreer_upload_route(Flask(__name__))
    assert not oud.exists() and nieuw.exists()


class _FakeApp:
    def __init__(self):
        self.functies = {}

    def callback(self, *args, **kwargs):
        def registreer(fn):
            self.functies[fn.__name__] = fn
            return fn

        return registreer

    def clientside_callback(self, *args, **kwargs):
        pass


@contextmanager
def _trigger(naam):
    with patch.object(uploads, "ctx") as nep:
        nep.triggered_id = naam
        yield


@pytest.fixture
def laad_dashboard():
    app = _FakeApp()
    uploads.registreer_callbacks(app)
    return app.functies["laad_dashboard"]


def test_mislukt_laden_toont_melding_in_plaats_van_niets(laad_dashboard):
    cho = {"token": "0" * 32, "filename": "weg.csv"}  # bestand bestaat niet meer
    with _trigger("btn-open-dashboard"):
        data, scores, melding, *_ = laad_dashboard(
            1, None, None, "sel", "cfg", cho, None, None, None, "upload"
        )
    assert "niet worden geopend" in str(melding)


def test_reset_verwijdert_1cho_upload(laad_dashboard, client, uploadmap):
    token = _post(client).get_json()["token"]
    cho = {"token": token, "filename": "1cho.csv"}
    with _trigger("btn-reset"):
        data, scores, _, cho_store, cho_status = laad_dashboard(
            None, None, 1, None, None, cho, None, None, None, None
        )
    assert data is None and cho_store is None and cho_status == ""
    assert list(uploadmap.iterdir()) == []
