"""
Zet demodata klaar voor de evaluatietool.

Kopieert de selectiedata en configs naar data/demo/ subdirectories per
opleiding-jaar combinatie, en genereert synthetische 1CHO-data voor de
kandidaten in elk bestand.

Draai eenmalig:
    uv run python scripts/maak_data.py
"""

import shutil
from pathlib import Path

import numpy as np
import pandas as pd

RNG = np.random.default_rng(2026)

DEMO_DIR = Path("data/demo")

GESLACHT_LABELS = ["vrouw", "man", "anders"]
HERKOMST_LABELS = [
    "Nederland",
    "westerse achtergrond",
    "Marokko",
    "Turkije",
    "Suriname/Antillen",
    "overig niet-westers",
]

DATASETS = [
    {
        "naam": "far_leiden_2026",
        "label": "Farmacie LUMC 2026",
        "selectiedata": "data/dummy data selectie FAR Leiden 2026.xlsx",
        "config": "config_FAR_Leiden_2026.xlsx",
        "id_kolom": "Studentnummer",
        "blad": "2026 LUMC Farmacie",
        "opleiding": "Farmacie",
        "instellingscode": "LUMC",
        "jaar": 2026,
        "opleidingsfase": "M",
        "vooropleidingen": {
            "Farmacie bachelor": 0.58,
            "Biomedische wetenschappen": 0.17,
            "Scheikunde": 0.10,
            "Biologie": 0.10,
            "Anders": 0.05,
        },
        "gem_vo": 7.1,
        "sd_vo": 0.5,
    },
    {
        "naam": "far_leiden_2025",
        "label": "Farmacie LUMC 2025",
        "selectiedata": "data/dummy data selectie FAR Leiden 2025.xlsx",
        "config": "config_FAR_Leiden_2025.xlsx",
        "id_kolom": "A_Nummer_Aanvraag",
        "blad": "2 Master beoordelingen",
        "opleiding": "Farmacie",
        "instellingscode": "LUMC",
        "jaar": 2025,
        "opleidingsfase": "M",
        "vooropleidingen": {
            "Farmacie bachelor": 0.58,
            "Biomedische wetenschappen": 0.17,
            "Scheikunde": 0.10,
            "Biologie": 0.10,
            "Anders": 0.05,
        },
        "gem_vo": 7.1,
        "sd_vo": 0.5,
    },
    {
        "naam": "psychologie_2026",
        "label": "Psychologie 2026-2027",
        "selectiedata": "data/2026-2027 Totaalscores Psychologie (dummy).xlsx",
        "config": "config_Psychologie_2026_2027.xlsx",
        "id_kolom": "Studentnummer",
        "blad": "Scores en ranking",
        "header_rij": 3,
        "opleiding": "Psychologie",
        "instellingscode": "Universiteit Leiden",
        "jaar": 2026,
        "opleidingsfase": "B",
        "vooropleidingen": {
            "VWO": 0.82,
            "HAVO + propedeuse": 0.10,
            "Anders": 0.08,
        },
        "gem_vo": 6.8,
        "sd_vo": 0.6,
    },
    {
        "naam": "psychologie_2022",
        "label": "Psychologie 2022-2023",
        "selectiedata": "data/2022-2023 Totaalscores Psychologie.xlsx",
        "config": "config_Psychologie_2022_2023.xlsx",
        "id_kolom": "Studentnummer",
        "blad": "Totaalscores met formules",
        "opleiding": "Psychologie",
        "instellingscode": "Universiteit Leiden",
        "jaar": 2022,
        "opleidingsfase": "B",
        "vooropleidingen": {
            "VWO": 0.82,
            "HAVO + propedeuse": 0.10,
            "Anders": 0.08,
        },
        "gem_vo": 6.8,
        "sd_vo": 0.6,
    },
]


def logistic(x):
    return 1 / (1 + np.exp(-x))


