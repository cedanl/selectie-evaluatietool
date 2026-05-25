"""
Evaluatietool: selectie & studiesucces dashboard

Draai met: uv run python app.py
Data aanmaken: uv run python scripts/maak_data.py
"""

import base64
import io
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from scipy import stats

import dash
from dash import dcc, html, dash_table, Input, Output, State, ctx
import dash_bootstrap_components as dbc

CHO_PATH    = Path("data/synthetic/studiesucces_data.csv")
SCORES_PATH = Path("data/synthetic/selectiescores_voorbeeld.csv")

GROEP_VOLGORDE = [
    "Niet gestart",
    "Gestart, niet naar jaar 2",
    "Doorgestroomd naar jaar 2",
]
GROEP_KLEUREN = {
    "Niet gestart": "#94a3b8",
    "Gestart, niet naar jaar 2": "#f97316",
    "Doorgestroomd naar jaar 2": "#22c55e",
}
GROEP_XTICKLABELS = [
    "Niet<br>gestart",
    "Gestart, niet<br>naar jaar 2",
    "Doorgestroomd<br>naar jaar 2",
]

VERPLICHTE_CHO_KOLOMMEN    = ["kandidaat_id", "selectiejaar", "groep"]
VERPLICHTE_SCORES_KOLOMMEN = ["kandidaat_id", "instrument", "item", "criterium", "score"]


def get_score_cols(df: pd.DataFrame) -> list[str]:
    return sorted(c for c in df.columns if c.endswith("_score") and c != "totaalscore")


def col_to_label(col: str) -> str:
    if col == "totaalscore":
        return "Totaalscore"
    name = col.replace("_score", "").replace("_", " ")
    return name[0].upper() + name[1:] if name else col


def score_opties_uit_df(df: pd.DataFrame) -> list[dict]:
    cols = get_score_cols(df) + ["totaalscore"]
    return [{"label": col_to_label(c), "value": c} for c in cols]


def koppel_data(cho_df: pd.DataFrame, scores_df: pd.DataFrame) -> pd.DataFrame:
    instrument_gem = (
        scores_df.groupby(["kandidaat_id", "instrument"])["score"]
        .mean()
        .reset_index()
    )
    pivot = instrument_gem.pivot(index="kandidaat_id", columns="instrument", values="score")
    score_cols = [f"{c}_score" for c in pivot.columns]
    pivot.columns = score_cols
    pivot["totaalscore"] = pivot[score_cols].mean(axis=1).round(2)
    pivot = pivot.reset_index()

    meta = scores_df.groupby("kandidaat_id").first()[["selectie_uitkomst"]].reset_index() \
        if "selectie_uitkomst" in scores_df.columns else pd.DataFrame({"kandidaat_id": pivot["kandidaat_id"]})
    pivot = pivot.merge(meta, on="kandidaat_id", how="left")

    df = pivot.merge(cho_df, on="kandidaat_id", how="outer")
    df["groep"] = pd.Categorical(
        df["groep"].fillna("Niet gestart"), categories=GROEP_VOLGORDE, ordered=True
    )
    return df


df_cho_demo    = pd.read_csv(CHO_PATH, sep=";")    if CHO_PATH.exists()    else pd.DataFrame()
df_scores_demo = pd.read_csv(SCORES_PATH, sep=";") if SCORES_PATH.exists() else pd.DataFrame()

if not df_cho_demo.empty and not df_scores_demo.empty:
    df_demo = koppel_data(df_cho_demo, df_scores_demo)
else:
    df_demo = df_cho_demo.copy()
    df_demo["groep"] = pd.Categorical(
        df_demo["groep"].fillna("Niet gestart") if "groep" in df_demo.columns else "Niet gestart",
        categories=GROEP_VOLGORDE, ordered=True,
    )

JAREN_DEMO    = sorted(df_demo["selectiejaar"].unique().tolist()) if "selectiejaar" in df_demo.columns else []
SCORE_OPTIES_INIT = score_opties_uit_df(df_demo)


def df_from_store(store_data: str | None) -> pd.DataFrame:
    if store_data is None:
        return df_demo.copy()
    df = pd.read_json(io.StringIO(store_data), orient="split")
    df["groep"] = pd.Categorical(
        df["groep"], categories=GROEP_VOLGORDE, ordered=True
    )
    return df


def maak_filter_opties(df: pd.DataFrame, kolom: str, alle_label: str = "Alle") -> list[dict]:
    return [{"label": alle_label, "value": "Alle"}] + [
        {"label": str(v), "value": str(v)}
        for v in sorted(df[kolom].dropna().unique())
    ]


def filter_data(df: pd.DataFrame, cohort, geslacht, vooropleiding, incl_cohort=True):
    if incl_cohort and cohort != "Alle":
        df = df[df["selectiejaar"] == int(cohort)]
    if geslacht != "Alle":
        df = df[df["geslacht"] == geslacht]
    if vooropleiding != "Alle":
        df = df[df["hoogste_vooropleiding"] == vooropleiding]
    return df


def fix_xas_labels(fig):
    fig.update_xaxes(
        tickmode="array",
        tickvals=GROEP_VOLGORDE,
        ticktext=GROEP_XTICKLABELS,
    )
    return fig


def sig_sym(p):
    return "***" if p < 0.001 else "**" if p < 0.01 else "*" if p < 0.05 else "ns"


def fmt_p(p):
    return "< 0.001" if p < 0.001 else f"{p:.3f}"


CHART_BASE = dict(plot_bgcolor="white", paper_bgcolor="white")

