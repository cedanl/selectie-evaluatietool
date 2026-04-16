"""
Evaluatietool: selectie & studiesucces dashboard

Draai met: uv run streamlit run app.py
Data aanmaken: uv run python scripts/maak_data.py
"""

from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from scipy import stats

DATA_PATH = Path("data/synthetic/gekoppeld.parquet")

GROEP_VOLGORDE = [
    "Niet gestart",
    "Gestart, niet naar jaar 2",
    "Doorgestroomd naar jaar 2",
]
GROEP_KLEUREN = {
    "Niet gestart":              "#94a3b8",
    "Gestart, niet naar jaar 2": "#f97316",
    "Doorgestroomd naar jaar 2": "#22c55e",
}

# Verkorte labels voor op de x-as (Plotly ondersteunt <br> als regelafbreking)
GROEP_XTICKLABELS = [
    "Niet<br>gestart",
    "Gestart, niet<br>naar jaar 2",
    "Doorgestroomd<br>naar jaar 2",
]

def fix_xas_labels(fig):
    """Vervangt de groepsnamen op de x-as door versies met regelafbreking."""
    fig.update_xaxes(
        tickmode="array",
        tickvals=GROEP_VOLGORDE,
        ticktext=GROEP_XTICKLABELS,
    )
    return fig

st.set_page_config(
    page_title="Evaluatietool Selectie",
    layout="wide",
)

st.title("Evaluatietool Selectie")
st.caption("B Gezondheidswetenschappen — DEMO Hogeschool")


@st.cache_data
def laad_data() -> pd.DataFrame:
    if not DATA_PATH.exists():
        st.error("Data niet gevonden. Draai eerst: `uv run python scripts/maak_data.py`")
        st.stop()
    df = pd.read_parquet(DATA_PATH)
    df["groep"] = pd.Categorical(df["groep"], categories=GROEP_VOLGORDE, ordered=True)
    return df


data = laad_data()

# --- Sidebar ---
st.sidebar.title("Filters")
cohort_keuzes = ["Alle cohorten"] + sorted(data["selectiejaar"].unique().tolist())
cohort = st.sidebar.selectbox("Cohort", cohort_keuzes)

geslacht_keuzes = ["Alle"] + sorted(data["geslacht"].unique().tolist())
geslacht = st.sidebar.selectbox("Geslacht", geslacht_keuzes)

vooropl_keuzes = ["Alle"] + sorted(data["hoogste_vooropleiding"].unique().tolist())
vooropleiding = st.sidebar.selectbox("Vooropleiding", vooropl_keuzes)


def filter_data(df: pd.DataFrame, incl_cohort: bool = True) -> pd.DataFrame:
    if incl_cohort and cohort != "Alle cohorten":
        df = df[df["selectiejaar"] == int(cohort)]
    if geslacht != "Alle":
        df = df[df["geslacht"] == geslacht]
    if vooropleiding != "Alle":
        df = df[df["hoogste_vooropleiding"] == vooropleiding]
    return df


st.sidebar.divider()
st.sidebar.caption("Synthetische voorbeelddata.")


# --- Tabs ---
tab_scores, tab_overzicht, tab_demo, tab_aantallen = st.tabs([
    "Selectiescores", "Verdeling", "Demografisch", "Aantallen"
])


