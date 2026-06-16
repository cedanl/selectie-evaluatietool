"""
Genereer een fictief selectiebestand voor Gedragswetenschappen (demo Leiden).

Structuur lijkt op Psychologie 2026-2027: schoolcijfers met drie
kernvakken, een combinatiecijfer en een matchingsvragenlijst. De
keuzevakken staan wel in het ruwe Excel-bestand, maar worden niet als
selectie-items in de config meegenomen (alleen via het combinatiecijfer).
Bachelor, header_rij=3.

150 kandidaten, waarvan 50 ingeschreven. Niet herleidbaar naar echte data.

Draai:
    uv run python scripts/eenmalig/maak_fictief_demo_leiden.py
"""

import shutil
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from update_configs import make_config

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from cho_transform import bouw_ruwe_cho  # noqa: E402

RNG = np.random.default_rng(2468)

OUT_DIR = Path("data/fictief")
OUT_DIR.mkdir(parents=True, exist_ok=True)

N = 150
OPLEIDING = "Gedragswetenschappen"
INSTELLING = "Universiteit Leiden"
JAAR = 2026
BLAD_NAAM = "Scores en ranking"


def clip_round(arr, lo, hi, decimals=2):
    return np.clip(arr, lo, hi).round(decimals)


studentnummers = RNG.choice(range(3000000, 3999999), size=N, replace=False)
studentnummers.sort()

# -- Instrument 1: Schooldiploma (kernvakken) --------------------------------
# Drie kernvakken met cijfers en puntenscore, net als Psychologie
kernvakken = {
    "Wiskunde": {"afk": "WI", "gem": 6.5, "std": 1.0},
    "Engels": {"afk": "EN", "gem": 6.9, "std": 0.9},
    "Biologie": {"afk": "BIO", "gem": 6.7, "std": 0.95},
}


def cijfer_naar_punten(cijfer):
    return clip_round((cijfer - 4.0) / 1.2, 0, 5)


kolommen = {}
kolom_volgorde = []

for vak, params in kernvakken.items():
    afk = params["afk"]
    cijfers = clip_round(RNG.normal(params["gem"], params["std"], N), 4.0, 10.0)
    punten = cijfer_naar_punten(cijfers)
    kolommen[f"{afk} CIJF"] = cijfers
    kolommen[f"{afk} SCORE"] = punten
    kolom_volgorde.extend([f"{afk} CIJF", f"{afk} SCORE"])

kern_scores = np.column_stack(
    [kolommen[f"{p['afk']} SCORE"] for p in kernvakken.values()]
)
kolommen["WI+EN+BIO (0-5)"] = kern_scores.mean(axis=1).round(2)
kolom_volgorde.append("WI+EN+BIO (0-5)")

# -- Instrument 2: Keuzevakken (V1-V10) --------------------------------------
keuzevakken_pool = [
    "Nederlands",
    "Frans",
    "Duits",
    "Geschiedenis",
    "Aardrijkskunde",
    "Economie",
    "Maatschappijleer",
    "Natuurkunde",
    "Scheikunde",
    "Informatica",
    "Filosofie",
    "Muziek",
    "Kunst",
]

max_keuzevakken = 10
n_keuzevakken_per_student = RNG.integers(4, 9, size=N)

for ki in range(1, max_keuzevakken + 1):
    vak_namen = []
    vak_cijfers = []
    vak_scores = []
    for si in range(N):
        if ki <= n_keuzevakken_per_student[si]:
            vak = RNG.choice(keuzevakken_pool)
            cijf = clip_round(RNG.normal(6.6, 1.0, 1), 4.0, 10.0)[0]
            vak_namen.append(vak)
            vak_cijfers.append(cijf)
            vak_scores.append(cijfer_naar_punten(cijf))
        else:
            vak_namen.append(np.nan)
            vak_cijfers.append(np.nan)
            vak_scores.append(np.nan)
    kolommen[f"V{ki}"] = vak_namen
    kolommen[f"V{ki} CIJF"] = vak_cijfers
    kolommen[f"V{ki} SCORE"] = vak_scores
    kolom_volgorde.extend([f"V{ki}", f"V{ki} CIJF", f"V{ki} SCORE"])

# Combinatiecijfer: gemiddelde van alle cijfers
alle_cijfers_per_student = []
for si in range(N):
    cijs = [kolommen[f"{p['afk']} CIJF"][si] for p in kernvakken.values()]
    for ki in range(1, max_keuzevakken + 1):
        c = kolommen[f"V{ki} CIJF"][si]
        if not np.isnan(c):
            cijs.append(c)
    alle_cijfers_per_student.append(np.mean(cijs))

