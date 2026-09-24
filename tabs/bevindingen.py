"""Tab 'Wat valt op': automatisch overzicht van bevindingen."""

import dash
from dash import dcc, html, Input, Output, State
import dash_bootstrap_components as dbc

from shared import (
    perspectief_voor,
    shorten_item,
    vergelijk_succes_per_item,
    toets_verschil_per_item,
    genereer_bevindingen,
    beleidsvervolgstappen,
    DEMO_DIMENSIES,
    demografie_scores,
    bereken_gezamenlijk_model,
    chi2_per_dimensie,
    model_stats_uit,
)

from helpers import (
    scores_df_from_store,
    df_from_store,
)


def _bevindingen_lijst(titel, items, leeg_tekst, uitleg=None):
    """Een sectie met een kop en lijst bevindingen. Met 'uitleg' krijgt de kop
    een (i)-icoon met een informatiewolkje dat uitlegt waar de bevindingen
    vandaan komen."""
    kop_kinderen = [titel]
    extra = []
    if uitleg:
        tip_id = "tip-" + "".join(c if c.isalnum() else "-" for c in titel.lower())
        kop_kinderen.append(
            html.Span(
                " ⓘ",
                id=tip_id,
                className="text-muted",
                style={"cursor": "help", "fontSize": "0.85em"},
            )
        )
        extra.append(dbc.Tooltip(uitleg, target=tip_id, placement="right"))
    inhoud = (
        html.Ul([html.Li(x) for x in items], className="small mb-0")
        if items
        else html.P(leeg_tekst, className="text-muted small mb-0")
    )
    return html.Div([html.H6(kop_kinderen), *extra, inhoud], className="mb-4")


def _uitleg_verschiltoets_regressie():
    """Legt uit waarom de verschiltoets voorop staat en wat de regressie daar als
    aanvulling op is. Ingeklapt zodat het de bevindingen niet in de weg zit."""
    return html.Details(
        [
            html.Summary(
                "Verschiltoets of regressie: wat zegt wat?",
                className="small text-muted",
                style={"cursor": "pointer"},
            ),
            html.Ul(
                [
                    html.Li(
                        "De verschiltoets en de regressie per item toetsen vrijwel "
                        "hetzelfde: scoort de groep met studiesucces anders op dit ene "
                        "item? Ze bevestigen elkaar meestal."
                    ),
                    html.Li(
                        "Het gezamenlijke model kijkt of een item iets toevoegt "
                        "bovenop alle andere items. Dat is informatiever, maar ook "
                        "gevoeliger: bij kleine groepen en items die elkaar "
                        "overlappen worden de schattingen snel onbetrouwbaar."
                    ),
                    html.Li(
                        "Vuistregel: bij de meeste selectiedatasets (ongeveer 50 tot 150 "
                        "studenten) is de verschiltoets per item het betrouwbaarste "
                        "signaal. Gebruik het gezamenlijke model als aanvulling, niet "
                        "als doorslag."
                    ),
                ],
                className="small text-muted mb-0 mt-2",
            ),
        ],
        className="mb-4",
    )


def _maak_vervolgstappen(bevindingen, model_stats=None, perspectief=None):
    """Beleidsconclusies onder de bevindingen (tekst uit
    shared.beleidsvervolgstappen, gedeeld met het rapport). Gerenderd als
    opvallend blauw blok (.vervolg-blok) zodat een beleidsmedewerker de
    conclusie meteen ziet."""
    stappen = beleidsvervolgstappen(bevindingen, model_stats, perspectief)

    return html.Div(
        [
            html.Div(
                "Wat kun je hiermee? Vervolgstappen voor beleid",
                className="vervolg-kop",
            ),
            html.P(
                "Onderstaande punten volgen uit wat hierboven is gevonden, als richting "
                "voor het gesprek, niet als kant-en-klaar oordeel.",
                className="small text-muted mb-2",
            ),
            html.Ul(
                [html.Li(s) for s in stappen],
                className="small text-muted",
            ),
        ],
        className="vervolg-blok",
    )


