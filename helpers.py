"""Gedeelde app-helpers en constanten voor het dashboard.

Bevat de data-koppeling, de demodata-loader, tabel-styling en de groep-/
kleur-helpers die meerdere tabs gebruiken. De statistiek zelf staat in
shared.py."""

import base64
import io
from pathlib import Path

import pandas as pd
import plotly.express as px
from plotly.colors import hex_to_rgb, unlabel_rgb

import dash

from transformatie import (
    normaliseer_studentnummer,
    lees_config,
    parse_jaar,
    parse_selectiedata,
    transformeer_naar_lang,
)
from cho_transform import (
    beste_opleiding_match,
    opleidingen_in_cho,
    selecteer_spells,
    transformeer_cho,
)
from shared import (
    GROEP_VOLGORDE,
    GROEP_NIET_GESTART,
    GROEP_NIET_IN_VERGELIJKING,
    GROEP_INGESCHREVEN,
    GROEP_KLEUREN,
    uitkomst_perspectief,
    binair_kleur_map,
    shorten_item,
    grenzen_van_label,
    DEMO_DIMENSIES,
    demografie_scores,
)


DEMO_DIR = Path("data/demo")

DEMO_DATASETS = []
if DEMO_DIR.exists():
    for subdir in sorted(DEMO_DIR.iterdir()):
        if subdir.is_dir() and (subdir / "config.xlsx").exists():
            DEMO_DATASETS.append(
                {"value": subdir.name, "label": subdir.name.replace("_", " ").title()}
            )


def koppel_data(cho_df: pd.DataFrame, scores_df: pd.DataFrame) -> pd.DataFrame:
    dubbel = cho_df["studentnummer"].dropna().duplicated()
    if dubbel.any():
        # Een student met meerdere 1CHO-spells zou dubbel in de analyse komen,
        # met mogelijk twee verschillende uitkomsten. Kies eerst één spell via
        # bereid_cho_voor() / selecteer_spells().
        raise ValueError(
            f"1CHO bevat {int(dubbel.sum())} studentnummers met meerdere "
            "inschrijvingen; kies eerst één inschrijving per student."
        )
    instrument_gem = (
        scores_df.groupby(["studentnummer", "instrument"])["score"].mean().reset_index()
    )
    pivot = instrument_gem.pivot(
        index="studentnummer", columns="instrument", values="score"
    )
    score_cols = [f"{c}_score" for c in pivot.columns]
    pivot.columns = score_cols
    zscores = pivot[score_cols].apply(
        lambda s: (
            (s - s.mean()) / s.std() if s.std() > 0 else pd.Series(0, index=s.index)
        )
    )
    pivot["totaalscore"] = zscores.mean(axis=1).round(2)
    pivot = pivot.reset_index()

    meta_cols = ["studentnummer"]
    for col in ["selectiejaar", "opleiding", "instellingscode"]:
        if col in scores_df.columns:
            meta_cols.append(col)
    meta = (
        scores_df.groupby("studentnummer")
        .first()[[c for c in meta_cols if c != "studentnummer"]]
        .reset_index()
    )
    pivot = pivot.merge(meta, on="studentnummer", how="left")

    df = pivot.merge(cho_df, on="studentnummer", how="left", suffixes=("", "_cho"))
    for col in ["selectiejaar", "opleiding", "instellingscode"]:
        cho_col = f"{col}_cho"
        if cho_col in df.columns:
            df[col] = df[col].fillna(df[cho_col])
            df = df.drop(columns=[cho_col])

    df["groep"] = pd.Categorical(
        df["groep"].fillna(GROEP_NIET_GESTART),
        categories=GROEP_VOLGORDE,
        ordered=True,
    )
    return df


def df_from_store(store_data: str | None) -> pd.DataFrame:
    if store_data is None:
        return pd.DataFrame()
    df = pd.read_json(io.StringIO(store_data), orient="split")
    df["groep"] = pd.Categorical(df["groep"], categories=GROEP_VOLGORDE, ordered=True)
    return df


