"""
Genereer een fictief selectiebestand voor Biomedische Wetenschappen (AUMC).

Structuur gebaseerd op het FAR Leiden 2026 format maar met andere
instrumentnamen, scoreschalen en kandidaataantallen. Niet 1-op-1
herleidbaar naar de brondata.

120 kandidaten, vier instrumenten, vergelijkbare complexiteit als het
echte Farmacie-bestand. Inclusief proceskolommen, Z-scores, totaalscores
en rangnummers.

Draai:
    uv run python scripts/maak_fictief_programma.py
"""

from pathlib import Path

import numpy as np
import pandas as pd

RNG = np.random.default_rng(42)

OUT_DIR = Path("data/fictief")
OUT_DIR.mkdir(parents=True, exist_ok=True)

N = 120
OPLEIDING = "Biomedische Wetenschappen"
INSTELLING = "AUMC"
JAAR = 2026
BLAD_NAAM = "2026 AUMC BioMed"


def generate_correlated_scores(n, means, stds, corr_strength=0.3):
    """Generate scores with moderate positive intercorrelation."""
    k = len(means)
    base = RNG.normal(0, 1, (n, 1))
    noise = RNG.normal(0, 1, (n, k))
    raw = corr_strength * base + np.sqrt(1 - corr_strength**2) * noise
    scores = np.zeros((n, k))
    for i in range(k):
        scores[:, i] = means[i] + stds[i] * raw[:, i]
    return scores


studentnummers = RNG.choice(range(100000, 999999), size=N, replace=False)
studentnummers.sort()

# ── Instrument 1: Analytische Vaardigheden Toets (AVT) ──────────────────────
# 6 subschalen, schaalscores ~15-35
avt_namen = [
    "Logisch redeneren",
    "Datavisualisatie",
    "Methodologie",
    "Probleemoplossing",
    "Kritisch lezen",
    "Numerieke vaardigheden",
]
avt_means = [24.5, 22.0, 26.5, 23.0, 25.0, 21.5]
avt_stds = [3.8, 4.2, 3.5, 4.0, 3.6, 4.5]
avt_scores = generate_correlated_scores(N, avt_means, avt_stds, corr_strength=0.25)
avt_scores = np.clip(avt_scores, 10, 40).round(0).astype(int)

# Normscores (stanines 1-9)
avt_norm = np.clip(
    np.round(
        1
        + 8
        * (avt_scores - avt_scores.min(axis=0))
        / (avt_scores.max(axis=0) - avt_scores.min(axis=0) + 0.01)
    ),
    1,
    9,
).astype(int)

# ── Instrument 2: Reflectie-opdracht (open vraag, beoordeeld) ───────────────
# 2 beoordelingen op schaal 1-2-3, plus woordenaantal
reflectie_analytisch = RNG.choice([1, 2, 3], size=N, p=[0.20, 0.50, 0.30])
reflectie_communicatief = RNG.choice([1, 2, 3], size=N, p=[0.15, 0.45, 0.40])
woordenaantal = RNG.integers(120, 280, size=N)

reflectie_tekst_keuzes = [
    "De kandidaat reflecteert op eigen handelen in relatie tot het biomedisch onderzoeksveld.",
    "Beschrijf een situatie waarin je wetenschappelijke integriteit moest afwegen.",
    "Hoe zou je omgaan met tegenstrijdige onderzoeksresultaten?",
]
reflectie_tekst = RNG.choice(reflectie_tekst_keuzes, size=N)

# Tekstuele beoordelingen
reflectie_niveau_map = {1: "onder niveau", 2: "op niveau", 3: "boven niveau"}
reflectie_analytisch_tekst = [reflectie_niveau_map[v] for v in reflectie_analytisch]
reflectie_communicatief_tekst = [
    reflectie_niveau_map[v] for v in reflectie_communicatief
]

# ── Instrument 3: Situational Judgement Test (SJT-B) ────────────────────────
# 1 totaalscore, schaal ~35-65
sjt_mean, sjt_std = 50.0, 6.5
sjt_raw = RNG.normal(sjt_mean, sjt_std, N)
sjt_scores = np.clip(sjt_raw, 30, 70).round(0).astype(int)
sjt_norm = np.clip(
    np.round(
        1
        + 8
        * (sjt_scores - sjt_scores.min())
        / (sjt_scores.max() - sjt_scores.min() + 0.01)
    ),
    1,
    9,
).astype(int)