TABLE_STYLE = dict(
    style_cell={
        "padding": "8px 14px",
        "fontSize": "13px",
        "border": "1px solid #f1f5f9",
        "fontFamily": "inherit",
    },
    style_header={
        "backgroundColor": "#f8fafc",
        "fontWeight": "600",
        "border": "1px solid #e2e8f0",
        "fontSize": "12px",
        "letterSpacing": "0.02em",
        "fontFamily": "inherit",
    },
    style_data={"backgroundColor": "#ffffff"},
)


def bereken_pct(agg: pd.DataFrame, groep_kolom: str) -> pd.DataFrame:
    agg["pct"] = (
        agg["n"] / agg.groupby(groep_kolom)["n"].transform("sum") * 100
    ).round(1)
    return agg


def _parse_csv(contents: str) -> pd.DataFrame:
    content_type, content_string = contents.split(",")
    decoded = base64.b64decode(content_string).decode("utf-8")
    sep = ";" if decoded[:500].count(";") > decoded[:500].count(",") else ","
    return pd.read_csv(io.StringIO(decoded), sep=sep)


# ── Upload overlay ─────────────────────────────────────────────────────────────

UPLOAD_OVERLAY = html.Div(
    id="upload-overlay",
    children=[
        html.Div(
            [
                html.Img(
                    src="/assets/nko-logo.svg",
                    style={"height": "48px", "marginBottom": "24px"},
                ),
                html.H3("Evaluatietool Selectie", className="mb-1"),
                html.P(
                    "Upload beide bestanden om het dashboard te openen.",
                    className="text-muted mb-4",
                ),
                dbc.Card(
                    dbc.CardBody(
                        [
                            html.H6("Selectiescores uploaden", className="mb-1"),
                            html.P(
                                "selectiescores.csv met scores op instrument-, item- en criterium-niveau.",
                                className="text-muted small mb-3",
                            ),
                            dcc.Upload(
                                id="upload-selectiescores",
                                children=html.Div(
                                    ["Sleep een bestand hierheen of ", html.A("blader", style={"cursor": "pointer"})]
                                ),
                                className="upload-zone",
                                accept=".csv",
                                max_size=50 * 1024 * 1024,
                            ),
                            html.Div(id="scores-upload-status", className="mt-2"),
                        ]
                    ),
                    className="mb-3 text-start",
                ),
                dbc.Card(
                    dbc.CardBody(
                        [
                            html.H6("Studiesuccesdata uploaden", className="mb-1"),
                            html.P(
                                "studiesucces_data.csv met 1CHO-gegevens en studieuitkomsten per kandidaat.",
                                className="text-muted small mb-3",
                            ),
                            dcc.Upload(
                                id="upload-studiesucces",
                                children=html.Div(
                                    ["Sleep een bestand hierheen of ", html.A("blader", style={"cursor": "pointer"})]
                                ),
                                className="upload-zone",
                                accept=".csv",
                                max_size=50 * 1024 * 1024,
                            ),
                            html.Div(id="cho-upload-status", className="mt-2"),
                        ]
                    ),
                    className="mb-3 text-start",
                ),
                html.Hr(className="my-3"),
                html.P("Nog geen eigen data?", className="text-muted small mb-2"),
                dbc.Button(
                    "Gebruik synthetische demodata",
                    id="btn-demodata",
                    color="secondary",
                    size="sm",
                ),
            ],
            className="upload-card",
        )
    ],
    className="upload-overlay",
)

# ── Sidebar ────────────────────────────────────────────────────────────────────

cohort_init = [{"label": "Alle cohorten", "value": "Alle"}] + [
    {"label": str(j), "value": str(j)} for j in JAREN_DEMO
]

SIDEBAR = html.Div(
    [
        html.Img(src="/assets/nko-logo.svg", className="sidebar-logo"),
        html.P("Filters", className="sidebar-label"),
        dbc.Label("Cohort"),
        dcc.Dropdown(
            id="cohort-dropdown",
            options=cohort_init,
            value="Alle",
            clearable=False,
            className="mb-3",
        ),
        dbc.Label("Geslacht"),
        dcc.Dropdown(
            id="geslacht-dropdown",
            options=maak_filter_opties(df_demo, "geslacht") if "geslacht" in df_demo.columns else [],
            value="Alle",
            clearable=False,
            className="mb-3",
        ),
        dbc.Label("Vooropleiding"),
        dcc.Dropdown(
            id="vooropleiding-dropdown",
            options=maak_filter_opties(df_demo, "hoogste_vooropleiding") if "hoogste_vooropleiding" in df_demo.columns else [],
            value="Alle",
            clearable=False,
            className="mb-4",
        ),
        html.Hr(className="my-2"),
        html.P("Kandidaten per cohort", className="sidebar-label"),
        html.Div(id="cohort-stats"),
        html.Hr(className="mt-3 mb-2"),
        dbc.Button(
            "Nieuw bestand laden",
            id="btn-reset",
            color="link",
            size="sm",
            className="p-0 text-muted",
            style={"fontSize": "12px"},
        ),
    ],
    className="sidebar-wrapper",
)

# ── App layout ─────────────────────────────────────────────────────────────────

app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    title="Evaluatietool Selectie",
    suppress_callback_exceptions=True,
)

