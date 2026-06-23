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


def _uitleg_details(samenvatting, inhoud):
    """Plain-language uitleg met een inklapbaar 'Hoe wordt dit berekend?'-blok
    eronder, zodat de statistische details beschikbaar zijn zonder de gewone
    gebruiker te overladen. Eenzelfde patroon over de tabbladen heen."""
    return html.Div(
        [
            html.P(samenvatting, className="text-muted small mb-1"),
            html.Details(
                [
                    html.Summary(
                        "Hoe wordt dit berekend?",
                        className="small text-muted",
                        style={"cursor": "pointer"},
                    ),
                    html.Div(inhoud, className="small text-muted mt-1"),
                ]
            ),
        ],
        className="mb-2",
    )


def _uitleg_verschil_uitkomst(perspectief):
    pos = perspectief["positief_label"]
    neg = perspectief["negatief_label"]
    return _uitleg_details(
        f"Per onderdeel vergelijken we of de groep '{pos}' hoger scoorde dan "
        f"'{neg}'. Een sterretje betekent dat het verschil waarschijnlijk niet "
        "op toeval berust; dan heeft het onderdeel voorspellende waarde. De "
        "kolom Effectgrootte zegt hoe groot het verschil is (niet hoeveel keer "
        "groter de kans is, dat staat op het tabblad Regressie).",
        f"We toetsen het verschil met een verdelingsvrije toets (Mann-Whitney U), "
        "passend bij de ordinale, vaak scheve schalen van selectie-items. De "
        "Effectgrootte is de rank-biseriale correlatie (-1 tot +1; positief = "
        f"'{pos}' scoort hoger), met een 95%-betrouwbaarheidsinterval. "
        "Vuistregels: onder 0.10 verwaarloosbaar, 0.10-0.30 zwak, 0.30-0.50 "
        "matig, daarboven sterk.",
    )


def _uitleg_verschil_demografisch(label):
    laag = label.lower()
    return _uitleg_details(
        f"Per onderdeel kijken we of de scores verschillen tussen {laag}-groepen. "
        "Een sterretje betekent een verschil dat waarschijnlijk niet op toeval "
        "berust; dat kan wijzen op onbedoelde vertekening. Staat er 'vergelijkbaar', "
        f"dan is er geen aangetoond verschil. De {laag} komt uit 1CHO en is alleen "
        "bekend voor ingeschreven studenten, dus we vergelijken binnen die groep.",
        "We toetsen het verschil met een verdelingsvrije toets (Kruskal-Wallis, "
        "werkt voor twee of meer groepen). De Effectgrootte is epsilon-kwadraat "
        "(0-1): onder 0.01 verwaarloosbaar, 0.01-0.06 zwak, 0.06-0.14 matig, "
        "daarboven sterk.",
    )


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
