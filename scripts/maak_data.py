"""
Genereert synthetische selectie- en 1CHO-data voor de evaluatietool.

Draai dit script eenmalig om de data in data/synthetic/ aan te maken:
    uv run python scripts/maak_data.py

Drie groepen worden aangemaakt:
  - Niet gestart: niet geselecteerd of aanmelding ingetrokken
  - Gestart, niet naar jaar 2: jaar-1 rij in 1CHO maar geen jaar-2 rij
  - Doorgestroomd naar jaar 2: zowel jaar-1 als jaar-2 rij in 1CHO
"""

from pathlib import Path
import numpy as np
import pandas as pd

RNG = np.random.default_rng(2024)

DATA_DIR = Path("data/synthetic")
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Parameters
JAREN = [2021, 2022, 2023]
N_KANDIDATEN = 400
N_GESELECTEERD = 100
OPLEIDING = "B Gezondheidswetenschappen"
INSTELLINGSCODE = "DEMO"
PGN_START = 10000


def maak_selectiedata() -> pd.DataFrame:
    cohorten = []

    for i, jaar in enumerate(JAREN):
        pgn_offset = PGN_START + i * N_KANDIDATEN
        n = N_KANDIDATEN

        geslacht = RNG.choice(
            ["vrouw", "man", "anders"], size=n, p=[0.65, 0.32, 0.03]
        )
        vooropl_keuzes = [
            "vwo profiel natuur & gezondheid",
            "vwo profiel natuur & techniek",
            "vwo profiel cultuur & maatschappij",
            "vwo profiel economie & maatschappij",
            "hbo-propedeuse",
            "anders",
        ]
        vooropl = RNG.choice(
            vooropl_keuzes, size=n, p=[0.45, 0.15, 0.20, 0.10, 0.07, 0.03]
        )
        herkomst = RNG.choice(
            ["Nederland", "westerse achtergrond", "Marokko", "Turkije",
             "Suriname/Antillen", "overig niet-westers"],
            size=n, p=[0.72, 0.08, 0.05, 0.04, 0.05, 0.06],
        )
        leeftijd = np.clip(RNG.normal(19.2, 1.4, n).round().astype(int), 17, 26)

        # VO-cijfer correleert licht met vooropleiding
        gem_vo_base = np.where(vooropl == "vwo profiel natuur & gezondheid", 7.2,
                     np.where(vooropl == "vwo profiel natuur & techniek", 7.1,
                     np.where(vooropl == "vwo profiel cultuur & maatschappij", 6.9,
                     np.where(vooropl == "vwo profiel economie & maatschappij", 6.8,
                     np.where(vooropl == "hbo-propedeuse", 6.5, 6.4)))))
        gem_vo = np.clip(RNG.normal(gem_vo_base, 0.6), 4, 10).round(1)

        # Selectiescores correleren via latente kwaliteit
        latent = RNG.normal(0, 1, n)
        motivatiescore  = np.clip((5 + 1.2 * latent + RNG.normal(0, 0.8, n)).round(1), 1, 10)
        cv_score        = np.clip((5 + 1.0 * latent + RNG.normal(0, 0.9, n)).round(1), 1, 10)
        interview_score = np.clip((5 + 1.3 * latent + RNG.normal(0, 0.7, n)).round(1), 1, 10)
        totaalscore     = (0.30 * motivatiescore + 0.20 * cv_score + 0.50 * interview_score).round(2)

        rangorde = pd.Series(totaalscore).rank(ascending=False, method="first").astype(int).values

        selectie_uitkomst = np.where(
            rangorde <= N_GESELECTEERD, "geselecteerd",
            np.where(rangorde <= N_GESELECTEERD + 20, "reserve", "niet geselecteerd")
        )

        kandidaat_id = pgn_offset + np.arange(1, n + 1)
        pgn = np.where(
            np.isin(selectie_uitkomst, ["geselecteerd", "reserve"]),
            kandidaat_id.astype(float),
            np.nan,
        )

        cohorten.append(pd.DataFrame({
            "kandidaat_id":              kandidaat_id,
            "persoonsgebonden_nummer":   pgn,
            "selectiejaar":              jaar,
            "opleiding":                 OPLEIDING,
            "instellingscode":           INSTELLINGSCODE,
            "geslacht":                  geslacht,
            "leeftijd":                  leeftijd,
            "herkomst":                  herkomst,
            "hoogste_vooropleiding":     vooropl,
            "gem_eindcijfer_vo":         gem_vo,
            "motivatiescore":            motivatiescore,
            "cv_score":                  cv_score,
            "interview_score":           interview_score,
            "totaalscore":               totaalscore,
            "rangorde":                  rangorde,
            "selectie_uitkomst":         selectie_uitkomst,
        }))

    return pd.concat(cohorten, ignore_index=True)


