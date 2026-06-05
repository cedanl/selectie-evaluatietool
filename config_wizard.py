"""
Config wizard: auto-detect configuratie-instellingen uit een selectiedata Excel-bestand.

Bevat drie onderdelen:
1. Detectiefuncties (puur Python, geen Dash)
2. Dash layout (maak_wizard_layout)
3. Callbacks (registreer_callbacks)
"""

import io
import json
import re

import pandas as pd
from openpyxl import Workbook

from dash import dcc, html, dash_table, Input, Output, State
import dash
import dash_bootstrap_components as dbc

from transformatie import _decode_upload


# =============================================================================
# 1. Detectiefuncties
# =============================================================================


def detecteer_bladen(raw: bytes) -> list[str]:
    xls = pd.ExcelFile(io.BytesIO(raw))
    return xls.sheet_names


def detecteer_header_rij(xls: pd.ExcelFile, sheet: str | int = 0) -> int:
    """Scan rijen 0-9; return 1-based index van de eerste 'echte' headerrij."""
    df_raw = xls.parse(sheet_name=sheet, header=None, nrows=10)
    best_row = 0
    best_score = 0
    ncols = min(20, len(df_raw.columns))
    for i in range(len(df_raw)):
        row = df_raw.iloc[i, :ncols]
        filled = sum(1 for v in row if pd.notna(v) and str(v).strip() != "")
        str_cells = sum(
            1 for v in row if pd.notna(v) and isinstance(v, str) and v.strip() != ""
        )
        score = filled + str_cells
        if score > best_score:
            best_score = score
            best_row = i
    return best_row + 1


_ID_PATRONEN = [
    "studentnummer",
    "aanvraagnummer",
    "nummer_aanvraag",
    "kandidaatnummer",
    "deelnemernummer",
    "student_id",
]


def detecteer_id_kolom(headers: list[str]) -> str | None:
    for patroon in _ID_PATRONEN:
        for h in headers:
            if patroon in str(h).lower().replace(" ", ""):
                return h
    return None


def detecteer_totaalscore(headers: list[str]) -> str | None:
    for h in headers:
        lower = str(h).lower()
        if "totaal" in lower and "score" in lower:
            return h
    for h in headers:
        if "totaal" in str(h).lower():
            return h
    return None


_SKIP_WOORDEN = {
    "data", "selectie", "selectiedata", "dummy", "totaalscores", "scores",
    "score", "ranking", "met", "formules", "en", "van", "de", "het",
    "beoordelingen", "master", "bachelor", "sheet", "blad", "resultaten",
    "overzicht", "export", "rapport", "tabel", "lijst", "bestand",
}


def detecteer_metadata(bestandsnaam: str, bladnamen: list[str]) -> dict:
    """Raad opleiding, instelling en jaar op basis van bestandsnaam en bladnamen."""
    tekst = bestandsnaam + " " + " ".join(bladnamen)

    jaren = re.findall(r"20\d{2}", tekst)
    jaar = jaren[0] if jaren else ""

    naam_zonder_ext = re.sub(r"\.\w+$", "", bestandsnaam)
    woorden = re.findall(r"[A-Za-zÀ-ɏ]+", naam_zonder_ext)
    inhoudelijk = [
        w for w in woorden
        if w.lower() not in _SKIP_WOORDEN
        and not re.fullmatch(r"20\d{2}", w)
        and len(w) >= 2
    ]

    return {
        "opleiding": " ".join(inhoudelijk) if inhoudelijk else "",
        "instelling": "",
        "jaar": jaar,
    }


_EXCLUDEER_PATRONEN = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"datum",
        r"tijd",
        r"voltooid",
        r"start",
        r"naam",
        r"email",
        r"e.?mail",
        r"telefoon",
        r"geboort",
        r"adres",
        r"bsn",
        r"rangnummer",
        r"rang.?nummer",
        r"loting",
        r"random",
        r"z.?score",
        r"zscore",
        r"normscore",
        r"norm.?groep",
        r"percentiel",
        r"proctoring",
        r"opmerking",
        r"toelichting",
        r"aanmak",
        r"aanvraag",
        r"afnametaal",
        r"beoordelingsresultaat",
        r"procesvoltooid",
        r"testvoltooid",
        r"aantal.?woord",
    ]
]


