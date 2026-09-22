import pandas as pd
import pytest

from config_wizard import (
    _raad_instrument,
    _maak_item_naam,
    _raad_schaal,
    detecteer_id_kolom,
    detecteer_metadata,
    detecteer_mogelijke_duplicaten,
    _duplicaat_tip,
)


def _score_kol(kolom_naam, meenemen=True):
    return {"kolom_naam": kolom_naam, "_meenemen": meenemen}


class TestRaadInstrument:
    def test_underscore_prefix(self):
        kolommen = ["ctb_reflecteren", "ctb_stressbestendigheid", "sjts_score"]
        assert _raad_instrument("ctb_reflecteren", kolommen) == "Ctb"

    def test_space_prefix(self):
        kolommen = ["Interview reflectie", "Interview motivatie", "Toets rekenen"]
        assert _raad_instrument("Interview reflectie", kolommen) == "Interview"

    def test_dash_prefix(self):
        kolommen = ["test-onderdeel1", "test-onderdeel2"]
        assert _raad_instrument("test-onderdeel1", kolommen) == "Test"

    def test_no_shared_prefix(self):
        kolommen = ["alpha_score", "beta_result"]
        assert _raad_instrument("alpha_score", kolommen) == ""

    def test_single_column(self):
        assert _raad_instrument("some_column", ["some_column"]) == ""


class TestMaakItemNaam:
    def test_strips_prefix(self):
        assert _maak_item_naam("ctb_reflecteren") == "Reflecteren"

    def test_strips_schaalscore_suffix(self):
        assert _maak_item_naam("ctb_reflecteren_schaalscore") == "Reflecteren"

    def test_strips_score_suffix(self):
        assert _maak_item_naam("test_onderdeel_score") == "Onderdeel"

    def test_replaces_underscores(self):
        assert _maak_item_naam("ctb_sociaal_vermogen") == "Sociaal vermogen"

    def test_camel_case_split(self):
        assert _maak_item_naam("prefix_socialSkills") == "Social Skills"


class TestRaadSchaal:
    def test_rounds_max_up_to_nette_grens(self):
        # niemand scoort het uiterste, dus 2-6 hoort bij een 1-7 schaal
        assert _raad_schaal(pd.Series([2, 3, 6, 4, 5])) == "1-7"

    def test_small_max_rounds_to_five(self):
        assert _raad_schaal(pd.Series([1, 2, 4])) == "1-5"

    def test_percentage_range(self):
        assert _raad_schaal(pd.Series([23, 45, 87, 80])) == "0-100"

    def test_grade_scale_rounds_to_ten(self):
        assert _raad_schaal(pd.Series([5.5, 8.2, 6.0])) == "1-10"

    def test_includes_zero_keeps_zero(self):
        assert _raad_schaal(pd.Series([0, 4, 9])) == "0-10"

    def test_large_scale_rounds_to_tens(self):
        assert _raad_schaal(pd.Series([120, 250, 333])) == "0-340"

    def test_constant_column_is_empty(self):
        assert _raad_schaal(pd.Series([3, 3, 3])) == ""

    def test_empty_column_is_empty(self):
        assert _raad_schaal(pd.Series([None, None], dtype="float")) == ""

    def test_ignores_non_numeric(self):
        assert _raad_schaal(pd.Series([1, "x", 4])) == "1-5"


class TestDetecteerIdKolom:
    def test_finds_studentnummer(self):
        assert detecteer_id_kolom(["naam", "studentnummer", "score"]) == "studentnummer"

    def test_finds_aanvraagnummer(self):
        assert detecteer_id_kolom(["aanvraagnummer", "score"]) == "aanvraagnummer"

    def test_none_when_no_match(self):
        assert detecteer_id_kolom(["naam", "score", "gpa"]) is None


class TestDetecteerMetadata:
    def test_extracts_from_filename(self):
        meta = detecteer_metadata("Psychologie_UvA_2024.xlsx", ["Blad1"])
        assert "Psychologie" in meta["opleiding"]
        assert meta["jaar"] == "2024"

    def test_handles_spaces(self):
        meta = detecteer_metadata(
            "Biomedische wetenschappen_AUMC_2025.xlsx", ["Sheet1"]
        )
        assert "Biomedische" in meta["opleiding"]
        assert meta["jaar"] == "2025"


