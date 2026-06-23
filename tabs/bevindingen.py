"""Tab 'Wat valt op': automatisch overzicht van bevindingen."""

import io
import pandas as pd
import dash
from dash import dcc, html, Input, Output, State
import dash_bootstrap_components as dbc

from shared import (
    PERSPECTIEF_DOORSTROOM,
    shorten_item,
    vergelijk_succes_per_item,
    toets_verschil_per_item,
    genereer_bevindingen,
    DEMO_DIMENSIES,
    demografie_scores,
    bereken_univariaat,
    chi2_per_dimensie,
)

from helpers import (
    df_from_store,
    _bereken_model_stats,
)


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


def maak_layout():
    return dbc.Tab(
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
    )


def registreer_callbacks(app):
    @app.callback(
        Output("bevindingen-inhoud", "children"),
        Input("main-tabs", "active_tab"),
        Input("data-store", "data"),
        State("scores-store", "data"),
    )
    def update_bevindingen(active_tab, store_data, scores_store):
        if active_tab != "tab-bevindingen":
            return dash.no_update
        df = df_from_store(store_data)
        if df.empty or not scores_store:
            return html.P(
                "Laad eerst data om de bevindingen te zien.", className="text-muted"
            )

        scores_df = pd.read_json(io.StringIO(scores_store), orient="split")

        perspectief = PERSPECTIEF_DOORSTROOM
        pop = df[df["groep"].isin(perspectief["populatie"])]
        n_pos = int(pop["groep"].isin(perspectief["positief_groepen"]).sum())
        n_neg = int(len(pop) - n_pos)
        groepsgroottes = {
            "n_totaal": len(df),
            "n_populatie": len(pop),
            "n_positief": n_pos,
            "n_negatief": n_neg,
        }
        scores = scores_df.merge(
            pop[["studentnummer", "groep"]].drop_duplicates(),
            on="studentnummer",
            how="inner",
        )
        scores["item_kort"] = scores["item"].apply(shorten_item)
        succes_tabel = vergelijk_succes_per_item(scores, perspectief=perspectief)
        uni_data = bereken_univariaat(df, scores_df, perspectief)
        model_stats = _bereken_model_stats(df, scores_df, perspectief)
        demo_verdelingen = chi2_per_dimensie(df, perspectief)

        demo_tabellen = {}
        for dim in DEMO_DIMENSIES:
            demo_scores = demografie_scores(df, scores_df, dim)
            if demo_scores is not None:
                demo_tabellen[dim["label"]] = toets_verschil_per_item(
                    demo_scores, dim["kolom"]
                )

        corr_matrix = None
        item_pivot = scores_df.pivot_table(
            index="studentnummer", columns="item", values="score", aggfunc="mean"
        )
        if not item_pivot.empty:
            item_pivot.columns = [shorten_item(c) for c in item_pivot.columns]
            corr_matrix = item_pivot.corr().round(3)

        bevindingen = genereer_bevindingen(
            succes_tabel,
            demo_tabellen,
            perspectief=perspectief,
            correlatie_matrix=corr_matrix,
            univariaat_data=uni_data,
            model_stats=model_stats,
            groepsgroottes=groepsgroottes,
            demografie_verdeling=demo_verdelingen,
        )

        secties = []
        if bevindingen["samenvatting"]:
            secties.append(
                html.P(" ".join(bevindingen["samenvatting"]), className="fw-bold")
            )
        secties.append(
            _bevindingen_lijst(
                "Verschiltoets",
                bevindingen["validiteit"],
                "Geen opvallende voorspellers gevonden in de cijfers.",
            )
        )
        if bevindingen.get("regressie"):
            secties.append(
                _bevindingen_lijst(
                    "Univariate regressie",
                    bevindingen["regressie"],
                    "Geen univariate regressieresultaten beschikbaar.",
                )
            )
        if bevindingen.get("model"):
            secties.append(
                _bevindingen_lijst(
                    "Gezamenlijk model",
                    bevindingen["model"],
                    "",
                )
            )
        if bevindingen.get("demografie"):
            secties.append(
                _bevindingen_lijst(
                    "Demografie en uitkomst",
                    bevindingen["demografie"],
                    "",
                )
            )

        secties.append(html.Hr())
        secties.append(html.H5("Samenhang tussen items", className="mt-3 mb-2"))
        secties.append(
            _bevindingen_lijst(
                "Correlatie",
                bevindingen["correlatie"],
                "Onvoldoende items voor een correlatieanalyse.",
            )
        )

        secties.append(html.Hr())
        secties.append(html.H5("Verschillen tussen groepen", className="mt-3 mb-2"))
        secties.append(
            _bevindingen_lijst(
                "Eerlijkheid (geslacht, vooropleiding)",
                bevindingen["fairness"],
                "Geen demografische gegevens beschikbaar om te vergelijken.",
            )
        )
        return secties