def _moet_uitsluiten(kolom_naam: str) -> bool:
    for patroon in _EXCLUDEER_PATRONEN:
        if patroon.search(kolom_naam):
            return True
    return False


def _raad_instrument(kolom: str, alle_kolommen: list[str]) -> str:
    lower = kolom.lower()
    if lower.startswith("ctb_"):
        return "Competentietest (breed)"
    if lower.startswith("ct_"):
        return "Competentietest"
    if lower.startswith("sjts_"):
        return "SIT-S"

    prefix = kolom.split("_")[0] if "_" in kolom else kolom.split(" ")[0]
    if len(prefix) >= 2:
        count = sum(
            1
            for k in alle_kolommen
            if k.startswith(prefix + "_") or k.startswith(prefix + " ")
        )
        if count >= 2:
            return prefix.title()

    return ""


def _maak_item_naam(kolom: str) -> str:
    naam = kolom
    lower = naam.lower()
    for prefix in ["ctb_", "ct_", "sjts_"]:
        if lower.startswith(prefix):
            naam = naam[len(prefix) :]
            break

    naam = re.sub(r"_?[Ss]chaalscore$", "", naam)
    naam = re.sub(r"_?SCORE$", "", naam)
    naam = re.sub(r"_?[Ss]core$", "", naam)

    naam = naam.replace("_", " ").strip()
    naam = re.sub(r"([a-z])([A-Z])", r"\1 \2", naam)

    if naam:
        naam = naam[0].upper() + naam[1:]

    return naam


def detecteer_score_kolommen(
    df: pd.DataFrame,
    id_kolom: str | None,
    totaalscore_kolom: str | None,
) -> list[dict]:
    skip = {id_kolom, totaalscore_kolom} - {None}
    alle_kolommen = [str(c) for c in df.columns]
    resultaat = []

    for col in df.columns:
        col_str = str(col)
        if col_str in skip:
            continue
        if not pd.api.types.is_numeric_dtype(df[col]):
            continue
        if _moet_uitsluiten(col_str):
            continue

        resultaat.append(
            {
                "kolom_naam": col_str,
                "instrument": _raad_instrument(col_str, alle_kolommen),
                "item": _maak_item_naam(col_str),
                "criterium": "",
            }
        )

    return resultaat


def bouw_config_dict(
    blad_naam: str,
    header_rij: int,
    koppel_id_kolom: str,
    totaalscore_kolom: str,
    opleiding: str,
    instellingscode: str,
    jaar: str,
    kolommen: list[dict],
) -> dict:
    return {
        "koppel_id_kolom": str(koppel_id_kolom).strip(),
        "opleiding": str(opleiding).strip(),
        "instellingscode": str(instellingscode).strip(),
        "jaar": str(jaar).strip(),
        "blad_naam": str(blad_naam).strip(),
        "header_rij": str(int(header_rij)),
        "totaalscore_kolom": str(totaalscore_kolom).strip(),
        "kolommen": [{k: str(v).strip() for k, v in kol.items()} for kol in kolommen],
    }


def exporteer_config_excel(config: dict) -> bytes:
    wb = Workbook()

    ws_inst = wb.active
    ws_inst.title = "instellingen"
    inst_rijen = [
        ("koppel_id_kolom", config.get("koppel_id_kolom", "")),
        ("opleiding", config.get("opleiding", "")),
        ("instellingscode", config.get("instellingscode", "")),
        ("jaar", config.get("jaar", "")),
        ("blad_naam", config.get("blad_naam", "")),
        ("header_rij", config.get("header_rij", "1")),
        ("totaalscore_kolom", config.get("totaalscore_kolom", "")),
    ]
    for r, (key, val) in enumerate(inst_rijen, start=1):
        ws_inst.cell(row=r, column=1, value=key)
        ws_inst.cell(row=r, column=2, value=val)

    ws_kol = wb.create_sheet("kolommen")
    kol_headers = ["kolom_naam", "instrument", "item", "criterium"]
    for c, h in enumerate(kol_headers, start=1):
        ws_kol.cell(row=1, column=c, value=h)
    for r, kol in enumerate(config.get("kolommen", []), start=2):
        for c, veld in enumerate(kol_headers, start=1):
            ws_kol.cell(row=r, column=c, value=kol.get(veld, ""))

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# =============================================================================
# 2. Layout
# =============================================================================