def scores_df_from_store(store_data: str | None) -> pd.DataFrame:
    """Deserialiseer de scores-store (long-format scores, geen 'groep'-kolom).

    Tegenhanger van df_from_store voor de scores-store, zodat de tabs het
    orient/StringIO-contract niet elk los hoeven te herhalen."""
    if not store_data:
        return pd.DataFrame()
    return pd.read_json(io.StringIO(store_data), orient="split")


TABLE_STYLE = dict(
    style_cell={
        "padding": "8px 14px",
        "fontSize": "13px",
        "border": "1px solid #f1f5f9",
        "fontFamily": "inherit",
    },
    style_header={
        "backgroundColor": "#f8fafc",
        "fontWeight": "600",
        "border": "1px solid #e2e8f0",
        "fontSize": "12px",
        "letterSpacing": "0.02em",
        "fontFamily": "inherit",
    },
    style_data={"backgroundColor": "#ffffff"},
)


# ── Groeperingsopties ─────────────────────────────────────────────────────────
# De Selectiescores- en Verschiltoets-tabs laten de gebruiker kiezen waarop te
# groeperen: doorstroom naar jaar 2 of een demografische dimensie (geslacht,
# vooropleiding). De vergelijking 'gestart vs niet gestart' en de losse
# 'Niet gestart'-groep zijn uit het dashboard gehaald; niet-gestarte kandidaten
# leven nog wel in de data en worden alleen als funnel-telling getoond.
GROEPEER_OPTIES = [
    # De labels in de grafieken volgen de data (doorstroom of diploma, zie
    # shared.perspectief_voor); de keuzelijst zelf is neutraal.
    {"label": "Studiesucces (doorstroom of diploma)", "value": "doorstroom"},
] + [{"label": d["label"], "value": d["kolom"]} for d in DEMO_DIMENSIES]

GROEPEER_OPTIES_SCORES = GROEPEER_OPTIES


def _file_to_data_uri(path: Path) -> str:
    b64 = base64.b64encode(path.read_bytes()).decode()
    return f"data:application/octet-stream;base64,{b64}"


def bereid_cho_voor(
    cho_ruw: pd.DataFrame,
    config: dict,
    scores_df: pd.DataFrame,
    cho_opleiding: str | None = None,
) -> dict:
    """Leid de 1CHO-uitkomst af en houd per student de spell over die bij deze
    selectie hoort (juiste opleiding en cohort).

    `cho_opleiding` is de keuze van de gebruiker in de upload-overlay; zonder
    keuze proberen we de opleiding uit de config te matchen. Eén plek voor de
    uploadvalidatie en het laden, zodat die dezelfde studenten tellen.

    Retourneert een dict met `cho_df`, `opleidingen` (alle opleidingen in het
    bestand), `gekozen` (de gebruikte opleiding of None), `keuze_nodig` (meer
    dan één opleiding en geen keuze of match) en `info` (tellingen)."""
    # Alleen inschrijvingen van kandidaten uit de selectie doen ertoe. Bij een
    # instellingsbreed bestand (miljoenen rijen) scheelt dat veel rekenwerk.
    # Matcht niemand, dan rekenen we op het hele bestand door, zodat de
    # validatie 'geen overlap' kan melden.
    nummers = normaliseer_studentnummer(cho_ruw["persoonsgebonden_nummer"])
    n_studenten_totaal = int(nummers.nunique())
    if not scores_df.empty:
        in_selectie = nummers.isin(set(scores_df["studentnummer"].dropna()))
        if in_selectie.any():
            cho_ruw = cho_ruw[in_selectie]
    afgeleid = transformeer_cho(cho_ruw)
    opleidingen = opleidingen_in_cho(afgeleid)
    gekozen = (
        cho_opleiding
        if cho_opleiding in opleidingen
        else beste_opleiding_match(opleidingen, config.get("opleiding", ""))
    )
    keuze_nodig = len(opleidingen) > 1 and gekozen is None
    cho_df, info = selecteer_spells(
        afgeleid,
        opleiding=gekozen,
        jaar=parse_jaar(config.get("jaar", "")),
        studentnummers=set(scores_df["studentnummer"].dropna())
        if not scores_df.empty
        else None,
    )
    return {
        "cho_df": cho_df,
        "opleidingen": opleidingen,
        "gekozen": gekozen,
        "keuze_nodig": keuze_nodig,
        "info": {**info, "n_studenten_totaal": n_studenten_totaal},
    }