kolommen["Combinatiecijfer"] = np.array(alle_cijfers_per_student).round(2)
kolom_volgorde.append("Combinatiecijfer")

combi_score = cijfer_naar_punten(np.array(alle_cijfers_per_student))
kolommen["COMBICIJF \nSCORE"] = combi_score
kolom_volgorde.append("COMBICIJF \nSCORE")

# Keuzevakken + combinatiecijfer deelscore
keuzevak_gem = []
for si in range(N):
    scores = []
    for ki in range(1, max_keuzevakken + 1):
        s = kolommen[f"V{ki} SCORE"][si]
        if not np.isnan(s):
            scores.append(s)
    scores.append(combi_score[si])
    keuzevak_gem.append(np.mean(scores))

kolommen["V1-V10 + COMBICIJF (0-5)"] = np.array(keuzevak_gem).round(2)
kolom_volgorde.append("V1-V10 + COMBICIJF (0-5)")

# -- Instrument 3: Matchingsvragenlijst (1-3 schaal) -------------------------
matching_score = RNG.choice([1, 2, 3], size=N, p=[0.15, 0.45, 0.40]).astype(float)
kolommen["Matching Score (1-3)"] = matching_score
kolom_volgorde.append("Matching Score (1-3)")

# -- Deelscores en totaalscore ------------------------------------------------
# Vragenlijst % = (WI+EN+BIO + V1-V10+COMBICIJF) / 2, genormaliseerd naar %
vragenlijst_pct = (
    (kolommen["WI+EN+BIO (0-5)"] + kolommen["V1-V10 + COMBICIJF (0-5)"]) / 2 / 5 * 100
).round(1)
matching_pct = (matching_score / 3 * 100).round(1)

kolommen["Vragenlijst %"] = vragenlijst_pct
kolommen["Matching %"] = matching_pct
kolom_volgorde.extend(["Vragenlijst %", "Matching %"])

totaal_pct = (0.60 * vragenlijst_pct + 0.40 * matching_pct).round(1)
kolommen["Totale selectiescore %"] = totaal_pct
kolommen["Rangnummer"] = (
    pd.Series(totaal_pct).rank(ascending=False, method="min").astype(int).values
)
kolom_volgorde.extend(["Totale selectiescore %", "Rangnummer"])

# -- Build DataFrame ----------------------------------------------------------
df = pd.DataFrame({"Studentnummer": studentnummers})
for col in kolom_volgorde:
    df[col] = kolommen[col]

print(f"Selectiebestand: {df.shape[0]} kandidaten, {df.shape[1]} kolommen")

# -- Write Excel met groepskoppen (header_rij=3) ------------------------------
from openpyxl import Workbook  # noqa: E402
from openpyxl.styles import Font, PatternFill  # noqa: E402

xlsx_path = OUT_DIR / "selectiedata_demo_leiden_2026.xlsx"

wb = Workbook()
ws = wb.active
ws.title = BLAD_NAAM

header_fill = PatternFill(start_color="2C3E50", end_color="2C3E50", fill_type="solid")
header_font = Font(color="FFFFFF", bold=True)
group_font = Font(bold=True, size=12)

# Rij 1: groepskoppen
ws.cell(row=1, column=2, value="Kernvakken Score").font = group_font
ws.cell(row=1, column=8, value="Keuzevakken").font = group_font
ws.cell(row=1, column=39, value="Deelscores").font = group_font
ws.cell(row=1, column=41, value="Matchingsvragenlijst").font = group_font
ws.cell(row=1, column=44, value="Totale selectiescore en rangnummer").font = group_font

# Rij 2: leeg (spacer)
# Rij 3: kolomnamen
for ci, col_name in enumerate(df.columns, 1):
    cell = ws.cell(row=3, column=ci, value=col_name)
    cell.font = header_font
    cell.fill = header_fill

# Rij 4+: data
for ri, (_, row) in enumerate(df.iterrows(), 4):
    for ci, val in enumerate(row, 1):
        if pd.notna(val):
            ws.cell(row=ri, column=ci, value=val)

wb.save(xlsx_path)
print(f"Opgeslagen: {xlsx_path}")