# ── Instrument 4: Wetenschappelijk Redeneren Casus (WRC) ───────────────────
# aantal goed, fout, beantwoord + schaalscore
wrc_n_vragen = 20
wrc_ability = RNG.normal(0.6, 0.15, N)
wrc_goed = np.clip(np.round(wrc_ability * wrc_n_vragen), 3, 20).astype(int)
wrc_fout = wrc_n_vragen - wrc_goed
wrc_beantwoord = np.full(N, wrc_n_vragen)
wrc_schaalscore = np.clip(np.round(5 + 10 * (wrc_goed / wrc_n_vragen)), 5, 15).astype(
    int
)
wrc_norm = np.clip(
    np.round(
        1
        + 8
        * (wrc_schaalscore - wrc_schaalscore.min())
        / (wrc_schaalscore.max() - wrc_schaalscore.min() + 0.01)
    ),
    1,
    9,
).astype(int)

# ── Z-scores voor alle schaalscores ─────────────────────────────────────────


def zscore(arr):
    s = np.std(arr, ddof=0)
    if s == 0:
        return np.zeros_like(arr, dtype=float)
    return ((arr - np.mean(arr)) / s).round(6)


avt_z = np.column_stack([zscore(avt_scores[:, i]) for i in range(6)])
sjt_z = zscore(sjt_scores)
wrc_z = zscore(wrc_schaalscore)
reflectie_analytisch_z = zscore(reflectie_analytisch.astype(float))
reflectie_communicatief_z = zscore(reflectie_communicatief.astype(float))

# Reversed score for Kritisch lezen (like problemenvermijden_R in Farmacie)
avt_z_kritisch_R = -avt_z[:, 4]

# Gemiddelden per criteriumgroep
analytisch_gem = (avt_z[:, 0] + avt_z[:, 2] + reflectie_analytisch_z) / 3
communicatie_gem = (avt_z[:, 4] + reflectie_communicatief_z) / 2
methodologie_gem = (avt_z[:, 1] + avt_z[:, 5]) / 2

# ── Totaalscores ─────────────────────────────────────────────────────────────
all_z = np.column_stack(
    [
        avt_z,
        reflectie_analytisch_z,
        reflectie_communicatief_z,
        sjt_z,
        wrc_z,
    ]
)
totaalscore = all_z.mean(axis=1).round(2)
z_totaalscore = zscore(totaalscore).round(2)

rang_totaal = (
    pd.Series(totaalscore).rank(ascending=False, method="min").astype(int).values
)
rang_z = pd.Series(z_totaalscore).rank(ascending=False, method="min").astype(int).values

# Selectie-uitkomst: top 40 geselecteerd, 41-55 reserve, rest niet
selectie_uitkomst = np.where(
    rang_totaal <= 40,
    "geselecteerd",
    np.where(rang_totaal <= 55, "reserve", "niet geselecteerd"),
)

# Master/premaster split
master_premaster = RNG.choice(["master", "premaster"], size=N, p=[0.85, 0.15])

# Random rangnummer voor gelijke scores
random_rang = RNG.permutation(N) + 1

# ── Proceskolommen (realistisch maar fictief) ────────────────────────────────
bedrijf = ["AUMC"] * N
processet = ["Selectie BioMed 2026-2027"] * N
proces = ["Selectieprocedure BioMed Master"] * N
gebruikersnaam = [f"kandidaat_{s}" for s in studentnummers]
emails = [f"k{s}@students.aumc.nl" for s in studentnummers]

