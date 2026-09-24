"""
Server-side opslag voor grote uploads (het 1CHO-bestand).

dcc.Upload leest een bestand in de browser in als één base64-tekst en stuurt
die bij elke callback opnieuw mee. Bij een instellingsbreed 1CHO-bestand van
honderden MB's gaat dat mis: Chrome kan zulke lange teksten niet aan (boven
~380 MB faalt de upload zonder melding) en elke validatie verstuurt het hele
bestand opnieuw.

Daarom gaat 1CHO via een eigen Flask-route: de browser streamt het bestand
één keer als multipart-upload (assets/grote_upload.js), de server schrijft
het naar een tijdelijk bestand en geeft een token terug. De callbacks werken
daarna alleen met dat token. Bij het inlezen nemen we alleen de kolommen die
de tool gebruikt.

De app draait lokaal (localhost); de bestanden blijven op deze machine.
"""

import io
import re
import tempfile
import uuid
from collections import OrderedDict
from pathlib import Path

import pandas as pd
from flask import jsonify, request

from cho_transform import CHO_BENODIGDE_KOLOMMEN
from transformatie import _repareer_xlsx

UPLOAD_DIR = Path(tempfile.gettempdir()) / "selectie-evaluatietool-uploads"

_TOEGESTANE_EXTENSIES = {".csv", ".txt", ".xlsx", ".xls"}
_TOKEN = re.compile(r"^[0-9a-f]{32}$")

# Ingelezen 1CHO-tabellen per token, zodat een wissel in het keuzemenu of
# 'Open dashboard' het bestand niet opnieuw hoeft te parsen.
_CACHE: OrderedDict[str, pd.DataFrame] = OrderedDict()
_CACHE_GROOTTE = 2


def registreer_upload_route(server) -> None:
    """Voeg POST /upload-bestand toe aan de Flask-server van de Dash-app."""

    @server.post("/upload-bestand")
    def upload_bestand():
        bestand = request.files.get("bestand")
        if bestand is None or not bestand.filename:
            return jsonify({"fout": "Geen bestand ontvangen."}), 400
        extensie = Path(bestand.filename).suffix.lower()
        if extensie not in _TOEGESTANE_EXTENSIES:
            return jsonify(
                {"fout": f"Bestandstype {extensie or '(geen)'} wordt niet ondersteund."}
            ), 400

        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        _ruim_oude_uploads_op()
        token = uuid.uuid4().hex
        pad = UPLOAD_DIR / f"{token}{extensie}"
        # Werkzeug heeft het bestand al naar schijf gestreamd; save() kopieert
        # in blokken, zonder het geheel in het geheugen te laden.
        bestand.save(pad)
        return jsonify(
            {
                "token": token,
                "filename": bestand.filename,
                "grootte": pad.stat().st_size,
            }
        )


def pad_voor_token(token: str) -> Path:
    """Het opgeslagen bestand bij een token. Controleert het token streng,
    zodat er geen willekeurig pad kan worden gelezen."""
    if not isinstance(token, str) or not _TOKEN.match(token):
        raise ValueError("Ongeldige upload-verwijzing.")
    kandidaten = [
        p for p in UPLOAD_DIR.glob(f"{token}.*") if p.suffix in _TOEGESTANE_EXTENSIES
    ]
    if not kandidaten:
        raise ValueError(
            "Het geüploade 1CHO-bestand is niet meer beschikbaar. Upload het opnieuw."
        )
    return kandidaten[0]


def lees_cho_upload(token: str) -> pd.DataFrame:
    """Lees het geüploade 1CHO-bestand (met cache per token)."""
    if token in _CACHE:
        _CACHE.move_to_end(token)
        return _CACHE[token]
    df = lees_cho_bestand(pad_voor_token(token))
    _CACHE[token] = df
    while len(_CACHE) > _CACHE_GROOTTE:
        _CACHE.popitem(last=False)
    return df


def _benodigd(kolom) -> bool:
    return str(kolom).strip() in CHO_BENODIGDE_KOLOMMEN


def lees_cho_bestand(pad: Path) -> pd.DataFrame:
    """Lees een (mogelijk heel groot) 1CHO-bestand van schijf.

    Alleen de kolommen die de tool gebruikt worden ingelezen; een
    instellingsbreed bestand heeft er vaak tientallen. CSV-scheidingsteken en
    encoding worden uit het begin van het bestand bepaald, met dezelfde
    fallback-volgorde als transformatie.parse_csv_or_excel."""
    if pad.suffix.lower() in (".xlsx", ".xls"):
        df = pd.read_excel(
            io.BytesIO(_repareer_xlsx(pad.read_bytes())), usecols=_benodigd
        )
    else:
        df = _lees_csv(pad)
    df.columns = [str(c).strip() for c in df.columns]
    return df


def _lees_csv(pad: Path) -> pd.DataFrame:
    with open(pad, "rb") as f:
        begin = f.read(64 * 1024)
    # Alleen hele regels, zodat een afgekapt multibyte-teken geen valse
    # decodeerfout geeft.
    begin = begin[: begin.rfind(b"\n") + 1] or begin
    kop = begin.split(b"\n", 1)[0]
    sep = ";" if kop.count(b";") > kop.count(b",") else ","

    fout = None
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            begin.decode(encoding)
            return pd.read_csv(
                pad,
                sep=sep,
                encoding=encoding,
                usecols=_benodigd,
                dtype={"persoonsgebonden_nummer": str},
                low_memory=False,
            )
        except UnicodeDecodeError as e:
            fout = e
            continue
    raise ValueError(
        "Het CSV-bestand kon niet worden gelezen. Sla het op als UTF-8 en probeer opnieuw."
    ) from fout


def _ruim_oude_uploads_op(max_bestanden: int = 5) -> None:
    """Houd de uploadmap klein: alleen de laatste paar uploads blijven staan."""
    bestanden = sorted(UPLOAD_DIR.glob("*"), key=lambda p: p.stat().st_mtime)
    for oud in bestanden[:-max_bestanden] if len(bestanden) > max_bestanden else []:
        try:
            oud.unlink()
        except OSError:
            pass
