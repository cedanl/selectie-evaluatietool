"""
Genereer een evaluatierapport als PDF vanuit de dashboard data.

Gebruikt fpdf2 voor PDF-generatie en kaleido voor Plotly chart export.
"""

import io
import logging
import tempfile
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from fpdf import FPDF

from shared import (
    GROEP_VOLGORDE,
    GROEP_KLEUREN,
    CHART_BASE,
    shorten_item,
    sig_sym,
    fmt_p,
)

log = logging.getLogger(__name__)

LOGO_PATH = Path(__file__).parent / "assets" / "nko-logo.png"

BLUE = (44, 62, 80)
DARK = (51, 51, 51)
GRAY = (120, 120, 120)
LIGHT_BG = (245, 245, 245)
WHITE = (255, 255, 255)
ACCENT = (41, 128, 185)


def _fig_to_bytes(fig, width=900, height=500) -> bytes:
    return fig.to_image(format="png", width=width, height=height)


def _render_figures(
    figures: dict[str, tuple[go.Figure, int, int]],
) -> dict[str, bytes | None]:
    images = {}
    for name, (fig, w, h) in figures.items():
        try:
            images[name] = _fig_to_bytes(fig, w, h)
        except Exception:
            log.warning("Figuur '%s' kon niet worden gerenderd", name, exc_info=True)
            images[name] = None
    return images


class RapportPDF(FPDF):
    def __init__(self, opleiding: str, jaar: str):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.opleiding = opleiding
        self.jaar = jaar
        self.set_auto_page_break(auto=True, margin=20)

    def header(self):
        if self.page_no() == 1:
            return
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(*GRAY)
        self.cell(
            0,
            8,
            f"Evaluatierapport {self.opleiding} {self.jaar}",
            align="L",
        )
        self.cell(
            0, 8, f"Pagina {self.page_no()}", align="R", new_x="LMARGIN", new_y="NEXT"
        )
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(4)

    def footer(self):
        if self.page_no() == 1:
            return
        self.set_y(-15)
        self.set_font("Helvetica", "I", 7)
        self.set_text_color(*GRAY)
        self.cell(0, 10, "Evaluatietool Selectie | CEDA", align="C")

    def cover_page(self, n_per_groep: dict):
        self.add_page()

        if LOGO_PATH.exists():
            self.image(str(LOGO_PATH), x=65, y=25, w=70)
            self.ln(75)
        else:
            self.ln(60)

        self.set_font("Helvetica", "B", 32)
        self.set_text_color(*BLUE)
        self.cell(0, 14, "Evaluatierapport", align="C", new_x="LMARGIN", new_y="NEXT")
        self.cell(0, 14, "Selectie", align="C", new_x="LMARGIN", new_y="NEXT")

        self.ln(10)
        self.set_font("Helvetica", "", 18)
        self.set_text_color(*DARK)
        self.cell(0, 10, self.opleiding, align="C", new_x="LMARGIN", new_y="NEXT")

        self.ln(4)
        self.set_font("Helvetica", "", 14)
        self.set_text_color(*GRAY)
        self.cell(
            0,
            8,
            f"Selectiejaar {self.jaar}",
            align="C",
            new_x="LMARGIN",
            new_y="NEXT",
        )
        self.cell(
            0,
            8,
            f"Rapport gegenereerd op {date.today().strftime('%d-%m-%Y')}",
            align="C",
            new_x="LMARGIN",
            new_y="NEXT",
        )

        self.ln(20)
        self.set_font("Helvetica", "", 11)
        self.set_text_color(*DARK)
        total = sum(n_per_groep.values())
        self.cell(
            0,
            7,
            f"Totaal kandidaten: {total}",
            align="C",
            new_x="LMARGIN",
            new_y="NEXT",
        )
        for groep in GROEP_VOLGORDE:
            n = n_per_groep.get(groep, 0)
            self.cell(
                0,
                7,
                f"{groep}: {n} ({n / total * 100:.0f}%)"
                if total > 0
                else f"{groep}: 0",
                align="C",
                new_x="LMARGIN",
                new_y="NEXT",
            )

    def section_title(self, title: str):
        self.ln(4)
        self.set_font("Helvetica", "B", 16)
        self.set_text_color(*BLUE)
        self.cell(0, 10, title, new_x="LMARGIN", new_y="NEXT")
        y = self.get_y()
        self.set_draw_color(*ACCENT)
        self.set_line_width(0.5)
        self.line(10, y, 80, y)
        self.ln(4)

    def subsection_title(self, title: str):
        self.ln(2)
        self.set_font("Helvetica", "B", 12)
        self.set_text_color(*DARK)
        self.cell(0, 8, title, new_x="LMARGIN", new_y="NEXT")
        self.ln(1)

    def body_text(self, text: str):
        self.set_font("Helvetica", "", 10)
        self.set_text_color(*DARK)
        self.multi_cell(0, 5, text)
        self.ln(2)

    def add_image_from_bytes(self, img_bytes: bytes, w=180):
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(img_bytes)
            tmp_path = Path(f.name)
        try:
            if 297 - self.get_y() - 20 < 80:
                self.add_page()
            self.image(str(tmp_path), x=15, w=w)
            self.ln(4)
        finally:
            tmp_path.unlink(missing_ok=True)

    def _fit_text(self, text: str, col_width: float) -> str:
        if self.get_string_width(text) <= col_width - 2:
            return text
        while len(text) > 1 and self.get_string_width(text + "..") > col_width - 2:
            text = text[:-1]
        return text + ".."

    def _render_table_header(self, headers: list[str], col_widths: list[float]):
        self.set_font("Helvetica", "B", 9)
        self.set_fill_color(*BLUE)
        self.set_text_color(*WHITE)
        for i, h in enumerate(headers):
            self.cell(col_widths[i], 7, h, border=1, fill=True, align="C")
        self.ln()
        self.set_font("Helvetica", "", 9)
        self.set_text_color(*DARK)

    def add_data_table(
        self, headers: list[str], rows: list[list[str]], col_widths=None
    ):
        if self.get_y() > 240:
            self.add_page()
        if col_widths is None:
            col_widths = [190 / len(headers)] * len(headers)

        self._render_table_header(headers, col_widths)

        for ri, row in enumerate(rows):
            if self.get_y() > 270:
                self.add_page()
                self._render_table_header(headers, col_widths)

            self.set_fill_color(*(LIGHT_BG if ri % 2 == 1 else WHITE))
            for i, val in enumerate(row):
                self.cell(
                    col_widths[i],
                    6,
                    self._fit_text(str(val), col_widths[i]),
                    border=1,
                    fill=True,
                    align="C",
                )
            self.ln()
        self.ln(3)


