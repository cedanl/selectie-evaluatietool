"""Tab 'Configuratie': de gebruikte config tonen en bewerken, met een voorbeeld
van de verwerkte data. Vanuit hier kan de config worden aangepast en het
dashboard opnieuw worden doorgerekend, of als Excel worden gedownload."""

import io
import json
import re

import pandas as pd
import dash
from dash import dcc, html, dash_table, Input, Output, State
import dash_bootstrap_components as dbc

from transformatie import parse_csv_or_excel
from helpers import bouw_data_stores, df_from_store, TABLE_STYLE
from config_wizard import bouw_config_dict, exporteer_config_excel

# Bewerkbare instellingen-velden: (configsleutel, label). De volgorde bepaalt
# de weergave; de sleutels komen overeen met wat bouw_config_dict verwacht.
INSTELLING_VELDEN = [
    ("opleiding", "Opleiding"),
    ("instellingscode", "Instelling"),
    ("jaar", "Jaar"),
    ("koppel_id_kolom", "Koppelkolom (student-ID)"),
    ("blad_naam", "Bladnaam in Excel"),
    ("header_rij", "Headerrij"),
    ("totaalscore_kolom", "Totaalscore-kolom"),
]

KOLOM_VELDEN = ["kolom_naam", "instrument", "item", "criterium", "schaal"]

# Hoeveel rijen we van een dataset tonen. De volledige set zit al in de browser;
# dit houdt de tabel responsief.
PREVIEW_RIJEN = 500


def _config_uit_velden(waarden: list, tabel_data: list[dict]) -> dict:
    """Bouw een config-dict uit de ingevulde velden en de kolommen-tabel."""
    inst = dict(zip([sleutel for sleutel, _ in INSTELLING_VELDEN], waarden))
    kolommen = [
        {veld: str(rij.get(veld, "")).strip() for veld in KOLOM_VELDEN}
        for rij in tabel_data
        if str(rij.get("kolom_naam", "")).strip()
    ]
    return bouw_config_dict(
        blad_naam=inst["blad_naam"],
        header_rij=int(inst["header_rij"] or 1),
        koppel_id_kolom=inst["koppel_id_kolom"],
        totaalscore_kolom=inst["totaalscore_kolom"],
        opleiding=inst["opleiding"],
        instellingscode=inst["instellingscode"],
        jaar=inst["jaar"],
        kolommen=kolommen,
    )


def _preview_tabel(tabel_id: str):
    """Een doorscrolbare, alleen-lezen tabel voor een datavoorbeeld."""
    return dash_table.DataTable(
        id=tabel_id,
        data=[],
        columns=[],
        page_action="none",
        fixed_rows={"headers": True},
        style_table={"overflowX": "auto", "overflowY": "auto", "maxHeight": "320px"},
        style_header=TABLE_STYLE["style_header"],
        style_cell={
            **TABLE_STYLE["style_cell"],
            "minWidth": "110px",
            "maxWidth": "260px",
            "textOverflow": "ellipsis",
            "overflow": "hidden",
        },
    )


def maak_layout():
    return dbc.Tab(
        label="Configuratie",
        tab_id="tab-config",
        children=[
            html.Div(
                [
                    html.H5("Configuratie en data"),
                    html.P(
                        "Hier zie je precies welke configuratie het dashboard "
                        "gebruikt en een voorbeeld van de verwerkte data. Pas de "
                        "configuratie aan en klik op 'Pas toe en herbereken' om het "
                        "dashboard met de nieuwe instellingen door te rekenen, of "
                        "download de configuratie als Excel om hem later opnieuw te "
                        "gebruiken.",
                        className="text-muted small",
                    ),
                    dbc.Card(
                        dbc.CardBody(
                            [
                                html.H6("Instellingen", className="mb-3"),
                                dbc.Row(
                                    [
                                        dbc.Col(
                                            [
                                                dbc.Label(label, className="small"),
                                                dbc.Input(
                                                    id=f"cfg-inst-{sleutel}",
                                                    type="text",
                                                    size="sm",
                                                ),
                                            ],
                                            md=4,
                                            className="mb-2",
                                        )
                                        for sleutel, label in INSTELLING_VELDEN
                                    ]
                                ),
                            ]
                        ),
                        className="mb-3",
                    ),
                    dbc.Card(
                        dbc.CardBody(
                            [
                                html.H6("Kolommen", className="mb-1"),
                                html.P(
                                    "De scorekolommen die worden meegenomen. Verwijder "
                                    "een rij met het kruisje, of pas instrument, item, "
                                    "criterium en schaal aan.",
                                    className="text-muted small",
                                ),
                                dash_table.DataTable(
                                    id="cfg-kolommen-tabel",
                                    columns=[
                                        {"name": "Kolom", "id": "kolom_naam"},
                                        {"name": "Instrument", "id": "instrument"},
                                        {"name": "Item", "id": "item"},
                                        {"name": "Criterium", "id": "criterium"},
                                        {"name": "Schaal", "id": "schaal"},
                                    ],
                                    data=[],
                                    editable=True,
                                    row_deletable=True,
                                    style_table={"overflowX": "auto"},
                                    style_header=TABLE_STYLE["style_header"],
                                    style_cell={
                                        **TABLE_STYLE["style_cell"],
                                        "minWidth": "110px",
                                    },
                                ),
                            ]
                        ),
                        className="mb-3",
                    ),
                    dbc.Row(
                        [
                            dbc.Col(
                                dbc.Button(
                                    "Pas toe en herbereken",
                                    id="cfg-apply-btn",
                                    color="primary",
                                    size="sm",
                                    className="w-100",
                                ),
                                md=6,
                            ),
                            dbc.Col(
                                dbc.Button(
                                    "Download config (Excel)",
                                    id="cfg-download-btn",
                                    color="secondary",
                                    outline=True,
                                    size="sm",
                                    className="w-100",
                                ),
                                md=6,
                            ),
                        ],
                        className="g-2",
                    ),
                    dcc.Download(id="cfg-download"),
                    dcc.Loading(html.Div(id="cfg-status", className="mt-2")),
                    html.Hr(className="my-4"),
                    html.H6("Voorbeeld van de data"),
                    html.P(
                        "De verwerkte data die het dashboard gebruikt. Scroll om "
                        "erdoorheen te bladeren.",
                        className="text-muted small",
                    ),
                    html.Div(
                        [
                            dbc.Label("Selectiescores", className="small fw-bold"),
                            _preview_tabel("cfg-preview-scores"),
                        ],
                        className="mb-4",
                    ),
                    html.Div(
                        [
                            dbc.Label(
                                "Studievoortgang en koppeling (1CHO)",
                                className="small fw-bold",
                            ),
                            _preview_tabel("cfg-preview-data"),
                        ],
                        className="mb-2",
                    ),
                ],
                className="config-tab",
            )
        ],
    )