voornamen = RNG.choice(
    [
        "Anna",
        "Emma",
        "Sophie",
        "Lotte",
        "Julia",
        "Lisa",
        "Eva",
        "Sara",
        "Thomas",
        "Lars",
        "Tim",
        "Max",
        "Daan",
        "Luuk",
        "Sven",
        "Milan",
        "Noor",
        "Iris",
        "Fem",
        "Roos",
        "Bas",
        "Niels",
        "Koen",
        "Rick",
    ],
    size=N,
)
achternamen = RNG.choice(
    [
        "de Vries",
        "Jansen",
        "Bakker",
        "Visser",
        "Smit",
        "Mulder",
        "Bos",
        "Vos",
        "Peters",
        "Hendriks",
        "van Dijk",
        "van Dam",
        "Willems",
        "Vermeer",
        "van Leeuwen",
        "Dijkstra",
        "Brouwer",
        "de Groot",
        "Hermans",
        "Koster",
        "van den Berg",
        "Jacobs",
    ],
    size=N,
)
tussenvoegsels = RNG.choice(
    ["", "", "", "", "van", "de", "van de", "van der"],
    size=N,
)
afnametaal = ["Nederlands"] * N

base_date = pd.Timestamp("2026-02-01")
start_dates = [base_date + pd.Timedelta(days=int(d)) for d in RNG.integers(0, 30, N)]
avt_start = [
    d + pd.Timedelta(minutes=int(m))
    for d, m in zip(start_dates, RNG.integers(0, 60, N))
]
avt_end = [
    d + pd.Timedelta(minutes=int(m)) for d, m in zip(avt_start, RNG.integers(40, 90, N))
]

proctoring_start = [d - pd.Timedelta(minutes=5) for d in avt_start]
proctoring_end = [d + pd.Timedelta(minutes=5) for d in avt_end]
proctor_review = RNG.choice(
    ["Goedgekeurd", "Goedgekeurd", "Goedgekeurd", "Handmatige controle"],
    size=N,
)
proctoring_status = ["Voltooid"] * N
beoordelingsresultaat = [np.nan] * N

toestemming = RNG.choice(["Ja", "Ja", "Ja", "Nee"], size=N)
proctor_ids = [f"PID-{RNG.integers(10000, 99999)}" for _ in range(N)]
proctor_aanmaak = [
    d - pd.Timedelta(days=int(dd)) for d, dd in zip(start_dates, RNG.integers(1, 14, N))
]