def _build_figures(
    df: pd.DataFrame,
    scores_df: pd.DataFrame,
    scores_met_groep: pd.DataFrame,
    item_pivot: pd.DataFrame,
    score_cols: list[str],
) -> dict[str, tuple[go.Figure, int, int]]:
    figures = {}

    items_kort = sorted(scores_met_groep["item_kort"].unique())
    try:
        fig_box = px.box(
            scores_met_groep,
            x="item_kort",
            y="score",
            color="groep",
            color_discrete_map=GROEP_KLEUREN,
            category_orders={"groep": GROEP_VOLGORDE, "item_kort": items_kort},
            height=500,
            labels={"item_kort": "", "score": "Score", "groep": ""},
        )
        fig_box.update_layout(
            boxgap=0.15,
            legend=dict(orientation="h", y=1.08, yanchor="bottom"),
            xaxis_tickangle=-25,
            **CHART_BASE,
            margin=dict(t=60, b=10, l=50, r=20),
        )
        figures["boxplot"] = (fig_box, 1000, 500)
    except Exception:
        log.warning("Boxplot kon niet worden gemaakt", exc_info=True)

    try:
        corr_matrix = item_pivot[score_cols].corr().round(2)
        fig_corr = go.Figure(
            data=go.Heatmap(
                z=corr_matrix.values,
                x=corr_matrix.columns.tolist(),
                y=corr_matrix.index.tolist(),
                colorscale="RdBu_r",
                zmid=0,
                zmin=-1,
                zmax=1,
                text=corr_matrix.values,
                texttemplate="%{text}",
                textfont={"size": 10},
            )
        )
        fig_corr.update_layout(
            height=500,
            xaxis_tickangle=-30,
            **CHART_BASE,
            margin=dict(t=20, b=10, l=100, r=20),
        )
        figures["heatmap"] = (fig_corr, 900, 500)
    except Exception:
        log.warning("Heatmap kon niet worden gemaakt", exc_info=True)

    try:
        agg_verdeling = (
            df.groupby(["selectiejaar", "groep"], observed=True)
            .size()
            .reset_index(name="n")
        )
        agg_verdeling["pct"] = (
            agg_verdeling["n"]
            / agg_verdeling.groupby("selectiejaar")["n"].transform("sum")
            * 100
        ).round(1)
        fig_verdeling = px.bar(
            agg_verdeling,
            x="selectiejaar",
            y="pct",
            color="groep",
            barmode="stack",
            color_discrete_map=GROEP_KLEUREN,
            category_orders={"groep": GROEP_VOLGORDE},
            labels={"selectiejaar": "Cohort", "pct": "%", "groep": ""},
            text="n",
        )
        fig_verdeling.update_traces(texttemplate="%{text}", textposition="inside")
        fig_verdeling.update_layout(
            height=400,
            legend=dict(orientation="h", y=-0.15),
            yaxis_range=[0, 115],
            **CHART_BASE,
        )
        figures["verdeling"] = (fig_verdeling, 800, 400)
    except Exception:
        log.warning("Verdelingsdiagram kon niet worden gemaakt", exc_info=True)

    has_vo = "gem_eindcijfer_vo" in df.columns and df["gem_eindcijfer_vo"].notna().any()
    if has_vo:
        try:
            df_vo = df[df["gem_eindcijfer_vo"].notna()]
            inschr_vo = df_vo[
                df_vo["groep"].isin(
                    ["Gestart, niet naar jaar 2", "Doorgestroomd naar jaar 2"]
                )
            ]
            if "totaalscore" in inschr_vo.columns and len(inschr_vo) >= 5:
                fig_vo = px.scatter(
                    inschr_vo,
                    x="gem_eindcijfer_vo",
                    y="totaalscore",
                    color="groep",
                    color_discrete_map=GROEP_KLEUREN,
                    category_orders={"groep": GROEP_VOLGORDE},
                    labels={
                        "gem_eindcijfer_vo": "VO-eindcijfer",
                        "totaalscore": "Totaalscore",
                        "groep": "",
                    },
                    opacity=0.55,
                    height=450,
                )
                fig_vo.update_traces(marker=dict(size=6))
                fig_vo.update_layout(
                    legend=dict(orientation="h", y=1.08, yanchor="bottom"),
                    **CHART_BASE,
                )
                figures["scatter"] = (fig_vo, 800, 450)
        except Exception:
            log.warning("Scatterplot kon niet worden gemaakt", exc_info=True)

    return figures


