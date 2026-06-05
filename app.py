"""
Evaluatietool: selectie & studiesucces dashboard

Draai met: uv run python app.py
Demodata aanmaken: uv run python scripts/maak_data.py
"""

import base64
import io
import json
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

import dash
from dash import dcc, html, dash_table, Input, Output, State, ctx
import dash_bootstrap_components as dbc

from transformatie import (
    lees_config,
    parse_csv_or_excel,
    parse_selectiedata,
    transformeer_naar_lang,
    valideer_config,
)
from config_wizard import maak_wizard_layout, registreer_callbacks
from rapport import genereer_rapport
from shared import (
    GROEP_VOLGORDE,
    GROEP_KLEUREN,
    CHART_BASE,
    shorten_item,
    sig_sym,
    fmt_p,
)

DEMO_DIR = Path("data/demo")

DEMO_DATASETS = []
if DEMO_DIR.exists():
    for subdir in sorted(DEMO_DIR.iterdir()):
        if subdir.is_dir() and (subdir / "config.xlsx").exists():
            DEMO_DATASETS.append(
                {"value": subdir.name, "label": subdir.name.replace("_", " ").title()}
            )
GROEP_XTICKLABELS = [
    "Niet<br>gestart",
    "Gestart, niet<br>naar jaar 2",
    "Doorgestroomd<br>naar jaar 2",
]

VERPLICHTE_CHO_KOLOMMEN = ["studentnummer", "selectiejaar", "groep"]


# ── Dashboard helpers ─────────────────────────────────────────────────────────


def koppel_data(cho_df: pd.DataFrame, scores_df: pd.DataFrame) -> pd.DataFrame:
    instrument_gem = (
        scores_df.groupby(["studentnummer", "instrument"])["score"].mean().reset_index()
    )
    pivot = instrument_gem.pivot(
        index="studentnummer", columns="instrument", values="score"
    )
    score_cols = [f"{c}_score" for c in pivot.columns]
    pivot.columns = score_cols
    zscores = pivot[score_cols].apply(
        lambda s: (
            (s - s.mean()) / s.std() if s.std() > 0 else pd.Series(0, index=s.index)
        )
    )
    pivot["totaalscore"] = zscores.mean(axis=1).round(2)
    pivot = pivot.reset_index()

    meta_cols = ["studentnummer"]
    for col in ["selectiejaar", "opleiding", "instellingscode"]:
        if col in scores_df.columns:
            meta_cols.append(col)
    meta = (
        scores_df.groupby("studentnummer")
        .first()[[c for c in meta_cols if c != "studentnummer"]]
        .reset_index()
    )
    pivot = pivot.merge(meta, on="studentnummer", how="left")

    df = pivot.merge(cho_df, on="studentnummer", how="left", suffixes=("", "_cho"))
    for col in ["selectiejaar", "opleiding", "instellingscode"]:
        cho_col = f"{col}_cho"
        if cho_col in df.columns:
            df[col] = df[col].fillna(df[cho_col])
            df = df.drop(columns=[cho_col])

    df["groep"] = pd.Categorical(
        df["groep"].fillna("Niet gestart"),
        categories=GROEP_VOLGORDE,
        ordered=True,
    )
    return df


def df_from_store(store_data: str | None) -> pd.DataFrame:
    if store_data is None:
        return pd.DataFrame()
    df = pd.read_json(io.StringIO(store_data), orient="split")
    df["groep"] = pd.Categorical(df["groep"], categories=GROEP_VOLGORDE, ordered=True)
    return df


def maak_filter_opties(
    df: pd.DataFrame, kolom: str, alle_label: str = "Alle"
) -> list[dict]:
    if kolom not in df.columns:
        return [{"label": alle_label, "value": "Alle"}]
    return [{"label": alle_label, "value": "Alle"}] + [
        {"label": str(v), "value": str(v)} for v in sorted(df[kolom].dropna().unique())
    ]


def filter_data(df: pd.DataFrame, cohort, geslacht, vooropleiding, incl_cohort=True):
    if incl_cohort and cohort != "Alle" and "selectiejaar" in df.columns:
        df = df[df["selectiejaar"] == int(cohort)]
    if geslacht != "Alle" and "geslacht" in df.columns:
        df = df[df["geslacht"] == geslacht]
    if vooropleiding != "Alle" and "hoogste_vooropleiding" in df.columns:
        df = df[df["hoogste_vooropleiding"] == vooropleiding]
    return df


def fix_xas_labels(fig):
    fig.update_xaxes(
        tickmode="array",
        tickvals=GROEP_VOLGORDE,
        ticktext=GROEP_XTICKLABELS,
    )
    return fig


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


# ── Upload overlay ────────────────────────────────────────────────────────────


def _upload_card(title, description, upload_id, status_id, accept):
    return dbc.Card(
        dbc.CardBody(
            [
                html.H6(title, className="mb-1"),
                html.P(description, className="text-muted small mb-3"),
                dcc.Upload(
                    id=upload_id,
                    children=html.Div(
                        [
                            "Sleep een bestand hierheen of ",
                            html.A("blader", style={"cursor": "pointer"}),
                        ]
                    ),
                    className="upload-zone",
                    accept=accept,
                    max_size=50 * 1024 * 1024,
                ),
                html.Div(id=status_id, className="mt-2"),
            ]
        ),
        className="mb-3 text-start",
    )


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
                    "Upload drie bestanden om het dashboard te openen.",
                    className="text-muted mb-4",
                ),
                _upload_card(
                    "Selectiedata",
                    "Het Excel-bestand met de selectieresultaten.",
                    "upload-selectiedata",
                    "selectiedata-status",
                    ".xlsx,.xls",
                ),
                _upload_card(
                    "Configuratiebestand",
                    "Beschrijft welke kolommen uit het selectiebestand worden meegenomen.",
                    "upload-config",
                    "config-status",
                    ".xlsx",
                ),
                maak_wizard_layout(),
                html.Div(id="validatie-resultaat", className="mb-3"),
                _upload_card(
                    "1CHO-data",
                    "Studiesuccesdata met groepindeling per kandidaat.",
                    "upload-1cho",
                    "cho-status",
                    ".csv,.xlsx,.xls",
                ),
                dbc.Button(
                    "Open dashboard",
                    id="btn-open-dashboard",
                    color="primary",
                    size="lg",
                    className="w-100 mb-3",
                    disabled=True,
                ),
                html.Hr(className="my-3"),
                html.P("Nog geen eigen data?", className="text-muted small mb-2"),
                dbc.Row(
                    [
                        dbc.Col(
                            dcc.Dropdown(
                                id="demo-dataset-picker",
                                options=DEMO_DATASETS,
                                value=DEMO_DATASETS[0]["value"]
                                if DEMO_DATASETS
                                else None,
                                clearable=False,
                            ),
                            width=8,
                        ),
                        dbc.Col(
                            dbc.Button(
                                "Laden",
                                id="btn-demodata",
                                color="secondary",
                                size="sm",
                                className="w-100",
                                style={"height": "36px"},
                            ),
                            width=4,
                        ),
                    ],
                    className="g-2 align-items-center",
                ),
            ],
            className="upload-card",
        )
    ],
    className="upload-overlay",
)


# ── Sidebar ───────────────────────────────────────────────────────────────────

