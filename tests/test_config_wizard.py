from config_wizard import (
    _raad_instrument,
    _maak_item_naam,
    detecteer_id_kolom,
    detecteer_metadata,
)


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