# ── Build the full DataFrame ─────────────────────────────────────────────────
df = pd.DataFrame(
    {
        "Bedrijf": bedrijf,
        "ProcesSet": processet,
        "Proces": proces,
        "Gebruikersnaam": gebruikersnaam,
        "Email": emails,
        "Achternaam": achternamen,
        "Tussenvoegsel": tussenvoegsels,
        "Voornaam": voornamen,
        "Studentnummer": studentnummers,
        "Afnametaal": afnametaal,
        "Processtartdatum": [d.strftime("%Y-%m-%d %H:%M") for d in start_dates],
        "Procesvoltooid": ["Ja"] * N,
        "Procesvoltooiddatum": [d.strftime("%Y-%m-%d %H:%M") for d in avt_end],
        "ProcessToestemmingAnoniemOnderzoek": toestemming,
        "StudentIdProctorId": proctor_ids,
        "ProctorIdaanmaakdatum": [d.strftime("%Y-%m-%d") for d in proctor_aanmaak],
        "Geplandestartvoorproctoring": [
            d.strftime("%Y-%m-%d %H:%M") for d in proctoring_start
        ],
        "Proctoringstarttijd": [d.strftime("%Y-%m-%d %H:%M") for d in proctoring_start],
        "Proctoringeindtijd": [d.strftime("%Y-%m-%d %H:%M") for d in proctoring_end],
        "ProctorReview": proctor_review,
        "Proctoringvoortgangsstatus": proctoring_status,
        "Beoordelingsresultaat": beoordelingsresultaat,
        "Opmerkingenbijbeoordeling": [np.nan] * N,
        # Instrument 1: AVT
        "AnalytischeVaardighedenToets": [np.nan] * N,
        "AVT_Teststartdatum": [d.strftime("%Y-%m-%d %H:%M") for d in avt_start],
        "AVT_Testvoltooiddatum": [d.strftime("%Y-%m-%d %H:%M") for d in avt_end],
        "AVT_Testvoltooid": ["Ja"] * N,
        "avt_logischredeneren_Schaalscore": avt_scores[:, 0],
        "avt_logischredeneren_Normscore": avt_norm[:, 0],
        "avt_datavisualisatie_Schaalscore": avt_scores[:, 1],
        "avt_datavisualisatie_Normscore": avt_norm[:, 1],
        "avt_methodologie_Schaalscore": avt_scores[:, 2],
        "avt_methodologie_Normscore": avt_norm[:, 2],
        "avt_probleemoplossing_Schaalscore": avt_scores[:, 3],
        "avt_probleemoplossing_Normscore": avt_norm[:, 3],
        "avt_kritischlezen_Schaalscore": avt_scores[:, 4],
        "avt_kritischlezen_Normscore": avt_norm[:, 4],
        "avt_numeriekevaardigheden_Schaalscore": avt_scores[:, 5],
        "avt_numeriekevaardigheden_Normscore": avt_norm[:, 5],
        # Instrument 2: Reflectie-opdracht
        "AUMCBioMedReflectieopdracht": [np.nan] * N,
        "AUMCBioMedReflectieopdracht_Teststartdatum": [
            (d + pd.Timedelta(hours=2)).strftime("%Y-%m-%d %H:%M") for d in avt_start
        ],
        "AUMCBioMedReflectieopdracht_Testvoltooiddatum": [
            (d + pd.Timedelta(hours=3)).strftime("%Y-%m-%d %H:%M") for d in avt_start
        ],
        "AUMCBioMedReflectieopdracht_Testvoltooid": ["Ja"] * N,
        "AUMC_BioMed_Reflectie001_BeschrijfEenSituatie": reflectie_tekst,
        "Aantalwoordenongeveer": woordenaantal,
        "Beoordeling analytisch denken": reflectie_analytisch_tekst,
        "Beoordeling communicatieve vaardigheden": reflectie_communicatief_tekst,
        "Toelichting bij Onder niveau Analytisch denken": [np.nan] * N,
        "Beoordeling_analytischdenken\nonder/op/boven niveau = 1/2/3": reflectie_analytisch,
        "Beoordeling_communicatievevaardigheden\nonder/op/boven niveau = 1/2/3": reflectie_communicatief,
        # Instrument 3: SJT-B
        "SituationalJudgementTestBioMed": [np.nan] * N,
        "SituationalJudgementTestBioMed_Teststartdatum": [
            (d + pd.Timedelta(hours=4)).strftime("%Y-%m-%d %H:%M") for d in avt_start
        ],
        "SituationalJudgementTestBioMed_Testvoltooiddatum": [
            (d + pd.Timedelta(hours=5)).strftime("%Y-%m-%d %H:%M") for d in avt_start
        ],
        "SituationalJudgementTestBioMed_Testvoltooid": ["Ja"] * N,
        "SituationalJudgementTestBioMed_Normgroep": ["Biomedisch 2026"] * N,
        "sjtb_totaal_Schaalscore": sjt_scores,
        "sjtb_totaal_Normscore": sjt_norm,
        # Instrument 4: WRC
        "WetenschappelijkRedenerenCasus": [np.nan] * N,
        "WRC_Teststartdatum": [
            (d + pd.Timedelta(hours=6)).strftime("%Y-%m-%d %H:%M") for d in avt_start
        ],
        "WRC_Testvoltooiddatum": [
            (d + pd.Timedelta(hours=7)).strftime("%Y-%m-%d %H:%M") for d in avt_start
        ],
        "WRC_Testvoltooid": ["Ja"] * N,
        "WRC_Normgroep": ["Biomedisch 2026"] * N,
        "wrc_Aantal_goed": wrc_goed,
        "wrc_Aantal_fout": wrc_fout,
        "wrc_Aantal_beantwoord": wrc_beantwoord,
        "wrc_Schaalscore": wrc_schaalscore,
        "wrc_Normscore": wrc_norm,
        # Z-scores
        "Zavt_logischredeneren_Schaalscore": avt_z[:, 0].round(6),
        "ZBeoordeling_analytischdenken": reflectie_analytisch_z.round(6),
        "Zavt_datavisualisatie_Schaalscore": avt_z[:, 1].round(6),
        "ZBeoordeling_communicatievevaardigheden": reflectie_communicatief_z.round(6),
        "Zavt_methodologie_Schaalscore": avt_z[:, 2].round(6),
        "Zavt_probleemoplossing_Schaalscore": avt_z[:, 3].round(6),
        "Zavt_kritischlezen_Schaalscore": avt_z[:, 4].round(6),
        "Zavt_kritischlezen_Schaalscore_R": avt_z_kritisch_R.round(6),
        "Zavt_numeriekevaardigheden_Schaalscore": avt_z[:, 5].round(6),
        "Zwrc_Aantal_goed": wrc_z.round(6),
        "Analytisch_GEM": analytisch_gem.round(6),
        "Communicatie_GEM": communicatie_gem.round(6),
        "Zsjtb_totaal_Schaalscore": sjt_z.round(6),
        "Methodologie_GEM": methodologie_gem.round(6),
        # Totaalscores en rangnummers
        "TOTAALSCORE": totaalscore,
        "ZTOTAALSCORE": z_totaalscore,
        "Rangordenummer_TOTAALSCORE": rang_totaal,
        "Rangordenummer_ZTOTAALSCORE": rang_z,
        "TOTAALSCORE (niet afgerond)": all_z.mean(axis=1).round(6),
        "ZTOTAALSCORE (niet afgerond)": zscore(all_z.mean(axis=1)).round(6),
        "Selectie master of premaster": master_premaster,
        f"Random rangnummer bepaald 15-04-{JAAR}": random_rang,
        f"Uiteindelijke rangnummer master BioMed {JAAR % 100}-{(JAAR + 1) % 100}": rang_totaal,
    }
)

