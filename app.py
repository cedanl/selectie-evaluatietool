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
from plotly.colors import hex_to_rgb, unlabel_rgb

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
from cho_transform import ontbrekende_cho_kolommen, transformeer_cho
from config_wizard import maak_wizard_layout, registreer_callbacks
from rapport import genereer_rapport
from shared import (
    GROEP_VOLGORDE,
    GROEP_KLEUREN,
    GROEP_INGESCHREVEN,
    GROEP_SUCCES,
    CHART_BASE,
    shorten_item,
    schaal_grenzen,
    bucket_per_item,
    meta_per_item,
    grenzen_van_label,
    sig_sym,
    fmt_p,
    vergelijk_succes_per_item,
    VERGELIJKING_KOLOMMEN,
    toets_verschil_per_item,
    VERSCHIL_KOLOMMEN,
    genereer_bevindingen,
    DEMO_DIMENSIES,
    demografie_scores,
)

DEMO_DIR = Path("data/demo")

DEMO_DATASETS = []
if DEMO_DIR.exists():
    for subdir in sorted(DEMO_DIR.iterdir()):
        if subdir.is_dir() and (subdir / "config.xlsx").exists():
            DEMO_DATASETS.append(
                {"value": subdir.name, "label": subdir.name.replace("_", " ").title()}
            )
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


