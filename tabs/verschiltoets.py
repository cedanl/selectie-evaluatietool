"""Tab 'Verschiltoets': significantietoets per item."""

import io
import pandas as pd
from dash import dcc, html, dash_table, Input, Output, State
import dash_bootstrap_components as dbc

from shared import (
    UITKOMST_PERSPECTIEVEN,
    shorten_item,
    vergelijk_succes_per_item,
    VERGELIJKING_KOLOMMEN,
    toets_verschil_per_item,
    VERSCHIL_KOLOMMEN,
    DEMO_DIMENSIES,
    demografie_scores,
)

from helpers import (
    TABLE_STYLE,
    GROEPEER_OPTIES,
    df_from_store,
)


def _uitleg_verschil_uitkomst(perspectief):
    pos = perspectief["positief_label"]
    neg = perspectief["negatief_label"]
    return [
        html.P(
            f"Deze tabel vergelijkt per item twee groepen: '{pos}' versus "
            f"'{neg}'. {perspectief['beschrijving']}",
            className="text-muted small mb-1",
        ),
        html.P(
            "Mann-Whitney U met de rank-biseriale effectgrootte (-1 tot +1, "
            f"positief = groep '{pos}' scoort hoger) en een "
            "95%-betrouwbaarheidsinterval. Positief en significant (p < 0.05) "
            "betekent dat het item voorspellende waarde heeft.",
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


def maak_layout():
    return dbc.Tab(
        label="Verschiltoets",
        tab_id="tab-verschil",
        children=[
            html.Div(
                [
                    html.H5("Verschiltoets per item"),
                    html.P(
                        "Toetst per item of de scores significant verschillen. Kies doorstroom "
                        "naar jaar 2 (voorspelt het item studiesucces?) of een demografische "
                        "dimensie (maakt het item onbedoeld onderscheid?).",
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
                                    value="doorstroom",
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
                                "if": {"filter_query": '{p} contains "*"'},
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
    )


def registreer_callbacks(app):
    @app.callback(
        Output("tabel-verschil", "data"),
        Output("tabel-verschil", "columns"),
        Output("verschiltoets-uitleg", "children"),
        Input("verschil-niveau", "value"),
        Input("data-store", "data"),
        State("scores-store", "data"),
    )
    def update_verschiltoets_tab(niveau, store_data, scores_store):
        df = df_from_store(store_data)
        if df.empty or not scores_store:
            return [], [], ""
        scores_df = pd.read_json(io.StringIO(scores_store), orient="split")

        perspectief = UITKOMST_PERSPECTIEVEN.get(niveau)
        if perspectief:
            pop = df[df["groep"].isin(perspectief["populatie"])]
            scores = scores_df.merge(
                pop[["studentnummer", "groep"]].drop_duplicates(),
                on="studentnummer",
                how="inner",
            )
            scores["item_kort"] = scores["item"].apply(shorten_item)
            tabel = vergelijk_succes_per_item(scores, perspectief=perspectief)
            kolommen = VERGELIJKING_KOLOMMEN
            uitleg = _uitleg_verschil_uitkomst(perspectief)
        else:
            dim = next((d for d in DEMO_DIMENSIES if d["kolom"] == niveau), None)
            scores = demografie_scores(df, scores_df, dim) if dim else None
            if scores is None:
                return (
                    [],
                    [],
                    _uitleg_verschil_demografisch(dim["label"] if dim else ""),
                )
            tabel = toets_verschil_per_item(scores, dim["kolom"])
            kolommen = VERSCHIL_KOLOMMEN
            uitleg = _uitleg_verschil_demografisch(dim["label"])

        data = tabel[kolommen].to_dict("records") if not tabel.empty else []
        cols = [{"name": c, "id": c} for c in kolommen]
        return data, cols, uitleg
