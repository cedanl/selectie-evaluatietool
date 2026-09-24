"""Tab 'Regressie': logistische regressie op studiesucces."""

from dash import dcc, html, dash_table, Input, Output, State
import dash_bootstrap_components as dbc

from shared import PERSPECTIEF_DOORSTROOM, bereken_gezamenlijk_model

from helpers import (
    scores_df_from_store,
    TABLE_STYLE,
    df_from_store,
)


def maak_layout():
    return dbc.Tab(
        label="Regressie",
        tab_id="tab-regressie",
        children=[
            html.Div(
                [
                    html.H5("Regressie-analyse: voorspelling studiesucces"),
                    html.P(
                        "Welke items van de selectie voorspellen het beste of een student "
                        "de opleiding succesvol vervolgt (doorstroom naar jaar 2, of een diploma "
                        "bij eenjarige opleidingen)?",
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
                                        "De tabellen tonen per item vier waarden:",
                                        className="small text-muted mb-1",
                                    ),
                                    html.Ul(
                                        [
                                            html.Li(
                                                "Coefficient: richting en sterkte. Positief = hogere score, hogere "
                                                "kans op doorstroom. Genormaliseerd (z-scores), dus vergelijkbaar."
                                            ),
                                            html.Li(
                                                "Odds ratio: een kansverhouding per standaarddeviatie hogere score. "
                                                "OR 1.5 = 50% meer kans, OR < 1 = minder kans. Dit is iets anders dan "
                                                "de Effectgrootte op het tabblad Verschiltoets: die zegt hoe groot het "
                                                "verschil is, niet hoeveel keer groter de kans wordt."
                                            ),
                                            html.Li(
                                                "p-waarde: kans op dit resultaat als het item geen effect heeft. "
                                                "p < 0.05 is significant."
                                            ),
                                            html.Li(
                                                "Sig.: * = p < 0.05, ** < 0.01, *** < 0.001, ns = niet significant."
                                            ),
                                        ],
                                        className="small text-muted mb-1",
                                    ),
                                    html.P(
                                        "Het univariate model toetst elk item afzonderlijk: voorspelt dit "
                                        "item op zichzelf studiesucces? Het gezamenlijke model zet alle "
                                        "items tegelijk in en laat zien welk item bovenop de andere "
                                        "nog een eigen bijdrage levert. Bij weinig studenten worden de zwakste "
                                        "items automatisch weggelaten: per item in het model zijn "
                                        "ongeveer vijf studenten met de uitkomst nodig, anders worden de "
                                        "schattingen onbetrouwbaar.",
                                        className="small text-muted mb-0",
                                    ),
                                ],
                                className="mt-1 mb-2",
                            ),
                        ],
                        className="mb-3",
                    ),
                    dcc.Loading(
                        [
                            html.Div(
                                id="regressie-samenvatting",
                                className="mb-3",
                            ),
                            html.H6("Elk item los getoetst"),
                            html.P(
                                "Voorspelt dit item op zichzelf studiesucces? Hier "
                                "wordt elk item afzonderlijk bekeken; alle items "
                                "blijven staan, er valt niets weg.",
                                className="text-muted small",
                            ),
                            dash_table.DataTable(
                                id="tabel-univariaat",
                                style_table={"overflowX": "auto"},
                                **TABLE_STYLE,
                            ),
                            html.H6(
                                "Gezamenlijk model",
                                className="mt-4",
                            ),
                            html.P(
                                "Alle items tegelijk in een model. Een item kan hier "
                                "niet-significant worden als het sterk overlapt met een ander item.",
                                className="text-muted small",
                            ),
                            dash_table.DataTable(
                                id="tabel-regressie",
                                style_table={"overflowX": "auto"},
                                **TABLE_STYLE,
                            ),
                        ],
                        type="default",
                    ),
                ],
                className="tab-body",
            ),
        ],
    )


_KOLOMMEN = ["Item", "Coefficient", "Odds ratio", "p-waarde", "Sig."]


def _tabel(rijen: list[dict]) -> tuple[list[dict], list[dict], list[dict]]:
    """Data, kolommen en de groene markering van significante rijen."""
    data = [{k: r[k] for k in _KOLOMMEN} for r in rijen]
    stijl = [
        {
            "if": {"row_index": i, "column_id": "Sig."},
            "backgroundColor": "#bbf7d0",
            "color": "#166534",
            "fontWeight": "600",
        }
        for i, r in enumerate(rijen)
        if r["_p"] < 0.05
    ]
    return data, [{"name": c, "id": c} for c in _KOLOMMEN], stijl


def _samenvatting(model: dict, perspectief: dict):
    pos_label = perspectief["positief_label"].lower()
    neg_label = perspectief["negatief_label"].lower()
    delen = [
        html.Span(
            f"n = {model['n']} ({pos_label}: {model['n_positief']}, "
            f"{neg_label}: {model['n_negatief']})",
            className="small text-muted me-3",
        ),
        html.Span(
            f"Verklarende kracht (pseudo R²) = {model['pseudo_r2']}",
            className="small fw-bold",
        ),
    ]
    redenen = [
        ("verwijderd_nan", "Items niet meegenomen (>30% ontbrekend)"),
        ("verwijderd_collineair", "Items niet meegenomen (te veel overlap)"),
        (
            "verwijderd_epv",
            "Items niet meegenomen (te weinig studenten met de uitkomst; "
            f"de {len(model.get('coefficienten', []))} sterkste behouden)",
        ),
    ]
    for sleutel, tekst in redenen:
        if model.get(sleutel):
            delen += [
                html.Br(),
                html.Span(
                    f"{tekst}: {', '.join(model[sleutel])}",
                    className="small text-muted",
                ),
            ]
    return html.Div(delen)


def registreer_callbacks(app):
    @app.callback(
        Output("regressie-samenvatting", "children"),
        Output("tabel-univariaat", "data"),
        Output("tabel-univariaat", "columns"),
        Output("tabel-univariaat", "style_data_conditional"),
        Output("tabel-regressie", "data"),
        Output("tabel-regressie", "columns"),
        Output("tabel-regressie", "style_data_conditional"),
        Input("data-store", "data"),
        State("scores-store", "data"),
    )
    def update_regressie_tab(store_data, scores_store):
        df = df_from_store(store_data)
        if df.empty or not scores_store:
            return ("", [], [], [], [], [], [])

        perspectief = PERSPECTIEF_DOORSTROOM
        model = bereken_gezamenlijk_model(
            df, scores_df_from_store(scores_store), perspectief
        )
        if "univariaat" not in model:
            # Te weinig data om ook maar iets te schatten.
            waarschuwing = dbc.Alert(
                model["melding"], color="warning", className="small"
            )
            return (waarschuwing, [], [], [], [], [], [])

        uni_data, uni_cols, uni_stijl = _tabel(model["univariaat"])
        if model["status"] != "ok":
            waarschuwing = dbc.Alert(
                model["melding"], color="warning", className="small"
            )
            return (waarschuwing, uni_data, uni_cols, uni_stijl, [], [], [])

        reg_data, reg_cols, reg_stijl = _tabel(model["coefficienten"])
        return (
            _samenvatting(model, perspectief),
            uni_data,
            uni_cols,
            uni_stijl,
            reg_data,
            reg_cols,
            reg_stijl,
        )
