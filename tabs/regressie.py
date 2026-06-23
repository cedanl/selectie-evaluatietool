"""Tab 'Regressie': logistische regressie op studiesucces."""

import io
import numpy as np
import pandas as pd
from dash import dcc, html, dash_table, Input, Output, State
import dash_bootstrap_components as dbc

from shared import (
    PERSPECTIEF_DOORSTROOM,
    shorten_item,
    sig_sym,
    fmt_p,
)

from helpers import (
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
                        "Welke onderdelen van de selectie voorspellen het beste of een student "
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
                                                "Odds ratio: kansverhouding per SD stijging. OR 1.5 = 50% hogere "
                                                "kans. OR < 1 = lagere kans."
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
                                        "Het univariate model toetst elk item afzonderlijk. Het gezamenlijke "
                                        "model zet alle items tegelijk in en laat zien welk item bovenop de "
                                        "andere items nog een eigen bijdrage levert. Bij weinig studenten "
                                        "worden de zwakste items automatisch weggelaten (EPV-regel: minimaal "
                                        "5 events per predictor).",
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
                            html.H6("Univariaat per item"),
                            html.P(
                                "Elk item afzonderlijk getoetst. Hier valt niets weg.",
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
                                "Alle items tegelijk. Items kunnen niet-significant worden door "
                                "overlap met andere items.",
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
        leeg7 = ("", [], [], [], [], [], [])
        if df.empty or not scores_store:
            return leeg7

        perspectief = PERSPECTIEF_DOORSTROOM
        scores_df = pd.read_json(io.StringIO(scores_store), orient="split")

        regressie_msg = ""
        uni_data = []
        uni_cols = []
        uni_style = []
        reg_data = []
        reg_cols = []
        reg_style = []

        item_pivot = scores_df.pivot_table(
            index="studentnummer", columns="item", values="score", aggfunc="mean"
        )
        item_pivot.columns = [shorten_item(c) for c in item_pivot.columns]
        all_score_cols = list(item_pivot.columns)

        populatie = df[df["groep"].isin(perspectief["populatie"])].copy()

        if len(populatie) < 10:
            regressie_msg = dbc.Alert(
                f"Te weinig studenten ({len(populatie)}) voor regressie. "
                "Minimaal 10 nodig.",
                color="warning",
                className="small",
            )
            return (regressie_msg, [], [], [], [], [], [])

        populatie["uitkomst"] = (
            populatie["groep"].isin(perspectief["positief_groepen"]).astype(int)
        )

        item_pivot_pop = item_pivot.loc[
            item_pivot.index.isin(populatie["studentnummer"])
        ].copy()

        nan_pct = item_pivot_pop.isna().mean()
        verwijderd_nan = [
            c
            for c in all_score_cols
            if c in item_pivot_pop.columns and nan_pct.get(c, 1) > 0.3
        ]
        bruikbare_cols = [
            c
            for c in all_score_cols
            if c in item_pivot_pop.columns and nan_pct.get(c, 1) <= 0.3
        ]

        if len(bruikbare_cols) < 1:
            regressie_msg = dbc.Alert(
                "Te weinig bruikbare items voor regressie.",
                color="warning",
                className="small",
            )
            return (regressie_msg, [], [], [], [], [], [])

        item_pivot_pop[bruikbare_cols] = item_pivot_pop[bruikbare_cols].fillna(
            item_pivot_pop[bruikbare_cols].mean()
        )
        item_pivot_pop = item_pivot_pop.dropna(subset=bruikbare_cols)

        if len(item_pivot_pop) < 10:
            regressie_msg = dbc.Alert(
                "Te weinig complete cases voor regressie.",
                color="warning",
                className="small",
            )
            return (regressie_msg, [], [], [], [], [], [])

        y = populatie.set_index("studentnummer").loc[item_pivot_pop.index, "uitkomst"]
        X_all = item_pivot_pop[bruikbare_cols]

        import statsmodels.api as sm

        for col in bruikbare_cols:
            x_col = X_all[[col]].astype(float)
            std = x_col.iloc[:, 0].std()
            if std > 0:
                x_z = (x_col - x_col.mean()) / std
            else:
                x_z = x_col * 0
            try:
                m = sm.Logit(y.astype(float), sm.add_constant(x_z)).fit(
                    disp=0, maxiter=50
                )
                coef = round(float(m.params.iloc[-1]), 3)
                odds = round(float(np.exp(m.params.iloc[-1])), 2)
                p = float(m.pvalues.iloc[-1])
                uni_data.append(
                    {
                        "Item": col,
                        "Coefficient": coef,
                        "Odds ratio": odds,
                        "p-waarde": fmt_p(p),
                        "Sig.": sig_sym(p),
                    }
                )
            except Exception:
                uni_data.append(
                    {
                        "Item": col,
                        "Coefficient": "-",
                        "Odds ratio": "-",
                        "p-waarde": "-",
                        "Sig.": "-",
                    }
                )

        uni_cols = [
            {"name": c, "id": c}
            for c in ["Item", "Coefficient", "Odds ratio", "p-waarde", "Sig."]
        ]
        for i, row in enumerate(uni_data):
            if row["Sig."] not in ("-", "ns"):
                uni_style.append(
                    {
                        "if": {"row_index": i, "column_id": "Sig."},
                        "backgroundColor": "#bbf7d0",
                        "color": "#166534",
                        "fontWeight": "600",
                    }
                )

        X = X_all.copy()

        from numpy.linalg import matrix_rank

        verwijderd_collinear = []
        while len(X.columns) > 1:
            rank = matrix_rank(X.values)
            if rank >= len(X.columns):
                break
            corr_vals = X.corr().abs().to_numpy().copy()
            np.fill_diagonal(corr_vals, 0)
            flat_idx = corr_vals.argmax()
            _, col_idx = divmod(flat_idx, corr_vals.shape[1])
            verwijderd_collinear.append(X.columns[col_idx])
            X = X.drop(columns=[X.columns[col_idx]])
        joint_cols = list(X.columns)

        n_events = min(int(y.sum()), int(len(y) - y.sum()))
        max_predictoren = max(2, n_events // 5)
        verwijderd_epv = []
        if len(joint_cols) > max_predictoren:
            uni_p = {
                row["Item"]: (
                    0.0001 if row["p-waarde"] == "< 0.001" else float(row["p-waarde"])
                )
                for row in uni_data
                if row["p-waarde"] not in ("-",)
            }
            gesorteerd = sorted(joint_cols, key=lambda c: uni_p.get(c, 1.0))
            verwijderd_epv = gesorteerd[max_predictoren:]
            joint_cols = gesorteerd[:max_predictoren]
            X = X[joint_cols]

        try:
            X_z = X.astype(float).apply(
                lambda s: (
                    (s - s.mean()) / s.std()
                    if s.std() > 0
                    else pd.Series(0, index=s.index)
                )
            )
            X_const = sm.add_constant(X_z)
            model = sm.Logit(y.astype(float), X_const).fit(disp=0, maxiter=100)

            n_positief = int(y.sum())
            n_negatief = int(len(y) - y.sum())
            pseudo_r2 = round(float(model.prsquared), 3)
            pos_label = perspectief["positief_label"].lower()
            neg_label = perspectief["negatief_label"].lower()
            msg_parts = [
                html.Span(
                    f"n = {len(y)} ({pos_label}: {n_positief}, {neg_label}: {n_negatief})",
                    className="small text-muted me-3",
                ),
                html.Span(f"Pseudo R² = {pseudo_r2}", className="small fw-bold"),
            ]
            if verwijderd_nan:
                msg_parts.append(html.Br())
                msg_parts.append(
                    html.Span(
                        f"Items niet meegenomen (>30% ontbrekend): {', '.join(verwijderd_nan)}",
                        className="small text-muted",
                    )
                )
            if verwijderd_collinear:
                msg_parts.append(html.Br())
                msg_parts.append(
                    html.Span(
                        f"Items niet meegenomen (overlap): {', '.join(verwijderd_collinear)}",
                        className="small text-muted",
                    )
                )
            if verwijderd_epv:
                msg_parts.append(html.Br())
                msg_parts.append(
                    html.Span(
                        f"Items niet meegenomen (EPV-beperking, top {len(joint_cols)} behouden): "
                        f"{', '.join(verwijderd_epv)}",
                        className="small text-muted",
                    )
                )
            regressie_msg = html.Div(msg_parts)

            for item_naam in joint_cols:
                if item_naam not in model.params.index:
                    continue
                coef = round(float(model.params[item_naam]), 3)
                odds = round(float(np.exp(model.params[item_naam])), 2)
                p = float(model.pvalues[item_naam])
                reg_data.append(
                    {
                        "Item": item_naam,
                        "Coefficient": coef,
                        "Odds ratio": odds,
                        "p-waarde": fmt_p(p),
                        "Sig.": sig_sym(p),
                    }
                )

            reg_cols = [
                {"name": c, "id": c}
                for c in ["Item", "Coefficient", "Odds ratio", "p-waarde", "Sig."]
            ]

            for i, row in enumerate(reg_data):
                p_str = row["p-waarde"]
                p_val = 0.0001 if p_str == "< 0.001" else float(p_str)
                if p_val < 0.05:
                    reg_style.append(
                        {
                            "if": {"row_index": i, "column_id": "Sig."},
                            "backgroundColor": "#bbf7d0",
                            "color": "#166534",
                            "fontWeight": "600",
                        }
                    )

        except Exception as e:
            regressie_msg = dbc.Alert(
                f"Regressie kon niet worden uitgevoerd: {e}",
                color="warning",
                className="small",
            )

        return (
            regressie_msg,
            uni_data,
            uni_cols,
            uni_style,
            reg_data,
            reg_cols,
            reg_style,
        )
