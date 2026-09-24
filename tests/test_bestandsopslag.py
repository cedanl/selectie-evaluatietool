"""
Tests voor de server-side upload van grote 1CHO-bestanden (bestandsopslag.py).
"""

import io

import pandas as pd
import pytest
from flask import Flask

import bestandsopslag


@pytest.fixture(autouse=True)
def eigen_uploadmap(tmp_path, monkeypatch):
    monkeypatch.setattr(bestandsopslag, "UPLOAD_DIR", tmp_path)
    bestandsopslag._CACHE.clear()


@pytest.fixture
def client():
    server = Flask(__name__)
    bestandsopslag.registreer_upload_route(server)
    return server.test_client()


CSV = (
    "persoonsgebonden_nummer;inschrijvingsjaar;eerste_jaar_aan_deze_opleiding_instelling;"
    "geslacht;hoogste_vooropleiding_omschrijving_vooropleiding;overbodig_1;overbodig_2\n"
    "00123;2024;2024;vrouw;vwo;x;y\n"
    "456;2025;2024;man;havo;x;y\n"
)


def _upload(client, inhoud: bytes, naam: str):
    return client.post(
        "/upload-bestand",
        data={"bestand": (io.BytesIO(inhoud), naam)},
        content_type="multipart/form-data",
    )


def test_upload_en_inlezen(client):
    antwoord = _upload(client, CSV.encode("utf-8"), "1cho.csv")
    assert antwoord.status_code == 200
    token = antwoord.get_json()["token"]
    df = bestandsopslag.lees_cho_upload(token)
    assert len(df) == 2
    # Alleen de kolommen die de tool gebruikt.
    assert "overbodig_1" not in df.columns
    # Studentnummers blijven tekst, voorloopnullen blijven staan.
    assert df["persoonsgebonden_nummer"].tolist() == ["00123", "456"]


def test_hoofdletterextensie_en_excel(client):
    buf = io.BytesIO()
    pd.read_csv(io.StringIO(CSV), sep=";").to_excel(buf, index=False)
    antwoord = _upload(client, buf.getvalue(), "1CHO.XLSX")
    assert antwoord.status_code == 200
    df = bestandsopslag.lees_cho_upload(antwoord.get_json()["token"])
    assert len(df) == 2 and "overbodig_2" not in df.columns


def test_cp1252_csv(client):
    inhoud = CSV.replace("vwo", "vwo – profiel").encode("cp1252")
    antwoord = _upload(client, inhoud, "1cho.csv")
    df = bestandsopslag.lees_cho_upload(antwoord.get_json()["token"])
    assert "–" in df["hoogste_vooropleiding_omschrijving_vooropleiding"].iloc[0]


def test_weigert_onbekend_type(client):
    antwoord = _upload(client, b"x", "virus.exe")
    assert antwoord.status_code == 400
    assert "niet ondersteund" in antwoord.get_json()["fout"]


@pytest.mark.parametrize("token", ["../../etc/passwd", "abc", "", None, "Z" * 32])
def test_ongeldig_token(token):
    with pytest.raises(ValueError):
        bestandsopslag.pad_voor_token(token)


def test_verlopen_token():
    with pytest.raises(ValueError, match="niet meer beschikbaar"):
        bestandsopslag.pad_voor_token("0" * 32)
