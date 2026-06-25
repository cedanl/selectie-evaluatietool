"""Tab 'Wat valt op': automatisch overzicht van bevindingen."""

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
    scores_df_from_store,
    df_from_store,
    _bereken_model_stats,
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


def _aantal(n, ev, mv):
    """'1 item' of '3 items': telwoord met enkel-/meervoud."""
    return f"{n} {ev if n == 1 else mv}"


def _namen(items):
    """'A', 'A en B' of 'A, B en C': nette opsomming van itemnamen."""
    items = list(items)
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + " en " + items[-1]


def _kracht_label(r2):
    """Pseudo R-kwadraat naar woord, gelijk aan shared._bevindingen_gezamenlijk_model."""
    if r2 < 0.05:
        return "zeer beperkt"
    if r2 < 0.15:
        return "beperkt"
    if r2 < 0.30:
        return "matig"
    return "substantieel"


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
                        "hetzelfde: scoort de doorgestroomde groep anders op dit ene "
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


def _maak_vervolgstappen(bevindingen, model_stats=None):
    """Beleidsconclusies onder de bevindingen, gekoppeld aan wat er in deze data
    is gevonden. De verschiltoets is het kernsignaal: vindt hij een effect, dan
    heeft een item voorspellende waarde; vindt hij niets, dan voorspelt de
    selectie in deze data geen studiesucces. De regressie komt er als aanvulling
    bij. Gerenderd als opvallend blauw blok (.vervolg-blok) zodat een
    beleidsmedewerker de conclusie meteen ziet."""
    stappen = []

    n_valide = len(bevindingen.get("validiteit", []))
    if n_valide:
        stappen.append(
            f"De verschiltoets vindt {_aantal(n_valide, 'item', 'items')} "
            "waarop doorstromers duidelijk anders scoorden dan uitvallers. Dat is een "
            "aanwijzing dat deze items studiesucces helpen voorspellen. "
            "Beleidsmatig: behoud ze of laat ze zwaarder meewegen, en bevestig het "
            "patroon eerst op een volgend cohort voordat je de procedure aanpast."
        )
    else:
        stappen.append(
            "De verschiltoets vindt geen enkel item waarop doorstromers en "
            "uitvallers significant verschillen. Beleidsmatig betekent dit dat de "
            "selectie in deze data geen studiesucces voorspelt: ga na of de items "
            "iets anders meten dat je bewust wilt behouden (motivatie, passendheid), "
            "of dat de procedure eenvoudiger en goedkoper kan."
        )

    if model_stats and model_stats.get("pseudo_r2") is not None:
        r2 = model_stats["pseudo_r2"]
        sig = model_stats.get("sig_items", [])
        if sig:
            ww = "levert" if len(sig) == 1 else "leveren"
            eigen = f"Vooral {_namen(sig)} {ww} een eigen bijdrage bovenop de rest. "
        else:
            eigen = "Geen item springt eruit als je ze samen bekijkt. "
        stappen.append(
            f"Alle items samen verklaren een {_kracht_label(r2)} deel van het "
            f"verschil in studiesucces (regressie, pseudo R² = {r2:.2f}). "
            + eigen
            + "Dit gezamenlijke model is bij kleine groepen wankel, dus leun voor "
            "beleid vooral op de verschiltoets hierboven."
        )

    n_fair = len(bevindingen.get("fairness", []))
    if n_fair:
        stappen.append(
            f"Bij {_aantal(n_fair, 'item', 'items')} scoorden "
            "achtergrondgroepen (geslacht, vooropleiding) verschillend. Beleidsmatig: "
            "onderzoek of dat verschil inhoudelijk te rechtvaardigen is of op "
            "onbedoelde vertekening wijst."
        )

    n_corr = len(bevindingen.get("correlatie", []))
    if n_corr:
        stappen.append(
            "De correlatie vindt "
            f"{_aantal(n_corr, 'sterke samenhang', 'sterke samenhangen')} tussen "
            "items die deels hetzelfde meten. Beleidsmatig: je kunt er een laten "
            "vallen om de selectie korter en goedkoper te maken zonder veel informatie "
            "te verliezen."
        )

    stappen.append(
        "Herhaal de analyse met een nieuw cohort voordat je de procedure echt "
        "aanpast. Een enkel jaar is een momentopname, zeker bij kleine groepen."
    )
    stappen.append(
        "Combineer deze cijfers met vakkennis en eerder onderzoek. Doorstroom naar "
        "jaar 2 is maar een van de manieren om studiesucces te meten."
    )

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
                    "Items waar de doorgestroomde groep duidelijk anders "
                    "scoorde dan de uitvallers. Komt van het tabblad Verschiltoets; "
                    "alleen verschillen die waarschijnlijk niet op toeval berusten."
                ),
            )
        )
        if bevindingen.get("regressie"):
            secties.append(
                _bevindingen_lijst(
                    "Regressie: elk item apart",
                    bevindingen["regressie"],
                    "Geen items die op zichzelf doorstroom voorspellen.",
                    uitleg=(
                        "Items die op zichzelf de kans op doorstroom "
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
                        "Hoe goed alle items samen doorstroom voorspellen, en "
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
                        "samen met de kans op doorstroom? Getoetst met een "
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

        secties.append(_maak_vervolgstappen(bevindingen, model_stats))
        return secties
