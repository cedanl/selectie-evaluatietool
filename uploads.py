"""Upload-overlay, sidebar en de bijbehorende callbacks."""

import json
import logging

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
from cho_transform import (
    ontbrekende_cho_kolommen,
    ontbrekende_demografie_kolommen,
)
from config_wizard import maak_wizard_layout
from tabs.intro import maak_upload_intro
from rapport import genereer_rapport
from shared import perspectief_voor, GROEP_INGESCHREVEN, GROEP_SUCCES
from helpers import (
    scores_df_from_store,
    DEMO_DATASETS,
    df_from_store,
    bereid_cho_voor,
    bouw_data_stores,
    _laad_demodata,
)


log = logging.getLogger(__name__)


def actieve_config_bron(trigger, bron, cfg, wiz_config) -> str | None:
    """Welke config geldt: het geüploade bestand ('upload') of de wizard
    ('wizard')? De laatst aangeleverde wint. Zonder expliciete keuze de enige
    die er is. Validatie en laden gebruiken allebei deze bron, zodat het
    dashboard nooit opent met een andere config dan die gevalideerd is."""
    if trigger == "upload-config" and cfg:
        return "upload"
    if trigger == "wiz-config-store" and wiz_config:
        return "wizard"
    if bron == "upload" and cfg:
        return "upload"
    if bron == "wizard" and wiz_config:
        return "wizard"
    if cfg:
        return "upload"
    if wiz_config:
        return "wizard"
    return None


def lees_actieve_config(bron, cfg, wiz_config) -> dict | None:
    if bron == "upload":
        return lees_config(cfg)
    if bron == "wizard":
        return json.loads(wiz_config)
    return None


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
                    # Geen limiet: een instellingsbrede 1CHO-extractie is al
                    # snel >50 MB, en dcc.Upload negeert te grote bestanden
                    # zonder enige melding.
                    max_size=-1,
                ),
                html.Div(id=status_id, className="mt-2"),
            ]
        ),
        className="mb-3 text-start",
    )


_INLEIDING_KOLOM = dbc.Col(
    [
        html.Img(
            src="/assets/nko-logo.svg",
            style={"height": "48px", "marginBottom": "20px"},
        ),
        html.H3("Selectie Evaluatietool", className="mb-2"),
        html.P(
            "Deze tool laat zien of je selectieprocedure studiesucces "
            "voorspelt: doen kandidaten die hoog scoorden bij de selectie "
            "het later ook beter in hun studie? Je hebt geen statistiek "
            "nodig. Je laadt je data en het dashboard rekent de "
            "vergelijkingen uit en legt in gewone taal uit wat eruit komt.",
            className="text-muted small mb-3",
        ),
        maak_upload_intro(),
    ],
    md=6,
    className="text-start",
)