app.layout = html.Div(
    [
        dcc.Store(id="data-store", storage_type="memory"),
        dcc.Store(id="scores-store", storage_type="memory"),
        UPLOAD_OVERLAY,
        html.Div(
            [
                SIDEBAR,
                html.Div(
                    [
                        html.H4("Evaluatietool Selectie", className="app-title"),
                        html.P(
                            id="app-subtitle",
                            className="text-muted mb-3",
                            style={"fontSize": "13px"},
                        ),
                        dbc.Tabs(
                            [
                                dbc.Tab(
                                    label="Selectiescores",
                                    tab_id="tab-scores",
                                    children=[
                                        html.Div(
                                            [
                                                html.H5("Selectiescores per uitkomstgroep"),
                                                html.P(
                                                    "Hogere scores bij doorstromers dan bij uitvallers signaleren predictieve validiteit "
                                                    "van het selectie-instrument. Let op overlap: een instrument dat groepen niet "
                                                    "onderscheidt heeft weinig voorspellende waarde.",
                                                    className="text-muted small",
                                                ),
                                                html.Div(
                                                    [
                                                        dbc.Label("Analyseniveau", className="me-2 mb-0 align-self-center", style={"fontSize": "13px"}),
                                                        dbc.RadioItems(
                                                            id="scores-niveau",
                                                            options=[
                                                                {"label": "Instrument", "value": "instrument"},
                                                                {"label": "Item", "value": "item", "disabled": True},
                                                                {"label": "Criterium", "value": "criterium", "disabled": True},
                                                            ],
                                                            value="instrument",
                                                            inline=True,
                                                        ),
                                                        html.Span(
                                                            id="niveau-hint",
                                                            className="text-muted ms-3 align-self-center",
                                                            style={"fontSize": "12px"},
                                                        ),
                                                    ],
                                                    className="d-flex align-items-center mb-3",
                                                ),
                                                dcc.Loading(dcc.Graph(id="fig-totaal"), type="dot"),
                                                html.Hr(),
                                                html.H6("Gemiddelden per groep"),
                                                dash_table.DataTable(
                                                    id="tabel-gemiddelden",
                                                    style_table={"overflowX": "auto"},
                                                    **TABLE_STYLE,
                                                ),
                                                html.Hr(),
                                                html.P(
                                                    "Mann-Whitney U toets: vergelijkt de scoreverdeling van studenten die niet "
                                                    "doorstroomden naar jaar 2 met studenten die dat wel deden. Een significante "
                                                    "uitkomst betekent dat de twee groepen systematisch anders scoren op dat "
                                                    "instrument, wat wijst op predictieve validiteit. De toets maakt geen aanname "
                                                    "over een normale verdeling en is daardoor geschikt voor scores op een begrensde "
                                                    "schaal (1-10). ns = niet significant (p>=0.05).  "
                                                    "* p<0.05  ** p<0.01  *** p<0.001",
                                                    className="text-muted small",
                                                ),
                                                dash_table.DataTable(
                                                    id="tabel-mannwhitney",
                                                    style_table={"overflowX": "auto", "maxWidth": "560px"},
                                                    **TABLE_STYLE,
                                                ),
                                            ],
                                            className="tab-body",
                                        ),
                                    ],
                                ),
                                dbc.Tab(
                                    label="Verdeling",
                                    tab_id="tab-verdeling",
                                    children=[
                                        html.Div(
                                            [
                                                html.H5("Verdeling per groep"),
                                                html.P(id="verdeling-caption", className="text-muted small"),
                                                dcc.Loading(dcc.Graph(id="fig-verdeling"), type="dot"),
                                            ],
                                            className="tab-body",
                                        ),
                                    ],
                                ),
                                dbc.Tab(
                                    label="Demografisch",
                                    tab_id="tab-demo",
                                    children=[
                                        html.Div(
                                            [
                                                html.H5("Demografisch profiel per groep"),
                                                html.P(
                                                    "Achtergrondkenmerken komen uit 1CHO en zijn alleen beschikbaar voor ingeschreven studenten.",
                                                    className="text-muted small",
                                                ),
                                                dbc.Row(
                                                    [
                                                        dbc.Col(dcc.Loading(dcc.Graph(id="fig-geslacht"), type="dot")),
                                                        dbc.Col(dcc.Loading(dcc.Graph(id="fig-herkomst"), type="dot")),
                                                    ]
                                                ),
                                                dcc.Loading(dcc.Graph(id="fig-vooropleiding"), type="dot"),
                                                html.Hr(),
                                                dcc.Loading(dcc.Graph(id="fig-instroom"), type="dot"),
                                            ],
                                            className="tab-body",
                                        ),
                                    ],
                                ),
                                dbc.Tab(
                                    label="Instrumentvergelijking",
                                    tab_id="tab-puntenwolk",
                                    children=[
                                        html.Div(
                                            [
                                                html.H5("Puntenwolk selectiescores"),
                                                html.P(
                                                    "Vergelijk twee selectie-instrumenten tegen elkaar. "
                                                    "Punten ver van de diagonaal zijn kandidaten die op de twee instrumenten sterk verschillen.",
                                                    className="text-muted small",
                                                ),
                                                dbc.Row(
                                                    [
                                                        dbc.Col(
                                                            [
                                                                dbc.Label("X-as"),
                                                                dcc.Dropdown(
                                                                    id="scatter-x",
                                                                    options=SCORE_OPTIES_INIT,
                                                                    value=SCORE_OPTIES_INIT[0]["value"] if SCORE_OPTIES_INIT else None,
                                                                    clearable=False,
                                                                ),
                                                            ],
                                                            width=3,
                                                        ),
                                                        dbc.Col(
                                                            [
                                                                dbc.Label("Y-as"),
                                                                dcc.Dropdown(
                                                                    id="scatter-y",
                                                                    options=SCORE_OPTIES_INIT,
                                                                    value=SCORE_OPTIES_INIT[1]["value"] if len(SCORE_OPTIES_INIT) > 1 else SCORE_OPTIES_INIT[0]["value"] if SCORE_OPTIES_INIT else None,
                                                                    clearable=False,
                                                                ),
                                                            ],
                                                            width=3,
                                                        ),
                                                    ],
                                                    className="mb-3",
                                                ),
                                                dcc.Loading(dcc.Graph(id="fig-puntenwolk"), type="dot"),
                                            ],
                                            className="tab-body",
                                        ),
                                    ],
                                ),
                                dbc.Tab(
                                    label="VO-cijfer",
                                    tab_id="tab-vo",
                                    children=[
                                        html.Div(
                                            [
                                                html.H5("VO-eindcijfer vs selectiescores"),
                                                html.P(
                                                    "Het VO-eindcijfer is het gemiddeld eindexamencijfer van de hoogste vooropleiding "
                                                    "voor het hoger onderwijs; voor de meeste studenten is dat het VWO-diploma. "
                                                    "Het komt rechtstreeks uit het EV-bestand van 1CHO en is daardoor onafhankelijk van "
                                                    "wat de opleiding zelf heeft gemeten tijdens de selectie. "
                                                    "De grafiek laat zien of de selectie-instrumenten informatie toevoegen die de school "
                                                    "nog niet had. Een lage samenhang (r = 0) betekent dat het instrument iets "
                                                    "wezenlijk anders meet dan cognitieve schoolprestaties, zoals motivatie of "
                                                    "communicatievaardigheid. Een hoge samenhang (r = 1) suggereert dat de selectie "
                                                    "grotendeels herhaalt wat het VO-cijfer al zegt. Alleen ingeschreven studenten zijn zichtbaar.",
                                                    className="text-muted small",
                                                ),
                                                dbc.Row(
                                                    [
                                                        dbc.Col(
                                                            [
                                                                dbc.Label("Selectiescore (y-as)"),
                                                                dcc.Dropdown(
                                                                    id="vo-score",
                                                                    options=SCORE_OPTIES_INIT,
                                                                    value=SCORE_OPTIES_INIT[0]["value"] if SCORE_OPTIES_INIT else None,
                                                                    clearable=False,
                                                                ),
                                                            ],
                                                            width=3,
                                                        ),
                                                    ],
                                                    className="mb-3",
                                                ),
                                                dcc.Loading(dcc.Graph(id="fig-vo"), type="dot"),
                                                html.Hr(),
                                                html.P(
                                                    "Pearson r meet de lineaire samenhang tussen VO-eindcijfer en selectiescore. "
                                                    "Een lage r is wenselijk: het instrument voegt informatie toe die VO-cijfers niet geven.",
                                                    className="text-muted small",
                                                ),
                                                dash_table.DataTable(
                                                    id="tabel-pearsonr",
                                                    style_table={"overflowX": "auto", "maxWidth": "380px"},
                                                    **TABLE_STYLE,
                                                ),
                                                html.P(
                                                    "Kleuren: groen (r < 0.3) = instrument meet iets anders dan schoolprestaties, "
                                                    "goede discriminante validiteit. "
                                                    "geel (0.3 tot 0.5) = enige overlap met VO-prestaties. "
                                                    "rood (r >= 0.5) = instrument selecteert grotendeels op dezelfde dimensie als VO-cijfers. "
                                                    "oranje (r < -0.2) = onverwacht negatief verband, nader onderzoek aanbevolen.",
                                                    className="text-muted small mt-2",
                                                ),
                                            ],
                                            className="tab-body",
                                        ),
                                    ],
                                ),
                            ],
                            id="main-tabs",
                            active_tab="tab-scores",
                        ),
                    ],
                    className="main-wrapper",
                ),
            ],
            className="app-shell",
        ),
    ]
)