def genereer_1cho(dataset_cfg, studentnummers, totaalscores):
    n = len(studentnummers)
    if n == 0:
        return pd.DataFrame()

    geslacht = RNG.choice(GESLACHT_LABELS, size=n, p=[0.62, 0.35, 0.03])

    vooropl_labels = list(dataset_cfg["vooropleidingen"].keys())
    vooropl_probs = list(dataset_cfg["vooropleidingen"].values())
    vooropl = RNG.choice(vooropl_labels, size=n, p=vooropl_probs)

    herkomst = RNG.choice(
        HERKOMST_LABELS, size=n, p=[0.70, 0.09, 0.05, 0.04, 0.05, 0.07]
    )

    gem_vo = dataset_cfg.get("gem_vo", 7.0)
    sd_vo = dataset_cfg.get("sd_vo", 0.5)
    vo_cijfers = np.clip(RNG.normal(gem_vo, sd_vo, n), 5, 10).round(1)

    totaal_arr = np.array(totaalscores, dtype=float)
    if totaal_arr.std() > 0:
        totaal_z = (totaal_arr - totaal_arr.mean()) / totaal_arr.std()
    else:
        totaal_z = np.zeros(n)
    doorstroom_kans = logistic(-0.2 + 0.5 * totaal_z)
    doorstroomt = RNG.random(n) < doorstroom_kans

    groep = np.where(
        doorstroomt,
        "Doorgestroomd naar jaar 2",
        "Gestart, niet naar jaar 2",
    )

    studie_df = pd.DataFrame(
        {
            "studentnummer": studentnummers,
            "selectiejaar": dataset_cfg["jaar"],
            "opleiding": dataset_cfg["opleiding"],
            "instellingscode": dataset_cfg["instellingscode"],
            "groep": groep,
            "geslacht": geslacht,
            "herkomst": herkomst,
            "hoogste_vooropleiding": vooropl,
            "gem_eindcijfer_vo": vo_cijfers,
        }
    )

    return studie_df


def verwerk_dataset(cfg):
    sel_path = Path(cfg["selectiedata"])
    config_path = Path(cfg["config"])
    naam = cfg["naam"]
    demo_subdir = DEMO_DIR / naam

    if not sel_path.exists():
        print(f"  WAARSCHUWING: {sel_path} niet gevonden, overslaan")
        return
    if not config_path.exists():
        print(f"  WAARSCHUWING: {config_path} niet gevonden, overslaan")
        return

    demo_subdir.mkdir(parents=True, exist_ok=True)

    shutil.copy2(sel_path, demo_subdir / "selectiedata.xlsx")
    shutil.copy2(config_path, demo_subdir / "config.xlsx")

    header_rij = int(cfg.get("header_rij", 1)) - 1
    df = pd.read_excel(sel_path, sheet_name=cfg["blad"], header=header_rij)

    id_kolom = cfg["id_kolom"]
    matching = [c for c in df.columns if id_kolom in str(c)]
    if not matching:
        print(f"  WAARSCHUWING: ID-kolom '{id_kolom}' niet gevonden in {sel_path.name}")
        return

    id_col_actual = matching[0]
    studentnummers = df[id_col_actual].dropna().astype(int).tolist()

    totaalscore_kolom = None
    for c in df.columns:
        if "totaal" in str(c).lower() and "score" in str(c).lower():
            totaalscore_kolom = c
            break
    if totaalscore_kolom is None:
        for c in df.columns:
            if "totaal" in str(c).lower():
                totaalscore_kolom = c
                break

    if totaalscore_kolom and totaalscore_kolom in df.columns:
        totaalscores = (
            pd.to_numeric(df[totaalscore_kolom], errors="coerce").fillna(0).tolist()
        )
    else:
        totaalscores = [0.0] * len(studentnummers)

    n_total = len(studentnummers)
    n_ingeschreven = max(3, int(n_total * 0.7))
    ingeschreven_ids = studentnummers[:n_ingeschreven]
    ingeschreven_scores = totaalscores[:n_ingeschreven]

    studie_df = genereer_1cho(cfg, ingeschreven_ids, ingeschreven_scores)

    if studie_df.empty:
        print(f"  WAARSCHUWING: geen studenten voor {naam}")
        return

    studie_df.to_csv(demo_subdir / "1cho_data.csv", index=False, sep=";")

    print(f"  {naam}: {n_total} kandidaten, {n_ingeschreven} in 1CHO")
    print(f"    Groepen: {studie_df['groep'].value_counts().to_dict()}")
    print(f"    Bestanden in {demo_subdir}/")


if __name__ == "__main__":
    print("Demo datasets aanmaken...")
    print()

    for cfg in DATASETS:
        print(f"Dataset: {cfg['label']}")
        verwerk_dataset(cfg)
        print()

    # Backwards-compatible: kopieer FAR 2026 naar data/demo/ root
    far2026_dir = DEMO_DIR / "far_leiden_2026"
    if far2026_dir.exists():
        for f in ["selectiedata.xlsx", "config.xlsx", "1cho_data.csv"]:
            src = far2026_dir / f
            if src.exists():
                shutil.copy2(src, DEMO_DIR / f)
        print("Root demo bestanden bijgewerkt (backwards compatible, FAR 2026)")

    print("\nKlaar. Draai nu: uv run python app.py")