_UPLOAD_KOLOM = dbc.Col(
    html.Div(
        [
            html.H5("Aan de slag", className="mb-1"),
            html.P(
                "Upload de drie bestanden om te beginnen, of probeer onderaan "
                "een voorbeeldset.",
                className="text-muted small mb-3",
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
                "Studiesuccesdata per kandidaat. Dit is de output van de "
                "1cijferho-pipeline (BSN al gekoppeld aan studentnummer), "
                "niet het ruwe DUO-bestand.",
                "upload-1cho",
                "cho-status",
                ".csv,.xlsx,.xls",
            ),
            # Verschijnt alleen als het 1CHO-bestand meerdere opleidingen bevat
            # (een instellingsbrede extractie): dan moet duidelijk zijn welke
            # inschrijvingen bij deze selectie horen.
            html.Div(
                [
                    html.Label(
                        "Welke opleiding in het 1CHO-bestand hoort bij deze selectie?",
                        htmlFor="cho-opleiding-picker",
                        className="small fw-bold mb-1",
                    ),
                    dcc.Dropdown(id="cho-opleiding-picker", clearable=False),
                ],
                id="cho-opleiding-kiezer",
                className="mb-3",
                style={"display": "none"},
            ),
            dcc.Loading(
                [
                    # data-store/scores-store staan hier als kind van de Loading
                    # (in plaats van boven in app.py) zodat target_components ze
                    # als afstammeling kan herkennen: dcc.Loading laat de
                    # spinner alleen zien voor callback-outputs die ergens
                    # onder deze wrapper in de layout-boom hangen.
                    dcc.Store(id="data-store", storage_type="memory"),
                    dcc.Store(id="config-bron", storage_type="memory"),
                    dcc.Store(id="scores-store", storage_type="memory"),
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
                target_components={"data-store": "data", "scores-store": "data"},
                custom_spinner=html.Div(
                    [
                        dbc.Spinner(
                            size="sm", color="primary", spinner_class_name="me-2"
                        ),
                        "Data wordt ingelezen, dit kan even duren...",
                    ],
                    className=(
                        "d-flex align-items-center justify-content-center "
                        "small text-muted py-3"
                    ),
                ),
            ),
        ],
        className="upload-actie text-start",
    ),
    md=6,
)

UPLOAD_OVERLAY = html.Div(
    id="upload-overlay",
    children=[
        html.Div(
            dbc.Row(
                [_INLEIDING_KOLOM, _UPLOAD_KOLOM],
                className="g-4 align-items-start",
            ),
            className="upload-shell",
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
        html.P("Van aanmelding tot studiesucces", className="sidebar-label"),
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
                html.Div(id="rapport-fout"),
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
        Output("cho-opleiding-picker", "options"),
        Output("cho-opleiding-picker", "value"),
        Output("cho-opleiding-kiezer", "style"),
        Output("config-bron", "data"),
        Input("upload-selectiedata", "contents"),
        Input("upload-config", "contents"),
        Input("upload-1cho", "contents"),
        Input("wiz-config-store", "data"),
        Input("cho-opleiding-picker", "value"),
        State("upload-selectiedata", "filename"),
        State("upload-config", "filename"),
        State("upload-1cho", "filename"),
        State("config-bron", "data"),
        prevent_initial_call=True,
    )
    def valideer_uploads(
        sel,
        cfg,
        cho,
        wiz_config,
        cho_opleiding,
        sel_fn,
        cfg_fn,
        cho_fn,
        bron,
    ):
        trigger = ctx.triggered_id
        no = dash.no_update
        bron = actieve_config_bron(trigger, bron, cfg, wiz_config)

        sel_status = no
        cfg_status = no
        validatie = no
        cho_status = no
        btn_disabled = True
        config = None
        kiezer_opties = no
        kiezer_waarde = no
        kiezer_stijl = no

        def resultaat():
            return (
                sel_status,
                cfg_status,
                validatie,
                cho_status,
                btn_disabled,
                kiezer_opties,
                kiezer_waarde,
                kiezer_stijl,
                bron,
            )

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
                validatie = ""
                return resultaat()

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

        if sel and bron:
            try:
                if config is None:
                    config = lees_actieve_config(bron, cfg, wiz_config)
                checks = valideer_config(config, sel)
                badges = [
                    dbc.Alert(
                        "Config: "
                        + (
                            f"geüpload bestand ({cfg_fn})"
                            if bron == "upload"
                            else "gegenereerd met de wizard"
                        ),
                        color="secondary",
                        className="small py-1 mb-1",
                    )
                ]
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
                    if not c["ok"]:
                        color = "danger"
                    elif c.get("waarschuwing"):
                        color = "warning"
                    else:
                        color = "success"
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
                            [
                                f"Ontbrekende kolommen in 1CHO: {', '.join(missing)}. ",
                                "Dit lijkt niet op de output van de "
                                "1cijferho-pipeline; controleer of je het "
                                "bewerkte 1CHO-bestand uploadt en niet het "
                                "ruwe DUO-bestand.",
                            ],
                            color="danger",
                            className="small py-1",
                        )
                        return resultaat()

                    demo_missing = ontbrekende_demografie_kolommen(cho_ruw)
                    if demo_missing:
                        cho_status = dbc.Alert(
                            "Ontbrekende achtergrondkolommen in 1CHO (nodig voor de "
                            f"demografie- en eerlijkheidsanalyse): {', '.join(demo_missing)}",
                            color="danger",
                            className="small py-1",
                        )
                        return resultaat()

                    # Bij een wissel in het keuzemenu de keuze van de gebruiker
                    # volgen; bij een nieuwe upload opnieuw matchen.
                    gebruiker_keuze = (
                        cho_opleiding if trigger == "cho-opleiding-picker" else None
                    )
                    cho = bereid_cho_voor(cho_ruw, config, scores_df, gebruiker_keuze)
                    cho_df = cho["cho_df"]
                    if len(cho["opleidingen"]) > 1:
                        kiezer_opties = [
                            {"label": o, "value": o} for o in cho["opleidingen"]
                        ]
                        kiezer_waarde = cho["gekozen"]
                        kiezer_stijl = {"display": "block"}
                    else:
                        kiezer_opties, kiezer_waarde = [], None
                        kiezer_stijl = {"display": "none"}
                    if trigger == "cho-opleiding-picker":
                        kiezer_opties = kiezer_waarde = no

                    if cho["keuze_nodig"]:
                        cho_status = dbc.Alert(
                            f"Het 1CHO-bestand bevat {len(cho['opleidingen'])} "
                            "opleidingen. Kies hieronder welke bij deze selectie "
                            "hoort; anders tellen inschrijvingen bij andere "
                            "opleidingen mee als 'gestart'.",
                            color="warning",
                            className="small py-1",
                        )
                        return resultaat()

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
                        return resultaat()

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
                    info = cho["info"]
                    filter_regels = []
                    if len(cho["opleidingen"]) > 1:
                        filter_regels.append(
                            f"alleen opleiding '{cho['gekozen']}' gebruikt "
                            f"({info['n_andere_opleiding']} inschrijvingen bij andere "
                            "opleidingen genegeerd)"
                        )
                    if info["n_eerder_cohort"]:
                        filter_regels.append(
                            f"{info['n_eerder_cohort']} inschrijvingen van voor het "
                            "selectiejaar genegeerd"
                        )
                    if info["n_studenten_meerdere_spells"]:
                        filter_regels.append(
                            f"{info['n_studenten_meerdere_spells']} studenten met "
                            "meerdere inschrijvingen: de inschrijving die het dichtst "
                            "bij het selectiejaar begon is gebruikt"
                        )
                    if filter_regels:
                        cho_alerts.append(
                            dbc.Alert(
                                "1CHO gefilterd: " + "; ".join(filter_regels) + ".",
                                color="info",
                                className="small py-1 mb-1",
                            )
                        )
                    if info["jaarfilter_overgeslagen"]:
                        cho_alerts.append(
                            dbc.Alert(
                                "Het jaar in de config sluit niet aan op het eerste "
                                "studiejaar in 1CHO; er is daarom niet op cohort "
                                "gefilterd. Controleer het jaar in de config.",
                                color="warning",
                                className="small py-1 mb-1",
                            )
                        )
                    cho_status = html.Div(cho_alerts)
                    btn_disabled = False

            except Exception as e:
                validatie = dbc.Alert(
                    f"Fout bij validatie: {e}", color="danger", className="small py-1"
                )

        return resultaat()

    @app.callback(
        Output("data-store", "data"),
        Output("scores-store", "data"),
        Input("btn-open-dashboard", "n_clicks"),
        Input("btn-demodata", "n_clicks"),
        Input("btn-reset", "n_clicks"),
        State("upload-selectiedata", "contents"),
        State("upload-config", "contents"),
        State("upload-1cho", "contents"),
        State("upload-1cho", "filename"),
        State("demo-dataset-picker", "value"),
        State("wiz-config-store", "data"),
        State("cho-opleiding-picker", "value"),
        State("config-bron", "data"),
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
        cho_opleiding,
        bron,
    ):
        trigger = ctx.triggered_id

        if trigger == "btn-reset":
            return None, None

        if trigger == "btn-demodata":
            return _laad_demodata(demo_dataset)

        bron = actieve_config_bron(None, bron, cfg_contents, wiz_config)
        if trigger == "btn-open-dashboard" and sel_contents and bron and cho_contents:
            config = lees_actieve_config(bron, cfg_contents, wiz_config)
            return bouw_data_stores(
                config,
                sel_contents,
                parse_csv_or_excel(cho_contents, cho_fn or "data.csv"),
                cho_opleiding,
            )

        return dash.no_update, dash.no_update

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
                stap(
                    perspectief_voor(df)["positief_label"],
                    n_doorgestroomd,
                    n_ingeschreven,
                ),
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
        Output("rapport-fout", "children"),
        Input("btn-download-rapport", "n_clicks"),
        State("data-store", "data"),
        State("scores-store", "data"),
        prevent_initial_call=True,
    )
    def download_rapport(_n, store_data, scores_store):
        df = df_from_store(store_data)
        if df.empty or not scores_store:
            return dash.no_update, ""
        scores_df = scores_df_from_store(scores_store)
        perspectief = perspectief_voor(df)
        try:
            pdf_bytes = genereer_rapport(df, scores_df, perspectief=perspectief)
        except Exception as e:
            # Zonder deze melding ziet de gebruiker alleen de toast
            # 'Rapport wordt gegenereerd' en daarna niets.
            log.exception("PDF-rapport genereren mislukt")
            return dash.no_update, dbc.Alert(
                f"Het rapport kon niet worden gemaakt: {e}",
                color="danger",
                className="small py-1 mt-2",
            )
        opleiding = ""
        if "opleiding" in df.columns and df["opleiding"].notna().any():
            opleiding = str(df["opleiding"].dropna().iloc[0]).strip()
        jaar = ""
        if "selectiejaar" in df.columns and df["selectiejaar"].notna().any():
            jaren = sorted(df["selectiejaar"].dropna().unique())
            jaar = " ".join(str(int(j)) for j in jaren)
        staart = " ".join(deel for deel in [opleiding, jaar] if deel).strip()
        filename = (
            f"Selectie evaluatierapport - {staart}.pdf"
            if staart
            else "Selectie evaluatierapport.pdf"
        )
        return dcc.send_bytes(pdf_bytes, filename), ""
