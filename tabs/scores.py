"""Tab 'Selectiescores': boxplots per item per groep."""

import plotly.express as px
import plotly.graph_objects as go
from dash import dcc, html, dash_table, Input, Output, State
import dash_bootstrap_components as dbc

from shared import (
    CHART_BASE,
    shorten_item,
    schaal_grenzen,
    bucket_per_item,
    meta_per_item,
)

from helpers import (
    scores_df_from_store,
    TABLE_STYLE,
    GROEPEER_OPTIES_SCORES,
    df_from_store,
    _scores_per_groep,
    _aantallen_per_groep,
    _groep_tabel_stijl,
    _sorteer_bereik,
)


def maak_layout():
    return dbc.Tab(
        label="Selectiescores",
        tab_id="tab-scores",
        children=[
            html.Div(
                [
                    html.H5("Selectiescores per groep"),
                    html.P(
                        "Vergelijk de selectiescores per item tussen groepen. Kies of je "
                        "groepeert op doorstroom naar jaar 2, of op een achtergrondkenmerk "
                        "(geslacht, vooropleiding). Scoren de groepen verschillend, dan "
                        "maakt dat item onderscheid.",
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
                                    options=GROEPEER_OPTIES_SCORES,
                                    value="doorstroom",
                                    clearable=False,
                                ),
                            ],
                            width=4,
                        ),
                        className="mb-3",
                    ),
                    html.H6("Aantal studenten per groep"),
                    html.P(
                        "Bij geslacht en vooropleiding tellen alleen ingeschreven studenten "
                        "mee (uit 1CHO). Bij 'Gestart met de opleiding' tellen alle kandidaten mee.",
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
    )


def registreer_callbacks(app):
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

        scores_df = scores_df_from_store(scores_store)
        meta = scores_df[["instrument", "item", "criterium"]].drop_duplicates().copy()
        meta["bereik"] = meta["item"].map(bucket_per_item(scores_df))

        sel = {
            "instrument": instrument_val,
            "criterium": criterium_val,
            "item": item_val,
            "bereik": bereik_val,
        }

        # Bij meer dan 8 items en alle filters op "Alle": selecteer het eerste
        # instrument zodat de boxplot leesbaar start.
        n_items = meta["item"].nunique()
        alles_alle = all(v in (None, "Alle") for v in sel.values())
        if n_items > 8 and alles_alle:
            instrumenten = sorted(meta["instrument"].unique())
            if instrumenten:
                sel["instrument"] = instrumenten[0]

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

        scores_df = scores_df_from_store(scores_store)
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
