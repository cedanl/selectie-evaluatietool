"""Tab 'Introductie': toegankelijke uitleg en context van het dashboard."""

from dash import html
import dash_bootstrap_components as dbc

from shared import (
    GROEP_KLEUREN,
    GROEP_GESTART_GEEN_VERVOLG,
    GROEP_DOORGESTROOMD,
)

# De groepen zoals we ze in de introductie uitleggen. De tool vergelijkt alleen
# studenten die daadwerkelijk aan de opleiding zijn begonnen: wie studiesucces
# had tegenover wie uitviel. De vergelijking 'gestart vs niet gestart' en de
# losse 'Niet gestart'-groep zitten niet in het dashboard, dus die tonen we hier
# ook niet als vergelijkingsgroep. Studiesucces is per opleiding ofwel doorstroom
# naar jaar 2 ofwel een diploma (eenjarige opleidingen zoals masters); die twee
# tonen we als een gecombineerde succesgroep. De kleur komt uit shared.py zodat
# hij gelijkloopt met de grafieken.
GROEP_KAARTEN = [
    (
        GROEP_KLEUREN[GROEP_GESTART_GEEN_VERVOLG],
        "Gestart, geen vervolg",
        "Begonnen aan het eerste jaar, maar niet doorgestroomd en geen diploma "
        "gehaald.",
    ),
    (
        GROEP_KLEUREN[GROEP_DOORGESTROOMD],
        "Studiesucces",
        "Doorgestroomd naar jaar 2, of bij eenjarige opleidingen zoals masters het "
        "diploma gehaald. Dit is de positieve uitkomst.",
    ),
]


def _stap(nummer, titel, tekst):
    """Een genummerde stap in de 'hoe werkt het'-uitleg."""
    return dbc.ListGroupItem(
        [
            html.Span(str(nummer), className="intro-stap-nummer"),
            html.Div([html.Strong(titel), html.Div(tekst, className="small")]),
        ],
        className="d-flex align-items-start gap-3",
    )


def _groep_kaart(kleur, titel, tekst):
    """Een kaartje dat een van de uitkomstgroepen in gewone taal uitlegt."""
    return dbc.Col(
        dbc.Card(
            dbc.CardBody(
                [
                    html.Div(
                        className="intro-groep-stip",
                        style={"backgroundColor": kleur},
                    ),
                    html.Strong(titel, className="small"),
                    html.P(tekst, className="small text-muted mb-0 mt-1"),
                ]
            ),
            className="h-100",
        ),
        md=6,
        className="mb-3",
    )


def _tab_uitleg(naam, tekst):
    """Een regel in het overzicht van wat elk tabblad laat zien."""
    return html.Li([html.Strong(naam + ": "), tekst], className="mb-1")


def maak_layout():
    return dbc.Tab(
        label="Introductie",
        tab_id="tab-intro",
        children=[
            html.Div(
                [
                    html.H5("Welkom bij de evaluatietool selectie"),
                    html.P(
                        "Deze tool helpt je een simpele maar belangrijke vraag te "
                        "beantwoorden: doen studenten die hoog scoorden bij de "
                        "selectie het later ook beter in hun studie? Met andere "
                        "woorden, voorspelt jouw selectieprocedure studiesucces?",
                        className="text-muted",
                    ),
                    html.P(
                        "Je hoeft geen statistiek te kennen om de tool te gebruiken. "
                        "Je laadt je eigen data of een voorbeeldset, en het dashboard "
                        "rekent de vergelijkingen voor je uit en legt in gewone taal "
                        "uit wat eruit komt.",
                        className="text-muted",
                    ),
                    html.Hr(className="my-4"),
                    html.H6("Hoe werkt het?"),
                    dbc.ListGroup(
                        [
                            _stap(
                                1,
                                "Data toevoegen",
                                "Je laadt de selectiescores, een korte configuratie "
                                "en de studievoortgang (1CHO). Geen eigen data bij de "
                                "hand? Kies links een voorbeeldset.",
                            ),
                            _stap(
                                2,
                                "Koppelen",
                                "De tool koppelt elke kandidaat aan de 1CHO-gegevens. "
                                "Alleen kandidaten die zich daadwerkelijk bij de "
                                "opleiding inschreven komen in 1CHO voor; daarvan "
                                "bepaalt de tool of ze doorstroomden of een diploma "
                                "haalden.",
                            ),
                            _stap(
                                3,
                                "Bekijken",
                                "In de tabbladen zie je per onderdeel of hogere scores "
                                "samenhangen met meer studiesucces, met uitleg erbij.",
                            ),
                        ],
                        flush=True,
                        className="mb-4",
                    ),
                    html.H6("De groepen"),
                    html.P(
                        "Deze tool kijkt alleen naar studenten die zich daadwerkelijk "
                        "bij de instelling en opleiding inschreven en daardoor in het "
                        "1CHO-bestand terechtkomen. Binnen die groep vergelijkt de tool "
                        "wie studiesucces had met wie uitviel:",
                        className="text-muted small",
                    ),
                    dbc.Row(
                        [
                            _groep_kaart(kleur, titel, tekst)
                            for kleur, titel, tekst in GROEP_KAARTEN
                        ],
                        className="mb-2",
                    ),
                    html.P(
                        "Kandidaten die niet werden geselecteerd, of die wel een plek "
                        "kregen maar niet aan de opleiding begonnen, staan niet in 1CHO. "
                        "Zij worden uit de analyse gehaald en niet met de ingeschreven "
                        "studenten vergeleken.",
                        className="text-muted small mb-4",
                    ),
                    html.H6("Wat vind je in de tabbladen?"),
                    html.Ul(
                        [
                            _tab_uitleg(
                                "Wat valt op",
                                "een automatisch overzicht van de opvallendste "
                                "bevindingen in jouw data.",
                            ),
                            _tab_uitleg(
                                "Selectiescores",
                                "hoe de scores per onderdeel verschillen tussen de "
                                "groepen.",
                            ),
                            _tab_uitleg(
                                "Demografie",
                                "hoe achtergrondkenmerken zoals geslacht en "
                                "vooropleiding samenhangen met doorstroom.",
                            ),
                            _tab_uitleg(
                                "Verschiltoets",
                                "per onderdeel een toets of het verschil tussen "
                                "groepen toeval kan zijn of niet.",
                            ),
                            _tab_uitleg(
                                "Correlatie",
                                "in hoeverre de onderdelen onderling hetzelfde meten.",
                            ),
                            _tab_uitleg(
                                "Regressie",
                                "welke onderdelen samen het beste studiesucces "
                                "voorspellen.",
                            ),
                        ],
                        className="small text-muted",
                    ),
                    dbc.Alert(
                        [
                            html.Strong("Lees de uitkomsten met zorg. "),
                            "Selectiegroepen zijn vaak klein, dus de resultaten laten "
                            "patronen zien, geen harde bewijzen. Gebruik ze als "
                            "startpunt voor een gesprek, niet als eindoordeel.",
                        ],
                        color="light",
                        className="small border mt-2",
                    ),
                ],
                className="intro-tab",
            )
        ],
    )