def maak_layout():
    return dbc.Tab(
        label="Wat valt op",
        tab_id="tab-bevindingen",
        children=[
            html.Div(
                [
                    html.H5("Wat valt op?"),
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

        scores_df = scores_df_from_store(scores_store)

        perspectief = perspectief_voor(df)
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
        model = bereken_gezamenlijk_model(df, scores_df, perspectief)
        uni_data = model.get("univariaat", [])
        model_stats = model_stats_uit(model)
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

        # Deel 1: voorspellen de selectiescores studiesucces?
        secties.append(html.H5("Selectiescores en studiesucces", className="mt-2 mb-1"))
        secties.append(
            html.P(
                "Hangen hogere selectiescores samen met meer studiesucces "
                "(doorstroom naar jaar 2 of een diploma)?",
                className="small text-muted",
            )
        )
        secties.append(
            _bevindingen_lijst(
                "Verschiltoets per item",
                bevindingen["validiteit"],
                "Geen opvallende voorspellers gevonden in de cijfers.",
                uitleg=(
                    "Items waar de groep met studiesucces duidelijk anders "
                    "scoorde dan de groep zonder. Komt van het tabblad Verschiltoets; "
                    "alleen verschillen die waarschijnlijk niet op toeval berusten."
                ),
            )
        )
        if bevindingen.get("regressie"):
            secties.append(
                _bevindingen_lijst(
                    "Regressie: elk item apart",
                    bevindingen["regressie"],
                    "Geen items die op zichzelf studiesucces voorspellen.",
                    uitleg=(
                        "Items die op zichzelf de kans op studiesucces "
                        "voorspellen. Komt van het tabblad Regressie, waar elk "
                        "item los is getoetst."
                    ),
                )
            )
        if bevindingen.get("model"):
            secties.append(
                _bevindingen_lijst(
                    "Regressie: alle items samen",
                    bevindingen["model"],
                    "",
                    uitleg=(
                        "Hoe goed alle items samen studiesucces voorspellen, en "
                        "welk item een eigen bijdrage levert bovenop de rest."
                    ),
                )
            )
        secties.append(_uitleg_verschiltoets_regressie())
        secties.append(
            _bevindingen_lijst(
                "Samenhang tussen items (correlatie)",
                bevindingen["correlatie"],
                "Onvoldoende items voor een correlatieanalyse.",
                uitleg=(
                    "Items die sterk met elkaar samenhangen en dus deels "
                    "hetzelfde meten. Komt van het tabblad Correlatie."
                ),
            )
        )

        # Deel 2: achtergrondkenmerken (geslacht, vooropleiding)
        secties.append(html.Hr())
        secties.append(
            html.H5(
                "Achtergrondkenmerken (geslacht, vooropleiding)", className="mt-3 mb-1"
            )
        )
        secties.append(
            html.P(
                "Hangen achtergrondkenmerken samen met de uitkomst, en scoren "
                "groepen verschillend op de selectie-items?",
                className="small text-muted",
            )
        )
        if bevindingen.get("demografie"):
            secties.append(
                _bevindingen_lijst(
                    "Samenhang met de uitkomst",
                    bevindingen["demografie"],
                    "",
                    uitleg=(
                        "Hangt een achtergrondkenmerk (geslacht, vooropleiding) "
                        "samen met de kans op studiesucces? Getoetst met een "
                        "chi-kwadraattoets op de kruistabel van het kenmerk tegen "
                        "de uitkomst."
                    ),
                )
            )
        secties.append(
            _bevindingen_lijst(
                "Verschiltoets: eerlijkheid",
                bevindingen["fairness"],
                "Geen demografische gegevens beschikbaar om te vergelijken.",
                uitleg=(
                    "Items waar achtergrondgroepen verschillend scoorden. "
                    "Kan wijzen op onbedoelde vertekening. Per item getoetst met "
                    "een Kruskal-Wallis-toets, net als op het tabblad Verschiltoets."
                ),
            )
        )

        secties.append(_maak_vervolgstappen(bevindingen, model_stats, perspectief))
        return secties