class TestDetecteerMogelijkeDuplicaten:
    def test_perfect_correlation_flagged(self):
        df = pd.DataFrame({"pct_goed": [10, 20, 30, 40], "aantal_goed": [1, 2, 3, 4]})
        kols = [_score_kol("pct_goed"), _score_kol("aantal_goed")]
        paren = detecteer_mogelijke_duplicaten(df, kols)
        assert len(paren) == 1
        a, b, r = paren[0]
        assert {a, b} == {"pct_goed", "aantal_goed"}
        assert r == pytest.approx(1.0)

    def test_perfect_negative_correlation_flagged(self):
        # bijv. rangnummer (laag = beter) tegenover score (hoog = beter)
        df = pd.DataFrame({"rang": [1, 2, 3, 4], "score": [40, 30, 20, 10]})
        kols = [_score_kol("rang"), _score_kol("score")]
        paren = detecteer_mogelijke_duplicaten(df, kols)
        assert len(paren) == 1
        assert paren[0][2] == pytest.approx(-1.0)

    def test_uncorrelated_columns_not_flagged(self):
        df = pd.DataFrame({"a": [1, 2, 3, 4, 5], "b": [3, 1, 4, 1, 5]})
        kols = [_score_kol("a"), _score_kol("b")]
        assert detecteer_mogelijke_duplicaten(df, kols) == []

    def test_below_threshold_not_flagged(self):
        # sterk maar niet extreem gecorreleerd (r rond 0.8, onder de 0.95-drempel)
        df = pd.DataFrame({"a": [1, 2, 3, 4, 5], "b": [1, 2, 2, 5, 4]})
        kols = [_score_kol("a"), _score_kol("b")]
        assert detecteer_mogelijke_duplicaten(df, kols) == []

    def test_unchecked_column_excluded(self):
        df = pd.DataFrame({"pct_goed": [10, 20, 30, 40], "aantal_goed": [1, 2, 3, 4]})
        kols = [_score_kol("pct_goed"), _score_kol("aantal_goed", meenemen=False)]
        assert detecteer_mogelijke_duplicaten(df, kols) == []

    def test_column_missing_from_df_ignored(self):
        df = pd.DataFrame({"a": [1, 2, 3, 4]})
        kols = [_score_kol("a"), _score_kol("nooit_geuploaded")]
        assert detecteer_mogelijke_duplicaten(df, kols) == []

    def test_fewer_than_two_columns_returns_empty(self):
        df = pd.DataFrame({"a": [1, 2, 3, 4]})
        assert detecteer_mogelijke_duplicaten(df, [_score_kol("a")]) == []
        assert detecteer_mogelijke_duplicaten(df, []) == []

    def test_constant_column_does_not_crash(self):
        # std=0 geeft een NaN-correlatie; dat mag niet als duplicaat tellen
        df = pd.DataFrame({"a": [3, 3, 3, 3], "b": [1, 2, 3, 4]})
        kols = [_score_kol("a"), _score_kol("b")]
        assert detecteer_mogelijke_duplicaten(df, kols) == []

    def test_missing_values_use_pairwise_deletion(self):
        df = pd.DataFrame(
            {
                "pct_goed": [10, 20, 30, 40, None],
                "aantal_goed": [1, 2, 3, 4, 5],
            }
        )
        kols = [_score_kol("pct_goed"), _score_kol("aantal_goed")]
        paren = detecteer_mogelijke_duplicaten(df, kols)
        assert len(paren) == 1
        assert paren[0][2] == pytest.approx(1.0)

    def test_three_columns_flags_only_the_correlated_pair(self):
        df = pd.DataFrame(
            {
                "pct_goed": [10, 20, 30, 40],
                "aantal_goed": [1, 2, 3, 4],
                "onafhankelijk": [5, 1, 9, 3],
            }
        )
        kols = [
            _score_kol("pct_goed"),
            _score_kol("aantal_goed"),
            _score_kol("onafhankelijk"),
        ]
        paren = detecteer_mogelijke_duplicaten(df, kols)
        assert len(paren) == 1
        assert {paren[0][0], paren[0][1]} == {"pct_goed", "aantal_goed"}


class TestDuplicaatTip:
    def test_no_pairs_returns_empty_string(self):
        df = pd.DataFrame({"a": [1, 2, 3, 4], "b": [3, 1, 4, 1]})
        kols = [_score_kol("a"), _score_kol("b")]
        assert _duplicaat_tip(df, kols) == ""

    def test_pairs_render_names_and_correlation(self):
        df = pd.DataFrame({"pct_goed": [10, 20, 30, 40], "aantal_goed": [1, 2, 3, 4]})
        kols = [_score_kol("pct_goed"), _score_kol("aantal_goed")]
        tip = _duplicaat_tip(df, kols)
        assert tip != ""
        # dbc.Alert-children bevatten de kolomnamen en de r-waarde
        rendered = str(tip)
        assert "pct_goed" in rendered
        assert "aantal_goed" in rendered