def bouw_data_stores(
    config: dict,
    sel_contents: str,
    cho_ruw: pd.DataFrame,
    cho_opleiding: str | None = None,
) -> tuple[str, str]:
    """Draai de pijplijn en geef de JSON voor data-store en scores-store terug.

    Eén plek voor de volgorde parse -> transformeer -> koppel, zodat de twee
    laadpaden (upload en demo) niet uiteen kunnen lopen. De ruwe 1CHO komt al
    geparseerd binnen, omdat de paden hem verschillend inlezen (demo via
    read_csv, uploads via parse_csv_or_excel)."""
    scores_df = transformeer_naar_lang(parse_selectiedata(sel_contents, config), config)
    cho = bereid_cho_voor(cho_ruw, config, scores_df, cho_opleiding)
    joined = koppel_data(cho["cho_df"], scores_df)
    return (
        joined.to_json(orient="split", date_format="iso"),
        scores_df.to_json(orient="split", date_format="iso"),
    )


def _laad_demodata(dataset_name=None):
    """Laad een demoset en geef de JSON voor data-store en scores-store terug."""
    demo_subdir = DEMO_DIR / dataset_name if dataset_name else DEMO_DIR

    sel_path = demo_subdir / "selectiedata.xlsx"
    cfg_path = demo_subdir / "config.xlsx"
    cho_path = demo_subdir / "1cho_data.csv"

    if not all(p.exists() for p in [sel_path, cfg_path, cho_path]):
        return dash.no_update, dash.no_update

    config = lees_config(_file_to_data_uri(cfg_path))
    return bouw_data_stores(
        config, _file_to_data_uri(sel_path), pd.read_csv(cho_path, sep=";")
    )


# Kwalitatief palet voor demografische groepen. De labels variëren per dataset
# (vooropleiding kan van alles zijn), dus kleuren worden op volgorde toegekend in
# plaats van per label hardgecodeerd.
_DEMO_PALET = px.colors.qualitative.Set2


def _demo_kleur_map(groepen) -> dict:
    return {g: _DEMO_PALET[i % len(_DEMO_PALET)] for i, g in enumerate(groepen)}


def _meng_met_wit(kleur: str, f: float = 0.80) -> str:
    """Lichtere tint van een kleur (f van de weg naar wit), voor
    tabelachtergronden. Werkt op '#rrggbb' en 'rgb(r, g, b)', de twee formaten
    die Plotly-paletten leveren."""
    rgb = hex_to_rgb(kleur) if kleur.startswith("#") else unlabel_rgb(kleur)
    r, g, b = (int(c + (255 - c) * f) for c in rgb)
    return f"#{r:02x}{g:02x}{b:02x}"


def _groep_tabel_stijl(groepeer, kleur_map, volgorde) -> list:
    """style_data_conditional dat tabelrijen op de groep kleurt met een lichte
    tint van de bijbehorende boxplot-kleur."""
    stijlen = [
        {
            "if": {"filter_query": f'{{Groep}} = "{groep}"'},
            "backgroundColor": _meng_met_wit(kleur_map[groep]),
        }
        for groep in volgorde
    ]
    stijlen.append(
        {
            "if": {"filter_query": f'{{Groep}} = "{GROEP_NIET_IN_VERGELIJKING}"'},
            "backgroundColor": "#f1f5f9",
            "fontStyle": "italic",
            "color": "#64748b",
        }
    )
    return stijlen


