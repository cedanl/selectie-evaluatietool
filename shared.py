import math
from collections.abc import Iterable

import pandas as pd

GROEP_NIET_GESTART = "Niet gestart"
GROEP_GESTART_GEEN_VERVOLG = "Gestart, niet naar jaar 2"
GROEP_DOORGESTROOMD = "Doorgestroomd naar jaar 2"
# Voor eenjarige opleidingen (bijv. masters) is er geen jaar 2; succes is dan
# het halen van het diploma in het cohortjaar.
GROEP_DIPLOMA = "Gestart, diploma gehaald"

GROEP_VOLGORDE = [
    GROEP_NIET_GESTART,
    GROEP_GESTART_GEEN_VERVOLG,
    GROEP_DOORGESTROOMD,
    GROEP_DIPLOMA,
]

# Studenten die daadwerkelijk zijn begonnen (alles behalve 'Niet gestart').
GROEP_INGESCHREVEN = [
    GROEP_GESTART_GEEN_VERVOLG,
    GROEP_DOORGESTROOMD,
    GROEP_DIPLOMA,
]

# Positieve uitkomsten: doorstroom naar jaar 2 of diploma in het eerste jaar.
GROEP_SUCCES = [GROEP_DOORGESTROOMD, GROEP_DIPLOMA]

GROEP_KLEUREN = {
    GROEP_NIET_GESTART: "#94a3b8",
    GROEP_GESTART_GEEN_VERVOLG: "#f97316",
    GROEP_DOORGESTROOMD: "#22c55e",
    GROEP_DIPLOMA: "#3b82f6",
}

CHART_BASE = dict(plot_bgcolor="white", paper_bgcolor="white")


def shorten_item(name: str) -> str:
    for suffix in [" schaalscore", " Schaalscore", " (1-2-3)"]:
        name = name.replace(suffix, "")
    return name


def schaal_grenzen(scores: Iterable[float]) -> tuple[float, float] | None:
    """Bepaal een nette (onder, boven) voor een reeks itemscores.

    Returnt ``None`` als er geen numerieke waarden zijn. De bovengrens wordt
    omhoog afgerond naar een canoniek 'net' getal (1, 2 of 5 maal een macht van
    10) en de ondergrens op 0 verankerd zolang er geen negatieve scores zijn.
    Zo vallen vergelijkbare schalen samen tot een handvol herkenbare bereiken
    (0-5, 0-50, 0-100) in plaats van bijna-identieke labels als 1-4, 0-5 en 4-5
    naast elkaar. De grenzen dienen als as-limieten en hoeven niet exact te zijn.
    """
    s = pd.to_numeric(pd.Series(scores), errors="coerce").dropna()
    if s.empty:
        return None
    vmin, vmax = float(s.min()), float(s.max())
    onder = 0.0 if vmin >= 0 else -_nette_bovengrens(-vmin)
    boven = _nette_bovengrens(vmax)
    if boven <= onder:  # alle waarden gelijk of nul: vermijd een nul-bereik
        boven = onder + 1
    return onder, boven


def schaal_bucket(scores: Iterable[float]) -> str:
    """Leid een dynamisch schaal-/bereiklabel af uit de waargenomen scores.

    De config legt het bereik per item niet vast, dus we bepalen het uit de
    data. Zo kun je op de boxplot-tab items met een vergelijkbare schaal samen
    tonen (bijv. alleen de 1-3 items) in plaats van een 1-3 item naast een
    0-100 item op dezelfde y-as te persen.

    Het label is data-gedreven maar canoniek: een 0-5.45 item wordt '0-5', een
    1-4 rating ook, een percentage '0-100', een ruwe schaalscore bijv. '0-1000'.
    Niets is vooraf vastgelegd, dus elke schaal die een instelling aanlevert
    werkt, en vergelijkbare schalen krijgen hetzelfde label.
    """
    grenzen = schaal_grenzen(scores)
    if grenzen is None:
        return "onbekend"
    onder, boven = grenzen
    return f"{_fmt_grens(onder)}-{_fmt_grens(boven)}"