def _tabel_inhoud(df: pd.DataFrame) -> tuple[list[dict], list[dict]]:
    """Kolomdefinities en (afgekapte) rijen voor een preview-tabel."""
    if df.empty:
        return [], []
    kolommen = [{"name": str(c), "id": str(c)} for c in df.columns]
    sub = df.head(PREVIEW_RIJEN).astype(object)
    data = sub.where(pd.notna(sub), "").to_dict("records")
    return kolommen, data


def registreer_callbacks(app):
    @app.callback(
        [Output(f"cfg-inst-{sleutel}", "value") for sleutel, _ in INSTELLING_VELDEN]
        + [Output("cfg-kolommen-tabel", "data")],
        Input("config-store", "data"),
    )
    def vul_config(config_json):
        if not config_json:
            return ["" for _ in INSTELLING_VELDEN] + [[]]
        config = json.loads(config_json)
        waarden = [config.get(sleutel, "") for sleutel, _ in INSTELLING_VELDEN]
        kolommen = [
            {veld: kol.get(veld, "") for veld in KOLOM_VELDEN}
            for kol in config.get("kolommen", [])
        ]
        return waarden + [kolommen]

    @app.callback(
        Output("cfg-preview-scores", "columns"),
        Output("cfg-preview-scores", "data"),
        Output("cfg-preview-data", "columns"),
        Output("cfg-preview-data", "data"),
        Input("scores-store", "data"),
        Input("data-store", "data"),
    )
    def vul_previews(scores_json, data_json):
        # scores_df heeft geen 'groep'-kolom, dus df_from_store (dat een
        # categorische groep verwacht) kan alleen op de gekoppelde data-store.
        scores_df = (
            pd.read_json(io.StringIO(scores_json), orient="split")
            if scores_json
            else pd.DataFrame()
        )
        data_df = df_from_store(data_json) if data_json else pd.DataFrame()
        scores_kol, scores_data = _tabel_inhoud(scores_df)
        data_kol, data_data = _tabel_inhoud(data_df)
        return scores_kol, scores_data, data_kol, data_data

    @app.callback(
        Output("data-store", "data", allow_duplicate=True),
        Output("scores-store", "data", allow_duplicate=True),
        Output("config-store", "data", allow_duplicate=True),
        Output("cfg-status", "children"),
        Input("cfg-apply-btn", "n_clicks"),
        [State(f"cfg-inst-{sleutel}", "value") for sleutel, _ in INSTELLING_VELDEN]
        + [
            State("cfg-kolommen-tabel", "data"),
            State("raw-selectie-store", "data"),
            State("raw-cho-store", "data"),
        ],
        prevent_initial_call=True,
    )
    def pas_toe(n, *args):
        no = dash.no_update
        if not n:
            return no, no, no, no

        *veld_waarden, tabel_data, raw_sel, raw_cho = args
        if not raw_sel or not raw_cho:
            return (
                no,
                no,
                no,
                dbc.Alert(
                    "De oorspronkelijke bestanden zijn niet beschikbaar. Dit werkt "
                    "alleen op data die in deze sessie is geladen.",
                    color="warning",
                    className="small py-1",
                ),
            )

        try:
            config = _config_uit_velden(veld_waarden, tabel_data or [])
            cho = json.loads(raw_cho)
            data_json, scores_json = bouw_data_stores(
                config, raw_sel, parse_csv_or_excel(cho["contents"], cho["filename"])
            )
        except Exception as e:
            return (
                no,
                no,
                no,
                dbc.Alert(
                    f"Herberekenen mislukt: {e}", color="danger", className="small py-1"
                ),
            )

        return (
            data_json,
            scores_json,
            json.dumps(config),
            dbc.Alert(
                "Dashboard opnieuw doorgerekend met de aangepaste configuratie.",
                color="success",
                className="small py-1",
            ),
        )

    @app.callback(
        Output("cfg-download", "data"),
        Input("cfg-download-btn", "n_clicks"),
        [State(f"cfg-inst-{sleutel}", "value") for sleutel, _ in INSTELLING_VELDEN]
        + [State("cfg-kolommen-tabel", "data")],
        prevent_initial_call=True,
    )
    def download_config(n, *args):
        if not n:
            return dash.no_update
        *veld_waarden, tabel_data = args
        config = _config_uit_velden(veld_waarden, tabel_data or [])
        excel_bytes = exporteer_config_excel(config)
        opleiding = config.get("opleiding", "config") or "config"
        veilig = re.sub(r"[^\w.-]", "_", opleiding)
        return dcc.send_bytes(
            lambda buf: buf.write(excel_bytes), f"config_{veilig}.xlsx"
        )
