"""
Evaluatietool: selectie & studiesucces dashboard

Draai met: uv run python app.py
Data aanmaken: uv run python scripts/maak_data.py
"""

from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from scipy import stats

import dash
from dash import dcc, html, dash_table, Input, Output
import dash_bootstrap_components as dbc

DATA_PATH = Path("data/synthetic/analysedata.csv")

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
SCORES = {
    "totaalscore": "Totaalscore",
    "interview_score": "Interview",
    "motivatiescore": "Motivatiebrief",
    "cv_score": "CV",
}
SCORE_OPTIES = [
    {"label": "Interview", "value": "interview_score"},
    {"label": "Motivatiebrief", "value": "motivatiescore"},
    {"label": "CV", "value": "cv_score"},
    {"label": "Totaalscore", "value": "totaalscore"},
]

df_global = pd.read_csv(DATA_PATH, sep=";")
df_global["groep"] = pd.Categorical(
    df_global["groep"], categories=GROEP_VOLGORDE, ordered=True
)

JAREN = sorted(df_global["selectiejaar"].unique().tolist())


def maak_filter_opties(kolom: str, alle_label: str = "Alle") -> list[dict]:
    return [{"label": alle_label, "value": "Alle"}] + [
        {"label": str(v), "value": str(v)}
        for v in sorted(df_global[kolom].dropna().unique())
    ]


cohort_opties = [{"label": "Alle cohorten", "value": "Alle"}] + [
    {"label": str(j), "value": str(j)} for j in JAREN
]
geslacht_opties = maak_filter_opties("geslacht")
vooropl_opties = maak_filter_opties("hoogste_vooropleiding")


def filter_data(cohort, geslacht, vooropleiding, incl_cohort=True):
    df = df_global
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


def maak_violin(df: pd.DataFrame, var: str, titel: str, hoogte: int) -> go.Figure:
    fig = go.Figure()
    for groep in GROEP_VOLGORDE:
        subset = df[df["groep"] == groep][var].dropna()
        fig.add_trace(
            go.Violin(
                y=subset,
                name=groep,
                box_visible=True,
                meanline_visible=True,
                fillcolor=GROEP_KLEUREN[groep],
                line_color=GROEP_KLEUREN[groep],
                opacity=0.7,
                hoverinfo="skip",
                showlegend=False,
            )
        )
    fig.update_layout(
        title=titel,
        yaxis_title="Score (1-10)",
        height=hoogte,
        violingap=0.3,
        margin=dict(t=50, b=10),
        **CHART_BASE,
    )
    fix_xas_labels(fig)
    return fig


def bereken_pct(agg: pd.DataFrame, groep_kolom: str) -> pd.DataFrame:
    agg["pct"] = (
        agg["n"] / agg.groupby(groep_kolom)["n"].transform("sum") * 100
    ).round(1)
    return agg


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

# ── Sidebar ───────────────────────────────────────────────────────────────────