def grenzen_van_label(label: str) -> tuple[float, float] | None:
    """Parse een 'onder-boven' schaallabel terug naar (onder, boven).

    Returnt ``None`` als het label niet die vorm heeft (bijv. 'onbekend'). Eén
    plek die het labelformaat van ``schaal_bucket`` kent, zodat sorteer-helpers
    in app.py en rapport.py niet elk los op '-' hoeven te splitsen.
    """
    try:
        onder, boven = (float(deel) for deel in label.split("-"))
        return onder, boven
    except ValueError:
        return None


def meta_per_item(scores_df: pd.DataFrame) -> pd.DataFrame:
    """Eén rij per item met het bijbehorende instrument en criterium.

    Eén bron voor zowel het dashboard als het PDF-rapport, zodat de
    instrument/criterium-labels bij een item niet tussen beide uiteen lopen.
    Verwacht de verkorte itemnaam in de kolom ``item_kort``.
    """
    return scores_df.drop_duplicates("item_kort")[
        ["item_kort", "instrument", "criterium"]
    ]


def bucket_per_item(scores_df: pd.DataFrame) -> pd.Series:
    """Schaal-label per item, afgeleid uit de volledige score-verdeling.

    Bewust op de ongefilterde data, zodat het label van een item niet
    meeschuift met demografische filters of itemselecties. Eén bron voor zowel
    de filter-dropdown als de boxplot, zodat die twee niet uiteen kunnen lopen.
    """
    return scores_df.groupby("item")["score"].apply(schaal_bucket)


def _nette_bovengrens(x: float) -> float:
    """Kleinste canonieke waarde (1, 2 of 5 maal een macht van 10) >= x."""
    if x <= 0:
        return 1.0
    macht = 10.0 ** math.floor(math.log10(x))
    for veelvoud in (1, 2, 5):
        if x <= veelvoud * macht:
            return veelvoud * macht
    return 10 * macht


def _fmt_grens(x: float) -> str:
    return str(int(x)) if float(x).is_integer() else f"{x:g}"


def sig_sym(p: float) -> str:
    return "***" if p < 0.001 else "**" if p < 0.01 else "*" if p < 0.05 else "ns"


def fmt_p(p: float) -> str:
    return "< 0.001" if p < 0.001 else f"{p:.3f}"


VERGELIJKING_KOLOMMEN = [
    "Item",
    "Succes (n)",
    "Geen succes (n)",
    "Effect (r)",
    "Sterkte",
    "95%-BI",
    "p",
]

VERSCHIL_KOLOMMEN = [
    "Item",
    "n",
    "Verschil",
    "Effectgrootte",
    "Sterkte",
    "p",
]


def effect_sterkte(r: float) -> str:
    """Magnitudelabel voor een rank-biseriale effectgrootte (zelfde grenzen als
    de correlatie-duiding: 0.10 / 0.30 / 0.50)."""
    a = abs(r)
    if a < 0.10:
        return "verwaarloosbaar"
    if a < 0.30:
        return "zwak"
    if a < 0.50:
        return "matig"
    return "sterk"


# z-waarde voor een tweezijdig 95%-interval; los benoemd zodat het
# betrouwbaarheidsniveau en de vermenigvuldiger niet uiteen kunnen lopen.
_Z_95 = 1.959963984540054


def _effect_met_bi(auc: float, nx: int, ny: int) -> tuple[float, float, float]:
    """Rank-biseriale effectgrootte met 95%-BI uit de AUC van twee groepen.

    ``auc = P(x > y)`` is de kans dat een succesvolle student hoger scoort dan
    een uitvaller (gelijk aan ``U / (nx * ny)`` uit de Mann-Whitney-toets). De
    effectgrootte is ``2 * AUC - 1`` (positief = de eerste groep scoort hoger).
    Het interval volgt de Hanley-McNeil benadering voor de variantie van de AUC:
    een analytische normaalbenadering in plaats van een bootstrap, zodat de
    tabel bij elke filterwijziging in het dashboard direct herberekent. Bij
    kleine groepen wordt het interval breed, wat de onzekerheid eerlijk weergeeft.
    """
    q1 = auc / (2 - auc)
    q2 = 2 * auc**2 / (1 + auc)
    var = (auc * (1 - auc) + (nx - 1) * (q1 - auc**2) + (ny - 1) * (q2 - auc**2)) / (
        nx * ny
    )
    se = math.sqrt(max(var, 0.0))
    lo = max(0.0, auc - _Z_95 * se)
    hi = min(1.0, auc + _Z_95 * se)
    return 2 * auc - 1, 2 * lo - 1, 2 * hi - 1