SIDEBAR = html.Div(
    [
        html.Img(src="/assets/nko-logo.svg", className="sidebar-logo"),
        html.P("Filters", className="sidebar-label"),
        dbc.Label("Cohort"),
        dcc.Dropdown(
            id="cohort-dropdown",
            options=[{"label": "Alle cohorten", "value": "Alle"}],
            value="Alle",
            clearable=False,
            className="mb-3",
        ),
        dbc.Label("Geslacht"),
        dcc.Dropdown(
            id="geslacht-dropdown",
            options=[{"label": "Alle", "value": "Alle"}],
            value="Alle",
            clearable=False,
            className="mb-3",
        ),
        dbc.Label("Vooropleiding"),
        dcc.Dropdown(
            id="vooropleiding-dropdown",
            options=[{"label": "Alle", "value": "Alle"}],
            value="Alle",
            clearable=False,
            className="mb-4",
        ),
        html.Hr(className="my-2"),
        html.P("Kandidaten per cohort", className="sidebar-label"),
        html.Div(id="cohort-stats"),
        html.Hr(className="mt-3 mb-2"),
        dcc.Loading(
            [
                dbc.Button(
                    "Download rapport (PDF)",
                    id="btn-download-rapport",
                    color="primary",
                    size="sm",
                    className="w-100 mb-2",
                ),
                dcc.Download(id="download-rapport"),
            ],
            type="circle",
            color="#2c3e50",
        ),
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


# ── App layout ────────────────────────────────────────────────────────────────

app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    title="Evaluatietool Selectie",
    suppress_callback_exceptions=True,
)
registreer_callbacks(app)

app.layout = html.Div(
    [
        dcc.Store(id="data-store", storage_type="memory"),
        dcc.Store(id="scores-store", storage_type="memory"),
        dbc.Toast(
            "Rapport wordt gegenereerd, dit kan even duren...",
            id="rapport-toast",
            header="PDF rapport",
            is_open=False,
            duration=20000,
            style={"position": "fixed", "top": 16, "right": 16, "zIndex": 9999},
        ),
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
                                                html.H5(
                                                    "Selectiescores per uitkomstgroep"
                                                ),
                                                html.P(
                                                    "Hier vergelijken we de selectiescores van drie groepen studenten. "
                                                    "Als studenten die doorstromen naar jaar 2 hoger scoren dan studenten die "
                                                    "uitvallen, dan werkt het selectie-instrument: het selecteert de juiste mensen. "
                                                    "Als de groepen ongeveer gelijk scoren, voorspelt dat item niet goed wie het gaat redden.",
                                                    className="text-muted small",
                                                ),
                                                dbc.Row(
                                                    [
                                                        dbc.Col(
                                                            [
                                                                dbc.Label(
                                                                    "Instrument",
                                                                    className="small",
                                                                ),
                                                                dcc.Dropdown(
                                                                    id="instrument-filter",
                                                                    options=[
                                                                        {
                                                                            "label": "Alle instrumenten",
                                                                            "value": "Alle",
                                                                        }
                                                                    ],
                                                                    value="Alle",
                                                                    clearable=False,
                                                                ),
                                                            ],
                                                            width=4,
                                                        ),
                                                        dbc.Col(
                                                            [
                                                                dbc.Label(
                                                                    "Criterium",
                                                                    className="small",
                                                                ),
                                                                dcc.Dropdown(
                                                                    id="criterium-filter",
                                                                    options=[
                                                                        {
                                                                            "label": "Alle criteria",
                                                                            "value": "Alle",
                                                                        }
                                                                    ],
                                                                    value="Alle",
                                                                    clearable=False,
                                                                ),
                                                            ],
                                                            width=4,
                                                        ),
                                                        dbc.Col(
                                                            [
                                                                dbc.Label(
                                                                    "Item",
                                                                    className="small",
                                                                ),
                                                                dcc.Dropdown(
                                                                    id="item-filter",
                                                                    options=[
                                                                        {
                                                                            "label": "Alle items",
                                                                            "value": "Alle",
                                                                        }
                                                                    ],
                                                                    value="Alle",
                                                                    clearable=False,
                                                                ),
                                                            ],
                                                            width=4,
                                                        ),
                                                    ],
                                                    className="mb-3",
                                                ),
                                                dcc.Loading(
                                                    dcc.Graph(id="fig-totaal"),
                                                    type="dot",
                                                ),
                                                html.Hr(),
                                                html.H6("Gemiddelden per groep"),
                                                dash_table.DataTable(
                                                    id="tabel-gemiddelden",
                                                    style_table={"overflowX": "auto"},
                                                    **TABLE_STYLE,
                                                ),
                                            ],
                                            className="tab-body",
                                        ),
                                    ],
                                ),
                                dbc.Tab(
                                    label="Samenhang",
                                    tab_id="tab-samenhang",
                                    children=[
                                        html.Div(
                                            [
                                                html.H5(
                                                    "Correlatiematrix tussen items"
                                                ),
                                                html.P(
                                                    "Meten de verschillende onderdelen van de selectie allemaal iets anders, "
                                                    "of meten sommige onderdelen eigenlijk hetzelfde? Een hoog getal (dicht bij 1) "
                                                    "betekent dat twee items sterk samenhangen. Een laag getal (dicht bij 0) betekent "
                                                    "dat ze iets anders meten en elkaar dus aanvullen.",
                                                    className="text-muted small",
                                                ),
                                                html.Details(
                                                    [
                                                        html.Summary(
                                                            "Interpretatie correlatiewaarden",
                                                            className="small text-muted",
                                                            style={"cursor": "pointer"},
                                                        ),
                                                        html.Div(
                                                            [
                                                                html.P(
                                                                    "De correlatiecoefficient (r) loopt van -1 tot +1. "
                                                                    "Vuistregels op basis van Cohen (1988):",
                                                                    className="small text-muted mb-1",
                                                                ),
                                                                html.Ul(
                                                                    [
                                                                        html.Li("r < 0.10: verwaarloosbaar"),
                                                                        html.Li("r = 0.10 - 0.30: zwak (items meten grotendeels iets anders)"),
                                                                        html.Li("r = 0.30 - 0.50: matig (gedeelde variantie, maar ook unieke bijdrage)"),
                                                                        html.Li("r = 0.50 - 0.70: sterk (substantiele overlap, vraag of beide items nodig zijn)"),
                                                                        html.Li("r > 0.70: zeer sterk (items meten vrijwel hetzelfde construct)"),
                                                                    ],
                                                                    className="small text-muted mb-1",
                                                                ),
                                                                html.P(
                                                                    "Negatieve correlaties betekenen dat hogere scores op het ene item samengaan "
                                                                    "met lagere scores op het andere. Bij selectie-instrumenten is een mix van "
                                                                    "zwakke tot matige correlaties (r = 0.10 - 0.50) wenselijk: de items vullen "
                                                                    "elkaar aan zonder te veel te overlappen.",
                                                                    className="small text-muted mb-0",
                                                                ),
                                                            ],
                                                            className="mt-1 mb-2",
                                                        ),
                                                    ],
                                                    className="mb-3",
                                                ),
                                                dbc.Row(
                                                    [
                                                        dbc.Col(
                                                            [
                                                                dbc.Label(
                                                                    "Instrument",
                                                                    className="small",
                                                                ),
                                                                dcc.Dropdown(
                                                                    id="samenhang-instrument",
                                                                    options=[
                                                                        {
                                                                            "label": "Alle instrumenten",
                                                                            "value": "Alle",
                                                                        }
                                                                    ],
                                                                    value="Alle",
                                                                    clearable=False,
                                                                ),
                                                            ],
                                                            width=4,
                                                        ),
                                                        dbc.Col(
                                                            [
                                                                dbc.Label(
                                                                    "Criterium",
                                                                    className="small",
                                                                ),
                                                                dcc.Dropdown(
                                                                    id="samenhang-criterium",
                                                                    options=[
                                                                        {
                                                                            "label": "Alle criteria",
                                                                            "value": "Alle",
                                                                        }
                                                                    ],
                                                                    value="Alle",
                                                                    clearable=False,
                                                                ),
                                                            ],
                                                            width=4,
                                                        ),
                                                    ],
                                                    className="mb-3",
                                                ),
                                                dcc.Loading(
                                                    dcc.Graph(id="fig-correlatie"),
                                                    type="dot",
                                                ),
                                                html.Hr(),
                                                html.H5(
                                                    "Regressie-analyse: voorspelling studiesucces"
                                                ),
                                                html.P(
                                                    "Welke onderdelen van de selectie voorspellen het beste of een student "
                                                    "doorstroomt naar jaar 2? Dit model kijkt naar alle items tegelijk en "
                                                    "bepaalt per item hoeveel het bijdraagt aan de voorspelling.",
                                                    className="text-muted small",
                                                ),
                                                html.Details(
                                                    [
                                                        html.Summary(
                                                            "Uitleg regressietabel",
                                                            className="small text-muted",
                                                            style={"cursor": "pointer"},
                                                        ),
                                                        html.Div(
                                                            [
                                                                html.P(
                                                                    "De tabel toont per item vier waarden:",
                                                                    className="small text-muted mb-1",
                                                                ),
                                                                html.Ul(
                                                                    [
                                                                        html.Li(
                                                                            "Coefficient: de richting en sterkte van het effect. "
                                                                            "Positief = hogere score op dit item hangt samen met hogere kans op doorstroom. "
                                                                            "Negatief = hogere score hangt samen met lagere kans."
                                                                        ),
                                                                        html.Li(
                                                                            "Odds ratio: hoeveel keer groter de kans op doorstroom wordt per punt stijging. "
                                                                            "OR = 1.5 betekent 50% hogere kans per extra punt. OR < 1 betekent lagere kans."
                                                                        ),
                                                                        html.Li(
                                                                            "p-waarde: hoe waarschijnlijk is dit resultaat als het item in werkelijkheid "
                                                                            "geen effect heeft? p < 0.05 geldt als statistisch significant."
                                                                        ),
                                                                        html.Li(
                                                                            "Sig.: samenvatting van de p-waarde. "
                                                                            "* = p < 0.05, ** = p < 0.01, *** = p < 0.001, ns = niet significant."
                                                                        ),
                                                                    ],
                                                                    className="small text-muted mb-1",
                                                                ),
                                                                html.P(
                                                                    "Pseudo R-kwadraat (boven de tabel) geeft aan hoeveel van de variatie in "
                                                                    "doorstroom het model als geheel verklaart. Waarden rond 0.10-0.20 zijn "
                                                                    "gebruikelijk bij selectiedata. Een item kan significant zijn zonder dat "
                                                                    "het model als geheel sterk voorspelt.",
                                                                    className="small text-muted mb-1",
                                                                ),
                                                                html.P(
                                                                    "Let op: elk item wordt beoordeeld rekening houdend met alle andere items "
                                                                    "in het model. Een item dat op zichzelf voorspellend is, kan niet-significant "
                                                                    "zijn als een ander item dezelfde informatie al bevat. Dat is geen fout, "
                                                                    "maar overlap.",
                                                                    className="small text-muted mb-0",
                                                                ),
                                                            ],
                                                            className="mt-1 mb-2",
                                                        ),
                                                    ],
                                                    className="mb-3",
                                                ),
                                                html.Div(
                                                    id="regressie-samenvatting",
                                                    className="mb-3",
                                                ),
                                                dash_table.DataTable(
                                                    id="tabel-regressie",
                                                    style_table={"overflowX": "auto"},
                                                    **TABLE_STYLE,
                                                ),
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
                                                html.H5("Verdeling per groep"),
                                                html.P(
                                                    "Hoeveel procent van de kandidaten valt in elke groep per selectiejaar? "
                                                    "Hiermee zie je of het selectieproces van jaar tot jaar verandert.",
                                                    className="text-muted small",
                                                ),
                                                html.P(
                                                    id="verdeling-caption",
                                                    className="text-muted small",
                                                ),
                                                dcc.Loading(
                                                    dcc.Graph(id="fig-verdeling"),
                                                    type="dot",
                                                ),
                                                html.Hr(),
                                                html.H5("Demografisch profiel"),
                                                html.P(
                                                    "Wie zijn de studenten in elke groep? Zijn er verschillen in "
                                                    "achtergrond tussen studenten die doorstromen en studenten die uitvallen?",
                                                    className="text-muted small",
                                                ),
                                                html.Details(
                                                    [
                                                        html.Summary(
                                                            "Waar komen deze gegevens vandaan?",
                                                            className="small text-muted",
                                                            style={"cursor": "pointer"},
                                                        ),
                                                        html.Div(
                                                            [
                                                                html.P(
                                                                    "De achtergrondkenmerken (geslacht, herkomst, vooropleiding, VO-cijfer) "
                                                                    "komen uit 1CHO: de landelijke registratie van inschrijvingen in het "
                                                                    "hoger onderwijs. Elke hogeronderwijsinstelling levert jaarlijks "
                                                                    "inschrijvingsgegevens aan bij 1CHO.",
                                                                    className="small text-muted mb-1",
                                                                ),
                                                                html.P(
                                                                    "Deze gegevens zijn alleen beschikbaar voor studenten die daadwerkelijk "
                                                                    "zijn ingeschreven bij de opleiding. Kandidaten die niet zijn toegelaten "
                                                                    "of nooit zijn gestart staan niet in 1CHO en hebben dus geen "
                                                                    "achtergrondkenmerken. Zij vallen in de groep 'Niet gestart'.",
                                                                    className="small text-muted mb-1",
                                                                ),
                                                                html.P(
                                                                    "Doorstroom naar jaar 2 wordt bepaald door te kijken of een student "
                                                                    "een tweede inschrijving heeft voor dezelfde opleiding in het jaar na "
                                                                    "het selectiejaar. Heeft een student alleen een eerstejaars inschrijving "
                                                                    "en geen tweedejaars, dan is dat uitval.",
                                                                    className="small text-muted mb-0",
                                                                ),
                                                            ],
                                                            className="mt-1 mb-2",
                                                        ),
                                                    ],
                                                    className="mb-3",
                                                ),
                                                dbc.Row(
                                                    [
                                                        dbc.Col(
                                                            dcc.Loading(
                                                                dcc.Graph(
                                                                    id="fig-geslacht"
                                                                ),
                                                                type="dot",
                                                            )
                                                        ),
                                                        dbc.Col(
                                                            dcc.Loading(
                                                                dcc.Graph(
                                                                    id="fig-herkomst"
                                                                ),
                                                                type="dot",
                                                            )
                                                        ),
                                                    ]
                                                ),
                                                dcc.Loading(
                                                    dcc.Graph(id="fig-vooropleiding"),
                                                    type="dot",
                                                ),
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
                                                html.H5(
                                                    "VO-eindcijfer vs selectiescores"
                                                ),
                                                html.P(
                                                    "Meet de selectie iets anders dan wat je op school al hebt laten zien? "
                                                    "Hier vergelijken we selectiescores met het gemiddelde eindcijfer van "
                                                    "de middelbare school (uit 1CHO).",
                                                    className="text-muted small",
                                                ),
                                                html.Details(
                                                    [
                                                        html.Summary(
                                                            "Waarom is dit relevant?",
                                                            className="small text-muted",
                                                            style={"cursor": "pointer"},
                                                        ),
                                                        html.Div(
                                                            [
                                                                html.P(
                                                                    "Het VO-eindcijfer is een maat voor cognitieve schoolprestaties die "
                                                                    "niet onderdeel is van de selectie. Door selectiescores hiermee te "
                                                                    "vergelijken kun je twee dingen beoordelen:",
                                                                    className="small text-muted mb-1",
                                                                ),
                                                                html.Ul(
                                                                    [
                                                                        html.Li(
                                                                            "Lage correlatie (r rond 0): het selectie-item meet iets anders dan "
                                                                            "schoolprestaties. Dat is vaak wenselijk, want de selectie voegt dan "
                                                                            "informatie toe die het diploma niet al geeft."
                                                                        ),
                                                                        html.Li(
                                                                            "Hoge correlatie (r > 0.5): het selectie-item overlapt sterk met het "
                                                                            "VO-cijfer. De selectie herhaalt dan grotendeels wat het schooldiploma "
                                                                            "al vertelt. Dat kan een bewuste keuze zijn, maar het is goed om te weten."
                                                                        ),
                                                                    ],
                                                                    className="small text-muted mb-1",
                                                                ),
                                                                html.P(
                                                                    "De scatterplot toont alleen ingeschreven studenten (niet de groep "
                                                                    "'Niet gestart'), omdat het VO-cijfer uit 1CHO komt en alleen beschikbaar "
                                                                    "is voor studenten die daadwerkelijk zijn ingeschreven.",
                                                                    className="small text-muted mb-1",
                                                                ),
                                                                html.P(
                                                                    "De tabel onderaan toont Pearson r per item. Vuistregels (Cohen 1988): "
                                                                    "r < 0.10 verwaarloosbaar, 0.10-0.30 zwak, 0.30-0.50 matig, > 0.50 sterk.",
                                                                    className="small text-muted mb-0",
                                                                ),
                                                            ],
                                                            className="mt-1 mb-2",
                                                        ),
                                                    ],
                                                    className="mb-3",
                                                ),
                                                dbc.Row(
                                                    [
                                                        dbc.Col(
                                                            [
                                                                dbc.Label(
                                                                    "Item (y-as)"
                                                                ),
                                                                dcc.Dropdown(
                                                                    id="vo-score",
                                                                    options=[],
                                                                    clearable=False,
                                                                ),
                                                            ],
                                                            width=4,
                                                        ),
                                                    ],
                                                    className="mb-3",
                                                ),
                                                dcc.Loading(
                                                    dcc.Graph(id="fig-vo"), type="dot"
                                                ),
                                                html.Hr(),
                                                html.P(
                                                    "Samenhang (r) per item met het VO-eindcijfer. "
                                                    "Hoe dichter bij 0, hoe meer het item iets anders meet dan schoolprestaties.",
                                                    className="text-muted small",
                                                ),
                                                dash_table.DataTable(
                                                    id="tabel-pearsonr",
                                                    style_table={
                                                        "overflowX": "auto",
                                                        "maxWidth": "420px",
                                                    },
                                                    **TABLE_STYLE,
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

# ── Upload callbacks ──────────────────────────────────────────────────────────


@app.callback(
    Output("upload-overlay", "style"),
    Input("data-store", "data"),
)
def toggle_overlay(store_data):
    return {"display": "flex"} if store_data is None else {"display": "none"}


@app.callback(
    Output("selectiedata-status", "children"),
    Output("config-status", "children"),
    Output("validatie-resultaat", "children"),
    Output("cho-status", "children"),
    Output("btn-open-dashboard", "disabled"),
    Input("upload-selectiedata", "contents"),
    Input("upload-config", "contents"),
    Input("upload-1cho", "contents"),
    Input("wiz-config-store", "data"),
    State("upload-selectiedata", "filename"),
    State("upload-config", "filename"),
    State("upload-1cho", "filename"),
    prevent_initial_call=True,
)
def valideer_uploads(
    sel,
    cfg,
    cho,
    wiz_config,
    sel_fn,
    cfg_fn,
    cho_fn,
):
    trigger = ctx.triggered_id
    no = dash.no_update

    sel_status = no
    cfg_status = no
    validatie = no
    cho_status = no
    btn_disabled = True

    if trigger == "upload-selectiedata" and sel:
        sel_status = dbc.Alert(
            f"{sel_fn} geladen.", color="success", className="small py-1"
        )

    if trigger == "upload-config" and cfg:
        try:
            config = lees_config(cfg)
            n_kol = len(config.get("kolommen", []))
            cfg_status = dbc.Alert(
                f"{cfg_fn} geladen ({n_kol} kolommen).",
                color="success",
                className="small py-1",
            )
        except Exception as e:
            cfg_status = dbc.Alert(f"Fout: {e}", color="danger", className="small py-1")
            return sel_status, cfg_status, "", cho_status, True

    if trigger == "wiz-config-store" and wiz_config:
        wiz_cfg = json.loads(wiz_config)
        n_kol = len(wiz_cfg.get("kolommen", []))
        cfg_status = dbc.Alert(
            f"Config gegenereerd ({n_kol} kolommen).",
            color="success",
            className="small py-1",
        )

    if trigger == "upload-1cho" and cho:
        cho_status = dbc.Alert(
            f"{cho_fn} geladen.", color="success", className="small py-1"
        )

    has_config = cfg or wiz_config

    if sel and has_config:
        try:
            if cfg:
                config = lees_config(cfg)
            else:
                config = json.loads(wiz_config)
            checks = valideer_config(config, sel)
            badges = []
            opl = config.get("opleiding", "")
            jaar = config.get("jaar", "")
            inst = config.get("instellingscode", "")
            if opl or jaar:
                label_parts = [p for p in [opl, inst, jaar] if p]
                badges.append(
                    dbc.Alert(
                        f"Opleiding: {' | '.join(label_parts)}",
                        color="info",
                        className="small py-1 mb-1",
                    )
                )
            for c in checks:
                color = "success" if c["ok"] else "danger"
                badges.append(
                    dbc.Alert(c["check"], color=color, className="small py-1 mb-1")
                )
            validatie = html.Div(badges)

            all_ok = all(c["ok"] for c in checks)
            if all_ok and cho:
                scores_df = transformeer_naar_lang(
                    parse_selectiedata(sel, config), config
                )
                cho_df = parse_csv_or_excel(cho, cho_fn or "data.csv")
                missing = [
                    c for c in VERPLICHTE_CHO_KOLOMMEN if c not in cho_df.columns
                ]
                if missing:
                    cho_status = dbc.Alert(
                        f"Ontbrekende kolommen in 1CHO: {', '.join(missing)}",
                        color="danger",
                        className="small py-1",
                    )
                    return sel_status, cfg_status, validatie, cho_status, True

                sel_ids = set(scores_df["studentnummer"].dropna().unique())
                cho_ids = set(cho_df["studentnummer"].dropna().unique())
                matches = sel_ids & cho_ids
                if not matches:
                    cho_status = dbc.Alert(
                        f"Geen overlap tussen selectiedata ({len(sel_ids)} studenten) "
                        f"en 1CHO-data ({len(cho_ids)} studenten). "
                        "Controleer of beide bestanden hetzelfde studentnummer gebruiken.",
                        color="danger",
                        className="small py-1",
                    )
                    return sel_status, cfg_status, validatie, cho_status, True

                n_zonder_match = len(sel_ids - cho_ids)
                cho_alerts = [
                    dbc.Alert(
                        f"{len(matches)} van {len(sel_ids)} kandidaten gekoppeld.",
                        color="success",
                        className="small py-1 mb-1",
                    )
                ]
                if n_zonder_match > 0:
                    cho_alerts.append(
                        dbc.Alert(
                            f"{n_zonder_match} kandidaten niet in 1CHO "
                            f"(worden 'Niet gestart').",
                            color="info",
                            className="small py-1 mb-1",
                        )
                    )
                cho_status = html.Div(cho_alerts)
                btn_disabled = False

        except Exception as e:
            validatie = dbc.Alert(
                f"Fout bij validatie: {e}", color="danger", className="small py-1"
            )

    return sel_status, cfg_status, validatie, cho_status, btn_disabled


@app.callback(
    Output("data-store", "data"),
    Output("scores-store", "data"),
    Input("btn-open-dashboard", "n_clicks"),
    Input("btn-demodata", "n_clicks"),
    Input("btn-reset", "n_clicks"),
    State("upload-selectiedata", "contents"),
    State("upload-config", "contents"),
    State("upload-1cho", "contents"),
    State("upload-1cho", "filename"),
    State("demo-dataset-picker", "value"),
    State("wiz-config-store", "data"),
    prevent_initial_call=True,
)
def laad_dashboard(
    _open,
    _demo,
    _reset,
    sel_contents,
    cfg_contents,
    cho_contents,
    cho_fn,
    demo_dataset,
    wiz_config,
):
    trigger = ctx.triggered_id

    if trigger == "btn-reset":
        return None, None

    if trigger == "btn-demodata":
        return _laad_demodata(demo_dataset)

    has_config = cfg_contents or wiz_config
    if trigger == "btn-open-dashboard" and sel_contents and has_config and cho_contents:
        if cfg_contents:
            config = lees_config(cfg_contents)
        else:
            config = json.loads(wiz_config)
        scores_df = transformeer_naar_lang(
            parse_selectiedata(sel_contents, config), config
        )
        cho_df = parse_csv_or_excel(cho_contents, cho_fn or "data.csv")
        joined = koppel_data(cho_df, scores_df)
        return (
            joined.to_json(orient="split", date_format="iso"),
            scores_df.to_json(orient="split", date_format="iso"),
        )

    return dash.no_update, dash.no_update


def _file_to_data_uri(path: Path) -> str:
    b64 = base64.b64encode(path.read_bytes()).decode()
    return f"data:application/octet-stream;base64,{b64}"


def _laad_demodata(dataset_name=None):
    demo_subdir = DEMO_DIR / dataset_name if dataset_name else DEMO_DIR

    sel_path = demo_subdir / "selectiedata.xlsx"
    cfg_path = demo_subdir / "config.xlsx"
    cho_path = demo_subdir / "1cho_data.csv"

    if not all(p.exists() for p in [sel_path, cfg_path, cho_path]):
        return dash.no_update, dash.no_update

    cfg_contents = _file_to_data_uri(cfg_path)
    config = lees_config(cfg_contents)

    sel_contents = _file_to_data_uri(sel_path)
    sel_df = parse_selectiedata(sel_contents, config)
    scores_df = transformeer_naar_lang(sel_df, config)
    cho_df = pd.read_csv(cho_path, sep=";")

    joined = koppel_data(cho_df, scores_df)

    return (
        joined.to_json(orient="split", date_format="iso"),
        scores_df.to_json(orient="split", date_format="iso"),
    )


# ── Sidebar callbacks ─────────────────────────────────────────────────────────


@app.callback(
    Output("cohort-dropdown", "options"),
    Output("cohort-dropdown", "value"),
    Output("geslacht-dropdown", "options"),
    Output("geslacht-dropdown", "value"),
    Output("vooropleiding-dropdown", "options"),
    Output("vooropleiding-dropdown", "value"),
    Output("samenhang-instrument", "options"),
    Output("samenhang-instrument", "value"),
    Output("samenhang-criterium", "options"),
    Output("samenhang-criterium", "value"),
    Output("vo-score", "options"),
    Output("vo-score", "value"),
    Output("app-subtitle", "children"),
    Input("data-store", "data"),
    State("scores-store", "data"),
)
def update_filters_on_data_change(store_data, scores_store):
    df = df_from_store(store_data)
    if df.empty:
        empty_opts = [{"label": "Alle", "value": "Alle"}]
        return (
            empty_opts, "Alle",  # cohort
            empty_opts, "Alle",  # geslacht
            empty_opts, "Alle",  # vooropleiding
            empty_opts, "Alle",  # samenhang-instrument
            empty_opts, "Alle",  # samenhang-criterium
            [], "totaalscore",   # vo-score
            "",                  # subtitle
        )

    jaren = (
        sorted(df["selectiejaar"].unique().tolist())
        if "selectiejaar" in df.columns
        else []
    )
    cohort_opties = [{"label": "Alle cohorten", "value": "Alle"}] + [
        {"label": str(j), "value": str(j)} for j in jaren
    ]
    opleiding = (
        df["opleiding"].dropna().iloc[0]
        if "opleiding" in df.columns and df["opleiding"].notna().any()
        else ""
    )
    instelling = (
        df["instellingscode"].dropna().iloc[0]
        if "instellingscode" in df.columns and df["instellingscode"].notna().any()
        else ""
    )
    subtitle = f"{opleiding} | {instelling}" if opleiding else ""

    instrument_opties = [{"label": "Alle instrumenten", "value": "Alle"}]
    criterium_opties = [{"label": "Alle criteria", "value": "Alle"}]
    item_opties = [{"label": "Alle items", "value": "Alle"}]
    vo_opties = [{"label": "Totaalscore", "value": "totaalscore"}]
    if scores_store:
        scores_df = pd.read_json(io.StringIO(scores_store), orient="split")
        for inst in sorted(scores_df["instrument"].unique()):
            instrument_opties.append({"label": inst, "value": inst})
        criteria = scores_df["criterium"].dropna().unique()
        criteria = [c for c in sorted(criteria) if c.strip()]
        for crit in criteria:
            criterium_opties.append({"label": crit, "value": crit})
        for item in sorted(scores_df["item"].unique()):
            item_opties.append({"label": shorten_item(item), "value": item})
            vo_opties.append({"label": shorten_item(item), "value": item})

    return (
        cohort_opties,
        "Alle",
        maak_filter_opties(df, "geslacht"),
        "Alle",
        maak_filter_opties(df, "hoogste_vooropleiding"),
        "Alle",
        instrument_opties,
        "Alle",
        criterium_opties,
        "Alle",
        vo_opties,
        "totaalscore",
        subtitle,
    )


@app.callback(
    Output("instrument-filter", "options"),
    Output("instrument-filter", "value"),
    Output("criterium-filter", "options"),
    Output("criterium-filter", "value"),
    Output("item-filter", "options"),
    Output("item-filter", "value"),
    Input("instrument-filter", "value"),
    Input("criterium-filter", "value"),
    Input("item-filter", "value"),
    Input("scores-store", "data"),
)
def update_score_filters(instrument_val, criterium_val, item_val, scores_store):
    alle_inst = [{"label": "Alle instrumenten", "value": "Alle"}]
    alle_crit = [{"label": "Alle criteria", "value": "Alle"}]
    alle_item = [{"label": "Alle items", "value": "Alle"}]

    if not scores_store:
        return alle_inst, "Alle", alle_crit, "Alle", alle_item, "Alle"

    scores_df = pd.read_json(io.StringIO(scores_store), orient="split")
    meta = scores_df[["instrument", "item", "criterium"]].drop_duplicates()

    filtered = meta.copy()
    if instrument_val and instrument_val != "Alle":
        filtered = filtered[filtered["instrument"] == instrument_val]
    if criterium_val and criterium_val != "Alle":
        filtered = filtered[filtered["criterium"] == criterium_val]
    if item_val and item_val != "Alle":
        filtered = filtered[filtered["item"] == item_val]

    if filtered.empty:
        filtered = meta.copy()
        instrument_val = "Alle"
        criterium_val = "Alle"
        item_val = "Alle"

    beschikbare_items = set(filtered["item"])
    beschikbare_criteria = set(filtered["criterium"].dropna()) - {""}
    beschikbare_instrumenten = set(filtered["instrument"])

    if instrument_val and instrument_val != "Alle":
        subset = meta[meta["instrument"] == instrument_val]
        beschikbare_items = set(subset["item"])
        beschikbare_criteria = set(subset["criterium"].dropna()) - {""}
    if criterium_val and criterium_val != "Alle":
        subset = meta[meta["criterium"] == criterium_val]
        beschikbare_items = beschikbare_items & set(subset["item"])
        beschikbare_instrumenten = set(subset["instrument"])
    if item_val and item_val != "Alle":
        subset = meta[meta["item"] == item_val]
        beschikbare_instrumenten = set(subset["instrument"])
        beschikbare_criteria = set(subset["criterium"].dropna()) - {""}

    inst_opts = alle_inst + [
        {"label": i, "value": i}
        for i in sorted(meta["instrument"].unique())
        if i in beschikbare_instrumenten
    ]
    crit_opts = alle_crit + [
        {"label": c, "value": c}
        for c in sorted(meta["criterium"].dropna().unique())
        if c.strip() and c in beschikbare_criteria
    ]
    item_opts = alle_item + [
        {"label": shorten_item(it), "value": it}
        for it in sorted(meta["item"].unique())
        if it in beschikbare_items
    ]

    inst_valid = instrument_val if any(o["value"] == instrument_val for o in inst_opts) else "Alle"
    crit_valid = criterium_val if any(o["value"] == criterium_val for o in crit_opts) else "Alle"
    item_valid = item_val if any(o["value"] == item_val for o in item_opts) else "Alle"

    return inst_opts, inst_valid, crit_opts, crit_valid, item_opts, item_valid


@app.callback(
    Output("cohort-stats", "children"),
    Input("geslacht-dropdown", "value"),
    Input("vooropleiding-dropdown", "value"),
    State("data-store", "data"),
)
def update_cohort_stats(geslacht, vooropleiding, store_data):
    df = df_from_store(store_data)
    if df.empty:
        return ""
    df = filter_data(df, "Alle", geslacht, vooropleiding, incl_cohort=False)
    jaren = (
        sorted(df["selectiejaar"].unique().tolist())
        if "selectiejaar" in df.columns
        else []
    )
    aantallen = df.groupby("selectiejaar").size() if jaren else pd.Series(dtype=int)
    return dbc.Row(
        [
            dbc.Col(
                html.Div(
                    [
                        html.Div(str(jaar), className="stat-year"),
                        html.Div(
                            str(int(aantallen.get(jaar, 0))), className="stat-value"
                        ),
                    ],
                    className="stat-box",
                )
            )
            for jaar in jaren
        ],
        className="g-1",
    )


# ── Rapport download ─────────────────────────────────────────────────────────


app.clientside_callback(
    "function(n) { return n > 0; }",
    Output("rapport-toast", "is_open"),
    Input("btn-download-rapport", "n_clicks"),
    prevent_initial_call=True,
)


@app.callback(
    Output("download-rapport", "data"),
    Input("btn-download-rapport", "n_clicks"),
    State("data-store", "data"),
    State("scores-store", "data"),
    prevent_initial_call=True,
)
def download_rapport(_n, store_data, scores_store):
    df = df_from_store(store_data)
    if df.empty or not scores_store:
        return dash.no_update
    scores_df = pd.read_json(io.StringIO(scores_store), orient="split")
    pdf_bytes = genereer_rapport(df, scores_df)
    opleiding = ""
    if "opleiding" in df.columns and df["opleiding"].notna().any():
        opleiding = str(df["opleiding"].dropna().iloc[0]).replace(" ", "_")
    filename = (
        f"evaluatierapport_{opleiding}.pdf" if opleiding else "evaluatierapport.pdf"
    )
    return dcc.send_bytes(pdf_bytes, filename)


# ── Dashboard callbacks ───────────────────────────────────────────────────────


GROEP_TABEL_KLEUREN = {
    "Niet gestart": {"backgroundColor": "#f1f5f9", "color": "#475569"},
    "Gestart, niet naar jaar 2": {"backgroundColor": "#fff7ed", "color": "#9a3412"},
    "Doorgestroomd naar jaar 2": {"backgroundColor": "#f0fdf4", "color": "#166534"},
}


@app.callback(
    Output("fig-totaal", "figure"),
    Output("tabel-gemiddelden", "data"),
    Output("tabel-gemiddelden", "columns"),
    Output("tabel-gemiddelden", "style_data_conditional"),
    Input("cohort-dropdown", "value"),
    Input("geslacht-dropdown", "value"),
    Input("vooropleiding-dropdown", "value"),
    Input("instrument-filter", "value"),
    Input("criterium-filter", "value"),
    Input("item-filter", "value"),
    State("data-store", "data"),
    State("scores-store", "data"),
)
def update_scores_tab(
    cohort,
    geslacht,
    vooropleiding,
    instrument_filter,
    criterium_filter,
    item_filter,
    store_data,
    scores_store,
):
    leeg = go.Figure().update_layout(**CHART_BASE, margin=dict(t=10, b=10))
    df = df_from_store(store_data)
    if df.empty or not scores_store:
        return leeg, [], [], []

    scores_df = pd.read_json(io.StringIO(scores_store), orient="split")
    df_groep = filter_data(df, cohort, geslacht, vooropleiding)[
        ["studentnummer", "groep"]
    ].drop_duplicates()
    scores = scores_df.merge(df_groep, on="studentnummer", how="inner")
    scores["groep"] = pd.Categorical(
        scores["groep"], categories=GROEP_VOLGORDE, ordered=True
    )

    if instrument_filter and instrument_filter != "Alle":
        scores = scores[scores["instrument"] == instrument_filter]
    if criterium_filter and criterium_filter != "Alle":
        scores = scores[scores["criterium"] == criterium_filter]
    if item_filter and item_filter != "Alle":
        scores = scores[scores["item"] == item_filter]

    if scores.empty:
        return leeg, [], [], []

    scores["item_kort"] = scores["item"].apply(shorten_item)
    items_kort = sorted(scores["item_kort"].unique())
    enkel_item = len(items_kort) == 1

    if enkel_item:
        fig = px.box(
            scores,
            x="groep",
            y="score",
            color="groep",
            color_discrete_map=GROEP_KLEUREN,
            category_orders={"groep": GROEP_VOLGORDE},
            points="all" if len(df_groep) <= 50 else False,
            height=480,
            labels={"groep": "", "score": items_kort[0]},
        )
        fig.update_layout(
            showlegend=False,
            **CHART_BASE,
            margin=dict(t=30, b=10),
        )
    else:
        fig = px.box(
            scores,
            x="item_kort",
            y="score",
            color="groep",
            color_discrete_map=GROEP_KLEUREN,
            category_orders={"groep": GROEP_VOLGORDE, "item_kort": items_kort},
            points="all" if len(df_groep) <= 30 else False,
            height=520,
            labels={"item_kort": "", "score": "Score", "groep": ""},
        )
        fig.update_layout(
            boxgap=0.15,
            legend=dict(orientation="h", y=1.05, yanchor="bottom"),
            xaxis_tickangle=-25,
            **CHART_BASE,
            margin=dict(t=60, b=10),
        )

    criterium_map = dict(
        scores.drop_duplicates("item_kort")[["item_kort", "criterium"]].values
    )
    tabel_pivot = (
        scores.groupby(["groep", "item_kort"], observed=True)["score"]
        .agg(["mean", "std"])
        .round(2)
        .reset_index()
    )
    tabel_pivot["criterium"] = tabel_pivot["item_kort"].map(criterium_map).fillna("")
    tabel_pivot = tabel_pivot.rename(
        columns={
            "item_kort": "Item",
            "mean": "Gem.",
            "std": "SD",
            "groep": "Groep",
            "criterium": "Criterium",
        }
    )
    tabel_pivot = tabel_pivot[["Groep", "Item", "Criterium", "Gem.", "SD"]]
    gem_data = tabel_pivot.to_dict("records")
    gem_cols = [{"name": c, "id": c} for c in tabel_pivot.columns]

    gem_style = []
    for groep, stijl in GROEP_TABEL_KLEUREN.items():
        gem_style.append(
            {
                "if": {"filter_query": f'{{Groep}} = "{groep}"'},
                **stijl,
            }
        )

    return fig, gem_data, gem_cols, gem_style


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
    if df.empty:
        return go.Figure().update_layout(**CHART_BASE), ""

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
        agg,
        x="selectiejaar",
        y="pct",
        color="groep",
        barmode="stack",
        color_discrete_map=GROEP_KLEUREN,
        category_orders={"groep": GROEP_VOLGORDE},
        labels={"selectiejaar": "Cohort", "pct": "Percentage (%)", "groep": ""},
        text="n",
        custom_data=["n"],
    )
    fig.update_traces(
        texttemplate="%{text}",
        textposition="inside",
        hovertemplate="%{fullData.name}<br>%{y:.1f}%  (n=%{customdata[0]})<extra></extra>",
    )
    for jaar, tot in agg.groupby("selectiejaar")["n"].sum().items():
        fig.add_annotation(
            x=jaar,
            y=101,
            text=f"n={tot}",
            showarrow=False,
            yshift=6,
            font=dict(size=12),
        )
    fig.update_layout(
        height=500,
        legend=dict(orientation="h", y=-0.15),
        yaxis_range=[0, 115],
        **CHART_BASE,
    )
    return fig, f"Gefilterd op: {', '.join(labels)}"


@app.callback(
    Output("fig-geslacht", "figure"),
    Output("fig-herkomst", "figure"),
    Output("fig-vooropleiding", "figure"),
    Input("cohort-dropdown", "value"),
    Input("geslacht-dropdown", "value"),
    Input("vooropleiding-dropdown", "value"),
    State("data-store", "data"),
)
def update_demo_tab(cohort, geslacht, vooropleiding, store_data):
    df = filter_data(df_from_store(store_data), cohort, geslacht, vooropleiding)
    leeg = go.Figure().update_layout(**CHART_BASE, height=300)

    if df.empty or "geslacht" not in df.columns:
        return leeg, leeg, leeg

    agg_g = bereken_pct(
        df.groupby(["groep", "geslacht"], observed=True).size().reset_index(name="n"),
        "groep",
    )
    fig3 = px.bar(
        agg_g,
        x="groep",
        y="pct",
        color="geslacht",
        barmode="stack",
        labels={"groep": "", "pct": "%", "geslacht": "Geslacht"},
        title="Geslacht per groep (%)",
    )
    fig3.update_layout(height=460, legend=dict(orientation="h", y=-0.2), **CHART_BASE)
    fix_xas_labels(fig3)

    if "herkomst" in df.columns and df["herkomst"].notna().any():
        agg_h = bereken_pct(
            df[df["herkomst"].notna()]
            .assign(
                herkomst_kort=lambda d: d["herkomst"].map(
                    lambda x: "Nederland" if x == "Nederland" else "niet-Nederland"
                )
            )
            .groupby(["groep", "herkomst_kort"], observed=True)
            .size()
            .reset_index(name="n"),
            "groep",
        )
        fig4 = px.bar(
            agg_h,
            x="groep",
            y="pct",
            color="herkomst_kort",
            barmode="stack",
            color_discrete_map={"Nederland": "#3b82f6", "niet-Nederland": "#a78bfa"},
            labels={"groep": "", "pct": "%", "herkomst_kort": "Herkomst"},
            title="Herkomst per groep (%)",
        )
        fig4.update_layout(
            height=460, legend=dict(orientation="h", y=-0.2), **CHART_BASE
        )
        fix_xas_labels(fig4)
    else:
        fig4 = leeg

    if (
        "hoogste_vooropleiding" in df.columns
        and df["hoogste_vooropleiding"].notna().any()
    ):
        agg_v = bereken_pct(
            df.groupby(["hoogste_vooropleiding", "groep"], observed=True)
            .size()
            .reset_index(name="n"),
            "groep",
        )
        fig5 = px.bar(
            agg_v,
            y="hoogste_vooropleiding",
            x="pct",
            color="groep",
            barmode="group",
            orientation="h",
            color_discrete_map=GROEP_KLEUREN,
            category_orders={"groep": GROEP_VOLGORDE},
            labels={"hoogste_vooropleiding": "", "pct": "%", "groep": ""},
            title="Vooropleiding per groep (%)",
        )
        fig5.update_layout(
            height=420, legend=dict(orientation="h", y=-0.2), **CHART_BASE
        )
    else:
        fig5 = leeg

    return fig3, fig4, fig5


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
    State("scores-store", "data"),
)
def update_vo_tab(
    cohort, geslacht, vooropleiding, score_keuze, store_data, scores_store
):
    leeg = go.Figure().update_layout(**CHART_BASE)
    df = df_from_store(store_data)
    if df.empty or "gem_eindcijfer_vo" not in df.columns:
        return leeg, [], [], []

    scores_df = (
        pd.read_json(io.StringIO(scores_store), orient="split")
        if scores_store
        else None
    )

    df_filtered = filter_data(df, cohort, geslacht, vooropleiding)
    df_vo = df_filtered[df_filtered["gem_eindcijfer_vo"].notna()].copy()
    if df_vo.empty:
        return leeg, [], [], []

    if score_keuze == "totaalscore" and "totaalscore" in df_vo.columns:
        plot_df = df_vo[
            ["studentnummer", "groep", "gem_eindcijfer_vo", "totaalscore"]
        ].copy()
        plot_df["score_val"] = plot_df["totaalscore"]
        score_label = "Totaalscore"
    elif scores_df is not None:
        item_scores = scores_df[scores_df["item"] == score_keuze][
            ["studentnummer", "score"]
        ]
        plot_df = df_vo[["studentnummer", "groep", "gem_eindcijfer_vo"]].merge(
            item_scores, on="studentnummer", how="inner"
        )
        plot_df["score_val"] = plot_df["score"]
        score_label = shorten_item(score_keuze)
    else:
        return leeg, [], [], []

    ingeschreven = plot_df[
        plot_df["groep"].isin(
            ["Gestart, niet naar jaar 2", "Doorgestroomd naar jaar 2"]
        )
    ]

    fig = px.scatter(
        ingeschreven,
        x="gem_eindcijfer_vo",
        y="score_val",
        color="groep",
        color_discrete_map=GROEP_KLEUREN,
        category_orders={"groep": GROEP_VOLGORDE},
        labels={
            "gem_eindcijfer_vo": "VO-eindcijfer",
            "score_val": score_label,
            "groep": "",
        },
        opacity=0.55,
        height=500,
    )
    fig.update_traces(marker=dict(size=6))
    for groep in ["Gestart, niet naar jaar 2", "Doorgestroomd naar jaar 2"]:
        sub = ingeschreven[ingeschreven["groep"] == groep][
            ["gem_eindcijfer_vo", "score_val"]
        ].dropna()
        if len(sub) >= 2:
            m, b = np.polyfit(sub["gem_eindcijfer_vo"], sub["score_val"], 1)
            x_line = np.linspace(
                sub["gem_eindcijfer_vo"].min(), sub["gem_eindcijfer_vo"].max(), 50
            )
            fig.add_trace(
                go.Scatter(
                    x=x_line,
                    y=m * x_line + b,
                    mode="lines",
                    line=dict(color=GROEP_KLEUREN[groep], width=2, dash="dot"),
                    showlegend=False,
                    hoverinfo="skip",
                )
            )
    fig.update_layout(
        legend=dict(orientation="h", y=1.05, yanchor="bottom"), **CHART_BASE
    )

    cor_rijen = []
    if scores_df is not None:
        all_items = sorted(scores_df["item"].unique())
        score_names = [("Totaalscore", "totaalscore")] + [
            (shorten_item(it), it) for it in all_items
        ]
        for label, item_name in score_names:
            if item_name == "totaalscore" and "totaalscore" in df_vo.columns:
                sub = df_vo[["gem_eindcijfer_vo", "totaalscore"]].dropna()
                r = (
                    float(sub["gem_eindcijfer_vo"].corr(sub["totaalscore"]))
                    if len(sub) >= 2
                    else None
                )
            else:
                item_scores = scores_df[scores_df["item"] == item_name][
                    ["studentnummer", "score"]
                ]
                merged = df_vo[["studentnummer", "gem_eindcijfer_vo"]].merge(
                    item_scores, on="studentnummer"
                )
                r = (
                    float(merged["gem_eindcijfer_vo"].corr(merged["score"]))
                    if len(merged) >= 2
                    else None
                )
            cor_rijen.append(
                {
                    "Item": label,
                    "r (Pearson)": round(r, 3)
                    if r is not None and not np.isnan(r)
                    else None,
                }
            )

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
        style_cond.append(
            {
                "if": {"row_index": i, "column_id": "r (Pearson)"},
                "backgroundColor": bg,
                "color": fg,
            }
        )

    pearson_cols = [{"name": c, "id": c} for c in ["Item", "r (Pearson)"]]
    return fig, cor_rijen, pearson_cols, style_cond


@app.callback(
    Output("fig-correlatie", "figure"),
    Output("regressie-samenvatting", "children"),
    Output("tabel-regressie", "data"),
    Output("tabel-regressie", "columns"),
    Output("tabel-regressie", "style_data_conditional"),
    Input("cohort-dropdown", "value"),
    Input("geslacht-dropdown", "value"),
    Input("vooropleiding-dropdown", "value"),
    Input("samenhang-instrument", "value"),
    Input("samenhang-criterium", "value"),
    State("data-store", "data"),
    State("scores-store", "data"),
)
def update_samenhang_tab(
    cohort,
    geslacht,
    vooropleiding,
    sh_instrument,
    sh_criterium,
    store_data,
    scores_store,
):
    leeg = go.Figure().update_layout(**CHART_BASE)
    df = df_from_store(store_data)
    if df.empty or not scores_store:
        return leeg, "", [], [], []

    scores_df = pd.read_json(io.StringIO(scores_store), orient="split")
    df_filtered = filter_data(df, cohort, geslacht, vooropleiding)
    student_ids = df_filtered["studentnummer"].unique()

    scores = scores_df[scores_df["studentnummer"].isin(student_ids)]

    if sh_instrument and sh_instrument != "Alle":
        scores = scores[scores["instrument"] == sh_instrument]
    if sh_criterium and sh_criterium != "Alle":
        scores = scores[scores["criterium"] == sh_criterium]

    if scores.empty:
        return leeg, "", [], [], []

    item_pivot = scores.pivot_table(
        index="studentnummer", columns="item", values="score", aggfunc="mean"
    )
    item_pivot.columns = [shorten_item(c) for c in item_pivot.columns]
    score_cols = list(item_pivot.columns)
    corr_matrix = item_pivot[score_cols].corr().round(3)

    fig = go.Figure(
        data=go.Heatmap(
            z=corr_matrix.values,
            x=corr_matrix.columns,
            y=corr_matrix.index,
            colorscale="RdBu_r",
            zmid=0,
            zmin=-1,
            zmax=1,
            text=corr_matrix.values.round(2),
            texttemplate="%{text}",
            textfont={"size": 10},
        )
    )
    fig.update_layout(
        height=500,
        xaxis_tickangle=-30,
        **CHART_BASE,
        margin=dict(t=20, b=10),
    )

    regressie_msg = ""
    reg_data = []
    reg_cols = []
    reg_style = []

    ingeschreven = df_filtered[
        df_filtered["groep"].isin(
            ["Gestart, niet naar jaar 2", "Doorgestroomd naar jaar 2"]
        )
    ].copy()

    if len(ingeschreven) < 10:
        regressie_msg = dbc.Alert(
            f"Te weinig ingeschreven studenten ({len(ingeschreven)}) voor betrouwbare regressie. "
            "Minimaal 10 nodig.",
            color="warning",
            className="small",
        )
        return fig, regressie_msg, reg_data, reg_cols, reg_style

    ingeschreven["doorgestroomd"] = (
        ingeschreven["groep"] == "Doorgestroomd naar jaar 2"
    ).astype(int)

    item_pivot_inschr = item_pivot.loc[
        item_pivot.index.isin(ingeschreven["studentnummer"])
    ].dropna()

    if len(item_pivot_inschr) < 10:
        regressie_msg = dbc.Alert(
            "Te weinig complete cases voor regressie.",
            color="warning",
            className="small",
        )
        return fig, regressie_msg, reg_data, reg_cols, reg_style

    y = ingeschreven.set_index("studentnummer").loc[
        item_pivot_inschr.index, "doorgestroomd"
    ]
    X = item_pivot_inschr[score_cols]

    try:
        import statsmodels.api as sm

        X_const = sm.add_constant(X.astype(float))
        model = sm.Logit(y.astype(float), X_const).fit(disp=0, maxiter=100)

        n_doorgestroomd = int(y.sum())
        n_niet = int(len(y) - y.sum())
        pseudo_r2 = round(float(model.prsquared), 3)
        regressie_msg = html.Div(
            [
                html.Span(
                    f"n = {len(y)} (doorgestroomd: {n_doorgestroomd}, niet: {n_niet})",
                    className="small text-muted me-3",
                ),
                html.Span(f"Pseudo R² = {pseudo_r2}", className="small fw-bold"),
            ]
        )

        for item_naam in score_cols:
            if item_naam not in model.params.index:
                continue
            coef = round(float(model.params[item_naam]), 3)
            odds = round(float(np.exp(model.params[item_naam])), 2)
            p = float(model.pvalues[item_naam])
            reg_data.append(
                {
                    "Item": item_naam,
                    "Coefficient": coef,
                    "Odds ratio": odds,
                    "p-waarde": fmt_p(p),
                    "Sig.": sig_sym(p),
                }
            )

        reg_cols = [
            {"name": c, "id": c}
            for c in ["Item", "Coefficient", "Odds ratio", "p-waarde", "Sig."]
        ]

        for i, row in enumerate(reg_data):
            p_str = row["p-waarde"]
            p_val = 0.0001 if p_str == "< 0.001" else float(p_str)
            if p_val < 0.05:
                reg_style.append(
                    {
                        "if": {"row_index": i, "column_id": "Sig."},
                        "backgroundColor": "#bbf7d0",
                        "color": "#166534",
                        "fontWeight": "600",
                    }
                )

    except Exception as e:
        regressie_msg = dbc.Alert(
            f"Regressie kon niet worden uitgevoerd: {e}",
            color="warning",
            className="small",
        )

    return fig, regressie_msg, reg_data, reg_cols, reg_style


if __name__ == "__main__":
    app.run(debug=True)
