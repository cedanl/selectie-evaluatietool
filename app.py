"""
Evaluatietool: selectie & studiesucces dashboard

Draai met: uv run python app.py
Demodata aanmaken: uv run python scripts/maak_data.py

De layout en callbacks zijn opgesplitst per verantwoordelijkheid:
uploads.py (upload-flow en sidebar), tabs/*.py (een module per tabblad) en
helpers.py (gedeelde app-helpers). Elke module levert een maak_layout()- en/of
registreer_callbacks(app)-functie, net als config_wizard.py.
"""

from urllib.parse import parse_qs, urlsplit

import dash
from dash import dcc, html, Input, Output
import dash_bootstrap_components as dbc

from config_wizard import registreer_callbacks as registreer_wizard
from helpers import DEMO_DATASETS, _laad_demodata
from uploads import UPLOAD_OVERLAY, SIDEBAR
from uploads import registreer_callbacks as registreer_uploads
from tabs import (
    intro,
    bevindingen,
    scores,
    demografie,
    verschiltoets,
    correlatie,
    regressie,
)

app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    title="Evaluatietool Selectie",
    suppress_callback_exceptions=True,
)

registreer_wizard(app)
registreer_uploads(app)
for tab in (bevindingen, scores, demografie, verschiltoets, correlatie, regressie):
    tab.registreer_callbacks(app)

app.layout = html.Div(
    [
        dcc.Location(id="url", refresh=False),
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
                                intro.maak_layout(),
                                bevindingen.maak_layout(),
                                scores.maak_layout(),
                                demografie.maak_layout(),
                                verschiltoets.maak_layout(),
                                correlatie.maak_layout(),
                                regressie.maak_layout(),
                            ],
                            id="main-tabs",
                            active_tab="tab-intro",
                        ),
                    ],
                    className="main-wrapper",
                ),
            ],
            className="app-shell",
        ),
    ]
)


@app.callback(
    Output("data-store", "data", allow_duplicate=True),
    Output("scores-store", "data", allow_duplicate=True),
    Output("main-tabs", "active_tab"),
    Input("url", "search"),
    prevent_initial_call="initial_duplicate",
)
def laad_via_url(search):
    """Maakt het dashboard embedbaar per tab. Een URL als
    ?demo=leiden&tab=correlatie laadt de demodata en opent meteen het
    gevraagde tabblad, zodat een iframe direct die tab toont."""
    if not search:
        return dash.no_update, dash.no_update, dash.no_update

    params = parse_qs(urlsplit(search).query)
    demo = (params.get("demo") or [None])[0]
    tab = (params.get("tab") or [None])[0]

    data_out, scores_out = dash.no_update, dash.no_update
    if demo:
        match = next((d["value"] for d in DEMO_DATASETS if demo in d["value"]), None)
        if match:
            data_out, scores_out = _laad_demodata(match)

    tab_out = f"tab-{tab}" if tab else dash.no_update
    return data_out, scores_out, tab_out


if __name__ == "__main__":
    app.run(debug=True)