# ── Groeperingsopties ─────────────────────────────────────────────────────────
# De Selectiescores- en Verschiltoets-tabs laten de gebruiker kiezen waarop te
# groeperen: de uitkomstgroep of een demografische dimensie (uit DEMO_DIMENSIES).
GROEPEER_OPTIES = [{"label": "Uitkomstgroep", "value": "groep"}] + [
    {"label": d["label"], "value": d["kolom"]} for d in DEMO_DIMENSIES
]


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
                                    label="Wat valt op",
                                    tab_id="tab-bevindingen",
                                    children=[
                                        html.Div(
                                            [
                                                html.H5("Wat valt op?"),
                                                html.P(
                                                    "Een automatisch overzicht van de opvallendste bevindingen, "
                                                    "rechtstreeks uit de toetsen op deze data. Er wordt niets "
                                                    "bijbedacht: elke regel volgt uit een effectgrootte of p-waarde. "
                                                    "Bekijk de afzonderlijke tabbladen voor het volledige beeld.",
                                                    className="text-muted small",
                                                ),
                                                dcc.Loading(
                                                    html.Div(id="bevindingen-inhoud"),
                                                    type="dot",
                                                ),
                                            ],
                                            className="tab-body",
                                        ),
                                    ],
                                ),
                                dbc.Tab(
                                    label="Selectiescores",
                                    tab_id="tab-scores",
                                    children=[
                                        html.Div(
                                            [
                                                html.H5("Selectiescores per groep"),
                                                html.P(
                                                    "Vergelijk de selectiescores per item tussen groepen. Standaard tussen de "
                                                    "uitkomstgroepen (niet gestart, uitval, doorstroom, diploma); met 'Groepeer op' "
                                                    "kun je ook splitsen op geslacht of vooropleiding. Scoren de groepen "
                                                    "verschillend, dan maakt dat item onderscheid.",
                                                    className="text-muted small",
                                                ),
                                                dbc.Row(
                                                    dbc.Col(
                                                        [
                                                            dbc.Label(
                                                                "Groepeer op",
                                                                className="small",
                                                            ),
                                                            dcc.Dropdown(
                                                                id="groepeer-op",
                                                                options=GROEPEER_OPTIES,
                                                                value="groep",
                                                                clearable=False,
                                                            ),
                                                        ],
                                                        width=4,
                                                    ),
                                                    className="mb-3",
                                                ),
                                                html.H6("Aantal studenten per groep"),
                                                html.P(
                                                    "Bij geslacht en vooropleiding tellen alleen studenten mee die met de "
                                                    "opleiding zijn gestart (die staan in 1CHO). Kandidaten die niet zijn "
                                                    "begonnen hebben geen achtergrondkenmerken en vallen daar dus weg.",
                                                    className="text-muted small",
                                                ),
                                                dash_table.DataTable(
                                                    id="tabel-aantallen",
                                                    style_table={
                                                        "overflowX": "auto",
                                                        "maxWidth": "460px",
                                                    },
                                                    **TABLE_STYLE,
                                                ),
                                                html.Hr(),
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
                                                            width=3,
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
                                                            width=3,
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
                                                            width=3,
                                                        ),
                                                        dbc.Col(
                                                            [
                                                                dbc.Label(
                                                                    "Schaal/Bereik",
                                                                    className="small",
                                                                ),
                                                                dcc.Dropdown(
                                                                    id="bereik-filter",
                                                                    options=[
                                                                        {
                                                                            "label": "Alle schalen",
                                                                            "value": "Alle",
                                                                        }
                                                                    ],
                                                                    value="Alle",
                                                                    clearable=False,
                                                                ),
                                                            ],
                                                            width=3,
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
                                    label="Verschiltoets",
                                    tab_id="tab-verschil",
                                    children=[
                                        html.Div(
                                            [
                                                html.H5("Verschiltoets per item"),
                                                html.P(
                                                    "Toetst per item of de scores significant verschillen. Kies het niveau: "
                                                    "tussen uitkomstgroepen (voorspelt het item studiesucces?) of tussen "
                                                    "demografische groepen (maakt het item onbedoeld onderscheid?).",
                                                    className="text-muted small",
                                                ),
                                                dbc.Row(
                                                    dbc.Col(
                                                        [
                                                            dbc.Label(
                                                                "Niveau",
                                                                className="small",
                                                            ),
                                                            dcc.Dropdown(
                                                                id="verschil-niveau",
                                                                options=GROEPEER_OPTIES,
                                                                value="groep",
                                                                clearable=False,
                                                            ),
                                                        ],
                                                        width=4,
                                                    ),
                                                    className="mb-3",
                                                ),
                                                html.Div(
                                                    id="verschiltoets-uitleg",
                                                    className="mb-3",
                                                ),
                                                dash_table.DataTable(
                                                    id="tabel-verschil",
                                                    style_table={"overflowX": "auto"},
                                                    style_data_conditional=[
                                                        {
                                                            "if": {
                                                                "filter_query": '{p} contains "*"'
                                                            },
                                                            "backgroundColor": "#f0fdf4",
                                                            "fontWeight": "bold",
                                                        }
                                                    ],
                                                    **TABLE_STYLE,
                                                ),
                                            ],
                                            className="tab-body",
                                        ),
                                    ],
                                ),
                                dbc.Tab(
                                    label="Samenhang items",
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
                                                                        html.Li(
                                                                            "r < 0.10: verwaarloosbaar"
                                                                        ),
                                                                        html.Li(
                                                                            "r = 0.10 - 0.30: zwak (items meten grotendeels iets anders)"
                                                                        ),
                                                                        html.Li(
                                                                            "r = 0.30 - 0.50: matig (gedeelde variantie, maar ook unieke bijdrage)"
                                                                        ),
                                                                        html.Li(
                                                                            "r = 0.50 - 0.70: sterk (substantiele overlap, vraag of beide items nodig zijn)"
                                                                        ),
                                                                        html.Li(
                                                                            "r > 0.70: zeer sterk (items meten vrijwel hetzelfde construct)"
                                                                        ),
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
                                                    "de opleiding succesvol vervolgt (doorstroom naar jaar 2, of een diploma "
                                                    "bij eenjarige opleidingen)? Dit model kijkt naar alle items tegelijk en "
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
                                                                            "Positief = hogere score hangt samen met hogere kans op doorstroom. "
                                                                            "Negatief = hogere score hangt samen met lagere kans. "
                                                                            "Scores zijn genormaliseerd (z-scores), dus de coefficienten zijn "
                                                                            "vergelijkbaar tussen items met verschillende schalen."
                                                                        ),
                                                                        html.Li(
                                                                            "Odds ratio: hoeveel keer groter de kans op doorstroom wordt per "
                                                                            "standaarddeviatie stijging. OR = 1.5 betekent 50% hogere kans als "
                                                                            "de score 1 SD stijgt. OR < 1 betekent lagere kans."
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
                                                                    className="small text-muted mb-1",
                                                                ),
                                                                html.P(
                                                                    "Scores worden genormaliseerd (z-scores) voor de regressie. Daardoor zijn "
                                                                    "de coefficienten en odds ratios vergelijkbaar tussen items met verschillende "
                                                                    "schalen. Een odds ratio van 2.0 betekent: per standaarddeviatie hoger scoren "
                                                                    "verdubbelt de kans op doorstroom.",
                                                                    className="small text-muted mb-1",
                                                                ),
                                                                html.P(
                                                                    "Bij weinig studenten kan het model niet alle items tegelijk meenemen. "
                                                                    "Als vuistregel heb je minimaal 5 studenten in de kleinste groep per item "
                                                                    "nodig. Bij minder selecteert de tool automatisch de items die individueel "
                                                                    "het sterkst samenhangen met doorstroom. De overige items worden niet "
                                                                    "meegenomen en staan vermeld boven de tabel.",
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
                            active_tab="tab-bevindingen",
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
    config = None

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
            return sel_status, cfg_status, no, cho_status, True

    if trigger == "wiz-config-store" and wiz_config:
        config = json.loads(wiz_config)
        n_kol = len(config.get("kolommen", []))
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
            if config is None:
                config = lees_config(cfg) if cfg else json.loads(wiz_config)
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
                cho_ruw = parse_csv_or_excel(cho, cho_fn or "data.csv")
                missing = ontbrekende_cho_kolommen(cho_ruw)
                if missing:
                    cho_status = dbc.Alert(
                        f"Ontbrekende kolommen in 1CHO: {', '.join(missing)}",
                        color="danger",
                        className="small py-1",
                    )
                    return sel_status, cfg_status, validatie, cho_status, True

                cho_df = transformeer_cho(cho_ruw)

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
        cho_df = transformeer_cho(
            parse_csv_or_excel(cho_contents, cho_fn or "data.csv")
        )
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
    cho_df = transformeer_cho(pd.read_csv(cho_path, sep=";"))

    joined = koppel_data(cho_df, scores_df)

    return (
        joined.to_json(orient="split", date_format="iso"),
        scores_df.to_json(orient="split", date_format="iso"),
    )


# ── Sidebar callbacks ─────────────────────────────────────────────────────────


@app.callback(
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
            empty_opts,
            "Alle",  # samenhang-instrument
            empty_opts,
            "Alle",  # samenhang-criterium
            [],
            "totaalscore",  # vo-score
            "",  # subtitle
        )

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
            vo_opties.append({"label": shorten_item(item), "value": item})

    return (
        instrument_opties,
        "Alle",
        criterium_opties,
        "Alle",
        vo_opties,
        "totaalscore",
        subtitle,
    )


def _sorteer_bereik(label: str) -> tuple[int, float, float]:
    """Sorteersleutel voor bereiklabels: op bovengrens, 'onbekend' achteraan."""
    grenzen = grenzen_van_label(label)
    if grenzen is None:
        return (1, 0.0, 0.0)
    onder, boven = grenzen
    return (0, boven, onder)


@app.callback(
    Output("instrument-filter", "options"),
    Output("instrument-filter", "value"),
    Output("criterium-filter", "options"),
    Output("criterium-filter", "value"),
    Output("item-filter", "options"),
    Output("item-filter", "value"),
    Output("bereik-filter", "options"),
    Output("bereik-filter", "value"),
    Input("instrument-filter", "value"),
    Input("criterium-filter", "value"),
    Input("item-filter", "value"),
    Input("bereik-filter", "value"),
    Input("scores-store", "data"),
)
def update_score_filters(
    instrument_val, criterium_val, item_val, bereik_val, scores_store
):
    alle_inst = [{"label": "Alle instrumenten", "value": "Alle"}]
    alle_crit = [{"label": "Alle criteria", "value": "Alle"}]
    alle_item = [{"label": "Alle items", "value": "Alle"}]
    alle_bereik = [{"label": "Alle schalen", "value": "Alle"}]

    if not scores_store:
        return (
            alle_inst,
            "Alle",
            alle_crit,
            "Alle",
            alle_item,
            "Alle",
            alle_bereik,
            "Alle",
        )

    scores_df = pd.read_json(io.StringIO(scores_store), orient="split")
    meta = scores_df[["instrument", "item", "criterium"]].drop_duplicates().copy()
    meta["bereik"] = meta["item"].map(bucket_per_item(scores_df))

    sel = {
        "instrument": instrument_val,
        "criterium": criterium_val,
        "item": item_val,
        "bereik": bereik_val,
    }

    # Levert de huidige combinatie niets op, reset dan alles naar "Alle".
    huidig = meta
    for dim, val in sel.items():
        if val and val != "Alle":
            huidig = huidig[huidig[dim] == val]
    if huidig.empty:
        sel = {dim: "Alle" for dim in sel}

    def beschikbare_waarden(dim):
        # Waarden van dim in rijen die aan alle andere actieve selecties voldoen;
        # dat maakt de dropdowns cascaderend.
        m = meta
        for ander, val in sel.items():
            if ander == dim or not val or val == "Alle":
                continue
            m = m[m[ander] == val]
        return set(m[dim].dropna())

    inst_opts = alle_inst + [
        {"label": i, "value": i}
        for i in sorted(meta["instrument"].unique())
        if i in beschikbare_waarden("instrument")
    ]
    crit_set = beschikbare_waarden("criterium") - {""}
    crit_opts = alle_crit + [
        {"label": c, "value": c}
        for c in sorted(meta["criterium"].dropna().unique())
        if c.strip() and c in crit_set
    ]
    item_set = beschikbare_waarden("item")
    item_opts = alle_item + [
        {"label": shorten_item(it), "value": it}
        for it in sorted(meta["item"].unique())
        if it in item_set
    ]
    bereik_opts = alle_bereik + [
        {"label": b, "value": b}
        for b in sorted(beschikbare_waarden("bereik"), key=_sorteer_bereik)
    ]

    def geldig(val, opts):
        return val if any(o["value"] == val for o in opts) else "Alle"

    return (
        inst_opts,
        geldig(sel["instrument"], inst_opts),
        crit_opts,
        geldig(sel["criterium"], crit_opts),
        item_opts,
        geldig(sel["item"], item_opts),
        bereik_opts,
        geldig(sel["bereik"], bereik_opts),
    )


@app.callback(
    Output("cohort-stats", "children"),
    Input("data-store", "data"),
)
def update_cohort_stats(store_data):
    df = df_from_store(store_data)
    if df.empty:
        return ""
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
    "Gestart, diploma gehaald": {"backgroundColor": "#eff6ff", "color": "#1e40af"},
}

# Kwalitatief palet voor demografische groepen. De labels variëren per dataset
# (vooropleiding kan van alles zijn), dus kleuren worden op volgorde toegekend in
# plaats van per label hardgecodeerd.
_DEMO_PALET = px.colors.qualitative.Set2


def _demo_kleur_map(groepen) -> dict:
    return {g: _DEMO_PALET[i % len(_DEMO_PALET)] for i, g in enumerate(groepen)}


def _meng_met_wit(kleur: str, f: float = 0.80) -> str:
    """Lichtere tint van een kleur (f van de weg naar wit), voor
    tabelachtergronden. Werkt op '#rrggbb' en 'rgb(r, g, b)', de twee formaten
    die Plotly-paletten leveren."""
    rgb = hex_to_rgb(kleur) if kleur.startswith("#") else unlabel_rgb(kleur)
    r, g, b = (int(c + (255 - c) * f) for c in rgb)
    return f"#{r:02x}{g:02x}{b:02x}"


def _groep_tabel_stijl(groepeer, kleur_map, volgorde) -> list:
    """style_data_conditional dat tabelrijen op de groep kleurt: uitkomstgroepen
    met de vaste kleuren, demografische groepen met een lichte tint van de
    bijbehorende boxplot-kleur."""
    if groepeer == "groep":
        return [
            {"if": {"filter_query": f'{{Groep}} = "{groep}"'}, **stijl}
            for groep, stijl in GROEP_TABEL_KLEUREN.items()
        ]
    return [
        {
            "if": {"filter_query": f'{{Groep}} = "{groep}"'},
            "backgroundColor": _meng_met_wit(kleur_map[groep]),
        }
        for groep in volgorde
    ]


def _aantallen_per_groep(df, groepeer):
    """Aantal studenten per groep (n en %). De uitkomstgroep telt alle
    kandidaten; geslacht en vooropleiding tellen alleen ingeschreven studenten,
    want die achtergrond komt uit 1CHO."""
    if groepeer == "groep":
        telling = df["groep"].value_counts().reindex(GROEP_VOLGORDE).dropna()
    else:
        ingeschr = df[df["groep"].isin(GROEP_INGESCHREVEN)]
        if groepeer not in ingeschr.columns:
            return pd.DataFrame()
        telling = ingeschr[groepeer].dropna().value_counts()
    totaal = int(telling.sum())
    if totaal == 0:
        return pd.DataFrame()
    return pd.DataFrame(
        [
            {"Groep": str(groep), "n": int(n), "%": f"{n / totaal * 100:.0f}%"}
            for groep, n in telling.items()
        ]
    )


def _scores_per_groep(df, scores_df, groepeer):
    """Long-format scores met een kolom 'groep' die de gekozen groepering bevat
    (uitkomstgroep of een demografische dimensie). Returnt
    (scores, kleur_map, volgorde), of ``None`` als de dimensie ontbreekt. De
    demografie bestaat alleen voor ingeschreven studenten."""
    if groepeer == "groep":
        scores = scores_df.merge(
            df[["studentnummer", "groep"]].drop_duplicates(),
            on="studentnummer",
            how="inner",
        )
        scores["groep"] = pd.Categorical(
            scores["groep"], categories=GROEP_VOLGORDE, ordered=True
        )
        scores["item_kort"] = scores["item"].apply(shorten_item)
        return scores, GROEP_KLEUREN, GROEP_VOLGORDE
    dim = next((d for d in DEMO_DIMENSIES if d["kolom"] == groepeer), None)
    if dim is None:
        return None
    scores = demografie_scores(df, scores_df, dim)
    if scores is None:
        return None
    scores = scores.rename(columns={dim["kolom"]: "groep"})
    groepen = sorted(scores["groep"].dropna().unique())
    return scores, _demo_kleur_map(groepen), groepen


@app.callback(
    Output("fig-totaal", "figure"),
    Output("tabel-aantallen", "data"),
    Output("tabel-aantallen", "columns"),
    Output("tabel-aantallen", "style_data_conditional"),
    Output("tabel-gemiddelden", "data"),
    Output("tabel-gemiddelden", "columns"),
    Output("tabel-gemiddelden", "style_data_conditional"),
    Input("groepeer-op", "value"),
    Input("instrument-filter", "value"),
    Input("criterium-filter", "value"),
    Input("item-filter", "value"),
    Input("bereik-filter", "value"),
    State("data-store", "data"),
    State("scores-store", "data"),
)
def update_scores_tab(
    groepeer,
    instrument_filter,
    criterium_filter,
    item_filter,
    bereik_filter,
    store_data,
    scores_store,
):
    leeg = go.Figure().update_layout(**CHART_BASE, margin=dict(t=10, b=10))
    df = df_from_store(store_data)
    if df.empty or not scores_store:
        return leeg, [], [], [], [], [], []

    scores_df = pd.read_json(io.StringIO(scores_store), orient="split")
    basis = _scores_per_groep(df, scores_df, groepeer)
    if basis is None:
        return leeg, [], [], [], [], [], []
    scores, kleur_map, volgorde = basis

    # Teltabel met groepsgroottes, los van de itemfilters zodat hij de volledige
    # groepering toont.
    aantallen = _aantallen_per_groep(df, groepeer)
    aant_data = aantallen.to_dict("records")
    aant_cols = (
        [{"name": c, "id": c} for c in ["Groep", "n", "%"]]
        if not aantallen.empty
        else []
    )
    groep_stijl = _groep_tabel_stijl(groepeer, kleur_map, volgorde)

    if instrument_filter and instrument_filter != "Alle":
        scores = scores[scores["instrument"] == instrument_filter]
    if criterium_filter and criterium_filter != "Alle":
        scores = scores[scores["criterium"] == criterium_filter]
    if item_filter and item_filter != "Alle":
        scores = scores[scores["item"] == item_filter]
    if bereik_filter and bereik_filter != "Alle":
        # Op de volledige verdeling bucketen, zodat de keuze dezelfde items
        # raakt als de dropdown en niet meeschuift met de groepsselectie.
        bereik_per_item = bucket_per_item(scores_df)
        items_in_bereik = bereik_per_item.index[bereik_per_item == bereik_filter]
        scores = scores[scores["item"].isin(items_in_bereik)]

    if scores.empty:
        return leeg, aant_data, aant_cols, groep_stijl, [], [], []

    items_kort = sorted(scores["item_kort"].unique())
    enkel_item = len(items_kort) == 1
    kleur = {"color_discrete_map": kleur_map} if kleur_map else {}
    n_studenten = scores["studentnummer"].nunique()

    if enkel_item:
        fig = px.box(
            scores,
            x="groep",
            y="score",
            color="groep",
            category_orders={"groep": volgorde},
            points="all" if n_studenten <= 50 else False,
            height=480,
            labels={"groep": "", "score": items_kort[0]},
            **kleur,
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
            category_orders={"groep": volgorde, "item_kort": items_kort},
            points="all" if n_studenten <= 30 else False,
            height=520,
            labels={"item_kort": "", "score": "Score", "groep": ""},
            **kleur,
        )
        fig.update_layout(
            boxgap=0.15,
            legend=dict(orientation="h", y=1.05, yanchor="bottom"),
            xaxis_tickangle=-25,
            **CHART_BASE,
            margin=dict(t=60, b=10),
        )

    # Bij een gekozen schaal de y-as op de afgeronde grenzen vastzetten, zodat
    # items met een vergelijkbaar bereik eerlijk naast elkaar staan.
    if bereik_filter and bereik_filter != "Alle":
        grenzen = schaal_grenzen(scores["score"])
        if grenzen is not None:
            fig.update_yaxes(range=list(grenzen))

    tabel_pivot = (
        scores.groupby(["groep", "item_kort"], observed=True)["score"]
        .agg(["mean", "std"])
        .round(2)
        .reset_index()
        .merge(meta_per_item(scores), on="item_kort", how="left")
    )
    tabel_pivot[["instrument", "criterium"]] = tabel_pivot[
        ["instrument", "criterium"]
    ].fillna("")
    tabel_pivot = tabel_pivot.rename(
        columns={
            "item_kort": "Item",
            "mean": "Gem.",
            "std": "SD",
            "groep": "Groep",
            "instrument": "Instrument",
            "criterium": "Criterium",
        }
    )
    tabel_pivot = tabel_pivot[
        ["Groep", "Instrument", "Criterium", "Item", "Gem.", "SD"]
    ]
    gem_data = tabel_pivot.to_dict("records")
    gem_cols = [{"name": c, "id": c} for c in tabel_pivot.columns]

    return fig, aant_data, aant_cols, groep_stijl, gem_data, gem_cols, groep_stijl


def _uitleg_verschil_uitkomst():
    return [
        html.P(
            "Deze tabel vergelijkt per item twee groepen studenten die met de "
            "opleiding zijn begonnen, en toetst of de succesgroep bij de selectie "
            "hoger scoorde:",
            className="text-muted small mb-1",
        ),
        html.Ul(
            [
                html.Li(
                    [
                        html.B("Succes: "),
                        "studenten die doorstroomden naar jaar 2 of hun diploma haalden.",
                    ]
                ),
                html.Li(
                    [
                        html.B("Geen succes: "),
                        "studenten die wel begonnen maar uitvielen (geen jaar 2, geen diploma).",
                    ]
                ),
            ],
            className="text-muted small mb-1",
        ),
        html.P(
            "Studenten die nooit startten blijven buiten de toets. Mann-Whitney U "
            "met de rank-biseriale effectgrootte (-1 tot +1, positief = succesgroep "
            "scoort hoger) en een 95%-betrouwbaarheidsinterval. Positief en "
            "significant (p < 0.05) betekent dat het item voorspellende waarde heeft.",
            className="text-muted small mb-0",
        ),
    ]


def _uitleg_verschil_demografisch(label):
    laag = label.lower()
    return [
        html.P(
            f"Deze tabel toetst per item of de selectiescores verschillen tussen "
            f"{laag}-groepen. Een systematisch verschil kan wijzen op onbedoelde "
            "vertekening van een instrument.",
            className="text-muted small mb-1",
        ),
        html.P(
            f"De {laag} komt uit 1CHO en is alleen bekend voor ingeschreven "
            "studenten; de toets vergelijkt dus binnen de ingeschreven groep. "
            "Kruskal-Wallis (werkt voor twee of meer groepen) met epsilon-kwadraat "
            "als effectgrootte (0-1: onder 0.01 verwaarloosbaar, 0.01-0.06 zwak, "
            "0.06-0.14 matig, boven 0.14 sterk). De kolom 'Verschil' toont welke "
            "groep het hoogst scoort. Een significant verschil (p < 0.05) verdient "
            "aandacht bij het beoordelen van de eerlijkheid van het instrument.",
            className="text-muted small mb-0",
        ),
    ]


@app.callback(
    Output("tabel-verschil", "data"),
    Output("tabel-verschil", "columns"),
    Output("verschiltoets-uitleg", "children"),
    Input("verschil-niveau", "value"),
    State("data-store", "data"),
    State("scores-store", "data"),
)
def update_verschiltoets_tab(niveau, store_data, scores_store):
    df = df_from_store(store_data)
    if df.empty or not scores_store:
        return [], [], ""
    scores_df = pd.read_json(io.StringIO(scores_store), orient="split")

    if niveau == "groep":
        scores = scores_df.merge(
            df[["studentnummer", "groep"]].drop_duplicates(),
            on="studentnummer",
            how="inner",
        )
        scores["item_kort"] = scores["item"].apply(shorten_item)
        tabel = vergelijk_succes_per_item(scores)
        kolommen = VERGELIJKING_KOLOMMEN
        uitleg = _uitleg_verschil_uitkomst()
    else:
        dim = next((d for d in DEMO_DIMENSIES if d["kolom"] == niveau), None)
        scores = demografie_scores(df, scores_df, dim) if dim else None
        if scores is None:
            return [], [], _uitleg_verschil_demografisch(dim["label"] if dim else "")
        tabel = toets_verschil_per_item(scores, dim["kolom"])
        kolommen = VERSCHIL_KOLOMMEN
        uitleg = _uitleg_verschil_demografisch(dim["label"])

    data = tabel[kolommen].to_dict("records") if not tabel.empty else []
    cols = [{"name": c, "id": c} for c in kolommen]
    return data, cols, uitleg


def _bevindingen_lijst(titel, items, leeg_tekst):
    return html.Div(
        [
            html.H6(titel),
            html.Ul([html.Li(x) for x in items], className="small mb-0")
            if items
            else html.P(leeg_tekst, className="text-muted small mb-0"),
        ],
        className="mb-4",
    )


@app.callback(
    Output("bevindingen-inhoud", "children"),
    Input("data-store", "data"),
    State("scores-store", "data"),
)
def update_bevindingen(store_data, scores_store):
    df = df_from_store(store_data)
    if df.empty or not scores_store:
        return html.P(
            "Laad eerst data om de bevindingen te zien.", className="text-muted"
        )

    scores_df = pd.read_json(io.StringIO(scores_store), orient="split")
    scores = scores_df.merge(
        df[["studentnummer", "groep"]].drop_duplicates(),
        on="studentnummer",
        how="inner",
    )
    scores["item_kort"] = scores["item"].apply(shorten_item)
    succes_tabel = vergelijk_succes_per_item(scores)

    demo_tabellen = {}
    for dim in DEMO_DIMENSIES:
        demo_scores = demografie_scores(df, scores_df, dim)
        if demo_scores is not None:
            demo_tabellen[dim["label"]] = toets_verschil_per_item(
                demo_scores, dim["kolom"]
            )

    bevindingen = genereer_bevindingen(succes_tabel, demo_tabellen)
    secties = []
    if bevindingen["samenvatting"]:
        secties.append(
            html.P(" ".join(bevindingen["samenvatting"]), className="fw-bold")
        )
    secties.append(
        _bevindingen_lijst(
            "Wat voorspelt studiesucces?",
            bevindingen["validiteit"],
            "Geen opvallende voorspellers gevonden in de cijfers.",
        )
    )
    secties.append(
        _bevindingen_lijst(
            "Verschillen tussen groepen (let op eerlijkheid)",
            bevindingen["fairness"],
            "Geen demografische gegevens beschikbaar om te vergelijken.",
        )
    )
    return secties


@app.callback(
    Output("fig-vo", "figure"),
    Output("tabel-pearsonr", "data"),
    Output("tabel-pearsonr", "columns"),
    Output("tabel-pearsonr", "style_data_conditional"),
    Input("vo-score", "value"),
    State("data-store", "data"),
    State("scores-store", "data"),
)
def update_vo_tab(score_keuze, store_data, scores_store):
    leeg = go.Figure().update_layout(**CHART_BASE)
    df = df_from_store(store_data)
    if df.empty or "gem_eindcijfer_vo" not in df.columns:
        return leeg, [], [], []

    scores_df = (
        pd.read_json(io.StringIO(scores_store), orient="split")
        if scores_store
        else None
    )

    df_vo = df[df["gem_eindcijfer_vo"].notna()].copy()
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

    ingeschreven = plot_df[plot_df["groep"].isin(GROEP_INGESCHREVEN)]

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
    for groep in GROEP_INGESCHREVEN:
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
    Input("samenhang-instrument", "value"),
    Input("samenhang-criterium", "value"),
    State("data-store", "data"),
    State("scores-store", "data"),
)
def update_samenhang_tab(
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
    scores = scores_df

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

    # Regressie draait altijd op alle items, niet op de instrument-subset
    all_item_pivot = scores_df.pivot_table(
        index="studentnummer", columns="item", values="score", aggfunc="mean"
    )
    all_item_pivot.columns = [shorten_item(c) for c in all_item_pivot.columns]
    all_score_cols = list(all_item_pivot.columns)

    # Items in de huidige filterselectie (voor markering in de tabel)
    gefilterde_items = set(shorten_item(i) for i in scores["item"].unique())

    ingeschreven = df[df["groep"].isin(GROEP_INGESCHREVEN)].copy()

    if len(ingeschreven) < 10:
        regressie_msg = dbc.Alert(
            f"Te weinig ingeschreven studenten ({len(ingeschreven)}) voor betrouwbare regressie. "
            "Minimaal 10 nodig.",
            color="warning",
            className="small",
        )
        return fig, regressie_msg, reg_data, reg_cols, reg_style

    ingeschreven["doorgestroomd"] = ingeschreven["groep"].isin(GROEP_SUCCES).astype(int)

    item_pivot_inschr = all_item_pivot.loc[
        all_item_pivot.index.isin(ingeschreven["studentnummer"])
    ].copy()

    # Verwijder kolommen waar >30% NaN is (optionele velden zoals keuzevakken)
    nan_pct = item_pivot_inschr.isna().mean()
    verwijderd_nan = [
        c
        for c in all_score_cols
        if c in item_pivot_inschr.columns and nan_pct.get(c, 1) > 0.3
    ]
    bruikbare_cols = [
        c
        for c in all_score_cols
        if c in item_pivot_inschr.columns and nan_pct.get(c, 1) <= 0.3
    ]

    if len(bruikbare_cols) < 2:
        regressie_msg = dbc.Alert(
            "Te weinig bruikbare items voor regressie.",
            color="warning",
            className="small",
        )
        return fig, regressie_msg, reg_data, reg_cols, reg_style

    # Vul resterende NaN's met kolomgemiddelde
    item_pivot_inschr[bruikbare_cols] = item_pivot_inschr[bruikbare_cols].fillna(
        item_pivot_inschr[bruikbare_cols].mean()
    )
    item_pivot_inschr = item_pivot_inschr.dropna(subset=bruikbare_cols)

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
    X = item_pivot_inschr[bruikbare_cols]

    # Verwijder kolommen met (bijna-)perfecte multicollineariteit
    from numpy.linalg import matrix_rank

    verwijderd_collinear = []
    while len(X.columns) > 1:
        rank = matrix_rank(X.values)
        if rank >= len(X.columns):
            break
        corr_vals = X.corr().abs().to_numpy().copy()
        np.fill_diagonal(corr_vals, 0)
        flat_idx = corr_vals.argmax()
        _, col_idx = divmod(flat_idx, corr_vals.shape[1])
        verwijderd_collinear.append(X.columns[col_idx])
        X = X.drop(columns=[X.columns[col_idx]])
    bruikbare_cols = list(X.columns)

    # Beperk predictoren als er te weinig events per variabele zijn
    n_events = min(int(y.sum()), int(len(y) - y.sum()))
    max_predictoren = max(2, n_events // 5)
    verwijderd_epv = []
    if len(bruikbare_cols) > max_predictoren:
        import statsmodels.api as sm

        univariate_p = {}
        for col in bruikbare_cols:
            x_col = X[[col]].astype(float)
            x_col = (x_col - x_col.mean()) / x_col.std().replace(0, 1)
            try:
                m = sm.Logit(y.astype(float), sm.add_constant(x_col)).fit(
                    disp=0, maxiter=50
                )
                univariate_p[col] = m.pvalues.iloc[-1]
            except Exception:
                univariate_p[col] = 1.0
        gesorteerd = sorted(bruikbare_cols, key=lambda c: univariate_p[c])
        verwijderd_epv = gesorteerd[max_predictoren:]
        bruikbare_cols = gesorteerd[:max_predictoren]
        X = X[bruikbare_cols]

    try:
        import statsmodels.api as sm

        X_z = X.astype(float).apply(
            lambda s: (s - s.mean()) / s.std() if s.std() > 0 else 0
        )
        X_const = sm.add_constant(X_z)
        model = sm.Logit(y.astype(float), X_const).fit(disp=0, maxiter=100)

        n_doorgestroomd = int(y.sum())
        n_niet = int(len(y) - y.sum())
        pseudo_r2 = round(float(model.prsquared), 3)
        msg_parts = [
            html.Span(
                f"n = {len(y)} (doorgestroomd: {n_doorgestroomd}, niet: {n_niet})",
                className="small text-muted me-3",
            ),
            html.Span(f"Pseudo R² = {pseudo_r2}", className="small fw-bold"),
        ]
        if verwijderd_nan:
            msg_parts.append(html.Br())
            msg_parts.append(
                html.Span(
                    f"Items niet meegenomen (>30% ontbrekend): {', '.join(verwijderd_nan)}",
                    className="small text-muted",
                )
            )
        if verwijderd_collinear:
            msg_parts.append(html.Br())
            msg_parts.append(
                html.Span(
                    f"Items niet meegenomen (overlap met andere items): {', '.join(verwijderd_collinear)}",
                    className="small text-muted",
                )
            )
        if verwijderd_epv:
            msg_parts.append(html.Br())
            msg_parts.append(
                html.Span(
                    f"Items niet meegenomen (te weinig studenten voor {len(bruikbare_cols) + len(verwijderd_epv)} "
                    f"predictoren, beperkt tot {len(bruikbare_cols)} sterkste): {', '.join(verwijderd_epv)}",
                    className="small text-muted",
                )
            )
        regressie_msg = html.Div(msg_parts)

        for item_naam in bruikbare_cols:
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
            if row["Item"] not in gefilterde_items:
                reg_style.append(
                    {
                        "if": {"row_index": i},
                        "opacity": "0.4",
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
