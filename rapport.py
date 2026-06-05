"""
Genereer een evaluatierapport als PDF vanuit de dashboard data.

Gebruikt fpdf2 voor PDF-generatie en kaleido voor Plotly chart export.
"""

import io
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

BLUE = (44, 62, 80)
DARK = (51, 51, 51)
GRAY = (120, 120, 120)
LIGHT_BG = (245, 245, 245)
WHITE = (255, 255, 255)
ACCENT = (41, 128, 185)


def _fig_to_bytes(fig, width=900, height=500) -> bytes:
    return fig.to_image(format="png", width=width, height=height)


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
                self.cell(col_widths[i], 6, str(val), border=1, fill=True, align="C")
            self.ln()
        self.ln(3)


def genereer_rapport(df: pd.DataFrame, scores_df: pd.DataFrame) -> bytes:
    opleiding = ""
    if "opleiding" in df.columns and df["opleiding"].notna().any():
        opleiding = str(df["opleiding"].dropna().iloc[0])

    jaar = ""
    if "selectiejaar" in df.columns:
        jaren = sorted(df["selectiejaar"].dropna().unique())
        jaar = ", ".join(str(int(j)) for j in jaren)

    pdf = RapportPDF(opleiding=opleiding, jaar=jaar)

    counts = df["groep"].value_counts()
    n_per_groep = {groep: int(counts.get(groep, 0)) for groep in GROEP_VOLGORDE}

    # -- Cover --
    pdf.cover_page(n_per_groep)

    # -- Section 1: Dataset overview --
    pdf.add_page()
    pdf.section_title("1. Dataset overzicht")

    instrumenten = sorted(scores_df["instrument"].unique())
    items = sorted(scores_df["item"].unique())
    pdf.body_text(
        f"Dit rapport beschrijft de selectieresultaten van {opleiding} "
        f"(selectiejaar {jaar}). De data bevat {len(instrumenten)} "
        f"instrument(en) met in totaal {len(items)} item(s), "
        f"gemeten bij {len(df)} kandidaten."
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
    groep_rows = []
    total = len(df)
    for groep in GROEP_VOLGORDE:
        n = n_per_groep[groep]
        pct = f"{n / total * 100:.1f}%" if total > 0 else "0%"
        groep_rows.append([groep, str(n), pct])
    pdf.add_data_table(
        ["Groep", "n", "%"],
        groep_rows,
        col_widths=[90, 30, 30],
    )

    # -- Section 2: Selectiescores per groep --
    pdf.add_page()
    pdf.section_title("2. Selectiescores per groep")
    pdf.body_text(
        "Per selectie-item worden de scores van de drie groepen vergeleken. "
        "Hogere scores bij doorstromers dan bij uitvallers signaleren "
        "voorspellende waarde van het selectie-instrument."
    )

    df_groep = df[["studentnummer", "groep"]].drop_duplicates()
    scores_met_groep = scores_df.merge(df_groep, on="studentnummer", how="inner")
    scores_met_groep["groep"] = pd.Categorical(
        scores_met_groep["groep"], categories=GROEP_VOLGORDE, ordered=True
    )
    scores_met_groep["item_kort"] = scores_met_groep["item"].apply(shorten_item)

    try:
        items_kort = sorted(scores_met_groep["item_kort"].unique())
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
        pdf.add_image_from_bytes(_fig_to_bytes(fig_box, width=1000, height=500))
    except Exception:
        pdf.body_text("[Boxplot kon niet worden gegenereerd]")

    pdf.subsection_title("Gemiddelden per groep")
    gem_tabel = (
        scores_met_groep.groupby(["groep", "item_kort"], observed=True)["score"]
        .agg(["mean", "std", "count"])
        .round(2)
        .reset_index()
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

    # -- Section 3: Samenhang en regressie --
    pdf.add_page()
    pdf.section_title("3. Samenhang en regressie")

    item_pivot = scores_met_groep.pivot_table(
        index="studentnummer", columns="item_kort", values="score", aggfunc="mean"
    )
    score_cols = list(item_pivot.columns)

    pdf.subsection_title("Correlatiematrix")
    pdf.body_text(
        "Hoe sterk hangen de selectie-items onderling samen? "
        "Hoge correlaties betekenen dat twee items grotendeels hetzelfde meten."
    )

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
        pdf.add_image_from_bytes(_fig_to_bytes(fig_corr, width=900, height=500))
    except Exception:
        pdf.body_text("[Correlatiematrix kon niet worden gegenereerd]")

    pdf.subsection_title("Logistische regressie")
    pdf.body_text(
        "Logistische regressie met doorstroom naar jaar 2 als uitkomst. "
        "Per item: hoe sterk voorspelt het doorstroom, rekening houdend met "
        "de andere items?"
    )

    ingeschreven = df[
        df["groep"].isin(["Gestart, niet naar jaar 2", "Doorgestroomd naar jaar 2"])
    ].copy()

    reg_rows = []
    pseudo_r2 = None
    if len(ingeschreven) >= 10:
        ingeschreven["doorgestroomd"] = (
            ingeschreven["groep"] == "Doorgestroomd naar jaar 2"
        ).astype(int)

        item_pivot_inschr = item_pivot.loc[
            item_pivot.index.isin(ingeschreven["studentnummer"])
        ].dropna()

        if len(item_pivot_inschr) >= 10:
            y = ingeschreven.set_index("studentnummer").loc[
                item_pivot_inschr.index, "doorgestroomd"
            ]
            X = item_pivot_inschr[score_cols]

            try:
                import statsmodels.api as sm

                X_const = sm.add_constant(X.astype(float))
                model = sm.Logit(y.astype(float), X_const).fit(disp=0, maxiter=100)
                pseudo_r2 = round(float(model.prsquared), 3)

                n_door = int(y.sum())
                n_niet = int(len(y) - y.sum())
                pdf.body_text(
                    f"n = {len(y)} (doorgestroomd: {n_door}, niet doorgestroomd: {n_niet}). "
                    f"Pseudo R-kwadraat = {pseudo_r2}."
                )

                for item_naam in score_cols:
                    if item_naam not in model.params.index:
                        continue
                    coef = round(float(model.params[item_naam]), 3)
                    odds = round(float(np.exp(model.params[item_naam])), 2)
                    p = float(model.pvalues[item_naam])
                    reg_rows.append(
                        [
                            item_naam,
                            str(coef),
                            str(odds),
                            fmt_p(p),
                            sig_sym(p),
                        ]
                    )
            except Exception as e:
                pdf.body_text(f"Regressie kon niet worden uitgevoerd: {e}")
    else:
        pdf.body_text(
            f"Te weinig ingeschreven studenten ({len(ingeschreven)}) voor regressie."
        )

    if reg_rows:
        pdf.add_data_table(
            ["Item", "Coeff.", "Odds ratio", "p-waarde", "Sig."],
            reg_rows,
            col_widths=[60, 30, 30, 35, 35],
        )

    # -- Section 4: Demografisch profiel --
    pdf.add_page()
    pdf.section_title("4. Demografisch profiel")
    pdf.body_text(
        "Verdeling van achtergrondkenmerken per groep. "
        "Data komt uit 1CHO en is alleen beschikbaar voor ingeschreven studenten."
    )

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
        pdf.add_image_from_bytes(_fig_to_bytes(fig_verdeling, width=800, height=400))
    except Exception:
        pdf.body_text("[Verdelingsdiagram kon niet worden gegenereerd]")

    if "geslacht" in df.columns and df["geslacht"].notna().any():
        pdf.subsection_title("Geslacht per groep")
        ges_agg = (
            df.groupby(["groep", "geslacht"], observed=True)
            .size()
            .reset_index(name="n")
        )
        ges_agg["pct"] = (
            ges_agg["n"] / ges_agg.groupby("groep")["n"].transform("sum") * 100
        ).round(1)
        ges_rows = []
        for _, r in ges_agg.iterrows():
            ges_rows.append(
                [str(r["groep"]), str(r["geslacht"]), str(r["n"]), f"{r['pct']}%"]
            )
        pdf.add_data_table(
            ["Groep", "Geslacht", "n", "%"],
            ges_rows,
            col_widths=[70, 40, 30, 30],
        )

    if (
        "hoogste_vooropleiding" in df.columns
        and df["hoogste_vooropleiding"].notna().any()
    ):
        pdf.subsection_title("Vooropleiding per groep")
        vo_agg = (
            df.groupby(["groep", "hoogste_vooropleiding"], observed=True)
            .size()
            .reset_index(name="n")
        )
        vo_agg["pct"] = (
            vo_agg["n"] / vo_agg.groupby("groep")["n"].transform("sum") * 100
        ).round(1)
        vo_rows = []
        for _, r in vo_agg.iterrows():
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

    # -- Section 5: VO-eindcijfer --
    has_vo = "gem_eindcijfer_vo" in df.columns and df["gem_eindcijfer_vo"].notna().any()
    if has_vo:
        pdf.add_page()
        pdf.section_title("5. VO-eindcijfer vs selectiescores")
        pdf.body_text(
            "Het VO-eindcijfer is een onafhankelijke meting uit 1CHO. "
            "Een lage samenhang (r dicht bij 0) betekent dat het selectie-item "
            "iets anders meet dan schoolprestaties."
        )

        df_vo = df[df["gem_eindcijfer_vo"].notna()].copy()
        cor_rows = []
        all_items = sorted(scores_df["item"].unique())

        if "totaalscore" in df_vo.columns:
            sub = df_vo[["gem_eindcijfer_vo", "totaalscore"]].dropna()
            r_val = (
                float(sub["gem_eindcijfer_vo"].corr(sub["totaalscore"]))
                if len(sub) >= 2
                else None
            )
            if r_val is not None and not np.isnan(r_val):
                cor_rows.append(["Totaalscore", f"{r_val:.3f}"])

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
                cor_rows.append([shorten_item(item_name), f"{r_val:.3f}"])

        if cor_rows:
            pdf.add_data_table(
                ["Item", "r (Pearson)"],
                cor_rows,
                col_widths=[120, 50],
            )

        try:
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
                pdf.add_image_from_bytes(_fig_to_bytes(fig_vo, width=800, height=450))
        except Exception:
            pass

    # -- Section 6: Samenvatting --
    section_nr = 6 if has_vo else 5
    pdf.add_page()
    pdf.section_title(f"{section_nr}. Samenvatting")

    bullets = []

    total = len(df)
    n_door = n_per_groep.get("Doorgestroomd naar jaar 2", 0)
    n_uitval = n_per_groep.get("Gestart, niet naar jaar 2", 0)
    n_niet = n_per_groep.get("Niet gestart", 0)
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
                f"Significante voorspellers van doorstroom: {', '.join(sig_items)}."
            )
        if ns_items:
            bullets.append(f"Geen significante bijdrage: {', '.join(ns_items)}.")
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
                f"(pseudo R-kwadraat = {pseudo_r2})."
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
                f"Deze items meten iets anders dan schoolprestaties."
            )

    n_ingeschreven = n_door + n_uitval
    if n_ingeschreven < 30:
        bullets.append(
            f"Let op: het aantal ingeschreven studenten is klein (n={n_ingeschreven}). "
            f"De statistische analyses zijn daardoor minder betrouwbaar."
        )

    for bullet in bullets:
        pdf.body_text(f"  {bullet}")

    buf = io.BytesIO()
    pdf.output(buf)
    return buf.getvalue()