# ── Tab 1: Selectiescores (hoofdfocus) ──────────────────────────────────────
with tab_scores:
    st.header("Selectiescores per uitkomstgroep")
    st.caption(
        "Hogere scores bij doorstromers dan bij uitvallers signaleren predictieve validiteit "
        "van het selectie-instrument. Let op overlap: een instrument dat groepen niet onderscheidt "
        "heeft weinig voorspellende waarde."
    )

    df = filter_data(data)

    SCORES = {
        "totaalscore":     "Totaalscore",
        "interview_score": "Interview",
        "motivatiescore":  "Motivatiebrief",
        "cv_score":        "CV",
    }

    # Totaalscore: groot, volledig breed
    fig_totaal = go.Figure()
    for groep in GROEP_VOLGORDE:
        subset = df[df["groep"] == groep]["totaalscore"].dropna()
        fig_totaal.add_trace(go.Violin(
            y=subset,
            name=groep,
            box_visible=True,
            meanline_visible=True,
            fillcolor=GROEP_KLEUREN[groep],
            line_color=GROEP_KLEUREN[groep],
            opacity=0.7,
            hoverinfo="skip",
        ))
    fig_totaal.update_layout(
        title="Totaalscore (gewogen: interview 50%, motivatie 30%, CV 20%)",
        yaxis_title="Score (1-10)",
        height=500,
        showlegend=False,
        violingap=0.3,
    )
    fix_xas_labels(fig_totaal)
    st.plotly_chart(fig_totaal, width="stretch")

    st.divider()

    # Drie losse instrumenten naast elkaar
    col1, col2, col3 = st.columns(3)

    for col, (var, label) in zip(
        [col1, col2, col3],
        [("interview_score", "Interview"), ("motivatiescore", "Motivatiebrief"), ("cv_score", "CV")]
    ):
        fig = go.Figure()
        for groep in GROEP_VOLGORDE:
            subset = df[df["groep"] == groep][var].dropna()
            fig.add_trace(go.Violin(
                y=subset,
                name=groep,
                box_visible=True,
                meanline_visible=True,
                fillcolor=GROEP_KLEUREN[groep],
                line_color=GROEP_KLEUREN[groep],
                opacity=0.7,
                showlegend=False,
                hoverinfo="skip",
            ))
        fig.update_layout(
            title=label,
            yaxis_title="Score (1-10)",
            height=420,
            violingap=0.3,
            margin=dict(t=50, b=10),
        )
        fix_xas_labels(fig)
        col.plotly_chart(fig, width="stretch")

    # Puntenwolk
    st.divider()
    st.subheader("Puntenwolk selectiescores")

    score_opties = {
        "Interview":      "interview_score",
        "Motivatiebrief": "motivatiescore",
        "CV":             "cv_score",
        "Totaalscore":    "totaalscore",
    }

    col_x, col_y, _ = st.columns([2, 2, 4])
    x_label = col_x.selectbox("X-as", list(score_opties.keys()), index=0, key="scatter_x")
    y_label = col_y.selectbox("Y-as", list(score_opties.keys()), index=1, key="scatter_y")
    x_var = score_opties[x_label]
    y_var = score_opties[y_label]

    fig_scatter = px.scatter(
        df[df["groep"].notna()],
        x=x_var, y=y_var,
        color="groep",
        color_discrete_map=GROEP_KLEUREN,
        category_orders={"groep": GROEP_VOLGORDE},
        labels={x_var: x_label, y_var: y_label, "groep": ""},
        opacity=0.55,
        height=520,
    )
    fig_scatter.update_traces(marker=dict(size=6))
    fig_scatter.update_layout(legend=dict(orientation="h", y=-0.15))
    st.plotly_chart(fig_scatter, width="stretch")

    # Gemiddelden tabel
    st.divider()
    st.subheader("Gemiddelden per groep")
    tabel_scores = (
        df
        .groupby("groep", observed=True)[list(SCORES.keys())]
        .agg(["mean", "std"])
        .round(2)
    )
    tabel_scores.columns = pd.MultiIndex.from_tuples(
        [(SCORES[var], "gem." if stat == "mean" else "SD") for var, stat in tabel_scores.columns]
    )
    st.dataframe(tabel_scores, width="stretch")

    # Mann-Whitney U: gestart niet naar jaar 2 vs doorgestroomd naar jaar 2
    a_groep = df[df["groep"] == "Gestart, niet naar jaar 2"]
    b_groep = df[df["groep"] == "Doorgestroomd naar jaar 2"]

    def sig_sym(p):
        return "***" if p < 0.001 else "**" if p < 0.01 else "*" if p < 0.05 else "ns"

    def fmt_p(p):
        return "< 0.001" if p < 0.001 else f"{p:.3f}"

    sig_rijen = []
    for var, label in SCORES.items():
        a = a_groep[var].dropna()
        b = b_groep[var].dropna()
        if len(a) >= 2 and len(b) >= 2:
            _, p = stats.mannwhitneyu(a, b, alternative="two-sided")
            sig_rijen.append({"Score": label, "p-waarde": fmt_p(p), "Sig.": sig_sym(p)})
        else:
            sig_rijen.append({"Score": label, "p-waarde": "n.v.t.", "Sig.": ""})

    st.caption(
        "Mann-Whitney U toets: gestart niet naar jaar 2 vs doorgestroomd naar jaar 2. "
        "ns = niet significant (p≥0.05).  \\* p<0.05  \\*\\* p<0.01  \\*\\*\\* p<0.001"
    )
    st.dataframe(pd.DataFrame(sig_rijen), hide_index=True, width="stretch")


