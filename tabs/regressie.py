"""Tab 'Regressie': logistische regressie op retentie (of diploma)."""

from dash import dcc, html, dash_table, Input, Output, State
import dash_bootstrap_components as dbc

from shared import (
    perspectief_voor,
    BH_UITLEG,
    P_GECORRIGEERD,
    VOORSELECTIE_UITLEG,
    SCHEIDING_UITLEG,
)

from helpers import (
    TABLE_STYLE,
    df_from_store,
    gezamenlijk_model_uit_stores,
)


def maak_layout():
    return dbc.Tab(
        label="Regressie",
        tab_id="tab-regressie",
        children=[
            html.Div(
                [
                    html.H5("Regressie-analyse: voorspelling retentie"),
                    html.P(
                        "Welke items van de selectie voorspellen het beste of een student "
                        "in jaar 2 nog ingeschreven staat (of bij eenjarige opleidingen "
                        "het diploma haalt)?",
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
                                                "kans op de positieve uitkomst. Genormaliseerd (z-scores), dus vergelijkbaar."
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
                                            html.Li(
                                                f"{P_GECORRIGEERD} (alleen bij 'Elk item los getoetst'): "
                                                "de p-waarde na correctie voor meervoudig toetsen. "
                                                "Daar volgt Sig. deze gecorrigeerde waarde."
                                            ),
                                        ],
                                        className="small text-muted mb-1",
                                    ),
                                    html.P(
                                        "Het univariate model toetst elk item afzonderlijk: voorspelt dit "
                                        "item op zichzelf de uitkomst? Het gezamenlijke model zet alle "
                                        "items tegelijk in en laat zien welk item bovenop de andere "
                                        "nog een eigen bijdrage levert. Bij weinig studenten worden de zwakste "
                                        "items automatisch weggelaten: per item in het model zijn "
                                        "ongeveer vijf studenten met de uitkomst nodig, anders worden de "
                                        "schattingen onbetrouwbaar.",
                                        className="small text-muted mb-1",
                                    ),
                                    html.P(
                                        [
                                            html.Strong(
                                                "Correctie voor meervoudig toetsen. "
                                            ),
                                            BH_UITLEG,
                                            " Het gezamenlijke model is één toets van "
                                            "alle items samen; daar corrigeren we niet.",
                                        ],
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
                                "Voorspelt dit item op zichzelf de uitkomst? Hier "
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
_KOLOMMEN_UNIVARIAAT = [
    "Item",
    "Coefficient",
    "Odds ratio",
    "p-waarde",
    P_GECORRIGEERD,
    "Sig.",
]


def _tabel(
    rijen: list[dict], kolommen: list[str] = _KOLOMMEN
) -> tuple[list[dict], list[dict], list[dict]]:
    """Data, kolommen en de groene markering van significante rijen. Rijen
    met een gecorrigeerde p (univariaat) worden daarop beoordeeld."""
    data = [{k: r[k] for k in kolommen} for r in rijen]
    stijl = [
        {
            "if": {"row_index": i, "column_id": "Sig."},
            "backgroundColor": "#bbf7d0",
            "color": "#166534",
            "fontWeight": "600",
        }
        for i, r in enumerate(rijen)
        if r.get("_p_bh", r["_p"]) < 0.05
    ]
    return data, [{"name": c, "id": c} for c in kolommen], stijl


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
        (
            "verwijderd_scheiding",
            "Items niet meegenomen (scheiden de groepen volledig)",
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
    if model.get("verwijderd_epv"):
        delen += [
            dbc.Alert(VOORSELECTIE_UITLEG, color="warning", className="small mt-2 mb-0")
        ]
    if model.get("verwijderd_scheiding"):
        delen += [
            dbc.Alert(SCHEIDING_UITLEG, color="info", className="small mt-2 mb-0")
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

        perspectief = perspectief_voor(df)
        model = gezamenlijk_model_uit_stores(store_data, scores_store)
        if "univariaat" not in model:
            # Te weinig data om ook maar iets te schatten.
            waarschuwing = dbc.Alert(
                model["melding"], color="warning", className="small"
            )
            return (waarschuwing, [], [], [], [], [], [])

        uni_data, uni_cols, uni_stijl = _tabel(
            model["univariaat"], _KOLOMMEN_UNIVARIAAT
        )
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
