"""Tab 'Correlatie': correlatiematrix tussen items."""

import io
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from dash import dcc, html, Input, Output, State
import dash_bootstrap_components as dbc

from shared import (
    CHART_BASE,
    shorten_item,
)

from helpers import (
    df_from_store,
)


def maak_layout():
    return dbc.Tab(
        label="Correlatie",
        tab_id="tab-correlatie",
        children=[
            html.Div(
                [
                    html.H5("Correlatiematrix tussen items"),
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
                ],
                className="tab-body",
            ),
        ],
    )


def registreer_callbacks(app):
    @app.callback(
        Output("samenhang-instrument", "options"),
        Output("samenhang-instrument", "value"),
        Output("samenhang-criterium", "options"),
        Output("samenhang-criterium", "value"),
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
        if scores_store:
            scores_df = pd.read_json(io.StringIO(scores_store), orient="split")
            for inst in sorted(scores_df["instrument"].unique()):
                instrument_opties.append({"label": inst, "value": inst})
            criteria = scores_df["criterium"].dropna().unique()
            criteria = [c for c in sorted(criteria) if c.strip()]
            for crit in criteria:
                criterium_opties.append({"label": crit, "value": crit})

        return (
            instrument_opties,
            "Alle",
            criterium_opties,
            "Alle",
            subtitle,
        )

    @app.callback(
        Output("fig-correlatie", "figure"),
        Input("samenhang-instrument", "value"),
        Input("samenhang-criterium", "value"),
        State("scores-store", "data"),
    )
    def update_correlatie_tab(sh_instrument, sh_criterium, scores_store):
        leeg = go.Figure().update_layout(**CHART_BASE)
        if not scores_store:
            return leeg

        scores_df = pd.read_json(io.StringIO(scores_store), orient="split")
        scores = scores_df

        if sh_instrument and sh_instrument != "Alle":
            scores = scores[scores["instrument"] == sh_instrument]
        if sh_criterium and sh_criterium != "Alle":
            scores = scores[scores["criterium"] == sh_criterium]

        if scores.empty:
            return leeg

        meta = scores.drop_duplicates(subset=["item"])[["item", "instrument"]].copy()
        label_map = {
            row["item"]: f"{row['instrument']} - {shorten_item(row['item'])}"
            for _, row in meta.iterrows()
        }

        item_pivot = scores.pivot_table(
            index="studentnummer", columns="item", values="score", aggfunc="mean"
        )
        item_pivot.columns = [
            label_map.get(c, shorten_item(c)) for c in item_pivot.columns
        ]
        score_cols = list(item_pivot.columns)
        corr_matrix = item_pivot[score_cols].corr().round(3)

        # De matrix is symmetrisch, dus de bovenste helft is een spiegeling van de
        # onderste. We tonen alleen de onderste driehoek (inclusief diagonaal),
        # zodat er geen verwarrende dubbelingen staan.
        boven = np.triu(np.ones(corr_matrix.shape, dtype=bool), k=1)
        z = corr_matrix.to_numpy(dtype=float).copy()
        z[boven] = np.nan
        tekst = [
            ["" if boven[i, j] else f"{corr_matrix.iat[i, j]:.2f}" for j in range(z.shape[1])]
            for i in range(z.shape[0])
        ]

        fig = go.Figure(
            data=go.Heatmap(
                z=z,
                x=corr_matrix.columns,
                y=corr_matrix.index,
                colorscale="RdBu_r",
                zmid=0,
                zmin=-1,
                zmax=1,
                text=tekst,
                texttemplate="%{text}",
                textfont={"size": 10},
                hoverongaps=False,
            )
        )
        fig.update_layout(
            height=500,
            xaxis_tickangle=-30,
            **CHART_BASE,
            margin=dict(t=20, b=10),
        )
        return fig