def _aantallen_per_groep(df, groepeer):
    """Aantal studenten per groep (n en %). Bij een binaire uitkomst telt de
    populatie die bij dat perspectief hoort; bij geslacht en vooropleiding
    tellen alleen ingeschreven studenten (achtergrond komt uit 1CHO)."""
    if groepeer == "groep":
        telling = (
            df["groep"]
            .value_counts()
            .reindex([g for g in GROEP_VOLGORDE if g in df["groep"].values])
        )
        n_buiten = 0
    elif perspectief := uitkomst_perspectief(groepeer, df):
        pop = df[df["groep"].isin(perspectief["populatie"])]
        binair = pop["groep"].isin(perspectief["positief_groepen"])
        labels = binair.map(
            {True: perspectief["positief_label"], False: perspectief["negatief_label"]}
        )
        volgorde = [perspectief["positief_label"], perspectief["negatief_label"]]
        telling = labels.value_counts().reindex(volgorde).dropna()
        n_buiten = int((~df["groep"].isin(perspectief["populatie"])).sum())
    else:
        ingeschr = df[df["groep"].isin(GROEP_INGESCHREVEN)]
        if groepeer not in ingeschr.columns:
            return pd.DataFrame()
        telling = ingeschr[groepeer].dropna().value_counts()
        n_buiten = 0
    totaal = int(telling.sum())
    if totaal == 0:
        return pd.DataFrame()
    rijen = [
        {"Groep": str(groep), "n": int(n), "%": f"{n / totaal * 100:.0f}%"}
        for groep, n in telling.items()
    ]
    if n_buiten > 0:
        rijen.append({"Groep": GROEP_NIET_IN_VERGELIJKING, "n": n_buiten, "%": ""})
    return pd.DataFrame(rijen)


def _scores_per_groep(df, scores_df, groepeer):
    """Long-format scores met een kolom 'groep' die de gekozen groepering bevat
    (binaire uitkomst, de 4-delige uitkomstgroep, of een demografische dimensie).
    Returnt (scores, kleur_map, volgorde), of ``None`` als de dimensie ontbreekt.
    De demografie bestaat alleen voor ingeschreven studenten."""
    if groepeer == "groep":
        scores = scores_df.merge(
            df[["studentnummer", "groep"]].drop_duplicates(),
            on="studentnummer",
            how="inner",
        )
        volgorde = [g for g in GROEP_VOLGORDE if g in scores["groep"].values]
        kleur_map = {g: GROEP_KLEUREN[g] for g in volgorde}
        scores["item_kort"] = scores["item"].apply(shorten_item)
        return scores, kleur_map, volgorde
    perspectief = uitkomst_perspectief(groepeer, df)
    if perspectief:
        pop = df[df["groep"].isin(perspectief["populatie"])]
        scores = scores_df.merge(
            pop[["studentnummer", "groep"]].drop_duplicates(),
            on="studentnummer",
            how="inner",
        )
        pos_label = perspectief["positief_label"]
        neg_label = perspectief["negatief_label"]
        scores["groep"] = (
            scores["groep"]
            .isin(perspectief["positief_groepen"])
            .map({True: pos_label, False: neg_label})
        )
        volgorde = [pos_label, neg_label]
        kleur_map = binair_kleur_map(perspectief)
        scores["item_kort"] = scores["item"].apply(shorten_item)
        return scores, kleur_map, volgorde
    dim = next((d for d in DEMO_DIMENSIES if d["kolom"] == groepeer), None)
    if dim is None:
        return None
    scores = demografie_scores(df, scores_df, dim)
    if scores is None:
        return None
    scores = scores.rename(columns={dim["kolom"]: "groep"})
    groepen = sorted(scores["groep"].dropna().unique())
    return scores, _demo_kleur_map(groepen), groepen


def _sorteer_bereik(label: str) -> tuple[int, float, float]:
    """Sorteersleutel voor bereiklabels: op bovengrens, 'onbekend' achteraan."""
    grenzen = grenzen_van_label(label)
    if grenzen is None:
        return (1, 0.0, 0.0)
    onder, boven = grenzen
    return (0, boven, onder)