SIDEBAR = html.Div(
    [
        html.Img(src="/assets/nko-logo.svg", className="sidebar-logo"),
        html.P("Filters", className="sidebar-label"),
        dbc.Label("Cohort"),
        dcc.Dropdown(
            id="cohort-dropdown",
            options=cohort_opties,
            value="Alle",
            clearable=False,
            className="mb-3",
        ),
        dbc.Label("Geslacht"),
        dcc.Dropdown(
            id="geslacht-dropdown",
            options=geslacht_opties,
            value="Alle",
            clearable=False,
            className="mb-3",
        ),
        dbc.Label("Vooropleiding"),
        dcc.Dropdown(
            id="vooropleiding-dropdown",
            options=vooropl_opties,
            value="Alle",
            clearable=False,
            className="mb-4",
        ),
        html.Hr(className="my-2"),
        html.P("Kandidaten per cohort", className="sidebar-label"),
        html.Div(id="cohort-stats"),
        html.Hr(className="mt-3 mb-2"),
        html.P(
            "Synthetische voorbeelddata.",
            className="text-muted",
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
)

app.layout = html.Div(
    [
        SIDEBAR,
        html.Div(
            [
                html.H4("Evaluatietool Selectie", className="app-title"),
                html.P(
                    "B Gezondheidswetenschappen | DEMO Hogeschool",
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
                                        dcc.Loading(
                                            dcc.Graph(id="fig-totaal"), type="dot"
                                        ),
                                        html.Hr(),
                                        dbc.Row(
                                            [
                                                dbc.Col(
                                                    dcc.Loading(
                                                        dcc.Graph(id="fig-interview"),
                                                        type="dot",
                                                    )
                                                ),
                                                dbc.Col(
                                                    dcc.Loading(
                                                        dcc.Graph(id="fig-motivatie"),
                                                        type="dot",
                                                    )
                                                ),
                                                dbc.Col(
                                                    dcc.Loading(
                                                        dcc.Graph(id="fig-cv"),
                                                        type="dot",
                                                    )
                                                ),
                                            ]
                                        ),
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
                                            "schaal (1-10). ns = niet significant (p≥0.05).  "
                                            "* p<0.05  ** p<0.01  *** p<0.001",
                                            className="text-muted small",
                                        ),
                                        dash_table.DataTable(
                                            id="tabel-mannwhitney",
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
                        dbc.Tab(
                            label="Verdeling",
                            tab_id="tab-verdeling",
                            children=[
                                html.Div(
                                    [
                                        html.H5("Verdeling per groep"),
                                        html.P(
                                            id="verdeling-caption",
                                            className="text-muted small",
                                        ),
                                        dcc.Loading(
                                            dcc.Graph(id="fig-verdeling"), type="dot"
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
                                        html.H5("Demografisch profiel per groep"),
                                        html.P(
                                            "Achtergrondkenmerken komen uit 1CHO en zijn alleen beschikbaar voor ingeschreven studenten.",
                                            className="text-muted small",
                                        ),
                                        dbc.Row(
                                            [
                                                dbc.Col(
                                                    dcc.Loading(
                                                        dcc.Graph(id="fig-geslacht"),
                                                        type="dot",
                                                    )
                                                ),
                                                dbc.Col(
                                                    dcc.Loading(
                                                        dcc.Graph(id="fig-herkomst"),
                                                        type="dot",
                                                    )
                                                ),
                                            ]
                                        ),
                                        dcc.Loading(
                                            dcc.Graph(id="fig-vooropleiding"),
                                            type="dot",
                                        ),
                                        html.Hr(),
                                        dcc.Loading(
                                            dcc.Graph(id="fig-instroom"), type="dot"
                                        ),
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
                                                            options=SCORE_OPTIES,
                                                            value="interview_score",
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
                                                            options=SCORE_OPTIES,
                                                            value="motivatiescore",
                                                            clearable=False,
                                                        ),
                                                    ],
                                                    width=3,
                                                ),
                                            ],
                                            className="mb-3",
                                        ),
                                        dcc.Loading(
                                            dcc.Graph(id="fig-puntenwolk"), type="dot"
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
                                        html.H5("VO-eindcijfer vs selectiescores"),
                                        html.P(
                                            "Het VO-eindcijfer is het gemiddeld eindexamencijfer van de hoogste vooropleiding "
                                            "vóór het hoger onderwijs; voor de meeste studenten is dat het VWO-diploma. "
                                            "Het komt rechtstreeks uit het EV-bestand van 1CHO en is daardoor onafhankelijk van "
                                            "wat de opleiding zelf heeft gemeten tijdens de selectie. "
                                            "De grafiek laat zien of de selectie-instrumenten informatie toevoegen die de school "
                                            "nog niet had. Een lage samenhang (r ≈ 0) betekent dat het instrument iets "
                                            "wezenlijk anders meet dan cognitieve schoolprestaties, zoals motivatie of "
                                            "communicatievaardigheid. Een hoge samenhang (r ≈ 1) suggereert dat de selectie "
                                            "grotendeels herhaalt wat het VO-cijfer al zegt. Alleen ingeschreven studenten zijn zichtbaar.",
                                            className="text-muted small",
                                        ),
                                        dbc.Row(
                                            [
                                                dbc.Col(
                                                    [
                                                        dbc.Label(
                                                            "Selectiescore (y-as)"
                                                        ),
                                                        dcc.Dropdown(
                                                            id="vo-score",
                                                            options=SCORE_OPTIES,
                                                            value="interview_score",
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
                                            style_table={
                                                "overflowX": "auto",
                                                "maxWidth": "380px",
                                            },
                                            **TABLE_STYLE,
                                        ),
                                        html.P(
                                            "Kleuren: groen (r < 0.3) = instrument meet iets anders dan schoolprestaties, "
                                            "goede discriminante validiteit. "
                                            "geel (0.3 tot 0.5) = enige overlap met VO-prestaties. "
                                            "rood (r ≥ 0.5) = instrument selecteert grotendeels op dezelfde dimensie als VO-cijfers. "
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
)

# ── Callbacks ─────────────────────────────────────────────────────────────────


@app.callback(
    Output("cohort-stats", "children"),
    Input("geslacht-dropdown", "value"),
    Input("vooropleiding-dropdown", "value"),
)
def update_cohort_stats(geslacht, vooropleiding):
    df = filter_data("Alle", geslacht, vooropleiding, incl_cohort=False)
    aantallen = df.groupby("selectiejaar").size()
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
            for jaar in JAREN
        ],
        className="g-1",
    )


@app.callback(
    Output("fig-totaal", "figure"),
    Output("fig-interview", "figure"),
    Output("fig-motivatie", "figure"),
    Output("fig-cv", "figure"),
    Output("tabel-gemiddelden", "data"),
    Output("tabel-gemiddelden", "columns"),
    Output("tabel-mannwhitney", "data"),
    Output("tabel-mannwhitney", "columns"),
    Input("cohort-dropdown", "value"),
    Input("geslacht-dropdown", "value"),
    Input("vooropleiding-dropdown", "value"),
)
def update_scores_tab(cohort, geslacht, vooropleiding):
    df = filter_data(cohort, geslacht, vooropleiding)

    fig_totaal = maak_violin(
        df,
        "totaalscore",
        "Totaalscore (gewogen: interview 50%, motivatie 30%, CV 20%)",
        500,
    )
    fig_interview = maak_violin(df, "interview_score", "Interview", 420)
    fig_motivatie = maak_violin(df, "motivatiescore", "Motivatiebrief", 420)
    fig_cv = maak_violin(df, "cv_score", "CV", 420)

    tabel = (
        df.groupby("groep", observed=True)[list(SCORES.keys())]
        .agg(["mean", "std"])
        .round(2)
    )
    tabel.columns = [
        f"{SCORES[var]} {'gem.' if stat == 'mean' else 'SD'}"
        for var, stat in tabel.columns
    ]
    tabel = tabel.reset_index().rename(columns={"groep": "Groep"})
    gem_data = tabel.to_dict("records")
    gem_cols = [{"name": c, "id": c} for c in tabel.columns]

    a_groep = df[df["groep"] == "Gestart, niet naar jaar 2"]
    b_groep = df[df["groep"] == "Doorgestroomd naar jaar 2"]
    mw_rijen = []
    for var, label in SCORES.items():
        a = a_groep[var].dropna()
        b = b_groep[var].dropna()
        if len(a) >= 2 and len(b) >= 2:
            _, p = stats.mannwhitneyu(a, b, alternative="two-sided")
            p = float(p)
            mw_rijen.append({"Score": label, "p-waarde": fmt_p(p), "Sig.": sig_sym(p)})
        else:
            mw_rijen.append({"Score": label, "p-waarde": "n.v.t.", "Sig.": ""})
    mw_cols = [{"name": c, "id": c} for c in ["Score", "p-waarde", "Sig."]]

    return (
        fig_totaal,
        fig_interview,
        fig_motivatie,
        fig_cv,
        gem_data,
        gem_cols,
        mw_rijen,
        mw_cols,
    )


@app.callback(
    Output("fig-verdeling", "figure"),
    Output("verdeling-caption", "children"),
    Input("cohort-dropdown", "value"),
    Input("geslacht-dropdown", "value"),
    Input("vooropleiding-dropdown", "value"),
)
def update_verdeling_tab(cohort, geslacht, vooropleiding):
    labels = [str(cohort) if cohort != "Alle" else "alle cohorten"]
    if geslacht != "Alle":
        labels.append(geslacht)
    if vooropleiding != "Alle":
        labels.append(vooropleiding)

    agg = (
        filter_data("Alle", geslacht, vooropleiding, incl_cohort=False)
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
    Output("fig-instroom", "figure"),
    Input("cohort-dropdown", "value"),
    Input("geslacht-dropdown", "value"),
    Input("vooropleiding-dropdown", "value"),
)
def update_demo_tab(cohort, geslacht, vooropleiding):
    df = filter_data(cohort, geslacht, vooropleiding)

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
    fig4.update_layout(height=460, legend=dict(orientation="h", y=-0.2), **CHART_BASE)
    fix_xas_labels(fig4)

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
    fig5.update_layout(height=420, legend=dict(orientation="h", y=-0.2), **CHART_BASE)

    agg_i = bereken_pct(
        df[df["instroom_type"].notna()]
        .groupby(["groep", "instroom_type"], observed=True)
        .size()
        .reset_index(name="n"),
        "groep",
    )
    fig6 = px.bar(
        agg_i,
        x="groep",
        y="pct",
        color="instroom_type",
        barmode="stack",
        color_discrete_map={
            "direct": "#3b82f6",
            "tussenjaar": "#f59e0b",
            "switcher": "#8b5cf6",
        },
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
)
def update_puntenwolk_tab(cohort, geslacht, vooropleiding, x_var, y_var):
    df = filter_data(cohort, geslacht, vooropleiding)
    fig = px.scatter(
        df[df["groep"].notna()],
        x=x_var,
        y=y_var,
        color="groep",
        color_discrete_map=GROEP_KLEUREN,
        category_orders={"groep": GROEP_VOLGORDE},
        labels={x_var: SCORES[x_var], y_var: SCORES[y_var], "groep": ""},
        opacity=0.55,
        height=560,
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
)
def update_vo_tab(cohort, geslacht, vooropleiding, score_var):
    df = filter_data(cohort, geslacht, vooropleiding)
    df_vo = df[df["gem_eindcijfer_vo"].notna()]
    score_label = SCORES[score_var]

    fig = px.scatter(
        df_vo[
            df_vo["groep"].isin(
                ["Gestart, niet naar jaar 2", "Doorgestroomd naar jaar 2"]
            )
        ],
        x="gem_eindcijfer_vo",
        y=score_var,
        color="groep",
        color_discrete_map=GROEP_KLEUREN,
        category_orders={"groep": GROEP_VOLGORDE},
        labels={
            "gem_eindcijfer_vo": "VO-eindcijfer",
            score_var: score_label,
            "groep": "",
        },
        opacity=0.55,
        height=500,
    )
    fig.update_traces(marker=dict(size=6))
    for groep in ["Gestart, niet naar jaar 2", "Doorgestroomd naar jaar 2"]:
        sub = df_vo[df_vo["groep"] == groep][["gem_eindcijfer_vo", score_var]].dropna()
        if len(sub) >= 2:
            m, b = np.polyfit(sub["gem_eindcijfer_vo"], sub[score_var], 1)
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
    fig.update_layout(legend=dict(orientation="h", y=-0.15), **CHART_BASE)

    cor_rijen = []
    for var, label in SCORES.items():
        subset = df_vo[df_vo[var].notna()]
        if len(subset) >= 2:
            r = float(subset["gem_eindcijfer_vo"].corr(subset[var]))
            cor_rijen.append(
                {
                    "Score": label,
                    "r (Pearson)": round(r, 3) if not np.isnan(r) else None,
                }
            )
        else:
            cor_rijen.append({"Score": label, "r (Pearson)": None})

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

    pearson_cols = [{"name": c, "id": c} for c in ["Score", "r (Pearson)"]]
    return fig, cor_rijen, pearson_cols, style_cond


if __name__ == "__main__":
    app.run(debug=True)