def maak_wizard_layout() -> html.Div:
    return html.Div(
        [
            dcc.Store(id="wiz-config-store", storage_type="memory"),
            dcc.Store(id="wiz-raw-store", storage_type="memory"),
            dcc.Download(id="wiz-download"),
            html.A(
                "Of: config automatisch genereren",
                id="wiz-toggle-link",
                href="#",
                className="small text-primary",
                style={"cursor": "pointer", "display": "block", "marginBottom": "8px"},
            ),
            dbc.Collapse(
                id="wiz-collapse",
                is_open=False,
                children=dbc.Card(
                    dbc.CardBody(
                        [
                            html.P(
                                "Detecteert automatisch welke kolommen scorekolommen zijn. "
                                "Controleer het resultaat en pas aan waar nodig.",
                                className="small text-muted mb-3",
                            ),
                            # Blad en headerrij
                            dbc.Row(
                                [
                                    dbc.Col(
                                        [
                                            dbc.Label("Blad", className="small"),
                                            dcc.Dropdown(
                                                id="wiz-sheet-dropdown",
                                                placeholder="Upload eerst selectiedata",
                                                clearable=False,
                                                className="mb-2",
                                            ),
                                        ]
                                    ),
                                    dbc.Col(
                                        [
                                            dbc.Label("Headerrij", className="small"),
                                            dbc.Input(
                                                id="wiz-header-rij",
                                                type="number",
                                                min=1,
                                                max=20,
                                                value=1,
                                                size="sm",
                                            ),
                                        ],
                                        width=4,
                                    ),
                                ],
                                className="mb-2",
                            ),
                            # Opleiding en jaar
                            dbc.Row(
                                [
                                    dbc.Col(
                                        [
                                            dbc.Label("Opleiding", className="small"),
                                            dbc.Input(
                                                id="wiz-opleiding",
                                                placeholder="bijv. Farmacie",
                                                size="sm",
                                            ),
                                        ]
                                    ),
                                    dbc.Col(
                                        [
                                            dbc.Label("Instelling", className="small"),
                                            dbc.Input(
                                                id="wiz-instelling",
                                                placeholder="bijv. LUMC",
                                                size="sm",
                                            ),
                                        ]
                                    ),
                                    dbc.Col(
                                        [
                                            dbc.Label(
                                                "Selectiejaar", className="small"
                                            ),
                                            dbc.Input(
                                                id="wiz-jaar",
                                                placeholder="bijv. 2026",
                                                size="sm",
                                                type="number",
                                            ),
                                        ],
                                        width=3,
                                    ),
                                ],
                                className="mb-2",
                            ),
                            # ID-kolom en totaalscore
                            dbc.Row(
                                [
                                    dbc.Col(
                                        [
                                            dbc.Label("ID-kolom", className="small"),
                                            dcc.Dropdown(
                                                id="wiz-id-kolom",
                                                placeholder="Wordt automatisch gedetecteerd",
                                                clearable=False,
                                                className="mb-2",
                                            ),
                                        ]
                                    ),
                                    dbc.Col(
                                        [
                                            dbc.Label(
                                                "Totaalscore-kolom", className="small"
                                            ),
                                            dcc.Dropdown(
                                                id="wiz-totaalscore",
                                                placeholder="Wordt automatisch gedetecteerd",
                                                clearable=True,
                                                className="mb-2",
                                            ),
                                        ]
                                    ),
                                ],
                                className="mb-2",
                            ),
                            # Kolommen tabel
                            html.Div(
                                id="wiz-tabel-container",
                                children=[
                                    dbc.Label("Scorekolommen", className="small"),
                                    html.P(
                                        "Upload selectiedata om kolommen te detecteren.",
                                        id="wiz-tabel-placeholder",
                                        className="small text-muted",
                                    ),
                                    dash_table.DataTable(
                                        id="wiz-kolommen-tabel",
                                        columns=[
                                            {
                                                "name": "Kolom",
                                                "id": "kolom_naam",
                                                "editable": False,
                                            },
                                            {
                                                "name": "Instrument",
                                                "id": "instrument",
                                                "editable": True,
                                            },
                                            {
                                                "name": "Item",
                                                "id": "item",
                                                "editable": True,
                                            },
                                            {
                                                "name": "Criterium",
                                                "id": "criterium",
                                                "editable": True,
                                            },
                                        ],
                                        data=[],
                                        editable=True,
                                        row_deletable=True,
                                        style_table={
                                            "overflowX": "auto",
                                            "fontSize": "13px",
                                        },
                                        style_header={
                                            "backgroundColor": "#f8f9fa",
                                            "fontWeight": "600",
                                            "fontSize": "12px",
                                        },
                                        style_cell={
                                            "textAlign": "left",
                                            "padding": "4px 8px",
                                            "whiteSpace": "normal",
                                            "height": "auto",
                                        },
                                        style_data_conditional=[
                                            {
                                                "if": {"column_id": "kolom_naam"},
                                                "backgroundColor": "#f8f9fa",
                                                "color": "#6c757d",
                                            }
                                        ],
                                    ),
                                ],
                            ),
                            html.Div(id="wiz-status", className="mt-2 mb-2"),
                            dbc.Row(
                                [
                                    dbc.Col(
                                        dbc.Button(
                                            "Bevestig config",
                                            id="wiz-bevestig-btn",
                                            color="primary",
                                            size="sm",
                                            className="w-100",
                                        ),
                                    ),
                                    dbc.Col(
                                        dbc.Button(
                                            "Download als Excel",
                                            id="wiz-download-btn",
                                            color="secondary",
                                            size="sm",
                                            outline=True,
                                            className="w-100",
                                            style={"display": "none"},
                                        ),
                                    ),
                                ],
                                className="mt-3 g-2",
                            ),
                        ]
                    ),
                    className="border-0 bg-light",
                ),
            ),
        ],
        className="mb-3",
    )


