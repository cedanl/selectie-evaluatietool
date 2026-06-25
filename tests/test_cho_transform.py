import pandas as pd
import pytest

from cho_transform import (
    transformeer_cho,
    bouw_ruwe_cho,
    ontbrekende_cho_kolommen,
    ontbrekende_demografie_kolommen,
)
from shared import GROEP_DOORGESTROOMD, GROEP_GESTART_GEEN_VERVOLG, GROEP_DIPLOMA


class TestTransformeerCho:
    def _maak_ruwe_cho(self, nummers, jaar, doorstroomt, diploma=None):
        return bouw_ruwe_cho(
            nummers, jaar=jaar, doorstroomt=doorstroomt, diploma_behaald=diploma
        )

    def test_doorstroom_groep(self):
        df = self._maak_ruwe_cho([1, 2, 3], 2024, [True, False, True])
        result = transformeer_cho(df)
        # studentnummer wordt genormaliseerd naar tekst voor robuust koppelen.
        groepen = result.set_index("studentnummer")["groep"]
        assert groepen["1"] == GROEP_DOORGESTROOMD
        assert groepen["2"] == GROEP_GESTART_GEEN_VERVOLG
        assert groepen["3"] == GROEP_DOORGESTROOMD

    def test_diploma_groep(self):
        df = self._maak_ruwe_cho(
            [1, 2, 3], 2024, [False, False, False], diploma=[True, False, True]
        )
        result = transformeer_cho(df)
        groepen = result.set_index("studentnummer")["groep"]
        assert groepen["1"] == GROEP_DIPLOMA
        assert groepen["2"] == GROEP_GESTART_GEEN_VERVOLG
        assert groepen["3"] == GROEP_DIPLOMA

    def test_doorstroom_prioriteit_boven_diploma(self):
        df = self._maak_ruwe_cho([1], 2024, [True], diploma=[True])
        result = transformeer_cho(df)
        assert result.iloc[0]["groep"] == GROEP_DOORGESTROOMD

    def test_selectiejaar_wordt_afgeleid(self):
        df = self._maak_ruwe_cho([1], 2024, [True])
        result = transformeer_cho(df)
        assert result.iloc[0]["selectiejaar"] == 2024

    def test_missing_kolom_raises(self):
        df = pd.DataFrame({"persoonsgebonden_nummer": [1], "inschrijvingsjaar": [2024]})
        with pytest.raises(ValueError, match="verplichte kolommen"):
            transformeer_cho(df)

    def test_diploma_als_tekst_wordt_correct_geparsed(self):
        # Een CSV levert diploma_behaald vaak als "True"/"False" aan; een kale
        # astype(bool) zou "False" ten onrechte als diploma tellen.
        df = self._maak_ruwe_cho([1, 2], 2024, [False, False], diploma=[True, False])
        df["diploma_behaald"] = df["diploma_behaald"].map(
            {True: "True", False: "False"}
        )
        groepen = transformeer_cho(df).set_index("studentnummer")["groep"]
        assert groepen["1"] == GROEP_DIPLOMA
        assert groepen["2"] == GROEP_GESTART_GEEN_VERVOLG

    def test_jaar_zonder_geldige_waarden_raises(self):
        df = self._maak_ruwe_cho([1], 2024, [False])
        df["inschrijvingsjaar"] = "geen jaar"
        with pytest.raises(ValueError, match="geldige jaartallen"):
            transformeer_cho(df)


class TestOntbrekendeChoKolommen:
    def test_alle_aanwezig(self):
        df = pd.DataFrame(
            {
                "persoonsgebonden_nummer": [1],
                "inschrijvingsjaar": [2024],
                "eerste_jaar_aan_deze_opleiding_instelling": [2024],
            }
        )
        assert ontbrekende_cho_kolommen(df) == []

    def test_een_ontbreekt(self):
        df = pd.DataFrame({"persoonsgebonden_nummer": [1], "inschrijvingsjaar": [2024]})
        assert "eerste_jaar_aan_deze_opleiding_instelling" in ontbrekende_cho_kolommen(
            df
        )


class TestOntbrekendeDemografieKolommen:
    def test_ontbreekt(self):
        df = pd.DataFrame({"geslacht": ["M"]})
        assert (
            "hoogste_vooropleiding_omschrijving_vooropleiding"
            in ontbrekende_demografie_kolommen(df)
        )

    def test_aanwezig(self):
        df = pd.DataFrame(
            {
                "geslacht": ["M"],
                "hoogste_vooropleiding_omschrijving_vooropleiding": ["VWO"],
            }
        )
        assert ontbrekende_demografie_kolommen(df) == []


class TestBouwRuweCho:
    def test_doorstromers_krijgen_jaar2_rij(self):
        df = bouw_ruwe_cho([1, 2], jaar=2024, doorstroomt=[True, False])
        assert len(df[df["persoonsgebonden_nummer"] == 1]) == 2
        assert len(df[df["persoonsgebonden_nummer"] == 2]) == 1

    def test_diploma_kolom_aanwezig(self):
        df = bouw_ruwe_cho([1], jaar=2024, diploma_behaald=[True])
        assert "diploma_behaald" in df.columns
        assert bool(df.iloc[0]["diploma_behaald"]) is True

    def test_lengte_mismatch_raises(self):
        with pytest.raises(ValueError, match="even lang"):
            bouw_ruwe_cho([1, 2], jaar=2024, doorstroomt=[True])
