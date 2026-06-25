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
    PERSPECTIEF_DOORSTROOM,
    binair_kleur_map,
    shorten_item,
    schaal_grenzen,
    bucket_per_item,
    meta_per_item,
    grenzen_van_label,
    sig_sym,
    fmt_p,
    vergelijk_succes_per_item,
    VERGELIJKING_KOLOMMEN,
    toets_verschil_per_item,
    VERSCHIL_KOLOMMEN,
    genereer_bevindingen,
    DEMO_DIMENSIES,
    demografie_scores,
    bereken_univariaat,
    chi2_per_dimensie,
)

log = logging.getLogger(__name__)

LOGO_PATH = Path(__file__).parent / "assets" / "nko-logo.png"

BLUE = (44, 62, 80)
DARK = (51, 51, 51)
GRAY = (120, 120, 120)
LIGHT_BG = (245, 245, 245)
WHITE = (255, 255, 255)
ACCENT = (41, 128, 185)


def _hex_to_rgb(hex_kleur: str) -> tuple[int, int, int]:
    """Zet een '#rrggbb' kleur om naar een (r, g, b)-tuple voor fpdf."""
    h = hex_kleur.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


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
        self.cell(0, 10, "Selectie Evaluatietool | CEDA", align="C")

    def cover_page(self, n_per_groep: dict, n_totaal: int):
        self.add_page()

        if LOGO_PATH.exists():
            self.image(str(LOGO_PATH), x=65, y=25, w=70)
            self.ln(75)
        else:
            self.ln(60)

        self.set_font("Helvetica", "B", 32)
        self.set_text_color(*BLUE)
        self.cell(0, 14, "Selectie", align="C", new_x="LMARGIN", new_y="NEXT")
        self.cell(0, 14, "Evaluatierapport", align="C", new_x="LMARGIN", new_y="NEXT")

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

        self.ln(6)
        self.set_font("Helvetica", "I", 11)
        self.set_text_color(*GRAY)
        self.cell(
            0,
            7,
            "Ontwikkeld in samenwerking met CEDA (Centre of Educational Data Analytics)",
            align="C",
            new_x="LMARGIN",
            new_y="NEXT",
        )

        self.ln(14)
        self.set_font("Helvetica", "", 11)
        self.set_text_color(*DARK)
        self.cell(
            0,
            7,
            f"Totaal kandidaten: {n_totaal}",
            align="C",
            new_x="LMARGIN",
            new_y="NEXT",
        )
        for groep, n in n_per_groep.items():
            self.cell(
                0,
                7,
                f"{groep}: {n} ({n / n_totaal * 100:.0f}%)"
                if n_totaal > 0
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

    def groep_header(
        self, groep: str, n: int, kleur_map: dict[str, str] | None = None
    ) -> None:
        """Gekleurde kop boven een groepstabel, met het kandidaataantal erbij."""
        if kleur_map is None:
            kleur_map = GROEP_KLEUREN
        if self.get_y() > 225:
            self.add_page()
        self.ln(2)
        y = self.get_y()
        self.set_fill_color(*_hex_to_rgb(kleur_map.get(groep, "#94a3b8")))
        self.rect(10, y + 0.5, 4, 5, style="F")
        self.set_xy(16, y)
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(*DARK)
        self.cell(0, 6, f"{groep} ({n} kandidaten):", new_x="LMARGIN", new_y="NEXT")
        self.ln(1)

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


def _bovengrens_van_label(label: str) -> float:
    """Bovengrens uit een 'onder-boven' schaallabel, voor oplopend sorteren."""
    grenzen = grenzen_van_label(label)
    return grenzen[1] if grenzen else float("inf")


def _build_figures(
    df: pd.DataFrame,
    scores_df: pd.DataFrame,
    scores_met_groep: pd.DataFrame,
    item_pivot: pd.DataFrame,
    score_cols: list[str],
    groep_kleuren: dict[str, str] | None = None,
    groep_volgorde: list[str] | None = None,
) -> dict[str, tuple[go.Figure, int, int]]:
    if groep_kleuren is None:
        groep_kleuren = GROEP_KLEUREN
    if groep_volgorde is None:
        groep_volgorde = GROEP_VOLGORDE
    figures = {}

    # Eén boxplot per schaal: items met een ander bereik horen niet op dezelfde
    # y-as. De buckets komen uit dezelfde bron als het dashboard.
    box_df = scores_met_groep.assign(
        bereik=scores_met_groep["item"].map(bucket_per_item(scores_df))
    )
    for bereik in sorted(box_df["bereik"].dropna().unique(), key=_bovengrens_van_label):
        subset = box_df[box_df["bereik"] == bereik]
        items_kort = sorted(subset["item_kort"].unique())
        try:
            fig_box = px.box(
                subset,
                x="item_kort",
                y="score",
                color="groep",
                color_discrete_map=groep_kleuren,
                category_orders={"groep": groep_volgorde, "item_kort": items_kort},
                height=500,
                labels={"item_kort": "", "score": "Score", "groep": ""},
            )
            fig_box.update_layout(
                boxgap=0.15,
                legend=dict(orientation="h", y=1.08, yanchor="bottom"),
                xaxis_tickangle=-25,
                **CHART_BASE,
                margin=dict(t=70, b=10, l=50, r=20),
                title=dict(text=f"Schaal {bereik}", x=0.01, font=dict(size=13)),
            )
            grenzen = schaal_grenzen(subset["score"])
            if grenzen is not None:
                fig_box.update_yaxes(range=list(grenzen))
            figures[f"boxplot::{bereik}"] = (fig_box, 1000, 500)
        except Exception:
            log.warning(
                "Boxplot voor schaal %s kon niet worden gemaakt", bereik, exc_info=True
            )

    try:
        corr_matrix = item_pivot[score_cols].corr().round(3)
        # Spiegelt de correlatietab: de matrix is symmetrisch, dus we tonen alleen
        # de onderste driehoek (inclusief diagonaal) om dubbelingen te vermijden.
        boven = np.triu(np.ones(corr_matrix.shape, dtype=bool), k=1)
        z = corr_matrix.to_numpy(dtype=float).copy()
        z[boven] = np.nan
        tekst = [
            [
                "" if boven[i, j] else f"{corr_matrix.iat[i, j]:.2f}"
                for j in range(z.shape[1])
            ]
            for i in range(z.shape[0])
        ]
        fig_corr = go.Figure(
            data=go.Heatmap(
                z=z,
                x=corr_matrix.columns.tolist(),
                y=corr_matrix.index.tolist(),
                colorscale="RdBu_r",
                zmid=0,
                zmin=-1,
                zmax=1,
                text=tekst,
                texttemplate="%{text}",
                textfont={"size": 10},
                hoverongaps=False,
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

    return figures


def _run_regression(
    df: pd.DataFrame,
    item_pivot: pd.DataFrame,
    score_cols: list[str],
    perspectief: dict | None = None,
) -> tuple[list[list[str]], float | None, str | None]:
    if perspectief is None:
        perspectief = PERSPECTIEF_DOORSTROOM
    populatie = df[df["groep"].isin(perspectief["populatie"])].copy()

    reg_rows = []
    pseudo_r2 = None
    reg_text = None

    if len(populatie) < 10:
        reg_text = f"Te weinig studenten ({len(populatie)}) voor regressie."
        return reg_rows, pseudo_r2, reg_text

    populatie["uitkomst"] = (
        populatie["groep"].isin(perspectief["positief_groepen"]).astype(int)
    )

    item_pivot_pop = item_pivot.loc[
        item_pivot.index.isin(populatie["studentnummer"])
    ].copy()

    nan_pct = item_pivot_pop.isna().mean()
    verwijderd_nan = [c for c in score_cols if nan_pct.get(c, 1) > 0.3]
    bruikbare_cols = [c for c in score_cols if nan_pct.get(c, 1) <= 0.3]

    if len(bruikbare_cols) < 2:
        reg_text = "Te weinig bruikbare items voor regressie."
        return reg_rows, pseudo_r2, reg_text

    item_pivot_pop[bruikbare_cols] = item_pivot_pop[bruikbare_cols].fillna(
        item_pivot_pop[bruikbare_cols].mean()
    )
    item_pivot_pop = item_pivot_pop.dropna(subset=bruikbare_cols)

    if len(item_pivot_pop) < 10:
        reg_text = f"Te weinig complete cases ({len(item_pivot_pop)}) voor regressie."
        return reg_rows, pseudo_r2, reg_text

    y = populatie.set_index("studentnummer").loc[item_pivot_pop.index, "uitkomst"]
    X = item_pivot_pop[bruikbare_cols]

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
                m = sm.Logit(y.astype(float), sm.add_constant(x_col)).fit(
                    disp=0, maxiter=50
                )
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
            lambda s: (
                (s - s.mean()) / s.std() if s.std() > 0 else pd.Series(0, index=s.index)
            )
        )
        X_const = sm.add_constant(X_z)
        model = sm.Logit(y.astype(float), X_const).fit(disp=0, maxiter=100)
        pseudo_r2 = round(float(model.prsquared), 3)

        n_pos = int(y.sum())
        n_neg = int(len(y) - y.sum())
        pos_label = perspectief["positief_label"].lower()
        neg_label = perspectief["negatief_label"].lower()
        reg_text = (
            f"n = {len(y)} ({pos_label}: {n_pos}, {neg_label}: {n_neg}). "
            f"Pseudo R-kwadraat = {pseudo_r2}."
        )
        if verwijderd_nan:
            reg_text += f" Items niet meegenomen (>30% ontbrekend): {', '.join(verwijderd_nan)}."
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


def _beleidsconclusies(bevindingen: dict, model_stats: dict | None) -> list[str]:
    """Beleidsgerichte vervolgstappen, gekoppeld aan de bevindingen. Spiegelt het
    'Vervolgstappen voor beleid'-blok op de 'Wat valt op'-tab van het dashboard, zodat
    het rapport dezelfde conclusie trekt: een significant verschil betekent
    voorspellende waarde, geen verschil betekent dat de selectie studiesucces niet
    voorspelt."""

    def aantal(n, ev, mv):
        return f"{n} {ev if n == 1 else mv}"

    def namen(items):
        items = list(items)
        if len(items) == 1:
            return items[0]
        return ", ".join(items[:-1]) + " en " + items[-1]

    def kracht(r2):
        if r2 < 0.05:
            return "zeer beperkt"
        if r2 < 0.15:
            return "beperkt"
        if r2 < 0.30:
            return "matig"
        return "substantieel"

    stappen = []
    n_valide = len(bevindingen.get("validiteit", []))
    if n_valide:
        stappen.append(
            f"De verschiltoets vindt {aantal(n_valide, 'item', 'items')} waarop "
            "doorstromers duidelijk anders scoorden dan uitvallers. Dat is een "
            "aanwijzing dat deze items studiesucces helpen voorspellen. Beleidsmatig: "
            "behoud ze of laat ze zwaarder meewegen, en bevestig het patroon eerst op "
            "een volgend cohort voordat je de procedure aanpast."
        )
    else:
        stappen.append(
            "De verschiltoets vindt geen enkel item waarop doorstromers en uitvallers "
            "significant verschillen. Beleidsmatig betekent dit dat de selectie in deze "
            "data geen studiesucces voorspelt: ga na of de items iets anders meten dat "
            "je bewust wilt behouden (motivatie, passendheid), of dat de procedure "
            "eenvoudiger en goedkoper kan."
        )

    if model_stats and model_stats.get("pseudo_r2") is not None:
        r2 = model_stats["pseudo_r2"]
        sig = model_stats.get("sig_items", [])
        if sig:
            ww = "levert" if len(sig) == 1 else "leveren"
            eigen = f"Vooral {namen(sig)} {ww} een eigen bijdrage bovenop de rest. "
        else:
            eigen = "Geen item springt eruit als je ze samen bekijkt. "
        stappen.append(
            f"Alle items samen verklaren een {kracht(r2)} deel van het verschil in "
            f"studiesucces (regressie, pseudo R-kwadraat = {r2:.2f}). "
            + eigen
            + "Dit gezamenlijke model is bij kleine groepen wankel, dus leun voor "
            "beleid vooral op de verschiltoets."
        )

    n_fair = len(bevindingen.get("fairness", []))
    if n_fair:
        stappen.append(
            f"Bij {aantal(n_fair, 'item', 'items')} scoorden achtergrondgroepen "
            "(geslacht, vooropleiding) verschillend. Beleidsmatig: onderzoek of dat "
            "verschil inhoudelijk te rechtvaardigen is of op onbedoelde vertekening "
            "wijst."
        )

    n_corr = len(bevindingen.get("correlatie", []))
    if n_corr:
        stappen.append(
            "De correlatie vindt "
            f"{aantal(n_corr, 'sterke samenhang', 'sterke samenhangen')} tussen items "
            "die deels hetzelfde meten. Beleidsmatig: je kunt er een laten vallen om de "
            "selectie korter en goedkoper te maken zonder veel informatie te verliezen."
        )

    stappen.append(
        "Herhaal de analyse met een nieuw cohort voordat je de procedure echt aanpast. "
        "Een enkel jaar is een momentopname, zeker bij kleine groepen."
    )
    stappen.append(
        "Combineer deze cijfers met vakkennis en eerder onderzoek. Doorstroom naar "
        "jaar 2 is maar een van de manieren om studiesucces te meten."
    )
    return stappen


def genereer_rapport(
    df: pd.DataFrame, scores_df: pd.DataFrame, perspectief: dict | None = None
) -> bytes:
    if perspectief is None:
        perspectief = PERSPECTIEF_DOORSTROOM
    opleiding = ""
    if "opleiding" in df.columns and df["opleiding"].notna().any():
        opleiding = str(df["opleiding"].dropna().iloc[0])

    jaar = ""
    if "selectiejaar" in df.columns:
        jaren = sorted(df["selectiejaar"].dropna().unique())
        jaar = ", ".join(str(int(j)) for j in jaren)

    pos_label = perspectief["positief_label"]
    neg_label = perspectief["negatief_label"]
    binaire_volgorde = [pos_label, neg_label]
    binaire_kleuren = binair_kleur_map(perspectief)

    pop = df[df["groep"].isin(perspectief["populatie"])]
    binair_col = (
        pop["groep"]
        .isin(perspectief["positief_groepen"])
        .map({True: pos_label, False: neg_label})
    )
    n_per_groep = binair_col.value_counts().reindex(binaire_volgorde, fill_value=0)
    n_per_groep = {groep: int(n_per_groep[groep]) for groep in binaire_volgorde}

    # -- Shared data --
    # scores_origineel behoudt de 4-level groep voor analyse-functies die
    # positief/negatief groepen matchen op de oorspronkelijke labels.
    df_groep = pop[["studentnummer", "groep"]].drop_duplicates()
    scores_origineel = scores_df.merge(df_groep, on="studentnummer", how="inner")
    scores_origineel["groep"] = pd.Categorical(
        scores_origineel["groep"], categories=GROEP_VOLGORDE, ordered=True
    )
    scores_origineel["item_kort"] = scores_origineel["item"].apply(shorten_item)

    # scores_met_groep heeft de binaire labels voor weergave (boxplots, tabellen).
    scores_met_groep = scores_origineel.copy()
    scores_met_groep["groep"] = (
        scores_met_groep["groep"]
        .isin(perspectief["positief_groepen"])
        .map({True: pos_label, False: neg_label})
    )
    scores_met_groep["groep"] = pd.Categorical(
        scores_met_groep["groep"], categories=binaire_volgorde, ordered=True
    )

    item_pivot = scores_met_groep.pivot_table(
        index="studentnummer", columns="item_kort", values="score", aggfunc="mean"
    )
    score_cols = list(item_pivot.columns)

    instrumenten = sorted(scores_df["instrument"].unique())
    items = sorted(scores_df["item"].unique())

    gem_tabel = (
        scores_met_groep.groupby(["groep", "item_kort"], observed=True)["score"]
        .agg(["mean", "std"])
        .round(2)
        .reset_index()
        .merge(meta_per_item(scores_met_groep), on="item_kort", how="left")
        .sort_values(["groep", "instrument", "criterium", "item_kort"])
    )

    reg_rows, pseudo_r2, reg_text = _run_regression(
        df, item_pivot, score_cols, perspectief=perspectief
    )

    # -- Build and render all charts --
    figures = _build_figures(
        df,
        scores_df,
        scores_met_groep,
        item_pivot,
        score_cols,
        groep_kleuren=binaire_kleuren,
        groep_volgorde=binaire_volgorde,
    )
    images = _render_figures(figures)

    # Demografische verschiltoetsen per dimensie (tabellen, geen figuren).
    demo_toetsen = {}
    for dim in DEMO_DIMENSIES:
        demo_scores = demografie_scores(df, scores_df, dim)
        if demo_scores is not None:
            demo_toetsen[dim["label"]] = toets_verschil_per_item(
                demo_scores, dim["kolom"]
            )

    # Correlatiematrix (voor conclusies)
    corr_pivot = scores_df.pivot_table(
        index="studentnummer", columns="item", values="score", aggfunc="mean"
    )
    corr_matrix = None
    if not corr_pivot.empty:
        corr_pivot.columns = [shorten_item(c) for c in corr_pivot.columns]
        corr_matrix = corr_pivot.corr().round(3)

    # Univariate regressie per item (voor conclusies)
    univariaat_data = bereken_univariaat(df, scores_df, perspectief)

    # Model stats uit de reeds gedraaide regressie
    model_stats = None
    if pseudo_r2 is not None:
        sig_items_model = [r[0] for r in reg_rows if r[4] != "ns"]
        model_stats = {"pseudo_r2": pseudo_r2, "sig_items": sig_items_model}

    demo_verdeling = chi2_per_dimensie(df, perspectief)

    # -- Assemble PDF --
    pdf = RapportPDF(opleiding=opleiding, jaar=jaar)

    total = len(df)
    n_pos = n_per_groep.get(pos_label, 0)
    n_neg = n_per_groep.get(neg_label, 0)
    n_pop = n_pos + n_neg

    groepsgroottes = {
        "n_totaal": total,
        "n_populatie": n_pop,
        "n_positief": n_pos,
        "n_negatief": n_neg,
    }

    pdf.cover_page(n_per_groep, total)

    # Inleiding
    pdf.add_page()
    pdf.section_title("1. Inleiding")

    pdf.body_text(
        f"Dit rapport evalueert de selectieprocedure van {opleiding} "
        f"voor selectiejaar {jaar}. Het doel is om te bekijken of de selectie "
        f"goed voorspelt welke studenten het eerste jaar succesvol afronden. "
        f"Met andere woorden: scoren studenten die uiteindelijk slagen "
        f"ook hoger bij de selectie dan studenten die stoppen?"
    )

    pdf.body_text(
        f"De data bevat {total} kandidaten. Dit rapport vergelijkt twee "
        f"groepen op basis van de uitkomstmaat '{perspectief['label']}':"
    )
    pdf.body_text(f"  - {pos_label} ({n_pos} studenten)")
    pdf.body_text(f"  - {neg_label} ({n_neg} studenten)")
    pdf.body_text(perspectief["beschrijving"])

    # Section 2: Dataset overview
    pdf.add_page()
    pdf.section_title("2. Dataset overzicht")
    pdf.body_text(
        f"De selectiedata bevat {len(instrumenten)} instrument(en) met in "
        f"totaal {len(items)} item(s). Een instrument is bijvoorbeeld een "
        f"toets of een gesprek; de items zijn de afzonderlijke scores binnen "
        f"zo'n instrument. Hieronder staat welke instrumenten en items er in "
        f"de data zitten."
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
        f"Hieronder staat de verdeling van kandidaten op basis van "
        f"'{perspectief['label']}'."
    )
    groep_rows = []
    for groep in binaire_volgorde:
        n = n_per_groep.get(groep, 0)
        pct = f"{n / n_pop * 100:.1f}%" if n_pop > 0 else "0%"
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
        f"simpel: als de selectie goed werkt, dan zou de groep '{pos_label}' "
        f"gemiddeld hoger moeten scoren dan de groep '{neg_label}'."
    )
    pdf.body_text(
        "De boxplots hieronder tonen de verdeling van scores per item, "
        "uitgesplitst naar de twee groepen. Items zijn gegroepeerd per "
        "meetschaal, zodat een item op een 1-5 schaal niet op dezelfde as wordt "
        "geplet als een item op een 0-100 schaal. Elke box laat zien waar de "
        "middelste 50% van de scores ligt. De lijn in het midden van de box "
        f"is de mediaan (het middelste getal). Als de groene boxen ('{pos_label}') "
        "duidelijk hoger liggen dan de oranje, dan heeft dat item "
        "voorspellende waarde."
    )

    boxplot_keys = [k for k in images if k.startswith("boxplot::") and images[k]]
    if boxplot_keys:
        for key in boxplot_keys:
            pdf.add_image_from_bytes(images[key])
    else:
        pdf.body_text("[Boxplot kon niet worden gegenereerd]")

    pdf.subsection_title("Gemiddelden per groep")
    pdf.body_text(
        "Per groep staat hieronder het gemiddelde (Gem.) en de standaarddeviatie "
        "(SD) per item, met het instrument en criterium waar het item bij hoort. "
        "De standaarddeviatie geeft aan hoe verspreid de scores zijn: een hoge SD "
        "betekent dat de scores ver uit elkaar liggen. Het aantal kandidaten "
        "staat bij de groepsnaam."
    )
    for groep in binaire_volgorde:
        sub = gem_tabel[gem_tabel["groep"] == groep]
        if sub.empty:
            continue
        pdf.groep_header(groep, n_per_groep.get(groep, 0), kleur_map=binaire_kleuren)
        groep_rows = [
            [
                str(r["instrument"]),
                str(r["criterium"]),
                str(r["item_kort"]),
                str(r["mean"]),
                str(r["std"]) if pd.notna(r["std"]) else "-",
            ]
            for _, r in sub.iterrows()
        ]
        pdf.add_data_table(
            ["Instrument", "Criterium", "Item", "Gem.", "SD"],
            groep_rows,
            col_widths=[55, 50, 45, 20, 20],
        )

    pdf.subsection_title(f"Verschiltoets: scoort '{pos_label}' hoger?")
    pdf.body_text(
        f"De tabel hieronder vergelijkt per item de groep '{pos_label}' met "
        f"de groep '{neg_label}'. {perspectief['beschrijving']}"
    )
    pdf.body_text(
        "De toets is een Mann-Whitney "
        "U, die past bij de ordinale en vaak scheve schalen van selectie-items. "
        "De kolom Effectgrootte is de rank-biseriale correlatie van -1 tot "
        f"+1: positief betekent dat de groep '{pos_label}' hoger scoorde. "
        "Vuistregels (Cohen, 1988): r < 0.10 verwaarloosbaar, 0.10-0.30 zwak, "
        "0.30-0.50 matig, boven 0.50 sterk. Het 95%-BI geeft de onzekerheid "
        "rond de effectgrootte; loopt het door 0, dan is zelfs de richting "
        "onzeker. Een p-waarde onder 0.05 geldt als significant. De items "
        "staan op effectgrootte gesorteerd, de sterkste voorspellers bovenaan."
    )
    vergelijking = vergelijk_succes_per_item(scores_origineel, perspectief=perspectief)
    if vergelijking.empty:
        pdf.body_text(
            "Er zijn te weinig gestarte studenten om de groepen te vergelijken."
        )
    else:
        verg_rows = [
            [str(rij[kolom]) for kolom in VERGELIJKING_KOLOMMEN]
            for _, rij in vergelijking.iterrows()
        ]
        pdf.add_data_table(
            ["Item", "Succes n", "Geen n", "Effect r", "Sterkte", "95%-BI", "p"],
            verg_rows,
            col_widths=[50, 20, 20, 22, 26, 32, 20],
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

    uitkomst_label = perspectief["label"].lower()
    uitkomst_kort = pos_label.lower()
    pdf.subsection_title("Logistische regressie")
    pdf.body_text(
        f"Met logistische regressie kijken we welke selectie-items {uitkomst_label} "
        "het beste voorspellen. De analyse houdt "
        "rekening met alle items tegelijk, zodat je kunt zien welk item een "
        "eigen bijdrage levert bovenop de andere items."
    )
    pdf.body_text(
        f"Let op: voor deze analyse gebruiken we de populatie die past bij "
        f"de uitkomstmaat '{perspectief['label']}' ({n_pop} studenten)."
    )
    pdf.body_text(
        "In de tabel hieronder staat per item de coefficient (hoe sterk het "
        f"effect is), de odds ratio (hoeveel keer groter de kans op {uitkomst_kort} "
        "wordt per standaarddeviatie stijging), de p-waarde (hoe zeker we zijn "
        "dat het effect echt is) en de significantie. Een p-waarde kleiner dan "
        "0.05 geldt als statistisch significant. Drie sterretjes (***) betekent "
        "p < 0.001, twee sterretjes (**) betekent p < 0.01, een sterretje (*) "
        "betekent p < 0.05, en 'ns' betekent niet significant."
    )
    pdf.body_text(
        "Scores worden genormaliseerd (z-scores) voor de regressie. Daardoor "
        "zijn de coefficienten en odds ratios vergelijkbaar tussen items met "
        "verschillende schalen. Een odds ratio van 2.0 betekent: als de score "
        "op dit item een standaarddeviatie hoger is, verdubbelt de kans op "
        f"{uitkomst_kort}."
    )
    pdf.body_text(
        "Bij weinig studenten kan het model niet alle items tegelijk betrouwbaar "
        "schatten. Als vuistregel zijn er minimaal 5 studenten in de kleinste "
        "groep nodig per item in het model. Bij minder selecteert de tool "
        "automatisch de items die individueel het sterkst samenhangen met "
        f"{uitkomst_kort}. De overige items worden niet meegenomen en staan vermeld "
        "in de samenvatting hieronder."
    )
    if reg_text:
        pdf.body_text(reg_text)
    if reg_rows:
        pdf.add_data_table(
            ["Item", "Coeff.", "Odds ratio", "p-waarde", "Sig."],
            reg_rows,
            col_widths=[60, 30, 30, 35, 35],
        )

    # Section 5: Selectiescores naar achtergrond
    pdf.add_page()
    pdf.section_title("5. Selectiescores naar achtergrond")
    pdf.body_text(
        "In deze sectie kijken we of de selectiescores verschillen tussen "
        "studenten met een andere achtergrond (geslacht, vooropleiding). "
        "Een systematisch verschil op een instrument kan wijzen op "
        "onbedoelde vertekening: het instrument meet dan deels iets dat met de "
        "achtergrond samenhangt in plaats van met geschiktheid."
    )
    pdf.body_text(
        "De achtergrondgegevens komen uit 1CHO en zijn alleen bekend voor "
        "ingeschreven studenten. Deze analyse vergelijkt dus binnen de "
        "ingeschreven groep, niet onder alle sollicitanten. Per item toetsen we "
        "met een Kruskal-Wallis of de groepen anders scoren. De effectgrootte is "
        "epsilon-kwadraat (0-1): onder 0.01 verwaarloosbaar, 0.01-0.06 zwak, "
        "0.06-0.14 matig, boven 0.14 sterk. De kolom 'Verschil' toont welke groep "
        "het hoogst scoort. Een p-waarde onder 0.05 is significant. Groepen met "
        "minder dan vijf studenten vallen weg."
    )

    if not demo_toetsen:
        pdf.body_text("Er zijn geen achtergrondgegevens beschikbaar om op te splitsen.")
    for label, tabel in demo_toetsen.items():
        pdf.subsection_title(label)
        if tabel.empty:
            pdf.body_text("Te weinig gegevens voor een toets.")
            continue
        demo_rows = [
            [str(r[kolom]) for kolom in VERSCHIL_KOLOMMEN] for _, r in tabel.iterrows()
        ]
        pdf.add_data_table(
            ["Item", "n", "Verschil", "Effect", "Sterkte", "p"],
            demo_rows,
            col_widths=[50, 15, 45, 25, 30, 25],
        )

    # Conclusies
    section_nr = 6
    pdf.add_page()
    pdf.section_title(f"{section_nr}. Conclusies")
    pdf.body_text(
        "De conclusies hieronder volgen rechtstreeks uit de toetsen in dit "
        "rapport: er is niets toegevoegd dat niet uit een effectgrootte of "
        "p-waarde volgt. Lees ze met de steekproefgrootte in het achterhoofd."
    )

    succes_tabel = vergelijk_succes_per_item(scores_origineel, perspectief=perspectief)
    bevindingen = genereer_bevindingen(
        succes_tabel,
        demo_toetsen,
        perspectief=perspectief,
        correlatie_matrix=corr_matrix,
        univariaat_data=univariaat_data,
        model_stats=model_stats,
        groepsgroottes=groepsgroottes,
        demografie_verdeling=demo_verdeling,
    )

    if bevindingen["samenvatting"]:
        for regel in bevindingen["samenvatting"]:
            pdf.body_text(regel)

    pdf.subsection_title("Verschiltoets per item")
    for regel in bevindingen["validiteit"]:
        pdf.body_text(f"  {regel}")
    if not bevindingen["validiteit"]:
        pdf.body_text(
            "  Geen enkel item laat een opvallend verschil zien tussen "
            "geslaagde en uitgevallen studenten."
        )

    if bevindingen["regressie"]:
        pdf.subsection_title("Univariate regressie")
        for regel in bevindingen["regressie"]:
            pdf.body_text(f"  {regel}")

    if bevindingen["model"]:
        pdf.subsection_title("Gezamenlijk model")
        for regel in bevindingen["model"]:
            pdf.body_text(f"  {regel}")

    if bevindingen["correlatie"]:
        pdf.subsection_title("Samenhang tussen items")
        for regel in bevindingen["correlatie"]:
            pdf.body_text(f"  {regel}")

    pdf.subsection_title("Verschillen tussen groepen (eerlijkheid)")
    for regel in bevindingen["fairness"]:
        pdf.body_text(f"  {regel}")
    if not bevindingen["fairness"]:
        pdf.body_text(
            "  Geen achtergrondgegevens beschikbaar om groepen te vergelijken."
        )

    if bevindingen["demografie"]:
        pdf.subsection_title("Demografie en uitkomst")
        for regel in bevindingen["demografie"]:
            pdf.body_text(f"  {regel}")

    pdf.subsection_title("Vervolgstappen voor beleid")
    pdf.body_text(
        "De punten hieronder volgen uit de bevindingen en zijn bedoeld als richting "
        "voor het gesprek, niet als kant-en-klaar oordeel."
    )
    for regel in _beleidsconclusies(bevindingen, model_stats):
        pdf.body_text(f"  - {regel}")

    buf = io.BytesIO()
    pdf.output(buf)
    return buf.getvalue()