def _build_demo_figures(
    df: pd.DataFrame,
) -> tuple[dict[str, tuple[go.Figure, int, int]], dict[str, pd.DataFrame]]:
    figures = {}
    agg_data = {}

    if "geslacht" in df.columns and df["geslacht"].notna().any():
        agg_g = (
            df.groupby(["groep", "geslacht"], observed=True)
            .size()
            .reset_index(name="n")
        )
        agg_g["pct"] = (
            agg_g["n"] / agg_g.groupby("groep")["n"].transform("sum") * 100
        ).round(1)
        agg_data["geslacht"] = agg_g
        try:
            fig_g = px.bar(
                agg_g,
                x="groep",
                y="pct",
                color="geslacht",
                barmode="stack",
                labels={"groep": "", "pct": "%", "geslacht": "Geslacht"},
                height=400,
            )
            fig_g.update_layout(legend=dict(orientation="h", y=-0.2), **CHART_BASE)
            figures["geslacht"] = (fig_g, 800, 400)
        except Exception:
            log.warning("Geslacht chart kon niet worden gemaakt", exc_info=True)

    if "herkomst" in df.columns and df["herkomst"].notna().any():
        df_h = df[df["herkomst"].notna()].assign(
            herkomst_kort=lambda d: d["herkomst"].map(
                lambda x: "Nederland" if x == "Nederland" else "niet-Nederland"
            )
        )
        agg_h = (
            df_h.groupby(["groep", "herkomst_kort"], observed=True)
            .size()
            .reset_index(name="n")
        )
        agg_h["pct"] = (
            agg_h["n"] / agg_h.groupby("groep")["n"].transform("sum") * 100
        ).round(1)
        agg_data["herkomst"] = agg_h
        try:
            fig_h = px.bar(
                agg_h,
                x="groep",
                y="pct",
                color="herkomst_kort",
                barmode="stack",
                color_discrete_map={
                    "Nederland": "#3b82f6",
                    "niet-Nederland": "#a78bfa",
                },
                labels={"groep": "", "pct": "%", "herkomst_kort": "Herkomst"},
                height=400,
            )
            fig_h.update_layout(legend=dict(orientation="h", y=-0.2), **CHART_BASE)
            figures["herkomst"] = (fig_h, 800, 400)
        except Exception:
            log.warning("Herkomst chart kon niet worden gemaakt", exc_info=True)

    if (
        "hoogste_vooropleiding" in df.columns
        and df["hoogste_vooropleiding"].notna().any()
    ):
        agg_v = (
            df.groupby(["hoogste_vooropleiding", "groep"], observed=True)
            .size()
            .reset_index(name="n")
        )
        agg_v["pct"] = (
            agg_v["n"] / agg_v.groupby("groep")["n"].transform("sum") * 100
        ).round(1)
        agg_data["vooropleiding"] = agg_v
        try:
            fig_v = px.bar(
                agg_v,
                y="hoogste_vooropleiding",
                x="pct",
                color="groep",
                barmode="group",
                orientation="h",
                color_discrete_map=GROEP_KLEUREN,
                category_orders={"groep": GROEP_VOLGORDE},
                labels={
                    "groep": "",
                    "pct": "%",
                    "hoogste_vooropleiding": "Vooropleiding",
                },
                height=400,
            )
            fig_v.update_layout(legend=dict(orientation="h", y=-0.2), **CHART_BASE)
            figures["vooropleiding"] = (fig_v, 800, 400)
        except Exception:
            log.warning("Vooropleiding chart kon niet worden gemaakt", exc_info=True)

    return figures, agg_data


