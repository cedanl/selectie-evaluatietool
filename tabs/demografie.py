"""Tab 'Demografie': achtergrond tegen studieuitkomst."""

import pandas as pd
import plotly.graph_objects as go
from dash import dcc, html, dash_table, Input, Output
import dash_bootstrap_components as dbc

from shared import (
    CHART_BASE,
    PERSPECTIEF_DOORSTROOM,
    binair_kleur_map,
    DEMO_DIMENSIES,
    chi2_per_dimensie,
    fmt_p,
)

from helpers import (
    TABLE_STYLE,
    df_from_store,
    _meng_met_wit,
)


def maak_layout():
    return dbc.Tab(
        label="Demografie",
        tab_id="tab-demografie",
        children=[
            html.Div(
                [
                    html.H5("Achtergrond van de kandidaten"),
                    html.P(
                        "Hoe verhouden geslacht en "
                        "vooropleiding zich tot de "
                        "studieuitkomst?",
                        className="text-muted small",
                    ),
                    dbc.Row(
                        dbc.Col(
                            [
                                dbc.Label(
                                    "Achtergrond",
                                    className="small",
                                ),
                                dcc.Dropdown(
                                    id="demo-dimensie",
                                    options=[
                                        {
                                            "label": d["label"],
                                            "value": d["kolom"],
                                        }
                                        for d in DEMO_DIMENSIES
                                    ],
                                    value=DEMO_DIMENSIES[0]["kolom"],
                                    clearable=False,
                                ),
                            ],
                            width=3,
                        ),
                        className="mb-3",
                    ),
                    dcc.Loading(
                        html.Div(id="demografie-inhoud"),
                        type="default",
                    ),
                ],
                className="tab-body",
            ),
        ],
    )


def registreer_callbacks(app):
    @app.callback(
        Output("demografie-inhoud", "children"),
        Input("demo-dimensie", "value"),
        Input("data-store", "data"),
    )
    def update_demografie_tab(dim_kolom, store_data):
        df = df_from_store(store_data)
        if df.empty:
            return html.P(
                "Laad eerst data om de demografie te zien.", className="text-muted"
            )

        dim = next((d for d in DEMO_DIMENSIES if d["kolom"] == dim_kolom), None)
        perspectief = PERSPECTIEF_DOORSTROOM
        if dim is None:
            return html.P("Selecteer een achtergrond.", className="text-muted")

        dim_col = dim["kolom"]
        dim_label = dim["label"]
        if dim_col not in df.columns or df[dim_col].dropna().empty:
            return html.P(
                f"Geen {dim_label.lower()} gegevens beschikbaar.",
                className="text-muted",
            )

        pos_label = perspectief["positief_label"]
        neg_label = perspectief["negatief_label"]
        pop = df[df["groep"].isin(perspectief["populatie"])].copy()
        pop["_uitkomst"] = (
            pop["groep"]
            .isin(perspectief["positief_groepen"])
            .map({True: pos_label, False: neg_label})
        )
        subset = pop.dropna(subset=[dim_col])
        if subset.empty:
            return html.P(
                "Te weinig data voor deze combinatie.", className="text-muted"
            )

        volgorde = [pos_label, neg_label]
        kleuren = binair_kleur_map(perspectief)

        ct = pd.crosstab(
            subset[dim_col], subset["_uitkomst"], margins=True, margins_name="Totaal"
        )
        aanwezig = [c for c in volgorde if c in ct.columns]
        ct = ct[aanwezig + ["Totaal"]]
        ct_pct = ct.div(ct["Totaal"], axis=0).drop(columns=["Totaal"]).round(3)

        tabel_data = []
        for rij_naam in ct.index:
            rij = {dim_label: str(rij_naam)}
            for col in aanwezig:
                n = int(ct.loc[rij_naam, col])
                pct = ct_pct.loc[rij_naam, col] * 100 if col in ct_pct.columns else 0
                rij[col] = f"{n} ({pct:.0f}%)"
            rij["Totaal"] = int(ct.loc[rij_naam, "Totaal"])
            tabel_data.append(rij)

        tabel_cols = [{"name": dim_label, "id": dim_label}]
        tabel_cols += [{"name": c, "id": c} for c in aanwezig]
        tabel_cols.append({"name": "Totaal", "id": "Totaal"})

        tabel_stijl = []
        for col_naam in aanwezig:
            tabel_stijl.append(
                {
                    "if": {"column_id": col_naam},
                    "backgroundColor": _meng_met_wit(kleuren[col_naam]),
                }
            )
        tabel_stijl.append(
            {
                "if": {"filter_query": '{%s} = "Totaal"' % dim_label},
                "fontWeight": "bold",
                "backgroundColor": "#f8fafc",
            }
        )

        groep_namen = [g for g in ct.index if g != "Totaal"]
        fig = go.Figure()
        for uitkomst_cat in aanwezig:
            waarden = [
                ct_pct.loc[g, uitkomst_cat] * 100
                if g in ct_pct.index and uitkomst_cat in ct_pct.columns
                else 0
                for g in groep_namen
            ]
            n_waarden = [int(ct.loc[g, uitkomst_cat]) for g in groep_namen]
            fig.add_trace(
                go.Bar(
                    name=uitkomst_cat,
                    x=[str(g) for g in groep_namen],
                    y=waarden,
                    text=[f"n={n}" for n in n_waarden],
                    textposition="inside",
                    marker_color=kleuren.get(uitkomst_cat, "#94a3b8"),
                )
            )
        fig.update_layout(
            barmode="stack",
            yaxis_title="Percentage",
            yaxis=dict(range=[0, 100]),
            height=320,
            **CHART_BASE,
            margin=dict(t=10, b=30),
            legend=dict(orientation="h", y=1.12),
        )

        chi2 = chi2_per_dimensie(df, perspectief).get(dim_label)
        if chi2 is not None:
            p = chi2["p"]
            significant = p < 0.05
            chi_tekst = (
                "Chi-kwadraattoets: de uitkomstverdeling verschilt significant "
                if significant
                else "Chi-kwadraattoets: geen significant verschil in "
                "uitkomstverdeling "
            ) + f"tussen de {dim_label.lower()}-groepen (p = {fmt_p(p)})."
            chi_element = dbc.Alert(
                chi_tekst,
                color="warning" if significant else "light",
                className="small py-2 mt-2 mb-0 border",
            )
        else:
            chi_element = html.P(
                "Te weinig groepen voor een chi-kwadraattoets.",
                className="text-muted small fst-italic mt-2 mb-0",
            )

        n_buiten = int((~df["groep"].isin(perspectief["populatie"])).sum())
        voetnoot = []
        if n_buiten > 0:
            voetnoot.append(
                html.P(
                    f"{n_buiten} studenten vallen buiten de populatie voor "
                    f"'{perspectief['label'].lower()}' en zijn niet meegenomen.",
                    className="text-muted small fst-italic mt-2 mb-0",
                )
            )

        return [
            dash_table.DataTable(
                data=tabel_data,
                columns=tabel_cols,
                style_table={"overflowX": "auto"},
                style_data_conditional=tabel_stijl,
                **TABLE_STYLE,
            ),
            chi_element,
            dcc.Graph(figure=fig),
            *voetnoot,
        ]