# -- Configuratiebestand ------------------------------------------------------
config_path = OUT_DIR / "config_demo_leiden_2026.xlsx"
make_config(
    str(config_path),
    [
        ("Koppel_id_kolom", "Studentnummer"),
        ("opleiding", OPLEIDING),
        ("instellingscode", INSTELLING),
        ("jaar", str(JAAR)),
        ("blad_naam", BLAD_NAAM),
        ("header_rij", "3"),
        ("totaalscore_kolom", "Totale selectiescore %"),
    ],
    [
        ["WI SCORE", "Schooldiploma", "Wiskunde puntenscore", "Vakkennis wiskunde"],
        ["EN SCORE", "Schooldiploma", "Engels puntenscore", "Vakkennis Engels"],
        ["BIO SCORE", "Schooldiploma", "Biologie puntenscore", "Vakkennis biologie"],
        [
            "WI+EN+BIO (0-5)",
            "Schooldiploma",
            "Gemiddelde kernvakken (0-5)",
            "Profielsterkheid",
        ],
        [
            "COMBICIJF \nSCORE",
            "Schooldiploma",
            "Combinatiecijfer puntenscore",
            "Algemeen studieniveau",
        ],
        [
            "Matching Score (1-3)",
            "Matchingsvragenlijst",
            "Matchingscore (1-3)",
            "Studiemotivatie",
        ],
        ["Vragenlijst %", "Deelscore", "Vragenlijst score percentage", ""],
    ],
)

# -- 1CHO-data ----------------------------------------------------------------
rang = kolommen["Rangnummer"]
ingeschreven_mask = rang <= 50
ingeschreven_ids = studentnummers[ingeschreven_mask]
ingeschreven_totaal = totaal_pct[ingeschreven_mask]
n_ingeschreven = len(ingeschreven_ids)

totaal_z = ingeschreven_totaal - ingeschreven_totaal.mean()
if ingeschreven_totaal.std() > 0:
    totaal_z = totaal_z / ingeschreven_totaal.std()
else:
    totaal_z = np.zeros(n_ingeschreven)

doorstroom_kans = 1 / (1 + np.exp(-(0.0 + 0.5 * totaal_z)))
doorstroomt = RNG.random(n_ingeschreven) < doorstroom_kans

geslacht = RNG.choice(
    ["vrouw", "man", "anders"], size=n_ingeschreven, p=[0.64, 0.33, 0.03]
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
    p=[0.71, 0.08, 0.05, 0.04, 0.05, 0.07],
)
vooropleiding = RNG.choice(
    ["VWO", "HAVO + propedeuse", "Anders"],
    size=n_ingeschreven,
    p=[0.80, 0.12, 0.08],
)
vo_cijfers = clip_round(RNG.normal(6.8, 0.6, n_ingeschreven), 5.0, 9.5)

cho_df = bouw_ruwe_cho(
    ingeschreven_ids,
    jaar=JAAR,
    doorstroomt=doorstroomt,
    opleiding=OPLEIDING,
    instellingscode=INSTELLING,
    geslacht=geslacht,
    herkomst=herkomst,
    vooropleiding_omschrijving=vooropleiding,
    gem_eindcijfer_vo=vo_cijfers,
)

cho_path = OUT_DIR / "1cho_data_demo_leiden_2026.csv"
cho_df.to_csv(cho_path, index=False, sep=";")

print(f"\n1CHO-data: {n_ingeschreven} ingeschreven van {N} kandidaten")
print(f"Doorgestroomd: {int(doorstroomt.sum())}, niet: {int((~doorstroomt).sum())}")

# -- Kopieer naar demo --------------------------------------------------------
demo_subdir = Path("data/demo/demo_leiden_2026")
demo_subdir.mkdir(parents=True, exist_ok=True)
shutil.copy2(xlsx_path, demo_subdir / "selectiedata.xlsx")
shutil.copy2(config_path, demo_subdir / "config.xlsx")
shutil.copy2(cho_path, demo_subdir / "1cho_data.csv")
print(f"Demo bestanden in {demo_subdir}/")

print("\nSamenvatting:")
print(f"  Kolommen in selectiebestand: {df.shape[1]}")
print("  Kolommen in config: 7 (keuzevak-items en matching % niet meegenomen)")
print(f"  Kandidaten: {N}")
print("  header_rij: 3 (groepskoppen boven kolomnamen)")
print(f"  Ingeschreven: {n_ingeschreven}")
print(f"  Doorgestroomd: {int(doorstroomt.sum())}")
print(f"  Niet doorgestroomd: {int(n_ingeschreven - doorstroomt.sum())}")
print(f"  Niet gestart: {N - n_ingeschreven}")
