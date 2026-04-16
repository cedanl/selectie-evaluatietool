"""
Evaluatietool: selectie & studiesucces dashboard

Draai met: uv run streamlit run app.py
Data aanmaken: uv run python scripts/maak_data.py
"""

from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

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

st.set_page_config(
    page_title="Evaluatietool Selectie",
    page_icon=":bar_chart:",
    layout="wide",
)


@st.cache_data
def laad_data() -> pd.DataFrame:
    if not DATA_PATH.exists():
        st.error(
            "Data niet gevonden. Draai eerst: `uv run python scripts/maak_data.py`"
        )
        st.stop()
    df = pd.read_parquet(DATA_PATH)
    df["groep"] = pd.Categorical(df["groep"], categories=GROEP_VOLGORDE, ordered=True)
    return df


data = laad_data()

# --- Sidebar filters ---
st.sidebar.title("Filters")

cohort_keuzes = ["Alle cohorten"] + sorted(data["selectiejaar"].unique().tolist())
cohort = st.sidebar.selectbox("Cohort (instroom jaar)", cohort_keuzes)

geslacht_keuzes = ["Alle"] + sorted(data["geslacht"].unique().tolist())
geslacht = st.sidebar.selectbox("Geslacht", geslacht_keuzes)

vooropl_keuzes = ["Alle"] + sorted(data["hoogste_vooropleiding"].unique().tolist())
vooropleiding = st.sidebar.selectbox("Vooropleiding", vooropl_keuzes)

st.sidebar.divider()
st.sidebar.caption(
    "Synthetische voorbeelddata. Vervang door echte selectie- en 1CHO-data "
    "via scripts/maak_data.py."
)


def filter_data(df: pd.DataFrame, incl_cohort=True) -> pd.DataFrame:
    if incl_cohort and cohort != "Alle cohorten":
        df = df[df["selectiejaar"] == int(cohort)]
    if geslacht != "Alle":
        df = df[df["geslacht"] == geslacht]
    if vooropleiding != "Alle":
        df = df[df["hoogste_vooropleiding"] == vooropleiding]
    return df


# --- Tabs ---
tab1, tab2, tab3 = st.tabs(["Overzicht", "Selectiescores", "Aantallen"])


# Tab 1: Overzicht
with tab1:
    st.header("Verdeling per groep")
    df = filter_data(data)

    col1, col2, col3 = st.columns(3)
    for col, groep in zip([col1, col2, col3], GROEP_VOLGORDE):
        n = (df["groep"] == groep).sum()
        pct = n / len(df) * 100 if len(df) > 0 else 0
        col.metric(groep, n, f"{pct:.0f}%")

    st.divider()

    col_links, col_rechts = st.columns(2)

    with col_links:
        # Gestapeld staafdiagram per cohort
        agg = (
            filter_data(data, incl_cohort=False)
            .groupby(["selectiejaar", "groep"], observed=True)
            .size()
            .reset_index(name="n")
        )
        fig = px.bar(
            agg,
            x="selectiejaar", y="n", color="groep",
            barmode="stack",
            color_discrete_map=GROEP_KLEUREN,
            category_orders={"groep": GROEP_VOLGORDE},
            labels={"selectiejaar": "Cohort", "n": "Aantal", "groep": ""},
            title="Verdeling per cohort",
        )
        fig.update_layout(legend=dict(orientation="h", yanchor="bottom", y=-0.35))
        st.plotly_chart(fig, use_container_width=True)

    with col_rechts:
        # Genormaliseerd (procentueel)
        agg_pct = agg.copy()
        totals = agg_pct.groupby("selectiejaar")["n"].transform("sum")
        agg_pct["pct"] = agg_pct["n"] / totals * 100
        fig2 = px.bar(
            agg_pct,
            x="selectiejaar", y="pct", color="groep",
            barmode="stack",
            color_discrete_map=GROEP_KLEUREN,
            category_orders={"groep": GROEP_VOLGORDE},
            labels={"selectiejaar": "Cohort", "pct": "Percentage (%)", "groep": ""},
            title="Procentueel per cohort",
        )
        fig2.update_layout(legend=dict(orientation="h", yanchor="bottom", y=-0.35))
        st.plotly_chart(fig2, use_container_width=True)

    # Demografisch
    col_g, col_h = st.columns(2)

    with col_g:
        agg_g = (
            df.groupby(["groep", "geslacht"], observed=True)
            .size()
            .reset_index(name="n")
        )
        fig3 = px.bar(
            agg_g, x="groep", y="n", color="geslacht",
            barmode="stack",
            labels={"groep": "", "n": "Aantal", "geslacht": "Geslacht"},
            title="Geslacht per groep",
        )
        fig3.update_layout(legend=dict(orientation="h", yanchor="bottom", y=-0.45))
        st.plotly_chart(fig3, use_container_width=True)

    with col_h:
        agg_h = (
            df.assign(herkomst_kort=df["herkomst"].apply(
                lambda x: "Nederland" if x == "Nederland" else "niet-Nederland"
            ))
            .groupby(["groep", "herkomst_kort"], observed=True)
            .size()
            .reset_index(name="n")
        )
        fig4 = px.bar(
            agg_h, x="groep", y="n", color="herkomst_kort",
            barmode="stack",
            color_discrete_map={"Nederland": "#3b82f6", "niet-Nederland": "#a78bfa"},
            labels={"groep": "", "n": "Aantal", "herkomst_kort": "Herkomst"},
            title="Herkomst per groep",
        )
        fig4.update_layout(legend=dict(orientation="h", yanchor="bottom", y=-0.45))
        st.plotly_chart(fig4, use_container_width=True)


# Tab 2: Selectiescores
with tab2:
    st.header("Selectiescores per groep")
    st.caption(
        "Als doorstromers hogere scores hebben, heeft het selectie-instrument predictieve validiteit."
    )

    df2 = filter_data(data, incl_cohort=False)
    if cohort != "Alle cohorten":
        df2 = df2[df2["selectiejaar"] == int(cohort)]

    scores = {
        "Totaalscore":    "totaalscore",
        "Motivatiebrief": "motivatiescore",
        "CV":             "cv_score",
        "Interview":      "interview_score",
    }

    cols = st.columns(len(scores))
    for col, (label, var) in zip(cols, scores.items()):
        fig = px.box(
            df2[df2["groep"].notna()],
            x="groep", y=var,
            color="groep",
            color_discrete_map=GROEP_KLEUREN,
            category_orders={"groep": GROEP_VOLGORDE},
            labels={"groep": "", var: "score"},
            title=label,
        )
        fig.update_layout(showlegend=False, xaxis_tickangle=-25)
        col.plotly_chart(fig, use_container_width=True)


# Tab 3: Aantallen
with tab3:
    st.header("Aantallen per cohort")

    tabel = (
        data.groupby(["selectiejaar", "groep"], observed=True)
        .size()
        .unstack(fill_value=0)
        .reset_index()
        .rename(columns={"selectiejaar": "Cohort"})
    )
    tabel["Totaal"] = tabel[list(GROEP_VOLGORDE)].sum(axis=1)
    st.dataframe(tabel, use_container_width=True, hide_index=True)
