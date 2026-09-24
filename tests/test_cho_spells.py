"""
Tests voor het kiezen van de juiste 1CHO-spell per student (pitch #32): een
instellingsbrede 1CHO-extractie bevat andere opleidingen en eerdere cohorten,
en mag kandidaten niet dubbel of met de verkeerde uitkomst laten meetellen.
"""

import pandas as pd
import pytest

from cho_transform import (
    beste_opleiding_match,
    bouw_ruwe_cho,
    opleidingen_in_cho,
    selecteer_spells,
    transformeer_cho,
)
from helpers import bereid_cho_voor, koppel_data
from shared import (
    GROEP_DOORGESTROOMD,
    GROEP_GESTART_GEEN_VERVOLG,
    GROEP_NIET_GESTART,
)


def _scores(nummers, jaar=2024, opleiding="Psychologie"):
    return pd.DataFrame(
        {
            "studentnummer": [str(n) for n in nummers],
            "selectiejaar": jaar,
            "opleiding": opleiding,
            "instellingscode": "X",
            "instrument": "Toets",
            "item": "A",
            "criterium": "",
            "score": [float(i) for i in range(len(nummers))],
        }
    )


@pytest.fixture
def instellingsbreed():
    """Student 1: Psychologie 2024 (doorgestroomd) én eerder Pedagogiek 2022.
    Student 2: Psychologie 2024, gestopt.
    Student 3: afgewezen voor Psychologie, maar gestart bij Pedagogiek 2024.
    Student 4: eerdere poging Psychologie 2022, niet in 2024 gestart."""
    return pd.concat(
        [
            bouw_ruwe_cho(
                [1, 2], jaar=2024, doorstroomt=[True, False], opleiding="Psychologie"
            ),
            bouw_ruwe_cho([1], jaar=2022, doorstroomt=[False], opleiding="Pedagogiek"),
            bouw_ruwe_cho([3], jaar=2024, doorstroomt=[True], opleiding="Pedagogiek"),
            bouw_ruwe_cho([4], jaar=2022, doorstroomt=[False], opleiding="Psychologie"),
        ],
        ignore_index=True,
    )


class TestOpleidingMatch:
    def test_een_opleiding_wordt_altijd_gekozen(self):
        assert (
            beste_opleiding_match(["B Psychologie"], "iets anders") == "B Psychologie"
        )

    def test_exact_zonder_hoofdletters(self):
        assert beste_opleiding_match(["Pedagogiek", "Psychologie"], "psychologie") == (
            "Psychologie"
        )

    def test_eenduidige_deelmatch(self):
        assert beste_opleiding_match(
            ["B Psychologie", "B Pedagogiek"], "Psychologie"
        ) == ("B Psychologie")

    def test_geen_of_dubbelzinnige_match(self):
        assert beste_opleiding_match(["A", "B"], "") is None
        assert (
            beste_opleiding_match(["B Psychologie", "M Psychologie"], "Psychologie")
            is None
        )

    def test_opleidingen_in_cho(self, instellingsbreed):
        opl = opleidingen_in_cho(transformeer_cho(instellingsbreed))
        assert set(opl) == {"Psychologie", "Pedagogiek"}


class TestSelecteerSpells:
    def test_filtert_opleiding_en_eerder_cohort(self, instellingsbreed):
        cho_df, info = selecteer_spells(
            transformeer_cho(instellingsbreed), opleiding="Psychologie", jaar=2024
        )
        assert sorted(cho_df["studentnummer"]) == ["1", "2"]
        assert info["n_andere_opleiding"] == 2
        assert info["n_eerder_cohort"] == 1

    def test_een_spell_per_student(self, instellingsbreed):
        cho_df, info = selecteer_spells(transformeer_cho(instellingsbreed), jaar=2024)
        assert not cho_df["studentnummer"].duplicated().any()
        # Zonder opleidingsfilter wint voor student 1 de spell uit 2024.
        rij = cho_df[cho_df["studentnummer"] == "1"].iloc[0]
        assert rij["groep"] == GROEP_DOORGESTROOMD

    def test_jaarfilter_overgeslagen_als_alles_wegvalt(self, instellingsbreed):
        cho_df, info = selecteer_spells(
            transformeer_cho(instellingsbreed),
            opleiding="Psychologie",
            jaar=2030,
            studentnummers={"1", "2"},
        )
        assert info["jaarfilter_overgeslagen"]
        assert {"1", "2"} <= set(cho_df["studentnummer"])


class TestKoppeling:
    def test_koppel_data_weigert_dubbele_studenten(self, instellingsbreed):
        with pytest.raises(ValueError, match="meerdere"):
            koppel_data(transformeer_cho(instellingsbreed), _scores([1, 2, 3]))

    def test_bereid_cho_voor_eindresultaat(self, instellingsbreed):
        scores = _scores([1, 2, 3, 4])
        config = {"opleiding": "Psychologie", "jaar": "2024"}
        cho = bereid_cho_voor(instellingsbreed, config, scores)
        assert cho["gekozen"] == "Psychologie"
        assert not cho["keuze_nodig"]
        df = koppel_data(cho["cho_df"], scores).set_index("studentnummer")
        assert len(df) == 4
        assert df.loc["1", "groep"] == GROEP_DOORGESTROOMD
        assert df.loc["2", "groep"] == GROEP_GESTART_GEEN_VERVOLG
        # Gestart bij een andere opleiding telt niet als gestart bij deze.
        assert df.loc["3", "groep"] == GROEP_NIET_GESTART
        # Een eerdere poging telt niet als start in dit selectiejaar.
        assert df.loc["4", "groep"] == GROEP_NIET_GESTART

    def test_keuze_nodig_zonder_match(self, instellingsbreed):
        cho = bereid_cho_voor(
            instellingsbreed, {"opleiding": "Geneeskunde"}, _scores([1])
        )
        assert cho["keuze_nodig"]
        assert cho["gekozen"] is None

    def test_keuze_van_gebruiker_wint(self, instellingsbreed):
        cho = bereid_cho_voor(
            instellingsbreed, {"opleiding": "Geneeskunde"}, _scores([1]), "Pedagogiek"
        )
        assert cho["gekozen"] == "Pedagogiek"
        assert not cho["keuze_nodig"]