def vergelijk_succes_per_item(
    scores_met_groep: pd.DataFrame,
    item_kolom: str = "item_kort",
    min_per_groep: int = 3,
) -> pd.DataFrame:
    """Toets per item of succesvolle studenten anders scoren dan uitvallers.

    Vergelijkt per item de scores van studenten met een positieve uitkomst
    (``GROEP_SUCCES``: doorstroom of diploma) met die van gestarte studenten
    zonder vervolg (``GROEP_GESTART_GEEN_VERVOLG``). De toets is een
    Mann-Whitney U, passend bij de ordinale en scheve schalen van
    selectie-items. De effectgrootte is de rank-biseriale correlatie (positief =
    succesgroep scoort hoger) met een analytisch 95%-BI.

    Returnt een tabel met de kolommen uit ``VERGELIJKING_KOLOMMEN``, gesorteerd
    op aflopende effectgrootte zodat de sterkste signalen bovenaan staan. Items
    met te weinig waarnemingen of zonder variatie blijven in de tabel met een
    toelichting in plaats van een effectgrootte, zodat zichtbaar is wat niet
    getoetst kon worden.
    """
    from scipy.stats import mannwhitneyu

    rijen = []
    for item, deel in scores_met_groep.groupby(item_kolom, observed=True):
        succes = (
            pd.to_numeric(
                deel.loc[deel["groep"].isin(GROEP_SUCCES), "score"], errors="coerce"
            )
            .dropna()
            .to_numpy()
        )
        geen = (
            pd.to_numeric(
                deel.loc[deel["groep"] == GROEP_GESTART_GEEN_VERVOLG, "score"],
                errors="coerce",
            )
            .dropna()
            .to_numpy()
        )

        rij = {
            "Item": item,
            "Succes (n)": len(succes),
            "Geen succes (n)": len(geen),
            "Effect (r)": "-",
            "Sterkte": "-",
            "95%-BI": "-",
            "p": "-",
            "_sort": -1.0,
            "_r": None,
            "_p": 1.0,
        }
        if len(succes) < min_per_groep or len(geen) < min_per_groep:
            rij["Sterkte"] = "te weinig data"
            rijen.append(rij)
            continue
        if succes.min() == succes.max() == geen.min() == geen.max():
            rij["Sterkte"] = "geen variatie"  # niets te rangschikken
            rijen.append(rij)
            continue

        # mannwhitneyu geeft U voor de eerste groep (succes) terug; AUC = U / (nx*ny)
        # is de kans dat een succesvolle student hoger scoort dan een uitvaller.
        toets = mannwhitneyu(succes, geen, alternative="two-sided")
        auc = float(toets.statistic) / (len(succes) * len(geen))
        r, lo, hi = _effect_met_bi(auc, len(succes), len(geen))
        rij.update(
            {
                "Effect (r)": f"{r:+.2f}",
                "Sterkte": effect_sterkte(r),
                "95%-BI": f"{lo:+.2f} tot {hi:+.2f}",
                "p": f"{fmt_p(float(toets.pvalue))} {sig_sym(float(toets.pvalue))}",
                "_sort": abs(r),
                "_r": r,
                "_p": float(toets.pvalue),
            }
        )
        rijen.append(rij)

    tabel = pd.DataFrame(rijen)
    if tabel.empty:
        return tabel
    tabel = tabel.sort_values("_sort", ascending=False).drop(columns="_sort")
    return tabel[VERGELIJKING_KOLOMMEN + ["_r", "_p"]].reset_index(drop=True)


# Demografische dimensies voor de analyse-tabs en de rapportsectie. Een dimensie
# toevoegen is één regel (key, kolom in de data, en een label).
DEMO_DIMENSIES = [
    {"key": "geslacht", "kolom": "geslacht", "label": "Geslacht"},
    {
        "key": "vooropleiding",
        "kolom": "hoogste_vooropleiding",
        "label": "Vooropleiding",
    },
]


