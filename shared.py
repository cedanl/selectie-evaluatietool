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
            }
        )
        rijen.append(rij)

    tabel = pd.DataFrame(rijen)
    if tabel.empty:
        return tabel
    tabel = tabel.sort_values("_sort", ascending=False).drop(columns="_sort")
    return tabel[VERGELIJKING_KOLOMMEN].reset_index(drop=True)