# ── Upload callbacks ───────────────────────────────────────────────────────────


@app.callback(
    Output("upload-overlay", "style"),
    Input("data-store", "data"),
)
def toggle_overlay(store_data):
    return {"display": "flex"} if store_data is None else {"display": "none"}


@app.callback(
    Output("data-store", "data"),
    Output("scores-store", "data"),
    Output("scores-upload-status", "children"),
    Output("cho-upload-status", "children"),
    Input("upload-selectiescores", "contents"),
    Input("upload-studiesucces", "contents"),
    Input("btn-demodata", "n_clicks"),
    Input("btn-reset", "n_clicks"),
    State("upload-selectiescores", "filename"),
    State("upload-studiesucces", "filename"),
    prevent_initial_call=True,
)
def verwerk_upload(scores_contents, cho_contents, _demo, _reset, scores_fn, cho_fn):
    trigger = ctx.triggered_id

    if trigger == "btn-reset":
        return None, None, "", ""

    if trigger == "btn-demodata":
        if df_cho_demo.empty or df_scores_demo.empty:
            return dash.no_update, dash.no_update, dash.no_update, dash.no_update
        joined = koppel_data(df_cho_demo, df_scores_demo)
        return (
            joined.to_json(orient="split", date_format="iso"),
            df_scores_demo.to_json(orient="split", date_format="iso"),
            "Demodata geladen.",
            "Demodata geladen.",
        )

    if trigger == "upload-selectiescores":
        if scores_contents is None:
            return dash.no_update, dash.no_update, dash.no_update, dash.no_update
        try:
            scores_df = _parse_csv(scores_contents)
        except Exception as e:
            return dash.no_update, dash.no_update, dbc.Alert(str(e), color="danger", className="small py-1"), dash.no_update
        missing = [c for c in VERPLICHTE_SCORES_KOLOMMEN if c not in scores_df.columns]
        if missing:
            return dash.no_update, dash.no_update, dbc.Alert(f"Ontbrekende kolommen: {', '.join(missing)}", color="danger", className="small py-1"), dash.no_update
        status = dbc.Alert(f"{scores_fn} geladen.", color="success", className="small py-1")
        if cho_contents is not None:
            try:
                cho_df = _parse_csv(cho_contents)
                joined = koppel_data(cho_df, scores_df)
                return joined.to_json(orient="split", date_format="iso"), scores_df.to_json(orient="split", date_format="iso"), status, dash.no_update
            except Exception as e:
                return dash.no_update, dash.no_update, dbc.Alert(str(e), color="danger", className="small py-1"), dash.no_update
        return dash.no_update, dash.no_update, status, dash.no_update

    if trigger == "upload-studiesucces":
        if cho_contents is None:
            return dash.no_update, dash.no_update, dash.no_update, dash.no_update
        try:
            cho_df = _parse_csv(cho_contents)
        except Exception as e:
            return dash.no_update, dash.no_update, dash.no_update, dbc.Alert(str(e), color="danger", className="small py-1")
        missing = [c for c in VERPLICHTE_CHO_KOLOMMEN if c not in cho_df.columns]
        if missing:
            return dash.no_update, dash.no_update, dash.no_update, dbc.Alert(f"Ontbrekende kolommen: {', '.join(missing)}", color="danger", className="small py-1")
        status = dbc.Alert(f"{cho_fn} geladen.", color="success", className="small py-1")
        if scores_contents is not None:
            try:
                scores_df = _parse_csv(scores_contents)
                joined = koppel_data(cho_df, scores_df)
                return joined.to_json(orient="split", date_format="iso"), scores_df.to_json(orient="split", date_format="iso"), dash.no_update, status
            except Exception as e:
                return dash.no_update, dash.no_update, dash.no_update, dbc.Alert(str(e), color="danger", className="small py-1")
        return dash.no_update, dash.no_update, dash.no_update, status

    return dash.no_update, dash.no_update, dash.no_update, dash.no_update


