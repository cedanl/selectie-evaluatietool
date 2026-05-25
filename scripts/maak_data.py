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

JAREN = [2021, 2022, 2023]
N_KANDIDATEN_PER_JAAR   = [342, 418, 391]
N_GESELECTEERD_PER_JAAR = [95, 110, 100]
OPLEIDING = "B Gezondheidswetenschappen"
INSTELLINGSCODE = "DEMO"
PGN_START = 10000

# Selectie-instrumenten met items, criteria, latente lading, ruis en wegingsfactor.
# De totaalscore is het gewogen gemiddelde van de instrument-scores.
INSTRUMENT_DEFINITIE = {
    "interview": {
        "lading":  1.3,
        "ruis":    0.8,
        "gewicht": 0.50,
        "items": {
            "vraag_1": ["inhoud", "presentatie"],
            "vraag_2": ["inhoud", "presentatie"],
            "vraag_3": ["inhoud", "presentatie"],
        },
    },
    "motivatiebrief": {
        "lading":  1.2,
        "ruis":    0.9,
        "gewicht": 0.30,
        "items": {
            "motivatie":   ["kwaliteit"],
            "aansluiting": ["kwaliteit"],
        },
    },
    "cv": {
        "lading":  1.0,
        "ruis":    1.0,
        "gewicht": 0.20,
        "items": {
            "opleiding": ["relevantie"],
            "ervaring":  ["relevantie"],
        },
    },
}