def maak_1cho_data(selectiedata: pd.DataFrame) -> pd.DataFrame:
    def logistic(x):
        return 1 / (1 + np.exp(-x))

    ingeschrevenen = selectiedata[
        selectiedata["selectie_uitkomst"].isin(["geselecteerd", "reserve"])
    ].copy()

    # Kans op inschrijving en doorstroom
    gaat_studeren_kans = np.where(
        ingeschrevenen["selectie_uitkomst"] == "geselecteerd", 0.95, 0.38
    )
    ingeschrevenen = ingeschrevenen[
        RNG.random(len(ingeschrevenen)) < gaat_studeren_kans
    ].copy()

    doorstroom_kans = logistic(-0.3 + 0.12 * ingeschrevenen["interview_score"].values)
    ingeschrevenen["doorstroomt"] = RNG.random(len(ingeschrevenen)) < doorstroom_kans

    rijen = []
    for _, s in ingeschrevenen.iterrows():
        for verblijfsjaar in [1, 2] if s["doorstroomt"] else [1]:
            inschrijvingsjaar = int(s["selectiejaar"]) + (verblijfsjaar - 1)
            rijen.append({
                "persoonsgebonden_nummer":                        s["persoonsgebonden_nummer"],
                "inschrijvingsjaar":                             inschrijvingsjaar,
                "instellingscode":                               "DEMO",
                "actuele_instelling_naam":                       "DEMO Hogeschool",
                "opleidingscode_naam_opleiding":                 s["opleiding"],
                "opleidingsvorm":                                "voltijd",
                "opleidingsfase":                                "bachelor",
                "eerste_jaar_aan_deze_opleiding_instelling":     int(s["selectiejaar"]),
                "verblijfsjaar_hoger_onderwijs":                 verblijfsjaar,
                "geslacht":                                      s["geslacht"],
                "leeftijd_per_peildatum_1_oktober":              int(s["leeftijd"]) + (verblijfsjaar - 1),
                "herkomstland_naam":                             s["herkomst"],
                "hoogste_vooropleiding_omschrijving":            s["hoogste_vooropleiding"],
                "gem_eindcijfer_vo":                             s["gem_eindcijfer_vo"],
                "indicatie_eerstejaars":                         "eerstejaars" if verblijfsjaar == 1 else "hogerejaars",
                "datum_inschrijving":                            f"{inschrijvingsjaar}0901",
            })

    return pd.DataFrame(rijen)


def koppel_en_classificeer(
    selectiedata: pd.DataFrame, cho_data: pd.DataFrame
) -> pd.DataFrame:
    pgns_jaar1 = set(cho_data.loc[cho_data["verblijfsjaar_hoger_onderwijs"] == 1, "persoonsgebonden_nummer"].dropna())
    pgns_jaar2 = set(cho_data.loc[cho_data["verblijfsjaar_hoger_onderwijs"] == 2, "persoonsgebonden_nummer"].dropna())

    def groep(row):
        pgn = row["persoonsgebonden_nummer"]
        if pd.isna(pgn) or pgn not in pgns_jaar1:
            return "Niet gestart"
        if pgn in pgns_jaar2:
            return "Doorgestroomd naar jaar 2"
        return "Gestart, niet naar jaar 2"

    df = selectiedata.copy()
    df["groep"] = df.apply(groep, axis=1)
    return df


if __name__ == "__main__":
    print("Selectiedata genereren...")
    selectiedata = maak_selectiedata()
    selectiedata.to_csv(DATA_DIR / "selectiedata_voorbeeld.csv", index=False, sep=";")
    print(f"  {len(selectiedata)} kandidaten, {selectiedata['selectie_uitkomst'].value_counts().to_dict()}")

    print("1CHO-data genereren...")
    cho_data = maak_1cho_data(selectiedata)
    cho_data.to_csv(DATA_DIR / "EV_DEMO_selectieopleiding.csv", index=False, sep=";")
    jaar1 = (cho_data["verblijfsjaar_hoger_onderwijs"] == 1).sum()
    jaar2 = (cho_data["verblijfsjaar_hoger_onderwijs"] == 2).sum()
    print(f"  {len(cho_data)} rijen — jaar 1: {jaar1}, jaar 2: {jaar2}, uitval: {jaar1 - jaar2}")

    print("Koppelen en classificeren...")
    gekoppeld = koppel_en_classificeer(selectiedata, cho_data)
    gekoppeld.to_parquet(DATA_DIR / "gekoppeld.parquet", index=False)
    print(gekoppeld.groupby(["selectiejaar", "groep"]).size().unstack(fill_value=0).to_string())
    print("\nKlaar. Draai nu: uv run streamlit run app.py")