print(f"Selectiebestand: {df.shape[0]} kandidaten, {df.shape[1]} kolommen")

xlsx_path = OUT_DIR / "selectiedata_biomed_2026.xlsx"
with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
    df.to_excel(writer, sheet_name=BLAD_NAAM, index=False)
print(f"Opgeslagen: {xlsx_path}")

# ── Configuratiebestand ──────────────────────────────────────────────────────
import sys

sys.path.insert(0, str(Path(__file__).parent))
from update_configs import make_config

config_path = OUT_DIR / "config_BioMed_AUMC_2026.xlsx"
make_config(
    str(config_path),
    [
        ("Koppel_id_kolom", "Studentnummer"),
        ("opleiding", OPLEIDING),
        ("instellingscode", INSTELLING),
        ("jaar", str(JAAR)),
        ("blad_naam", BLAD_NAAM),
        ("header_rij", "1"),
        ("totaalscore_kolom", "TOTAALSCORE"),
        (
            "rangnummer_kolom",
            f"Uiteindelijke rangnummer master BioMed {JAAR % 100}-{(JAAR + 1) % 100}",
        ),
        ("loting_kolom", f"Random rangnummer bepaald 15-04-{JAAR}"),
    ],
    [
        [
            "avt_logischredeneren_Schaalscore",
            "Analytische Vaardigheden Toets",
            "Logisch redeneren schaalscore",
            "Analytisch denken",
        ],
        [
            "avt_datavisualisatie_Schaalscore",
            "Analytische Vaardigheden Toets",
            "Datavisualisatie schaalscore",
            "Methodologisch inzicht",
        ],
        [
            "avt_methodologie_Schaalscore",
            "Analytische Vaardigheden Toets",
            "Methodologie schaalscore",
            "Analytisch denken",
        ],
        [
            "avt_probleemoplossing_Schaalscore",
            "Analytische Vaardigheden Toets",
            "Probleemoplossing schaalscore",
            "Probleemoplossend vermogen",
        ],
        [
            "avt_kritischlezen_Schaalscore",
            "Analytische Vaardigheden Toets",
            "Kritisch lezen schaalscore",
            "Communicatieve vaardigheden",
        ],
        [
            "avt_numeriekevaardigheden_Schaalscore",
            "Analytische Vaardigheden Toets",
            "Numerieke vaardigheden schaalscore",
            "Methodologisch inzicht",
        ],
        [
            "Beoordeling_analytischdenken\nonder/op/boven niveau = 1/2/3",
            "Reflectie-opdracht",
            "Beoordeling analytisch denken (1-2-3)",
            "Analytisch denken",
        ],
        [
            "Beoordeling_communicatievevaardigheden\nonder/op/boven niveau = 1/2/3",
            "Reflectie-opdracht",
            "Beoordeling communicatie (1-2-3)",
            "Communicatieve vaardigheden",
        ],
        [
            "sjtb_totaal_Schaalscore",
            "SJT-B",
            "Totaalscore sociale intelligentie biomedisch",
            "Sociale intelligentie",
        ],
        [
            "wrc_Schaalscore",
            "Wetenschappelijk Redeneren Casus",
            "Schaalscore wetenschappelijk redeneren",
            "Wetenschappelijk redeneren",
        ],
    ],
)