# ── Niveau selector ────────────────────────────────────────────────────────────


@app.callback(
    Output("scores-niveau", "options"),
    Output("scores-niveau", "value"),
    Output("niveau-hint", "children"),
    Input("scores-store", "data"),
    State("scores-niveau", "value"),
)
def update_niveau_opties(scores_store, huidig_niveau):
    heeft_scores = scores_store is not None
    opties = [
        {"label": "Instrument", "value": "instrument"},
        {"label": "Item", "value": "item", "disabled": not heeft_scores},
        {"label": "Criterium", "value": "criterium", "disabled": not heeft_scores},
    ]
    hint = "" if heeft_scores else "Laad selectiescores voor item- en criterium-detail"
    nieuw_niveau = huidig_niveau if heeft_scores else "instrument"
    return opties, nieuw_niveau, hint


# ── Sidebar callbacks ──────────────────────────────────────────────────────────


@app.callback(
    Output("cohort-dropdown", "options"),
    Output("cohort-dropdown", "value"),
    Output("geslacht-dropdown", "options"),
    Output("geslacht-dropdown", "value"),
    Output("vooropleiding-dropdown", "options"),
    Output("vooropleiding-dropdown", "value"),
    Output("scatter-x", "options"),
    Output("scatter-x", "value"),
    Output("scatter-y", "options"),
    Output("scatter-y", "value"),
    Output("vo-score", "options"),
    Output("vo-score", "value"),
    Output("app-subtitle", "children"),
    Input("data-store", "data"),
)
def update_filters_on_data_change(store_data):
    df = df_from_store(store_data)
    jaren = sorted(df["selectiejaar"].unique().tolist()) if "selectiejaar" in df.columns else []
    cohort_opties = [{"label": "Alle cohorten", "value": "Alle"}] + [
        {"label": str(j), "value": str(j)} for j in jaren
    ]
    opleiding  = df["opleiding"].dropna().iloc[0]  if "opleiding"  in df.columns and df["opleiding"].notna().any()  else ""
    instelling = df["instellingscode"].dropna().iloc[0] if "instellingscode" in df.columns and df["instellingscode"].notna().any() else ""
    subtitle   = f"{opleiding} | {instelling}" if opleiding else ""

    score_opties = score_opties_uit_df(df)
    default_x  = score_opties[0]["value"]  if score_opties else None
    default_y  = score_opties[1]["value"]  if len(score_opties) > 1 else default_x
    default_vo = score_opties[0]["value"]  if score_opties else None

    return (
        cohort_opties, "Alle",
        maak_filter_opties(df, "geslacht") if "geslacht" in df.columns else [{"label": "Alle", "value": "Alle"}], "Alle",
        maak_filter_opties(df, "hoogste_vooropleiding") if "hoogste_vooropleiding" in df.columns else [{"label": "Alle", "value": "Alle"}], "Alle",
        score_opties, default_x,
        score_opties, default_y,
        score_opties, default_vo,
        subtitle,
    )


@app.callback(
    Output("cohort-stats", "children"),
    Input("geslacht-dropdown", "value"),
    Input("vooropleiding-dropdown", "value"),
    State("data-store", "data"),
)
def update_cohort_stats(geslacht, vooropleiding, store_data):
    df = df_from_store(store_data)
    df = filter_data(df, "Alle", geslacht, vooropleiding, incl_cohort=False)
    jaren = sorted(df["selectiejaar"].unique().tolist()) if "selectiejaar" in df.columns else []
    aantallen = df.groupby("selectiejaar").size() if jaren else pd.Series(dtype=int)
    return dbc.Row(
        [
            dbc.Col(
                html.Div(
                    [
                        html.Div(str(jaar), className="stat-year"),
                        html.Div(str(int(aantallen.get(jaar, 0))), className="stat-value"),
                    ],
                    className="stat-box",
                )
            )
            for jaar in jaren
        ],
        className="g-1",
    )


# ── Dashboard callbacks ────────────────────────────────────────────────────────


