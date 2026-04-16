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


# Coderingen die overeenkomen met het raw EV_* formaat van 1cijferho
# Bron: EV299XX24_DEMO.csv + Dec_* bestanden
GESLACHT_CODES = {"vrouw": "V", "man": "M", "anders": "O"}

VOOROPLEIDING_CODES = {
    "vwo profiel natuur & gezondheid":     405,
    "vwo profiel natuur & techniek":       411,
    "vwo profiel cultuur & maatschappij":  404,
    "vwo profiel economie & maatschappij": 403,
    "hbo-propedeuse":                      502,
    "anders":                              402,
}

# herkomst_indikking_volgens_cbs_definitie (1CHO/CBS codering)
HERKOMST_CODES = {
    "Nederland":            1,
    "westerse achtergrond": 2,
    "Marokko":              3,
    "Turkije":              4,
    "Suriname/Antillen":    5,
    "overig niet-westers":  7,
}

# Omgekeerde mappings voor decodering in de koppelstap
GESLACHT_DECODE    = {v: k for k, v in GESLACHT_CODES.items()}
HERKOMST_DECODE    = {v: k for k, v in HERKOMST_CODES.items()}
VOOROPLEIDING_DECODE = {v: k for k, v in VOOROPLEIDING_CODES.items()}


def maak_1cho_data(selectiedata: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Genereert 1CHO-inschrijvingsrijen in het raw EV_* formaat van 1cijferho.

    Kolommen gebruiken de numerieke en letter-codes zoals in de echte data:
      geslacht V/M, opleidingsvorm 1/2, hoogste_vooropleiding numeriek, etc.

    De groepsindeling wordt ook teruggegeven: tijdens generatie weten we al
    wie doorstroomt, dus een tweede lookup achteraf is niet nodig.

    Returns:
        cho_data: inschrijvingsrijen (raw EV-formaat)
        groep_per_pgn: DataFrame met persoonsgebonden_nummer + groep
    """
    def logistic(x):
        return 1 / (1 + np.exp(-x))

    ingeschrevenen = selectiedata[
        selectiedata["selectie_uitkomst"].isin(["geselecteerd", "reserve"])
    ].copy()

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
                "persoonsgebonden_nummer":                          int(s["persoonsgebonden_nummer"]),
                "inschrijvingsjaar":                               inschrijvingsjaar,
                "instellingscode":                                 "DEMO",
                "actuele_instelling":                              "DEMO",
                "opleidingscode":                                  99001,
                "opleidingsvorm":                                  1,
                "opleidingsfase":                                  "B",
                "maand_vanaf":                                     9,
                "code_beeindiging":                                0,
                "eerste_jaar_aan_deze_instelling":                 int(s["selectiejaar"]),
                "eerste_jaar_in_het_hoger_onderwijs":              int(s["selectiejaar"]) - (
                    RNG.integers(1, 4) if s["hoogste_vooropleiding"] == "hbo-propedeuse" else 0
                ),
                "eerste_jaar_aan_deze_opleiding_instelling":       int(s["selectiejaar"]),
                "verblijfsjaar_hoger_onderwijs":                   verblijfsjaar,
                "geslacht":                                        GESLACHT_CODES.get(s["geslacht"], "O"),
                "leeftijd_per_peildatum_1_oktober":                int(s["leeftijd"]) + (verblijfsjaar - 1),
                "hoogste_vooropleiding":                           VOOROPLEIDING_CODES.get(s["hoogste_vooropleiding"], 402),
                "diplomajaar_van_de_hoogste_vooropl_voor_het_ho":  int(s["selectiejaar"]) - RNG.integers(0, 3),
                "herkomst_indikking_volgens_cbs_definitie":        HERKOMST_CODES.get(s["herkomst"], 7),
                "gem_eindcijfer_vo_van_de_hoogste_vooropl_voor_het_ho": s["gem_eindcijfer_vo"],
                "indicatie_actief_op_peildatum":                   1,
                "soort_inschrijving_continu_type_ho_binnen_ho":    1 if verblijfsjaar == 1 else 2,
                "indicatie_eerstejaars_continu_type_ho_binnen_ho": 1 if verblijfsjaar == 1 else 2,
                "datum_inschrijving":                              f"{inschrijvingsjaar}0901",
                "datum_uitschrijving":                             f"{inschrijvingsjaar}0831" if verblijfsjaar == 1 and not s["doorstroomt"] else 0,
            })

    cho_data = pd.DataFrame(rijen)

    groep_per_pgn = ingeschrevenen[["persoonsgebonden_nummer", "doorstroomt"]].assign(
        groep=np.where(
            ingeschrevenen["doorstroomt"],
            "Doorgestroomd naar jaar 2",
            "Gestart, niet naar jaar 2",
        )
    ).drop(columns="doorstroomt")

    return cho_data, groep_per_pgn


def decodeer_cho(cho_data: pd.DataFrame) -> pd.DataFrame:
    """
    Decodeert de raw EV-codes naar leesbare waarden voor gebruik in het dashboard.
    In een echte pipeline zou dit via de Dec_* bestanden van 1cijferho lopen.
    """
    return cho_data.assign(
        geslacht=cho_data["geslacht"].map(GESLACHT_DECODE).fillna("onbekend"),
        herkomst=cho_data["herkomst_indikking_volgens_cbs_definitie"].map(HERKOMST_DECODE).fillna("overig"),
        hoogste_vooropleiding=cho_data["hoogste_vooropleiding"].map(VOOROPLEIDING_DECODE).fillna("onbekend"),
    )


if __name__ == "__main__":
    print("Selectiedata genereren...")
    selectiedata = maak_selectiedata()
    selectiedata.to_csv(DATA_DIR / "selectiedata_voorbeeld.csv", index=False, sep=";")
    print(f"  {len(selectiedata)} kandidaten, {selectiedata['selectie_uitkomst'].value_counts().to_dict()}")

    print("1CHO-data genereren + groepen bepalen...")
    cho_data, groep_per_pgn = maak_1cho_data(selectiedata)
    # Sla raw format op — zelfde structuur als echte EV_*.csv van 1cijferho
    cho_data.to_csv(DATA_DIR / "EV_DEMO_selectieopleiding.csv", index=False, sep=";")
    jaar1 = (cho_data["verblijfsjaar_hoger_onderwijs"] == 1).sum()
    jaar2 = (cho_data["verblijfsjaar_hoger_onderwijs"] == 2).sum()
    print(f"  {len(cho_data)} rijen — jaar 1: {jaar1}, jaar 2: {jaar2}, uitval: {jaar1 - jaar2}")

    # Decodeer CHO voor gebruik in het dashboard.
    # In een echte pipeline: lees de Dec_* bestanden van 1cijferho voor de mapping.
    cho_decoded = decodeer_cho(cho_data[cho_data["verblijfsjaar_hoger_onderwijs"] == 1])

    gekoppeld = (
        selectiedata
        .merge(groep_per_pgn, on="persoonsgebonden_nummer", how="left")
        .assign(groep=lambda df: df["groep"].fillna("Niet gestart"))
        # Voeg CHO-kolommen toe: in echte data is dit de bron voor demographics
        .merge(
            cho_decoded[["persoonsgebonden_nummer", "geslacht", "herkomst",
                         "hoogste_vooropleiding",
                         "gem_eindcijfer_vo_van_de_hoogste_vooropl_voor_het_ho"]],
            on="persoonsgebonden_nummer", how="left", suffixes=("_sel", "_cho")
        )
        # Gebruik CHO als beschikbaar, anders selectiedata
        .assign(
            geslacht=lambda df: df["geslacht_cho"].fillna(df["geslacht_sel"]),
            herkomst=lambda df: df["herkomst_cho"].fillna(df["herkomst_sel"]),
            hoogste_vooropleiding=lambda df: df["hoogste_vooropleiding_cho"].fillna(df["hoogste_vooropleiding_sel"]),
            gem_eindcijfer_vo_cho=lambda df: df["gem_eindcijfer_vo_van_de_hoogste_vooropl_voor_het_ho"],
        )
        .drop(columns=["geslacht_sel", "geslacht_cho",
                        "herkomst_sel", "herkomst_cho",
                        "hoogste_vooropleiding_sel", "hoogste_vooropleiding_cho",
                        "gem_eindcijfer_vo_van_de_hoogste_vooropl_voor_het_ho"])
    )
    gekoppeld.to_parquet(DATA_DIR / "gekoppeld.parquet", index=False)
    print(gekoppeld.groupby(["selectiejaar", "groep"]).size().unstack(fill_value=0).to_string())
    print("\nKlaar. Draai nu: uv run streamlit run app.py")