# ── 1CHO-data ────────────────────────────────────────────────────────────────
# 40 geselecteerd -> ingeschreven, 15 reserve -> 5 ingeschreven, rest niet
ingeschreven_mask = (rang_totaal <= 40) | ((rang_totaal <= 55) & (RNG.random(N) < 0.33))
ingeschreven_ids = studentnummers[ingeschreven_mask]
ingeschreven_scores = totaalscore[ingeschreven_mask]
n_ingeschreven = len(ingeschreven_ids)

# Doorstroom correlates with selection score
ingeschreven_z = ingeschreven_scores - ingeschreven_scores.mean()
if ingeschreven_scores.std() > 0:
    ingeschreven_z = ingeschreven_z / ingeschreven_scores.std()
else:
    ingeschreven_z = np.zeros(n_ingeschreven)

doorstroom_kans = 1 / (1 + np.exp(-(-0.1 + 0.6 * ingeschreven_z)))
doorstroomt = RNG.random(n_ingeschreven) < doorstroom_kans

geslacht = RNG.choice(
    ["vrouw", "man", "anders"], size=n_ingeschreven, p=[0.65, 0.32, 0.03]
)
herkomst = RNG.choice(
    [
        "Nederland",
        "westerse achtergrond",
        "Marokko",
        "Turkije",
        "Suriname/Antillen",
        "overig niet-westers",
    ],
    size=n_ingeschreven,
    p=[0.72, 0.08, 0.04, 0.03, 0.05, 0.08],
)
vooropleiding = RNG.choice(
    [
        "Biomedische wetenschappen bachelor",
        "Geneeskunde bachelor",
        "Biologie",
        "Scheikunde",
        "Anders",
    ],
    size=n_ingeschreven,
    p=[0.45, 0.25, 0.15, 0.10, 0.05],
)
vo_cijfers = np.clip(RNG.normal(7.2, 0.5, n_ingeschreven), 5.5, 9.5).round(1)

groep = np.where(
    doorstroomt,
    "Doorgestroomd naar jaar 2",
    "Gestart, niet naar jaar 2",
)

cho_df = pd.DataFrame(
    {
        "studentnummer": ingeschreven_ids,
        "selectiejaar": JAAR,
        "opleiding": OPLEIDING,
        "instellingscode": INSTELLING,
        "groep": groep,
        "geslacht": geslacht,
        "herkomst": herkomst,
        "hoogste_vooropleiding": vooropleiding,
        "gem_eindcijfer_vo": vo_cijfers,
    }
)

cho_path = OUT_DIR / "1cho_data_biomed_2026.csv"
cho_df.to_csv(cho_path, index=False, sep=";")

print(f"\n1CHO-data: {n_ingeschreven} ingeschreven van {N} kandidaten")
print(f"Groepen: {dict(cho_df['groep'].value_counts())}")
print(f"Opgeslagen: {cho_path}")

# ── Kopieer naar demo directory ──────────────────────────────────────────────
import shutil

demo_subdir = Path("data/demo/biomed_aumc_2026")
demo_subdir.mkdir(parents=True, exist_ok=True)
shutil.copy2(xlsx_path, demo_subdir / "selectiedata.xlsx")
shutil.copy2(config_path, demo_subdir / "config.xlsx")
shutil.copy2(cho_path, demo_subdir / "1cho_data.csv")
print(f"\nDemo bestanden gekopieerd naar {demo_subdir}/")

print("\nSamenvatting:")
print(f"  Kolommen in selectiebestand: {df.shape[1]}")
print("  Kolommen in config: 10")
print(f"  Kandidaten: {N}")
print(f"  Ingeschreven: {n_ingeschreven}")
print(f"  Doorgestroomd: {int(doorstroomt.sum())}")
print(f"  Niet doorgestroomd: {int(n_ingeschreven - doorstroomt.sum())}")
print(f"  Niet gestart: {N - n_ingeschreven}")