# =============================================================================
# 3. Callbacks
# =============================================================================


def registreer_callbacks(app: dash.Dash) -> None:

    @app.callback(
        Output("wiz-collapse", "is_open"),
        Input("wiz-toggle-link", "n_clicks"),
        State("wiz-collapse", "is_open"),
        prevent_initial_call=True,
    )
    def toggle_wizard(n, is_open):
        return not is_open

    @app.callback(
        Output("wiz-raw-store", "data"),
        Input("upload-selectiedata", "contents"),
        prevent_initial_call=True,
    )
    def bewaar_selectiedata(contents):
        if not contents:
            return dash.no_update
        return contents

    @app.callback(
        Output("wiz-sheet-dropdown", "options"),
        Output("wiz-sheet-dropdown", "value"),
        Output("wiz-header-rij", "value"),
        Output("wiz-opleiding", "value"),
        Output("wiz-instelling", "value"),
        Output("wiz-jaar", "value"),
        Input("wiz-raw-store", "data"),
        Input("wiz-collapse", "is_open"),
        State("upload-selectiedata", "filename"),
        prevent_initial_call=True,
    )
    def detecteer_blad_en_header(raw_contents, is_open, filename):
        if not is_open or not raw_contents:
            return [], None, 1, None, None, None

        try:
            raw = _decode_upload(raw_contents)
            xls = pd.ExcelFile(io.BytesIO(raw))
            bladen = xls.sheet_names
            options = [{"label": b, "value": b} for b in bladen]
            gekozen = bladen[0] if len(bladen) == 1 else None

            header = 1
            if gekozen:
                header = detecteer_header_rij(xls, gekozen)

            meta = detecteer_metadata(filename or "", bladen)

            return (
                options,
                gekozen,
                header,
                meta["opleiding"] or None,
                meta["instelling"] or None,
                meta["jaar"] or None,
            )
        except Exception:
            return [], None, 1, None, None, None

    @app.callback(
        Output("wiz-id-kolom", "options"),
        Output("wiz-id-kolom", "value"),
        Output("wiz-totaalscore", "options"),
        Output("wiz-totaalscore", "value"),
        Output("wiz-kolommen-tabel", "data"),
        Output("wiz-tabel-placeholder", "style"),
        Input("wiz-sheet-dropdown", "value"),
        Input("wiz-header-rij", "value"),
        State("wiz-raw-store", "data"),
        prevent_initial_call=True,
    )
    def detecteer_kolommen(blad, header_rij, raw_contents):
        leeg = ([], None, [], None, [], {"display": "block"})

        if not blad or not raw_contents or not header_rij:
            return leeg

        try:
            raw = _decode_upload(raw_contents)
            header_idx = int(header_rij) - 1
            df = pd.read_excel(
                io.BytesIO(raw),
                sheet_name=blad,
                header=header_idx,
            )
            headers = [str(c) for c in df.columns]
            col_options = [{"label": h, "value": h} for h in headers]

            id_kol = detecteer_id_kolom(headers)
            totaal_kol = detecteer_totaalscore(headers)

            score_kols = detecteer_score_kolommen(df, id_kol, totaal_kol)

            return (
                col_options,
                id_kol,
                col_options,
                totaal_kol,
                score_kols,
                {"display": "none"} if score_kols else {"display": "block"},
            )
        except Exception:
            return leeg

    @app.callback(
        Output("wiz-config-store", "data"),
        Output("wiz-status", "children"),
        Output("wiz-download-btn", "style"),
        Input("wiz-bevestig-btn", "n_clicks"),
        State("wiz-kolommen-tabel", "data"),
        State("wiz-sheet-dropdown", "value"),
        State("wiz-header-rij", "value"),
        State("wiz-id-kolom", "value"),
        State("wiz-totaalscore", "value"),
        State("wiz-opleiding", "value"),
        State("wiz-instelling", "value"),
        State("wiz-jaar", "value"),
        prevent_initial_call=True,
    )
    def bevestig_config(
        n, tabel_data, blad, header_rij, id_kol, totaal_kol, opleiding, instelling, jaar
    ):
        if not n or not tabel_data:
            return dash.no_update, dash.no_update, {"display": "none"}

        if not id_kol:
            return (
                dash.no_update,
                dbc.Alert(
                    "Selecteer een ID-kolom.", color="danger", className="small py-1"
                ),
                {"display": "none"},
            )

        if not blad:
            return (
                dash.no_update,
                dbc.Alert(
                    "Selecteer een blad.", color="danger", className="small py-1"
                ),
                {"display": "none"},
            )

        config = bouw_config_dict(
            blad_naam=blad,
            header_rij=header_rij or 1,
            koppel_id_kolom=id_kol,
            totaalscore_kolom=totaal_kol or "",
            opleiding=opleiding or "",
            instellingscode=instelling or "",
            jaar=str(jaar) if jaar else "",
            kolommen=tabel_data,
        )

        return (
            json.dumps(config),
            dbc.Alert(
                f"Config aangemaakt ({len(tabel_data)} kolommen). "
                "Upload nu 1CHO-data om het dashboard te openen.",
                color="success",
                className="small py-1",
            ),
            {"display": "block"},
        )

    @app.callback(
        Output("wiz-download", "data"),
        Input("wiz-download-btn", "n_clicks"),
        State("wiz-config-store", "data"),
        prevent_initial_call=True,
    )
    def download_config(n, config_json):
        if not n or not config_json:
            return dash.no_update
        config = json.loads(config_json)
        return dcc.send_bytes(exporteer_config_excel(config), "config_wizard.xlsx")