def maak_selectiedata() -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Genereert selectiedata op twee niveaus:
      - breed formaat (een rij per kandidaat) met geaggregeerde scores
      - lang formaat (een rij per kandidaat x instrument x item x criterium)

    Returns:
        selectiedata: DataFrame met een rij per kandidaat
        selectiescores: DataFrame met scores per instrument, item en criterium
    """
    cohorten = []
    scores_lang = []

    for i, jaar in enumerate(JAREN):
        pgn_offset = PGN_START + sum(N_KANDIDATEN_PER_JAAR[:i])
        n = N_KANDIDATEN_PER_JAAR[i]
        n_geselecteerd = N_GESELECTEERD_PER_JAAR[i]

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

        gem_vo_base = np.where(vooropl == "vwo profiel natuur & gezondheid", 7.2,
                     np.where(vooropl == "vwo profiel natuur & techniek", 7.1,
                     np.where(vooropl == "vwo profiel cultuur & maatschappij", 6.9,
                     np.where(vooropl == "vwo profiel economie & maatschappij", 6.8,
                     np.where(vooropl == "hbo-propedeuse", 6.5, 6.4)))))
        gem_vo = np.clip(RNG.normal(gem_vo_base, 0.6), 4, 10).round(1)

        kandidaat_id = pgn_offset + np.arange(1, n + 1)
        latent = RNG.normal(0, 1, n)

        # Genereer scores per instrument, item en criterium via gedeelde latente kwaliteit.
        # Instrument-score = gemiddelde over alle bijbehorende item/criterium-scores.
        instrument_scores = {}
        scores_lang_cohort = []
        for instrument, definitie in INSTRUMENT_DEFINITIE.items():
            item_arrays = []
            for item, criteria in definitie["items"].items():
                for criterium in criteria:
                    score = np.clip(
                        (5 + definitie["lading"] * latent
                         + RNG.normal(0, definitie["ruis"], n)).round(1),
                        1, 10,
                    )
                    item_arrays.append(score)
                    scores_lang_cohort.append(pd.DataFrame({
                        "kandidaat_id": kandidaat_id,
                        "selectiejaar":  jaar,
                        "instrument":    instrument,
                        "item":          item,
                        "criterium":     criterium,
                        "score":         score,
                    }))
            instrument_scores[instrument] = np.mean(item_arrays, axis=0).round(2)

        interview_score = instrument_scores["interview"]
        motivatiescore  = instrument_scores["motivatiebrief"]
        cv_score        = instrument_scores["cv"]
        totaalscore     = (
            INSTRUMENT_DEFINITIE["interview"]["gewicht"]      * interview_score
            + INSTRUMENT_DEFINITIE["motivatiebrief"]["gewicht"] * motivatiescore
            + INSTRUMENT_DEFINITIE["cv"]["gewicht"]             * cv_score
        ).round(2)

        rangorde = pd.Series(totaalscore).rank(ascending=False, method="first").astype(int).values

        selectie_uitkomst = np.where(
            rangorde <= n_geselecteerd, "geselecteerd",
            np.where(rangorde <= n_geselecteerd + 20, "reserve", "niet geselecteerd")
        )

        pgn = np.where(
            np.isin(selectie_uitkomst, ["geselecteerd", "reserve"]),
            kandidaat_id.astype(float),
            np.nan,
        )

        # Voeg kandidaatmetadata toe aan de score-rijen zodat het bestand
        # als zelfstandig invoerformaat bruikbaar is.
        meta = pd.DataFrame({
            "kandidaat_id":            kandidaat_id,
            "persoonsgebonden_nummer": pgn,
            "opleiding":               OPLEIDING,
            "instellingscode":         INSTELLINGSCODE,
            "selectie_uitkomst":       selectie_uitkomst,
        })
        cohort_scores = pd.concat(scores_lang_cohort, ignore_index=True).merge(
            meta, on="kandidaat_id"
        )[["kandidaat_id", "persoonsgebonden_nummer", "selectiejaar", "opleiding",
           "instellingscode", "instrument", "item", "criterium", "score",
           "selectie_uitkomst"]]
        scores_lang.append(cohort_scores)

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

    selectiedata   = pd.concat(cohorten, ignore_index=True)
    selectiescores = pd.concat(scores_lang, ignore_index=True)
    return selectiedata, selectiescores


# Coderingen die overeenkomen met het raw EV_* formaat van 1cijferho
GESLACHT_CODES = {"vrouw": "V", "man": "M", "anders": "O"}

VOOROPLEIDING_CODES = {
    "vwo profiel natuur & gezondheid":     405,
    "vwo profiel natuur & techniek":       411,
    "vwo profiel cultuur & maatschappij":  404,
    "vwo profiel economie & maatschappij": 403,
    "hbo-propedeuse":                      502,
    "anders":                              402,
}

HERKOMST_CODES = {
    "Nederland":            1,
    "westerse achtergrond": 2,
    "Marokko":              3,
    "Turkije":              4,
    "Suriname/Antillen":    5,
    "overig niet-westers":  7,
}

GESLACHT_DECODE      = {v: k for k, v in GESLACHT_CODES.items()}
HERKOMST_DECODE      = {v: k for k, v in HERKOMST_CODES.items()}
VOOROPLEIDING_DECODE = {v: k for k, v in VOOROPLEIDING_CODES.items()}


def maak_1cho_data(selectiedata: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Genereert 1CHO-inschrijvingsrijen in het raw EV_* formaat van 1cijferho.

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
    selectiedata, selectiescores = maak_selectiedata()
    selectiedata.to_csv(DATA_DIR / "selectiedata_voorbeeld.csv", index=False, sep=";")
    selectiescores.to_csv(DATA_DIR / "selectiescores_voorbeeld.csv", index=False, sep=";")
    print(f"  {len(selectiedata)} kandidaten, {selectiedata['selectie_uitkomst'].value_counts().to_dict()}")
    print(f"  {len(selectiescores)} score-rijen ({selectiescores['instrument'].value_counts().to_dict()})")

    print("1CHO-data genereren + groepen bepalen...")
    cho_data, groep_per_pgn = maak_1cho_data(selectiedata)
    cho_data.to_csv(DATA_DIR / "EV_DEMO_selectieopleiding.csv", index=False, sep=";")
    jaar1 = (cho_data["verblijfsjaar_hoger_onderwijs"] == 1).sum()
    jaar2 = (cho_data["verblijfsjaar_hoger_onderwijs"] == 2).sum()
    print(f"  {len(cho_data)} rijen - jaar 1: {jaar1}, jaar 2: {jaar2}, uitval: {jaar1 - jaar2}")

    cho_decoded = decodeer_cho(cho_data[cho_data["verblijfsjaar_hoger_onderwijs"] == 1])

    sel_cols = [
        "kandidaat_id", "persoonsgebonden_nummer", "selectiejaar",
        "opleiding", "instellingscode",
        "motivatiescore", "cv_score", "interview_score",
        "totaalscore", "rangorde", "selectie_uitkomst",
    ]
    cho_cols = [
        "persoonsgebonden_nummer",
        "geslacht",
        "herkomst",
        "hoogste_vooropleiding",
        "gem_eindcijfer_vo_van_de_hoogste_vooropl_voor_het_ho",
        "eerste_jaar_in_het_hoger_onderwijs",
        "eerste_jaar_aan_deze_instelling",
        "diplomajaar_van_de_hoogste_vooropl_voor_het_ho",
    ]

    def bereken_instroom_type(df):
        heeft_cho = df["eerste_jaar_in_het_hoger_onderwijs"].notna()
        eerste_ho   = df["eerste_jaar_in_het_hoger_onderwijs"].fillna(0)
        eerste_hier = df["eerste_jaar_aan_deze_instelling"].fillna(0)
        diplomajaar = df["diplomajaar_van_de_hoogste_vooropl_voor_het_ho"].fillna(0)
        switcher   = heeft_cho & (eerste_ho < eerste_hier)
        tussenjaar = heeft_cho & ~switcher & ((eerste_hier - diplomajaar) > 1)
        direct     = heeft_cho & ~switcher & ~tussenjaar
        result = pd.Series(index=df.index, dtype="object")
        result[switcher]   = "switcher"
        result[tussenjaar] = "tussenjaar"
        result[direct]     = "direct"
        return result

    gekoppeld = (
        selectiedata[sel_cols]
        .merge(groep_per_pgn, on="persoonsgebonden_nummer", how="left")
        .assign(groep=lambda df: df["groep"].fillna("Niet gestart"))
        .merge(cho_decoded[cho_cols], on="persoonsgebonden_nummer", how="left")
        .rename(columns={
            "gem_eindcijfer_vo_van_de_hoogste_vooropl_voor_het_ho": "gem_eindcijfer_vo",
        })
        .assign(instroom_type=bereken_instroom_type)
        .drop(columns=[
            "eerste_jaar_in_het_hoger_onderwijs",
            "eerste_jaar_aan_deze_instelling",
            "diplomajaar_van_de_hoogste_vooropl_voor_het_ho",
        ])
    )
    gekoppeld.to_csv(DATA_DIR / "analysedata.csv", index=False, sep=";")
    print(gekoppeld.groupby(["selectiejaar", "groep"]).size().unstack(fill_value=0).to_string())
    print("\nKlaar. Draai nu: uv run python app.py")
