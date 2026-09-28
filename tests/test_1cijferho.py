"""
De tool moet de EV-uitvoer van de 1cijferho-pipeline direct kunnen lezen:
het eigen studentnummer staat daar in `studentnummer` (niet in
`persoonsgebonden_nummer`), en voor masters is er `diplomajaar` in plaats van
`diploma_behaald`.
"""

import pandas as pd

from bestandsopslag import lees_cho_bestand
from cho_transform import normaliseer_1cijferho, transformeer_cho
from shared import GROEP_DIPLOMA, GROEP_DOORGESTROOMD, GROEP_GESTART_GEEN_VERVOLG


def _ev(fase="bachelor"):
    """Een klein stukje 1cijferho-uitvoer (snake_case, verrijkt)."""
    return pd.DataFrame(
        {
            "persoonsgebonden_nummer": ["5965", "5965", "6133", "7001"],
            "burgerservicenummer": ["000174063", "000174063", "000190571", "0001"],
            "studentnummer": ["S0001", "S0001", "S0002", "S0003"],
            "inschrijvingsjaar": ["2024", "2025", "2024", "2024"],
            "eerste_jaar_aan_deze_opleiding_instelling": ["2024"] * 4,
            "opleidingsfase_actueel": [fase] * 4,
            "diplomajaar": [
                "geen examen geregistreerd > 0000 voor overige inschrijvingen",
                "geen examen geregistreerd > 0000 voor overige inschrijvingen",
                "2024",
                "geen examen geregistreerd > 0000 voor overige inschrijvingen",
            ],
            "geslacht": ["vrouw", "vrouw", "man", "vrouw"],
            "hoogste_vooropleiding_omschrijving_vooropleiding": [
                "vwo profiel natuur & gezondheid",
                "vwo profiel natuur & gezondheid",
                "hbo-ba economie",
                "havo profiel economie & maatschappij",
            ],
        }
    )


def test_studentnummer_wordt_koppelsleutel():
    df = normaliseer_1cijferho(_ev())
    assert list(df["persoonsgebonden_nummer"].unique()) == ["S0001", "S0002", "S0003"]
    assert "studentnummer" not in df.columns


def test_bachelor_krijgt_geen_diplomakolom():
    df = normaliseer_1cijferho(_ev("bachelor"))
    assert "diploma_behaald" not in df.columns
    groepen = transformeer_cho(df).set_index("studentnummer")["groep"]
    assert groepen["S0001"] == GROEP_DOORGESTROOMD
    assert groepen["S0002"] == GROEP_GESTART_GEEN_VERVOLG


def test_master_diploma_uit_diplomajaar():
    df = normaliseer_1cijferho(_ev("master"))
    assert df["diploma_behaald"].tolist() == [False, False, True, False]
    groepen = transformeer_cho(df).set_index("studentnummer")["groep"]
    assert groepen["S0002"] == GROEP_DIPLOMA
    assert groepen["S0003"] == GROEP_GESTART_GEEN_VERVOLG


def test_diploma_in_later_studiejaar_telt_niet():
    # diplomajaar is een studiejaar, net als inschrijvingsjaar. Een diploma uit
    # 2025-2026 op de rij van 2024-2025 is niet in het startjaar gehaald.
    ev = _ev("master")
    ev.loc[2, "diplomajaar"] = "2025"
    df = normaliseer_1cijferho(ev)
    assert not df["diploma_behaald"].any()
    groepen = transformeer_cho(df).set_index("studentnummer")["groep"]
    assert groepen["S0002"] == GROEP_GESTART_GEEN_VERVOLG


def test_ruwe_fasecode_m_telt_ook_als_master():
    df = normaliseer_1cijferho(_ev("M"))
    assert df["diploma_behaald"].sum() == 1


def test_eigen_formaat_blijft_ongewijzigd():
    eigen = _ev().drop(
        columns=["studentnummer", "diplomajaar", "opleidingsfase_actueel"]
    )
    df = normaliseer_1cijferho(eigen)
    pd.testing.assert_frame_equal(df, eigen)


def test_bestaande_diplomakolom_wint():
    ev = _ev("master")
    ev["diploma_behaald"] = [True, False, False, False]
    assert normaliseer_1cijferho(ev)["diploma_behaald"].tolist() == [
        True,
        False,
        False,
        False,
    ]


def test_lees_cho_bestand_leest_1cijferho_csv(tmp_path):
    ev = _ev("master")
    ev["overbodige_kolom"] = "x"  # 1cijferho levert er ~180; de rest valt weg
    pad = tmp_path / "EV299XX24_enriched.csv"
    ev.to_csv(pad, sep=";", index=False)
    df = lees_cho_bestand(pad)
    assert "overbodige_kolom" not in df.columns
    assert "burgerservicenummer" not in df.columns
    assert df["persoonsgebonden_nummer"].iloc[0] == "S0001"
    assert "diploma_behaald" in df.columns
