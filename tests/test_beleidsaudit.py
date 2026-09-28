"""
Tests voor de beleidsaudit (issues #46-#52): geen 'vereenvoudig'-advies bij
nulresultaten, kleinste aantoonbare effect, retentie per scoregroep en het
afschermen van kleine aantallen.
"""

import pandas as pd
import pytest

from shared import (
    AFGESCHERMD,
    BEREIKSBEPERKING_UITLEG,
    GROEP_DOORGESTROOMD,
    GROEP_GESTART_GEEN_VERVOLG,
    GROEP_NIET_GESTART,
    MIN_CEL,
    PERSPECTIEF_DOORSTROOM,
    _bevindingen_demografie_verdeling,
    afgeschermde_kruistabel,
    beleidsvervolgstappen,
    cel_tekst,
    genereer_bevindingen,
    kleinste_aantoonbaar_effect,
    retentie_per_scoregroep,
    vergelijk_succes_per_item,
)


def _scores(n_per_groep=20, verschil=0.0, item="Toets"):
    """Long-format scores: evenveel doorstromers als niet-doorstromers."""
    rijen = []
    for i in range(n_per_groep):
        rijen.append(
            {
                "studentnummer": f"d{i}",
                "item_kort": item,
                "score": i + verschil,
                "groep": GROEP_DOORGESTROOMD,
            }
        )
        rijen.append(
            {
                "studentnummer": f"g{i}",
                "item_kort": item,
                "score": float(i),
                "groep": GROEP_GESTART_GEEN_VERVOLG,
            }
        )
    return pd.DataFrame(rijen)


# -- #46: nulresultaat is geen bewijs -------------------------------------


def test_geen_significant_item_adviseert_niet_vereenvoudigen():
    tekst = " ".join(beleidsvervolgstappen({"tellingen": {"n_getoetst": 5}}))
    assert "eenvoudiger" not in tekst and "goedkoper kan" not in tekst
    assert "geen bewijs dat de selectie niet werkt" in tekst
    assert "schrap of vereenvoudig" in tekst


def test_kleinste_aantoonbaar_effect():
    # 50 tegen 20: ongeveer 0.43 (matig), kleiner bij grotere groepen.
    assert kleinste_aantoonbaar_effect(50, 20) == pytest.approx(0.43, abs=0.01)
    assert kleinste_aantoonbaar_effect(500, 500) < kleinste_aantoonbaar_effect(50, 50)
    assert kleinste_aantoonbaar_effect(0, 10) is None
    assert kleinste_aantoonbaar_effect(1, 1) == 1.0  # afgekapt


def test_bevindingen_bevatten_kanttekeningen():
    tabel = vergelijk_succes_per_item(_scores(), perspectief=PERSPECTIEF_DOORSTROOM)
    b = genereer_bevindingen(tabel, {}, perspectief=PERSPECTIEF_DOORSTROOM)
    assert BEREIKSBEPERKING_UITLEG in b["kanttekeningen"]
    assert any("niet aangetoond" in k for k in b["kanttekeningen"])


# -- #50: retentie per scoregroep -----------------------------------------


def test_scoregroepen_kwartielen_en_aandeel():
    # Hoge scores stromen allemaal door, lage niet: het aandeel loopt op.
    scores = _scores(n_per_groep=20, verschil=20)
    tabel = retentie_per_scoregroep(scores, PERSPECTIEF_DOORSTROOM)
    assert list(tabel["Scoregroep"]) == [
        "1 van 4 (laagste)",
        "2 van 4",
        "3 van 4",
        "4 van 4 (hoogste)",
    ]
    assert tabel["Aandeel"].iloc[0] == "0%"
    assert tabel["Aandeel"].iloc[-1] == "100%"


def test_scoregroepen_per_waarde_bij_weinig_waarden():
    scores = _scores(n_per_groep=12)
    scores["score"] = scores["score"] % 3 + 1  # schaal 1-3
    tabel = retentie_per_scoregroep(scores, PERSPECTIEF_DOORSTROOM)
    assert list(tabel["Scoregroep"]) == ["Score 1", "Score 2", "Score 3"]


def test_scoregroepen_schermen_kleine_groep_af():
    scores = _scores(n_per_groep=12)
    scores["score"] = 2.0
    scores.loc[scores.index[:3], "score"] = 1.0  # drie studenten met score 1
    tabel = retentie_per_scoregroep(scores, PERSPECTIEF_DOORSTROOM)
    klein = tabel[tabel["Scoregroep"] == "Score 1"].iloc[0]
    assert klein["n"] == AFGESCHERMD and klein["Aandeel"] == "-"


def test_scoregroepen_negeren_niet_gestart():
    scores = _scores(n_per_groep=20)
    extra = scores.copy()
    extra["groep"] = GROEP_NIET_GESTART
    extra["studentnummer"] = "x" + extra["studentnummer"]
    tabel = retentie_per_scoregroep(pd.concat([scores, extra]), PERSPECTIEF_DOORSTROOM)
    assert sum(int(n) for n in tabel["n"]) == 40


# -- #51: kleine aantallen afschermen --------------------------------------


def test_cel_tekst():
    assert cel_tekst(0) == "0"
    assert cel_tekst(MIN_CEL - 1) == AFGESCHERMD
    assert cel_tekst(MIN_CEL) == str(MIN_CEL)


def test_kruistabel_zonder_kleine_cellen_toont_alles():
    ct = pd.DataFrame({"Ja": [20, 15], "Nee": [10, 12]}, index=["Man", "Vrouw"])
    tekst, afgeschermd = afgeschermde_kruistabel(ct, ["Ja", "Nee"])
    assert not afgeschermd
    assert tekst.loc["Man", "Ja"] == "20 (67%)"
    assert tekst.loc["Totaal", "Totaal"] == "57"


def test_kruistabel_kleine_cel_schermt_rij_en_totaal_af():
    ct = pd.DataFrame({"Ja": [20, 9], "Nee": [10, 2]}, index=["VWO", "HO"])
    tekst, afgeschermd = afgeschermde_kruistabel(ct, ["Ja", "Nee"])
    assert afgeschermd == {"HO"}
    assert tekst.loc["HO", "Nee"] == AFGESCHERMD
    assert tekst.loc["HO", "Ja"] == "-"  # anders terug te rekenen uit het totaal
    assert tekst.loc["HO", "Totaal"] == "11"
    # Eén afgeschermde rij: de totaalrij zou hem verraden.
    assert tekst.loc["Totaal", "Nee"] == "-"


def test_kruistabel_kleine_rij_volledig_afgeschermd():
    ct = pd.DataFrame(
        {"Ja": [20, 15, 2], "Nee": [10, 12, 1]}, index=["VWO", "HAVO", "HO"]
    )
    tekst, afgeschermd = afgeschermde_kruistabel(ct, ["Ja", "Nee"])
    assert afgeschermd == {"HO"}
    assert (tekst.loc["HO"] == AFGESCHERMD).all()


def test_demografie_bevinding_noemt_geen_kleine_groep():
    ct = pd.DataFrame(
        {"Doorgestroomd": [2, 10, 30], "Niet doorgestroomd": [0, 20, 5]},
        index=["HO", "HAVO", "VWO"],
    )
    regels = []
    _bevindingen_demografie_verdeling(
        {"Vooropleiding": {"ct": ct, "p": 0.001}}, regels, PERSPECTIEF_DOORSTROOM
    )
    assert "'VWO'" in regels[0] and "'HO'" not in regels[0]