def _run_regression(
    df: pd.DataFrame, item_pivot: pd.DataFrame, score_cols: list[str]
) -> tuple[list[list[str]], float | None, str | None]:
    ingeschreven = df[
        df["groep"].isin(["Gestart, niet naar jaar 2", "Doorgestroomd naar jaar 2"])
    ].copy()

    reg_rows = []
    pseudo_r2 = None
    reg_text = None

    if len(ingeschreven) < 10:
        reg_text = (
            f"Te weinig ingeschreven studenten ({len(ingeschreven)}) voor regressie."
        )
        return reg_rows, pseudo_r2, reg_text

    ingeschreven["doorgestroomd"] = (
        ingeschreven["groep"] == "Doorgestroomd naar jaar 2"
    ).astype(int)

    item_pivot_inschr = item_pivot.loc[
        item_pivot.index.isin(ingeschreven["studentnummer"])
    ].copy()

    nan_pct = item_pivot_inschr.isna().mean()
    verwijderd_nan = [c for c in score_cols if nan_pct.get(c, 1) > 0.3]
    bruikbare_cols = [c for c in score_cols if nan_pct.get(c, 1) <= 0.3]

    if len(bruikbare_cols) < 2:
        reg_text = "Te weinig bruikbare items voor regressie."
        return reg_rows, pseudo_r2, reg_text

    item_pivot_inschr[bruikbare_cols] = item_pivot_inschr[bruikbare_cols].fillna(
        item_pivot_inschr[bruikbare_cols].mean()
    )
    item_pivot_inschr = item_pivot_inschr.dropna(subset=bruikbare_cols)

    if len(item_pivot_inschr) < 10:
        reg_text = (
            f"Te weinig complete cases ({len(item_pivot_inschr)}) voor regressie."
        )
        return reg_rows, pseudo_r2, reg_text

    y = ingeschreven.set_index("studentnummer").loc[
        item_pivot_inschr.index, "doorgestroomd"
    ]
    X = item_pivot_inschr[bruikbare_cols]

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
    bruikbare_cols = list(X.columns)

    n_events = min(int(y.sum()), int(len(y) - y.sum()))
    max_predictoren = max(2, n_events // 5)
    verwijderd_epv = []
    if len(bruikbare_cols) > max_predictoren:
        import statsmodels.api as sm
        univariate_p = {}
        for col in bruikbare_cols:
            x_col = X[[col]].astype(float)
            x_col = (x_col - x_col.mean()) / x_col.std().replace(0, 1)
            try:
                m = sm.Logit(y.astype(float), sm.add_constant(x_col)).fit(disp=0, maxiter=50)
                univariate_p[col] = m.pvalues.iloc[-1]
            except Exception:
                univariate_p[col] = 1.0
        gesorteerd = sorted(bruikbare_cols, key=lambda c: univariate_p[c])
        verwijderd_epv = gesorteerd[max_predictoren:]
        bruikbare_cols = gesorteerd[:max_predictoren]
        X = X[bruikbare_cols]

    try:
        import statsmodels.api as sm

        X_z = X.astype(float).apply(
            lambda s: (s - s.mean()) / s.std() if s.std() > 0 else 0
        )
        X_const = sm.add_constant(X_z)
        model = sm.Logit(y.astype(float), X_const).fit(disp=0, maxiter=100)
        pseudo_r2 = round(float(model.prsquared), 3)

        n_door = int(y.sum())
        n_niet = int(len(y) - y.sum())
        reg_text = (
            f"n = {len(y)} (doorgestroomd: {n_door}, niet doorgestroomd: {n_niet}). "
            f"Pseudo R-kwadraat = {pseudo_r2}."
        )
        if verwijderd_nan:
            reg_text += (
                f" Items niet meegenomen (>30% ontbrekend): {', '.join(verwijderd_nan)}."
            )
        if verwijderd_collinear:
            reg_text += (
                f" Items niet meegenomen (overlap met andere items): "
                f"{', '.join(verwijderd_collinear)}."
            )
        if verwijderd_epv:
            reg_text += (
                f" Items niet meegenomen (te weinig studenten voor "
                f"{len(bruikbare_cols) + len(verwijderd_epv)} predictoren, "
                f"beperkt tot {len(bruikbare_cols)} sterkste): "
                f"{', '.join(verwijderd_epv)}."
            )

        for item_naam in bruikbare_cols:
            if item_naam not in model.params.index:
                continue
            coef = round(float(model.params[item_naam]), 3)
            odds = round(float(np.exp(model.params[item_naam])), 2)
            p = float(model.pvalues[item_naam])
            reg_rows.append([item_naam, str(coef), str(odds), fmt_p(p), sig_sym(p)])
    except Exception as e:
        reg_text = f"Regressie kon niet worden uitgevoerd: {e}"

    return reg_rows, pseudo_r2, reg_text


def _interpret_r(r_val: float) -> str:
    r = abs(r_val)
    if r < 0.10:
        return "verwaarloosbaar"
    if r < 0.30:
        return "zwak"
    if r < 0.50:
        return "matig"
    if r < 0.70:
        return "sterk"
    return "zeer sterk"


def genereer_rapport(df: pd.DataFrame, scores_df: pd.DataFrame) -> bytes:
    opleiding = ""
    if "opleiding" in df.columns and df["opleiding"].notna().any():
        opleiding = str(df["opleiding"].dropna().iloc[0])

    jaar = ""
    if "selectiejaar" in df.columns:
        jaren = sorted(df["selectiejaar"].dropna().unique())
        jaar = ", ".join(str(int(j)) for j in jaren)

    counts = df["groep"].value_counts()
    n_per_groep = {groep: int(counts.get(groep, 0)) for groep in GROEP_VOLGORDE}

    # -- Shared data --
    df_groep = df[["studentnummer", "groep"]].drop_duplicates()
    scores_met_groep = scores_df.merge(df_groep, on="studentnummer", how="inner")
    scores_met_groep["groep"] = pd.Categorical(
        scores_met_groep["groep"], categories=GROEP_VOLGORDE, ordered=True
    )
    scores_met_groep["item_kort"] = scores_met_groep["item"].apply(shorten_item)

    item_pivot = scores_met_groep.pivot_table(
        index="studentnummer", columns="item_kort", values="score", aggfunc="mean"
    )
    score_cols = list(item_pivot.columns)

    instrumenten = sorted(scores_df["instrument"].unique())
    items = sorted(scores_df["item"].unique())

    gem_tabel = (
        scores_met_groep.groupby(["groep", "item_kort"], observed=True)["score"]
        .agg(["mean", "std", "count"])
        .round(2)
        .reset_index()
    )

    reg_rows, pseudo_r2, reg_text = _run_regression(df, item_pivot, score_cols)

    has_vo = "gem_eindcijfer_vo" in df.columns and df["gem_eindcijfer_vo"].notna().any()
    cor_rows = []
    if has_vo:
        df_vo = df[df["gem_eindcijfer_vo"].notna()].copy()
        all_items = sorted(scores_df["item"].unique())
        if "totaalscore" in df_vo.columns:
            sub = df_vo[["gem_eindcijfer_vo", "totaalscore"]].dropna()
            r_val = (
                float(sub["gem_eindcijfer_vo"].corr(sub["totaalscore"]))
                if len(sub) >= 2
                else None
            )
            if r_val is not None and not np.isnan(r_val):
                cor_rows.append(["Totaalscore", f"{r_val:.3f}", _interpret_r(r_val)])
        for item_name in all_items:
            item_scores = scores_df[scores_df["item"] == item_name][
                ["studentnummer", "score"]
            ]
            merged = df_vo[["studentnummer", "gem_eindcijfer_vo"]].merge(
                item_scores, on="studentnummer"
            )
            r_val = (
                float(merged["gem_eindcijfer_vo"].corr(merged["score"]))
                if len(merged) >= 2
                else None
            )
            if r_val is not None and not np.isnan(r_val):
                cor_rows.append(
                    [shorten_item(item_name), f"{r_val:.3f}", _interpret_r(r_val)]
                )

    # -- Build and render all charts --
    figures = _build_figures(df, scores_df, scores_met_groep, item_pivot, score_cols)
    demo_figures, demo_agg = _build_demo_figures(df)
    figures.update(demo_figures)
    images = _render_figures(figures)

    # -- Assemble PDF --
    pdf = RapportPDF(opleiding=opleiding, jaar=jaar)

    pdf.cover_page(n_per_groep)

    # Inleiding
    pdf.add_page()
    pdf.section_title("1. Inleiding")

    n_door = n_per_groep.get("Doorgestroomd naar jaar 2", 0)
    n_uitval = n_per_groep.get("Gestart, niet naar jaar 2", 0)
    n_niet = n_per_groep.get("Niet gestart", 0)
    total = len(df)

    pdf.body_text(
        f"Dit rapport evalueert de selectieprocedure van {opleiding} "
        f"voor selectiejaar {jaar}. Het doel is om te bekijken of de selectie "
        f"goed voorspelt welke studenten het eerste jaar succesvol afronden. "
        f"Met andere woorden: scoren studenten die uiteindelijk doorstromen "
        f"ook hoger bij de selectie dan studenten die stoppen?"
    )

    pdf.body_text(f"De data bevat {total} kandidaten, verdeeld over drie groepen:")

    pdf.body_text(
        f"  1. Niet gestart ({n_niet} kandidaten): deze personen staan niet in "
        f"de inschrijvingsdata (1CHO). Ze zijn niet toegelaten, of wel "
        f"geselecteerd maar uiteindelijk nooit begonnen aan de opleiding."
    )
    pdf.body_text(
        f"  2. Gestart, niet naar jaar 2 ({n_uitval} studenten): deze studenten "
        f"zijn wel begonnen, maar zijn na het eerste jaar gestopt of overgestapt. "
        f"Ze hebben in 1CHO een inschrijving voor jaar 1, maar niet voor jaar 2."
    )
    pdf.body_text(
        f"  3. Doorgestroomd naar jaar 2 ({n_door} studenten): deze studenten "
        f"zijn begonnen en hebben het eerste jaar succesvol doorlopen. Ze hebben "
        f"zowel een jaar 1 als een jaar 2 inschrijving in 1CHO."
    )

    pdf.subsection_title("Waarom kijken we soms alleen naar twee groepen?")
    pdf.body_text(
        "Bij sommige analyses in dit rapport (zoals de regressie en het "
        "VO-eindcijfer) gebruiken we alleen de studenten die daadwerkelijk "
        "begonnen zijn aan de opleiding. We vergelijken dan alleen groep 2 "
        "(gestart, niet naar jaar 2) met groep 3 (doorgestroomd naar jaar 2). "
        "Groep 1 (niet gestart) laten we in die gevallen buiten beschouwing."
    )
    pdf.body_text(
        "De reden is dat we voor de niet-gestarte kandidaten geen "
        "studiesuccesgegevens hebben. We weten niet of ze het goed zouden "
        "hebben gedaan, want ze zijn nooit begonnen. Bovendien zitten in "
        "deze groep zowel afgewezen kandidaten als kandidaten die zelf "
        "hebben afgezien. Dat maakt het lastig om hun selectiescores zinvol "
        "te vergelijken met studenten die wel zijn gestart."
    )
    pdf.body_text(
        "Bij de selectiescores (boxplots) en demografische gegevens laten we "
        "alle drie de groepen wel zien, zodat je het volledige plaatje hebt."
    )

    # Section 2: Dataset overview
    pdf.add_page()
    pdf.section_title("2. Dataset overzicht")
    pdf.body_text(
        f"De selectiedata bevat {len(instrumenten)} instrument(en) met in "
        f"totaal {len(items)} item(s). Een instrument is bijvoorbeeld een "
        f"toets of een gesprek, en de items zijn de onderdelen daarvan. "
        f"Hieronder staat welke instrumenten en items er in de data zitten."
    )

    pdf.subsection_title("Instrumenten en items")
    inst_rows = []
    for inst in instrumenten:
        inst_items = scores_df[scores_df["instrument"] == inst]["item"].unique()
        inst_rows.append(
            [
                inst,
                str(len(inst_items)),
                ", ".join(shorten_item(i) for i in sorted(inst_items)),
            ]
        )
    pdf.add_data_table(
        ["Instrument", "Items", "Itemnamen"],
        inst_rows,
        col_widths=[45, 15, 130],
    )

    pdf.subsection_title("Groepsverdeling")
    pdf.body_text(
        "Hieronder staat hoeveel kandidaten er in elke groep zitten. Dit geeft "
        "een eerste indruk van de verhoudingen: hoeveel procent van de "
        "kandidaten is daadwerkelijk doorgestroomd?"
    )
    groep_rows = []
    for groep in GROEP_VOLGORDE:
        n = n_per_groep[groep]
        pct = f"{n / total * 100:.1f}%" if total > 0 else "0%"
        groep_rows.append([groep, str(n), pct])
    pdf.add_data_table(
        ["Groep", "n", "%"],
        groep_rows,
        col_widths=[90, 30, 30],
    )

    # Section 3: Selectiescores per groep
    pdf.add_page()
    pdf.section_title("3. Selectiescores per groep")
    pdf.body_text(
        "In deze sectie bekijken we de selectiescores per groep. Het idee is "
        "simpel: als de selectie goed werkt, dan zouden studenten die "
        "uiteindelijk doorstromen gemiddeld hoger moeten scoren dan studenten "
        "die stoppen of niet gestart zijn."
    )
    pdf.body_text(
        "De boxplot hieronder toont de verdeling van scores per item, "
        "uitgesplitst naar de drie groepen. Elke box laat zien waar de "
        "middelste 50% van de scores ligt. De lijn in het midden van de box "
        "is de mediaan (het middelste getal). Als de groene boxen (doorstromers) "
        "duidelijk hoger liggen dan de oranje en grijze, dan heeft dat item "
        "voorspellende waarde."
    )

    if images.get("boxplot"):
        pdf.add_image_from_bytes(images["boxplot"])
    else:
        pdf.body_text("[Boxplot kon niet worden gegenereerd]")

    pdf.subsection_title("Gemiddelden per groep")
    pdf.body_text(
        "De tabel hieronder toont het gemiddelde (Gem.), de standaarddeviatie "
        "(SD) en het aantal kandidaten (n) per groep per item. De "
        "standaarddeviatie geeft aan hoe verspreid de scores zijn: een hoge SD "
        "betekent dat de scores ver uit elkaar liggen."
    )
    gem_rows = []
    for _, r in gem_tabel.iterrows():
        gem_rows.append(
            [
                str(r["groep"]),
                str(r["item_kort"]),
                str(r["mean"]),
                str(r["std"]) if pd.notna(r["std"]) else "-",
                str(int(r["count"])),
            ]
        )
    pdf.add_data_table(
        ["Groep", "Item", "Gem.", "SD", "n"],
        gem_rows,
        col_widths=[65, 55, 25, 25, 20],
    )

    # Section 4: Samenhang en regressie
    pdf.add_page()
    pdf.section_title("4. Samenhang en regressie")

    pdf.subsection_title("Correlatiematrix")
    pdf.body_text(
        "De correlatiematrix laat zien hoe sterk de selectie-items onderling "
        "samenhangen. Een correlatie (r) loopt van -1 tot +1. Als twee items "
        "hoog correleren, dan meten ze grotendeels hetzelfde. Dat is niet per "
        "se slecht, maar het betekent wel dat ze weinig extra informatie "
        "toevoegen ten opzichte van elkaar."
    )
    pdf.body_text(
        "Vuistregels voor het interpreteren van correlaties (Cohen, 1988): "
        "r < 0.10 is verwaarloosbaar, r van 0.10 tot 0.30 is zwak (de items "
        "meten grotendeels iets anders), r van 0.30 tot 0.50 is matig (er is "
        "wat overlap, maar ook een unieke bijdrage), r van 0.50 tot 0.70 is "
        "sterk (er is veel overlap, het is de vraag of beide items nodig zijn), "
        "en r boven 0.70 is zeer sterk (de items meten vrijwel hetzelfde)."
    )
    pdf.body_text(
        "Bij selectie-instrumenten is een mix van zwakke tot matige correlaties "
        "(r tussen 0.10 en 0.50) wenselijk. Dat betekent dat de items "
        "verschillende dingen meten en elkaar aanvullen, zonder te veel te "
        "overlappen."
    )
    if images.get("heatmap"):
        pdf.add_image_from_bytes(images["heatmap"])
    else:
        pdf.body_text("[Correlatiematrix kon niet worden gegenereerd]")

    pdf.subsection_title("Logistische regressie")
    pdf.body_text(
        "Met logistische regressie kijken we welke selectie-items de "
        "doorstroom naar jaar 2 het beste voorspellen. De analyse houdt "
        "rekening met alle items tegelijk, zodat je kunt zien welk item een "
        "eigen bijdrage levert bovenop de andere items."
    )
    pdf.body_text(
        "Let op: voor deze analyse gebruiken we alleen de studenten die "
        "daadwerkelijk begonnen zijn (groep 2 en 3). De niet-gestarte "
        "kandidaten (groep 1) zitten hier niet in, omdat we voor hen geen "
        "studiesuccesgegevens hebben."
    )
    pdf.body_text(
        "In de tabel hieronder staat per item de coefficient (hoe sterk het "
        "effect is), de odds ratio (hoeveel keer groter de kans op doorstroom "
        "wordt per punt hoger), de p-waarde (hoe zeker we zijn dat het effect "
        "echt is) en de significantie. Een p-waarde kleiner dan 0.05 geldt als "
        "statistisch significant. Drie sterretjes (***) betekent p < 0.001, "
        "twee sterretjes (**) betekent p < 0.01, een sterretje (*) betekent "
        "p < 0.05, en 'ns' betekent niet significant."
    )
    if reg_text:
        pdf.body_text(reg_text)
    if reg_rows:
        pdf.add_data_table(
            ["Item", "Coeff.", "Odds ratio", "p-waarde", "Sig."],
            reg_rows,
            col_widths=[60, 30, 30, 35, 35],
        )

    # Section 5: Demografisch profiel
    pdf.add_page()
    pdf.section_title("5. Demografisch profiel")
    pdf.body_text(
        "In deze sectie bekijken we de achtergrondkenmerken van de kandidaten "
        "per groep. Het gaat om gegevens zoals geslacht, herkomst en "
        "vooropleiding. Deze data komt uit 1CHO (het landelijke "
        "studentregistratiesysteem) en is daarom alleen beschikbaar voor "
        "studenten die daadwerkelijk ingeschreven zijn geweest."
    )
    pdf.body_text(
        "Het doel van deze sectie is om te kijken of de selectie eerlijk "
        "uitpakt voor verschillende groepen. Als er grote verschillen zijn "
        "in de verdeling van achtergrondkenmerken tussen doorstromers en "
        "uitvallers, dan kan dat aanleiding zijn om de selectieprocedure "
        "nader te onderzoeken."
    )

    if images.get("verdeling"):
        pdf.subsection_title("Verdeling per cohort")
        pdf.body_text(
            "Het gestapelde staafdiagram laat zien hoe de drie groepen verdeeld "
            "zijn per cohort (selectiejaar). De getallen in de staven geven het "
            "absolute aantal kandidaten weer."
        )
        pdf.add_image_from_bytes(images["verdeling"])

    if images.get("geslacht"):
        pdf.subsection_title("Geslacht per groep")
        pdf.body_text(
            "Hieronder staat de verdeling van geslacht binnen elke groep. "
            "Grote verschillen tussen groepen kunnen erop wijzen dat de "
            "selectie voor een bepaald geslacht anders uitpakt."
        )
        pdf.add_image_from_bytes(images["geslacht"])

    if "geslacht" in demo_agg:
        ges_rows = []
        for _, r in demo_agg["geslacht"].iterrows():
            ges_rows.append(
                [str(r["groep"]), str(r["geslacht"]), str(r["n"]), f"{r['pct']}%"]
            )
        pdf.add_data_table(
            ["Groep", "Geslacht", "n", "%"],
            ges_rows,
            col_widths=[70, 40, 30, 30],
        )

    if images.get("herkomst"):
        pdf.subsection_title("Herkomst per groep")
        pdf.body_text(
            "De herkomst van studenten is vereenvoudigd tot twee categorieen: "
            "Nederland en niet-Nederland. Dit geeft een eerste indruk van "
            "diversiteit binnen de groepen."
        )
        pdf.add_image_from_bytes(images["herkomst"])

    if "herkomst" in demo_agg:
        h_rows = []
        for _, r in demo_agg["herkomst"].iterrows():
            h_rows.append(
                [str(r["groep"]), str(r["herkomst_kort"]), str(r["n"]), f"{r['pct']}%"]
            )
        pdf.add_data_table(
            ["Groep", "Herkomst", "n", "%"],
            h_rows,
            col_widths=[65, 55, 30, 30],
        )

    if images.get("vooropleiding"):
        pdf.subsection_title("Vooropleiding per groep")
        pdf.body_text(
            "De vooropleiding geeft aan wat het hoogst behaalde diploma van "
            "de student is voordat deze aan de opleiding begon. Denk aan "
            "VWO, HBO-propedeuse, of een ander diploma."
        )
        pdf.add_image_from_bytes(images["vooropleiding"])

    if "vooropleiding" in demo_agg:
        vo_rows = []
        for _, r in demo_agg["vooropleiding"].iterrows():
            vo_rows.append(
                [
                    str(r["groep"]),
                    str(r["hoogste_vooropleiding"]),
                    str(r["n"]),
                    f"{r['pct']}%",
                ]
            )
        pdf.add_data_table(
            ["Groep", "Vooropleiding", "n", "%"],
            vo_rows,
            col_widths=[65, 55, 30, 30],
        )

    # Section 6: VO-eindcijfer
    if has_vo:
        pdf.add_page()
        pdf.section_title("6. VO-eindcijfer vs selectiescores")
        pdf.body_text(
            "Het gemiddeld eindcijfer van het voortgezet onderwijs (VO) is een "
            "onafhankelijke meting die uit 1CHO komt. Het is interessant om te "
            "kijken of de selectiescores samenhangen met dit cijfer."
        )
        pdf.body_text(
            "Een lage samenhang (r dicht bij 0) is positief: het betekent dat "
            "het selectie-item iets anders meet dan schoolprestaties. Een hoge "
            "samenhang kan erop wijzen dat het item vooral meet wat het "
            "VO-diploma al vertelt, en dus weinig nieuwe informatie toevoegt."
        )
        pdf.body_text(
            "Let op: voor deze analyse gebruiken we alleen de studenten die "
            "daadwerkelijk ingeschreven zijn geweest, omdat het VO-eindcijfer "
            "uit 1CHO komt en dus alleen beschikbaar is voor ingeschrevenen."
        )
        if cor_rows:
            pdf.add_data_table(
                ["Item", "r (Pearson)", "Sterkte"],
                cor_rows,
                col_widths=[100, 40, 40],
            )
        if images.get("scatter"):
            pdf.body_text(
                "De scatterplot hieronder toont het verband tussen het "
                "VO-eindcijfer en de totaalscore. Elk punt is een student. "
                "Hoe meer de punten op een lijn liggen, hoe sterker het verband."
            )
            pdf.add_image_from_bytes(images["scatter"])

    # Samenvatting
    section_nr = 7 if has_vo else 6
    pdf.add_page()
    pdf.section_title(f"{section_nr}. Samenvatting")

    pdf.body_text(
        "Hieronder staan de belangrijkste bevindingen uit dit rapport samengevat."
    )

    bullets = []

    if total > 0:
        bullets.append(
            f"Van de {total} kandidaten zijn er {n_door} doorgestroomd naar jaar 2 "
            f"({n_door / total * 100:.0f}%), {n_uitval} gestart maar niet doorgestroomd "
            f"({n_uitval / total * 100:.0f}%), en {n_niet} niet gestart "
            f"({n_niet / total * 100:.0f}%)."
        )

    if reg_rows:
        sig_items = [r[0] for r in reg_rows if r[4] != "ns"]
        ns_items = [r[0] for r in reg_rows if r[4] == "ns"]
        if sig_items:
            bullets.append(
                f"Significante voorspellers van doorstroom: {', '.join(sig_items)}. "
                f"Dit zijn de items die een statistisch aantoonbaar verband "
                f"hebben met doorstroom naar jaar 2."
            )
        if ns_items:
            bullets.append(
                f"Geen significante bijdrage: {', '.join(ns_items)}. "
                f"Deze items hebben geen statistisch aantoonbaar verband met "
                f"doorstroom, rekening houdend met de andere items."
            )
        if pseudo_r2 is not None:
            if pseudo_r2 < 0.05:
                kracht = "zeer beperkte"
            elif pseudo_r2 < 0.15:
                kracht = "beperkte"
            elif pseudo_r2 < 0.30:
                kracht = "matige"
            else:
                kracht = "substantiele"
            bullets.append(
                f"Het regressiemodel heeft {kracht} voorspellende kracht "
                f"(pseudo R-kwadraat = {pseudo_r2}). Hoe hoger dit getal "
                f"(maximaal 1.0), hoe beter de selectie-items samen de "
                f"doorstroom voorspellen."
            )

    if has_vo and cor_rows:
        high_r = [r for r in cor_rows if abs(float(r[1])) > 0.4]
        low_r = [r for r in cor_rows if abs(float(r[1])) < 0.15]
        if high_r:
            bullets.append(
                f"Sterke samenhang met VO-eindcijfer: "
                f"{', '.join(r[0] + ' (r=' + r[1] + ')' for r in high_r)}. "
                f"Deze items overlappen met wat het schooldiploma al vertelt."
            )
        if low_r:
            bullets.append(
                f"Lage samenhang met VO-eindcijfer: "
                f"{', '.join(r[0] + ' (r=' + r[1] + ')' for r in low_r)}. "
                f"Deze items meten iets anders dan schoolprestaties, wat "
                f"positief is voor de selectie."
            )

    n_ingeschreven = n_door + n_uitval
    if n_ingeschreven < 30:
        bullets.append(
            f"Let op: het aantal ingeschreven studenten is klein (n={n_ingeschreven}). "
            f"Bij kleine aantallen zijn statistische analyses minder "
            f"betrouwbaar. Wees daarom voorzichtig met het trekken van "
            f"conclusies."
        )

    for bullet in bullets:
        pdf.body_text(f"  {bullet}")

    buf = io.BytesIO()
    pdf.output(buf)
    return buf.getvalue()
