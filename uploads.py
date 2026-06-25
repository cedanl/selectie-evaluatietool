"""Upload-overlay, sidebar en de bijbehorende callbacks."""

import io
import json

import pandas as pd

import dash
from dash import dcc, html, Input, Output, State, ctx
import dash_bootstrap_components as dbc

from transformatie import (
    lees_config,
    parse_csv_or_excel,
    parse_selectiedata,
    transformeer_naar_lang,
    valideer_config,
)
from cho_transform import ontbrekende_cho_kolommen, transformeer_cho
from config_wizard import maak_wizard_layout
from rapport import genereer_rapport
from shared import PERSPECTIEF_DOORSTROOM, GROEP_INGESCHREVEN, GROEP_SUCCES
from helpers import (
    DEMO_DATASETS,
    df_from_store,
    koppel_data,
    _laad_demodata,
)


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
                    "Deze tool laat zien of je selectieprocedure studiesucces "
                    "voorspelt: doen kandidaten die hoog scoorden bij de selectie "
                    "het later ook beter in hun studie? Je hebt geen statistiek "
                    "nodig. Je laadt je data en het dashboard rekent de "
                    "vergelijkingen uit en legt in gewone taal uit wat eruit komt.",
                    className="text-muted small mb-2 text-start",
                ),
                html.P(
                    "Upload de drie bestanden hieronder om te beginnen, of probeer "
                    "onderaan eerst een voorbeeldset.",
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


SIDEBAR = html.Div(
    [
        html.Img(src="/assets/nko-logo.svg", className="sidebar-logo"),
        html.P("Kandidaten per cohort", className="sidebar-label"),
        html.Div(id="cohort-stats"),
        html.Hr(className="mt-3 mb-2"),
        html.P("Van aanmelding tot doorstroom", className="sidebar-label"),
        html.Div(id="funnel-stats"),
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


def registreer_callbacks(app):
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
                cfg_status = dbc.Alert(
                    f"Fout: {e}", color="danger", className="small py-1"
                )
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
        Output("config-store", "data"),
        Output("raw-selectie-store", "data"),
        Output("raw-cho-store", "data"),
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
            return None, None, None, None, None

        if trigger == "btn-demodata":
            return _laad_demodata(demo_dataset)

        has_config = cfg_contents or wiz_config
        if (
            trigger == "btn-open-dashboard"
            and sel_contents
            and has_config
            and cho_contents
        ):
            if cfg_contents:
                config = lees_config(cfg_contents)
            else:
                config = json.loads(wiz_config)
            scores_df = transformeer_naar_lang(
                parse_selectiedata(sel_contents, config), config
            )
            cho_fn_safe = cho_fn or "data.csv"
            cho_df = transformeer_cho(parse_csv_or_excel(cho_contents, cho_fn_safe))
            joined = koppel_data(cho_df, scores_df)
            return (
                joined.to_json(orient="split", date_format="iso"),
                scores_df.to_json(orient="split", date_format="iso"),
                json.dumps(config),
                sel_contents,
                json.dumps({"contents": cho_contents, "filename": cho_fn_safe}),
            )

        return (dash.no_update,) * 5

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

    @app.callback(
        Output("funnel-stats", "children"),
        Input("data-store", "data"),
    )
    def update_funnel(store_data):
        """Korte trechter als context: hoeveel kandidaten begonnen er en hoeveel
        stroomden door. Vervangt de losse 'Niet gestart'-groep, die uit de
        analyses is gehaald omdat hij voor gebruikers weinig zei."""
        df = df_from_store(store_data)
        if df.empty:
            return ""
        n_kandidaten = len(df)
        n_ingeschreven = int(df["groep"].isin(GROEP_INGESCHREVEN).sum())
        n_doorgestroomd = int(df["groep"].isin(GROEP_SUCCES).sum())

        def stap(label, n, deel_van):
            pct = f" ({n / deel_van * 100:.0f}%)" if deel_van else ""
            return html.Div(
                [
                    html.Span(label, className="text-muted small"),
                    html.Span(f"{n}{pct}", className="fw-bold small"),
                ],
                className="d-flex justify-content-between",
            )

        return html.Div(
            [
                stap("Kandidaten", n_kandidaten, None),
                stap("Ingeschreven", n_ingeschreven, n_kandidaten),
                stap("Doorgestroomd", n_doorgestroomd, n_ingeschreven),
            ]
        )

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
        perspectief = PERSPECTIEF_DOORSTROOM
        pdf_bytes = genereer_rapport(df, scores_df, perspectief=perspectief)
        opleiding = ""
        if "opleiding" in df.columns and df["opleiding"].notna().any():
            opleiding = str(df["opleiding"].dropna().iloc[0]).replace(" ", "_")
        filename = (
            f"evaluatierapport_{opleiding}.pdf" if opleiding else "evaluatierapport.pdf"
        )
        return dcc.send_bytes(pdf_bytes, filename)