def demografie_scores(
    df: pd.DataFrame, scores_df: pd.DataFrame, dim: dict
) -> pd.DataFrame | None:
    """Long-format scores van ingeschreven studenten met de demografische
    groepskolom erbij, of ``None`` als de dimensie niet beschikbaar is.

    Eén bron voor de demografische tab, het 'wat valt op'-overzicht en het PDF-
    rapport, zodat die niet uiteenlopen. De demografie komt uit 1CHO en bestaat
    alleen voor ingeschreven studenten (``GROEP_INGESCHREVEN``).
    """
    kolom = dim["kolom"]
    ingeschr = df[df["groep"].isin(GROEP_INGESCHREVEN)].copy()
    if kolom not in ingeschr.columns:
        return None
    ingeschr = ingeschr[ingeschr[kolom].notna()]
    if ingeschr.empty:
        return None
    scores = scores_df.merge(
        ingeschr[["studentnummer", kolom]].drop_duplicates(),
        on="studentnummer",
        how="inner",
    )
    if scores.empty:
        return None
    scores["item_kort"] = scores["item"].apply(shorten_item)
    return scores


def eta_sterkte(eps2: float) -> str:
    """Magnitudelabel voor epsilon-kwadraat (Cohen-achtige grenzen voor eta2:
    0.01 / 0.06 / 0.14)."""
    if eps2 < 0.01:
        return "verwaarloosbaar"
    if eps2 < 0.06:
        return "zwak"
    if eps2 < 0.14:
        return "matig"
    return "sterk"


def toets_verschil_per_item(
    scores: pd.DataFrame,
    groep_kolom: str,
    item_kolom: str = "item_kort",
    min_per_groep: int = 5,
) -> pd.DataFrame:
    """Toets per item of de selectiescores verschillen tussen groepen.

    Bedoeld voor demografische analyses: splits de ingeschreven studenten per
    item op de waarden van ``groep_kolom`` (bijv. geslacht of vooropleiding) en
    toets met een Kruskal-Wallis of de groepen anders scoren. Die toets werkt
    voor twee of meer groepen en past bij de ordinale, scheve schalen van
    selectie-items. De effectgrootte is epsilon-kwadraat (``H / (n - 1)``,
    bereik 0-1). De richting volgt uit de mediaan per groep.

    Groepen met minder dan ``min_per_groep`` waarnemingen vallen weg, zodat een
    enkeling geen toets stuurt. Returnt een frame met de displaykolommen uit
    ``VERSCHIL_KOLOMMEN`` plus numerieke hulpkolommen (``_eps2``, ``_p``) voor
    de conclusietekst, gesorteerd op aflopende effectgrootte.
    """
    from scipy.stats import kruskal

    rijen = []
    for item, deel in scores.groupby(item_kolom, observed=True):
        sub = deel[[groep_kolom, "score"]].copy()
        sub["score"] = pd.to_numeric(sub["score"], errors="coerce")
        sub = sub.dropna(subset=[groep_kolom, "score"])
        groepen = {
            str(naam): groep["score"].to_numpy()
            for naam, groep in sub.groupby(groep_kolom, observed=True)
            if len(groep) >= min_per_groep
        }
        n_tot = sum(len(v) for v in groepen.values())

        rij = {
            "Item": item,
            "n": n_tot,
            "Verschil": "-",
            "Effectgrootte": "-",
            "Sterkte": "-",
            "p": "-",
            "_eps2": float("nan"),  # NaN = niet getoetst; sorteert vanzelf onderaan
            "_p": float("nan"),
        }
        if len(groepen) < 2:
            rij["Sterkte"] = "te weinig data"
            rijen.append(rij)
            continue

        try:
            h, p = kruskal(*groepen.values())
        except ValueError:  # alle waarden identiek: niets te rangschikken
            rij["Sterkte"] = "geen variatie"
            rijen.append(rij)
            continue

        eps2 = float(h) / (n_tot - 1)
        medianen = {naam: float(pd.Series(v).median()) for naam, v in groepen.items()}
        hoog = max(medianen, key=medianen.get)
        laag = min(medianen, key=medianen.get)
        if medianen[hoog] == medianen[laag]:
            verschil = "vergelijkbaar"
        elif len(groepen) == 2:
            verschil = f"{hoog} > {laag}"
        else:
            verschil = f"{hoog} hoogst, {laag} laagst"

        rij.update(
            {
                "Verschil": verschil,
                "Effectgrootte": f"{eps2:.3f}",
                "Sterkte": eta_sterkte(eps2),
                "p": f"{fmt_p(p)} {sig_sym(p)}",
                "_eps2": eps2,
                "_p": float(p),
            }
        )
        rijen.append(rij)

    tabel = pd.DataFrame(rijen)
    if tabel.empty:
        return tabel
    return tabel.sort_values("_eps2", ascending=False).reset_index(drop=True)