@app.callback(
    Output("fig-totaal", "figure"),
    Output("tabel-gemiddelden", "data"),
    Output("tabel-gemiddelden", "columns"),
    Output("tabel-mannwhitney", "data"),
    Output("tabel-mannwhitney", "columns"),
    Input("cohort-dropdown", "value"),
    Input("geslacht-dropdown", "value"),
    Input("vooropleiding-dropdown", "value"),
    Input("scores-niveau", "value"),
    State("data-store", "data"),
    State("scores-store", "data"),
)
def update_scores_tab(cohort, geslacht, vooropleiding, niveau, store_data, scores_store):
    df = filter_data(df_from_store(store_data), cohort, geslacht, vooropleiding)
    leeg = go.Figure().update_layout(**CHART_BASE, margin=dict(t=10, b=10))

    if niveau in ("item", "criterium") and scores_store is not None:
        scores_df = pd.read_json(io.StringIO(scores_store), orient="split")
        if niveau == "item":
            pivot = scores_df.groupby(["kandidaat_id", "instrument", "item"])["score"].mean().reset_index()
            pivot["score_naam"] = pivot["instrument"] + " / " + pivot["item"]
        else:
            pivot = scores_df.groupby(["kandidaat_id", "instrument", "item", "criterium"])["score"].mean().reset_index()
            pivot["score_naam"] = pivot["instrument"] + " / " + pivot["item"] + " / " + pivot["criterium"]

        df_groep = df[["kandidaat_id", "groep"]].drop_duplicates()
        pivot = pivot.merge(df_groep, on="kandidaat_id", how="inner")
        pivot["groep"] = pd.Categorical(pivot["groep"], categories=GROEP_VOLGORDE, ordered=True)
        namen = sorted(pivot["score_naam"].unique())

        fig = px.violin(
            pivot, x="score_naam", y="score", color="groep",
            color_discrete_map=GROEP_KLEUREN,
            category_orders={"groep": GROEP_VOLGORDE, "score_naam": namen},
            box=True, points=False, height=560,
            labels={"score_naam": "", "score": "Score (1-10)", "groep": ""},
        )
        fig.update_layout(
            violingap=0.15, legend=dict(orientation="h", y=-0.2),
            xaxis_tickangle=-25, **CHART_BASE, margin=dict(t=20, b=10),
        )

        tabel_pivot = (
            pivot.groupby(["groep", "score_naam"], observed=True)["score"]
            .agg(["mean", "std"]).round(2).reset_index()
            .rename(columns={"score_naam": "Score", "mean": "Gem.", "std": "SD", "groep": "Groep"})
        )
        gem_data = tabel_pivot.to_dict("records")
        gem_cols = [{"name": c, "id": c} for c in tabel_pivot.columns]

        a_ids = df[df["groep"] == "Gestart, niet naar jaar 2"]["kandidaat_id"]
        b_ids = df[df["groep"] == "Doorgestroomd naar jaar 2"]["kandidaat_id"]
        mw_rijen = []
        for naam in namen:
            sub = pivot[pivot["score_naam"] == naam]
            a = sub[sub["kandidaat_id"].isin(a_ids)]["score"].dropna()
            b = sub[sub["kandidaat_id"].isin(b_ids)]["score"].dropna()
            if len(a) >= 2 and len(b) >= 2:
                _, p = stats.mannwhitneyu(a, b, alternative="two-sided")
                mw_rijen.append({"Score": naam, "p-waarde": fmt_p(float(p)), "Sig.": sig_sym(float(p))})
            else:
                mw_rijen.append({"Score": naam, "p-waarde": "n.v.t.", "Sig.": ""})
        mw_cols = [{"name": c, "id": c} for c in ["Score", "p-waarde", "Sig."]]
        return fig, gem_data, gem_cols, mw_rijen, mw_cols

    # Instrument niveau
    score_cols = get_score_cols(df)
    all_cols   = sorted(score_cols) + ["totaalscore"]
    valid_cols = [c for c in all_cols if c in df.columns]

    if not valid_cols:
        return leeg, [], [], [], []

    df_long = df[["kandidaat_id", "groep"] + valid_cols].melt(
        id_vars=["kandidaat_id", "groep"],
        value_vars=valid_cols,
        var_name="col",
        value_name="score",
    )
    df_long["score_naam"] = df_long["col"].apply(col_to_label)
    naam_volgorde = [col_to_label(c) for c in valid_cols]

    fig = px.violin(
        df_long, x="score_naam", y="score", color="groep",
        color_discrete_map=GROEP_KLEUREN,
        category_orders={"groep": GROEP_VOLGORDE, "score_naam": naam_volgorde},
        box=True, points=False, height=520,
        labels={"score_naam": "", "score": "Score (1-10)", "groep": ""},
    )
    fig.update_layout(
        violingap=0.2, legend=dict(orientation="h", y=-0.15),
        **CHART_BASE, margin=dict(t=20, b=10),
    )

    tabel = df.groupby("groep", observed=True)[valid_cols].agg(["mean", "std"]).round(2)
    tabel.columns = [
        f"{col_to_label(var)} {'gem.' if stat == 'mean' else 'SD'}"
        for var, stat in tabel.columns
    ]
    tabel = tabel.reset_index().rename(columns={"groep": "Groep"})
    gem_data = tabel.to_dict("records")
    gem_cols = [{"name": c, "id": c} for c in tabel.columns]

    a_groep = df[df["groep"] == "Gestart, niet naar jaar 2"]
    b_groep = df[df["groep"] == "Doorgestroomd naar jaar 2"]
    mw_rijen = []
    for col in valid_cols:
        a = a_groep[col].dropna()
        b = b_groep[col].dropna()
        if len(a) >= 2 and len(b) >= 2:
            _, p = stats.mannwhitneyu(a, b, alternative="two-sided")
            mw_rijen.append({"Score": col_to_label(col), "p-waarde": fmt_p(float(p)), "Sig.": sig_sym(float(p))})
        else:
            mw_rijen.append({"Score": col_to_label(col), "p-waarde": "n.v.t.", "Sig.": ""})
    mw_cols = [{"name": c, "id": c} for c in ["Score", "p-waarde", "Sig."]]

    return fig, gem_data, gem_cols, mw_rijen, mw_cols