# ── Tab 2: Verdeling ─────────────────────────────────────────────────────────
with tab_overzicht:
    st.header("Verdeling per groep")
    filter_labels = [cohort if cohort != "Alle cohorten" else "alle cohorten"]
    if geslacht != "Alle":
        filter_labels.append(geslacht)
    if vooropleiding != "Alle":
        filter_labels.append(vooropleiding)
    st.caption(f"Gefilterd op: {', '.join(filter_labels)}")
    df = filter_data(data)

    col1, col2, col3 = st.columns(3)
    for col, groep in zip([col1, col2, col3], GROEP_VOLGORDE):
        n = (df["groep"] == groep).sum()
        pct = n / len(df) * 100 if len(df) > 0 else 0
        col.metric(groep, n, f"{pct:.0f}%", delta_color="off")

    st.divider()

    agg = (
        filter_data(data, incl_cohort=False)
        .groupby(["selectiejaar", "groep"], observed=True)
        .size()
        .reset_index(name="n")
    )
    totals = agg.groupby("selectiejaar")["n"].transform("sum")
    agg["pct"] = (agg["n"] / totals * 100).round(1)

    fig = px.bar(
        agg, x="selectiejaar", y="pct", color="groep",
        barmode="stack",
        color_discrete_map=GROEP_KLEUREN,
        category_orders={"groep": GROEP_VOLGORDE},
        labels={"selectiejaar": "Cohort", "pct": "Percentage (%)", "groep": ""},
        custom_data=["n"],
    )
    fig.update_traces(hovertemplate="%{fullData.name}<br>%{y:.1f}%  (n=%{customdata[0]})<extra></extra>")
    fig.update_layout(height=500, legend=dict(orientation="h", y=-0.15))
    st.plotly_chart(fig, width="stretch")


# ── Tab 3: Demografisch ───────────────────────────────────────────────────────
with tab_demo:
    st.header("Demografisch profiel per groep")
    df = filter_data(data)

    col_g, col_h = st.columns(2)

    with col_g:
        agg_g = (
            df.groupby(["groep", "geslacht"], observed=True)
            .size().reset_index(name="n")
        )
        totals_g = agg_g.groupby("groep")["n"].transform("sum")
        agg_g["pct"] = (agg_g["n"] / totals_g * 100).round(1)
        fig3 = px.bar(
            agg_g, x="groep", y="pct", color="geslacht",
            barmode="stack",
            labels={"groep": "", "pct": "%", "geslacht": "Geslacht"},
            title="Geslacht per groep (%)",
        )
        fig3.update_layout(height=460, legend=dict(orientation="h", y=-0.2))
        fix_xas_labels(fig3)
        st.plotly_chart(fig3, width="stretch")

    with col_h:
        agg_h = (
            df.assign(herkomst_kort=df["herkomst"].map(
                lambda x: "Nederland" if x == "Nederland" else "niet-Nederland"
            ))
            .groupby(["groep", "herkomst_kort"], observed=True)
            .size().reset_index(name="n")
        )
        totals_h = agg_h.groupby("groep")["n"].transform("sum")
        agg_h["pct"] = (agg_h["n"] / totals_h * 100).round(1)
        fig4 = px.bar(
            agg_h, x="groep", y="pct", color="herkomst_kort",
            barmode="stack",
            color_discrete_map={"Nederland": "#3b82f6", "niet-Nederland": "#a78bfa"},
            labels={"groep": "", "pct": "%", "herkomst_kort": "Herkomst"},
            title="Herkomst per groep (%)",
        )
        fig4.update_layout(height=460, legend=dict(orientation="h", y=-0.2))
        fix_xas_labels(fig4)
        st.plotly_chart(fig4, width="stretch")

    # Vooropleiding: horizontale grouped bar — leesbaarder dan gestapeld met 6 kleuren
    agg_v = (
        df.groupby(["hoogste_vooropleiding", "groep"], observed=True)
        .size().reset_index(name="n")
    )
    totals_v = agg_v.groupby("groep")["n"].transform("sum")
    agg_v["pct"] = (agg_v["n"] / totals_v * 100).round(1)
    fig5 = px.bar(
        agg_v, y="hoogste_vooropleiding", x="pct", color="groep",
        barmode="group",
        orientation="h",
        color_discrete_map=GROEP_KLEUREN,
        category_orders={"groep": GROEP_VOLGORDE},
        labels={"hoogste_vooropleiding": "", "pct": "%", "groep": ""},
        title="Vooropleiding per groep (%)",
    )
    fig5.update_layout(height=420, legend=dict(orientation="h", y=-0.2))
    st.plotly_chart(fig5, width="stretch")


# ── Tab 4: Aantallen ─────────────────────────────────────────────────────────
with tab_aantallen:
    st.header("Aantallen per cohort")
    tabel = (
        filter_data(data)
        .groupby(["selectiejaar", "groep"], observed=True)
        .size().unstack(fill_value=0).reset_index()
        .rename(columns={"selectiejaar": "Cohort"})
    )
    for groep in GROEP_VOLGORDE:
        if groep not in tabel.columns:
            tabel[groep] = 0
    tabel["Totaal"] = tabel[list(GROEP_VOLGORDE)].sum(axis=1)
    st.dataframe(tabel, width="stretch", hide_index=True)