def _sorteer_abs(serie: pd.Series) -> pd.Series:
    return serie.abs()


def genereer_bevindingen(
    succes_tabel: pd.DataFrame,
    demo_tabellen: dict[str, pd.DataFrame],
    top: int = 3,
) -> dict[str, list[str]]:
    """Vat de toetsuitkomsten samen tot datagedreven bevindingen.

    Voedt zowel het 'wat valt op'-overzicht in het dashboard als de
    conclusiesectie van het rapport. Elke regel is een feit dat rechtstreeks uit
    een effectgrootte of p-waarde volgt; er wordt niets bijbedacht. ``succes_tabel``
    komt van ``vergelijk_succes_per_item`` (met _r/_p), ``demo_tabellen`` is per
    demografische dimensie een ``toets_verschil_per_item`` frame (met _eps2/_p).
    Returnt drie lijsten: een korte samenvatting, validiteitsbevindingen (welke
    items voorspellen succes) en fairnessbevindingen (demografische verschillen).
    """
    samenvatting: list[str] = []
    validiteit: list[str] = []
    fairness: list[str] = []

    if (
        succes_tabel is not None
        and not succes_tabel.empty
        and "_r" in succes_tabel.columns
    ):
        getoetst = succes_tabel[succes_tabel["_r"].notna()]
        sig = getoetst[getoetst["_p"] < 0.05]
        if len(getoetst):
            samenvatting.append(
                f"Van de {len(getoetst)} getoetste items tonen er {len(sig)} een "
                "significant verband met studiesucces (doorstroom of diploma)."
            )
        gesorteerd = sig.sort_values("_r", key=_sorteer_abs, ascending=False)
        for _, r in gesorteerd.head(top).iterrows():
            if r["_r"] > 0:
                validiteit.append(
                    f"{r['Item']}: geslaagde studenten scoorden hoger "
                    f"(effect {r['Effect (r)']}, p = {fmt_p(r['_p'])}). Dit item heeft "
                    "voorspellende waarde."
                )
            else:
                validiteit.append(
                    f"{r['Item']}: juist de uitvallers scoorden hoger "
                    f"(effect {r['Effect (r)']}, p = {fmt_p(r['_p'])}). Onverwacht en de "
                    "moeite waard om nader te bekijken."
                )
        if len(getoetst) and sig.empty:
            sterkste = getoetst.sort_values(
                "_r", key=_sorteer_abs, ascending=False
            ).iloc[0]
            validiteit.append(
                "Geen enkel item verschilt significant tussen geslaagden en uitvallers. "
                f"Het sterkste (niet-significante) signaal is {sterkste['Item']} "
                f"(effect {sterkste['Effect (r)']}). Bij kleine groepen is dat niet "
                "ongebruikelijk."
            )

    for label, tab in demo_tabellen.items():
        if tab is None or tab.empty or "_eps2" not in tab.columns:
            continue
        getoetst = tab[tab["_eps2"].notna()]
        if not len(getoetst):
            continue
        sig = getoetst[getoetst["_p"] < 0.05]
        if sig.empty:
            fairness.append(
                f"{label}: geen significante verschillen tussen de groepen op de "
                "selectie-items."
            )
            continue
        for _, r in sig.head(top).iterrows():
            fairness.append(
                f"{label}: op {r['Item']} verschillen de groepen significant "
                f"({r['Verschil']}, effectgrootte {r['Effectgrootte']}, "
                f"p = {fmt_p(r['_p'])}). Beoordeel of dit een terecht onderscheid is."
            )

    return {
        "samenvatting": samenvatting,
        "validiteit": validiteit,
        "fairness": fairness,
    }