@app.callback(
    Output("fig-verdeling", "figure"),
    Output("verdeling-caption", "children"),
    Input("cohort-dropdown", "value"),
    Input("geslacht-dropdown", "value"),
    Input("vooropleiding-dropdown", "value"),
    State("data-store", "data"),
)
def update_verdeling_tab(cohort, geslacht, vooropleiding, store_data):
    df = df_from_store(store_data)
    labels = [str(cohort) if cohort != "Alle" else "alle cohorten"]
    if geslacht != "Alle":
        labels.append(geslacht)
    if vooropleiding != "Alle":
        labels.append(vooropleiding)

    agg = (
        filter_data(df, "Alle", geslacht, vooropleiding, incl_cohort=False)
        .groupby(["selectiejaar", "groep"], observed=True)
        .size()
        .reset_index(name="n")
    )
    agg["pct"] = (
        agg["n"] / agg.groupby("selectiejaar")["n"].transform("sum") * 100
    ).round(1)

    fig = px.bar(
        agg, x="selectiejaar", y="pct", color="groep", barmode="stack",
        color_discrete_map=GROEP_KLEUREN,
        category_orders={"groep": GROEP_VOLGORDE},
        labels={"selectiejaar": "Cohort", "pct": "Percentage (%)", "groep": ""},
        text="n", custom_data=["n"],
    )
    fig.update_traces(
        texttemplate="%{text}", textposition="inside",
        hovertemplate="%{fullData.name}<br>%{y:.1f}%  (n=%{customdata[0]})<extra></extra>",
    )
    for jaar, tot in agg.groupby("selectiejaar")["n"].sum().items():
        fig.add_annotation(
            x=jaar, y=101, text=f"n={tot}",
            showarrow=False, yshift=6, font=dict(size=12),
        )
    fig.update_layout(
        height=500, legend=dict(orientation="h", y=-0.15),
        yaxis_range=[0, 115], **CHART_BASE,
    )
    return fig, f"Gefilterd op: {', '.join(labels)}"


@app.callback(
    Output("fig-geslacht", "figure"),
    Output("fig-herkomst", "figure"),
    Output("fig-vooropleiding", "figure"),
    Output("fig-instroom", "figure"),
    Input("cohort-dropdown", "value"),
    Input("geslacht-dropdown", "value"),
    Input("vooropleiding-dropdown", "value"),
    State("data-store", "data"),
)
def update_demo_tab(cohort, geslacht, vooropleiding, store_data):
    df = filter_data(df_from_store(store_data), cohort, geslacht, vooropleiding)

    agg_g = bereken_pct(
        df.groupby(["groep", "geslacht"], observed=True).size().reset_index(name="n"), "groep",
    )
    fig3 = px.bar(
        agg_g, x="groep", y="pct", color="geslacht", barmode="stack",
        labels={"groep": "", "pct": "%", "geslacht": "Geslacht"},
        title="Geslacht per groep (%)",
    )
    fig3.update_layout(height=460, legend=dict(orientation="h", y=-0.2), **CHART_BASE)
    fix_xas_labels(fig3)

    agg_h = bereken_pct(
        df[df["herkomst"].notna()]
        .assign(herkomst_kort=lambda d: d["herkomst"].map(lambda x: "Nederland" if x == "Nederland" else "niet-Nederland"))
        .groupby(["groep", "herkomst_kort"], observed=True).size().reset_index(name="n"),
        "groep",
    )
    fig4 = px.bar(
        agg_h, x="groep", y="pct", color="herkomst_kort", barmode="stack",
        color_discrete_map={"Nederland": "#3b82f6", "niet-Nederland": "#a78bfa"},
        labels={"groep": "", "pct": "%", "herkomst_kort": "Herkomst"},
        title="Herkomst per groep (%)",
    )
    fig4.update_layout(height=460, legend=dict(orientation="h", y=-0.2), **CHART_BASE)
    fix_xas_labels(fig4)

    agg_v = bereken_pct(
        df.groupby(["hoogste_vooropleiding", "groep"], observed=True).size().reset_index(name="n"), "groep",
    )
    fig5 = px.bar(
        agg_v, y="hoogste_vooropleiding", x="pct", color="groep", barmode="group", orientation="h",
        color_discrete_map=GROEP_KLEUREN,
        category_orders={"groep": GROEP_VOLGORDE},
        labels={"hoogste_vooropleiding": "", "pct": "%", "groep": ""},
        title="Vooropleiding per groep (%)",
    )
    fig5.update_layout(height=420, legend=dict(orientation="h", y=-0.2), **CHART_BASE)

    agg_i = bereken_pct(
        df[df["instroom_type"].notna()]
        .groupby(["groep", "instroom_type"], observed=True).size().reset_index(name="n"),
        "groep",
    )
    fig6 = px.bar(
        agg_i, x="groep", y="pct", color="instroom_type", barmode="stack",
        color_discrete_map={"direct": "#3b82f6", "tussenjaar": "#f59e0b", "switcher": "#8b5cf6"},
        category_orders={"instroom_type": ["direct", "tussenjaar", "switcher"]},
        labels={"groep": "", "pct": "%", "instroom_type": "Instroom"},
        title="Instroomtype per groep (%): direct, tussenjaar, switcher",
    )
    fig6.update_layout(height=460, legend=dict(orientation="h", y=-0.2), **CHART_BASE)
    fix_xas_labels(fig6)

    return fig3, fig4, fig5, fig6


@app.callback(
    Output("fig-puntenwolk", "figure"),
    Input("cohort-dropdown", "value"),
    Input("geslacht-dropdown", "value"),
    Input("vooropleiding-dropdown", "value"),
    Input("scatter-x", "value"),
    Input("scatter-y", "value"),
    State("data-store", "data"),
)
def update_puntenwolk_tab(cohort, geslacht, vooropleiding, x_var, y_var, store_data):
    df = filter_data(df_from_store(store_data), cohort, geslacht, vooropleiding)
    score_cols = get_score_cols(df) + ["totaalscore"]
    if x_var not in df.columns:
        x_var = score_cols[0] if score_cols else None
    if y_var not in df.columns:
        y_var = score_cols[1] if len(score_cols) > 1 else score_cols[0] if score_cols else None
    if x_var is None or y_var is None:
        return go.Figure().update_layout(**CHART_BASE)

    fig = px.scatter(
        df[df["groep"].notna()],
        x=x_var, y=y_var,
        color="groep",
        color_discrete_map=GROEP_KLEUREN,
        category_orders={"groep": GROEP_VOLGORDE},
        labels={x_var: col_to_label(x_var), y_var: col_to_label(y_var), "groep": ""},
        opacity=0.55, height=560,
    )
    fig.update_traces(marker=dict(size=6))
    fig.update_layout(legend=dict(orientation="h", y=-0.15), **CHART_BASE)
    return fig


@app.callback(
    Output("fig-vo", "figure"),
    Output("tabel-pearsonr", "data"),
    Output("tabel-pearsonr", "columns"),
    Output("tabel-pearsonr", "style_data_conditional"),
    Input("cohort-dropdown", "value"),
    Input("geslacht-dropdown", "value"),
    Input("vooropleiding-dropdown", "value"),
    Input("vo-score", "value"),
    State("data-store", "data"),
)
def update_vo_tab(cohort, geslacht, vooropleiding, score_var, store_data):
    df = filter_data(df_from_store(store_data), cohort, geslacht, vooropleiding)

    if "gem_eindcijfer_vo" not in df.columns:
        leeg = go.Figure().update_layout(**CHART_BASE)
        return leeg, [], [], []

    df_vo = df[df["gem_eindcijfer_vo"].notna()]
    score_cols = get_score_cols(df) + ["totaalscore"]
    if score_var not in df.columns:
        score_var = score_cols[0] if score_cols else None
    if score_var is None:
        return go.Figure().update_layout(**CHART_BASE), [], [], []

    score_label = col_to_label(score_var)
    fig = px.scatter(
        df_vo[df_vo["groep"].isin(["Gestart, niet naar jaar 2", "Doorgestroomd naar jaar 2"])],
        x="gem_eindcijfer_vo", y=score_var,
        color="groep",
        color_discrete_map=GROEP_KLEUREN,
        category_orders={"groep": GROEP_VOLGORDE},
        labels={"gem_eindcijfer_vo": "VO-eindcijfer", score_var: score_label, "groep": ""},
        opacity=0.55, height=500,
    )
    fig.update_traces(marker=dict(size=6))
    for groep in ["Gestart, niet naar jaar 2", "Doorgestroomd naar jaar 2"]:
        sub = df_vo[df_vo["groep"] == groep][["gem_eindcijfer_vo", score_var]].dropna()
        if len(sub) >= 2:
            m, b = np.polyfit(sub["gem_eindcijfer_vo"], sub[score_var], 1)
            x_line = np.linspace(sub["gem_eindcijfer_vo"].min(), sub["gem_eindcijfer_vo"].max(), 50)
            fig.add_trace(go.Scatter(
                x=x_line, y=m * x_line + b, mode="lines",
                line=dict(color=GROEP_KLEUREN[groep], width=2, dash="dot"),
                showlegend=False, hoverinfo="skip",
            ))
    fig.update_layout(legend=dict(orientation="h", y=-0.15), **CHART_BASE)

    cor_rijen = []
    for col in sorted(get_score_cols(df)) + ["totaalscore"]:
        if col not in df.columns:
            continue
        subset = df_vo[df_vo[col].notna()]
        if len(subset) >= 2:
            r = float(subset["gem_eindcijfer_vo"].corr(subset[col]))
            cor_rijen.append({"Score": col_to_label(col), "r (Pearson)": round(r, 3) if not np.isnan(r) else None})
        else:
            cor_rijen.append({"Score": col_to_label(col), "r (Pearson)": None})

    style_cond = []
    for i, row in enumerate(cor_rijen):
        r = row["r (Pearson)"]
        if r is None:
            continue
        if r < -0.2:
            bg, fg = "#fed7aa", "#7c2d12"
        elif r < 0.3:
            bg, fg = "#bbf7d0", "#14532d"
        elif r < 0.5:
            bg, fg = "#fef08a", "#713f12"
        else:
            bg, fg = "#fecaca", "#7f1d1d"
        style_cond.append({"if": {"row_index": i, "column_id": "r (Pearson)"}, "backgroundColor": bg, "color": fg})

    pearson_cols = [{"name": c, "id": c} for c in ["Score", "r (Pearson)"]]
    return fig, cor_rijen, pearson_cols, style_cond


if __name__ == "__main__":
    app.run(debug=True)
