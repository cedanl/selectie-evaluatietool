"""
Tests voor de beleidsvervolgstappen (pitch #30): de aantallen moeten uit de
toetsuitkomsten komen, niet uit de lengte van de tekstlijsten, die ook
'niets gevonden'-regels bevatten.
"""

import pandas as pd

from helpers import _laad_demodata, df_from_store, scores_df_from_store
from shared import (
    DEMO_DIMENSIES,
    PERSPECTIEF_DOORSTROOM,
    beleidsvervolgstappen,
    demografie_scores,
    genereer_bevindingen,
    shorten_item,
    toets_verschil_per_item,
    vergelijk_succes_per_item,
)


def _succes_tabel(rijen):
    """Minimale verschiltoetstabel: (item, r, p)."""
    return pd.DataFrame(
        [
            {
                "Item": item,
                "Effectgrootte": f"{r:+.2f}",
                "_r": r,
                "_p": p,
            }
            for item, r, p in rijen
        ]
    )


def _demo_tabel(rijen):
    """Minimale Kruskal-Wallis-tabel: (item, p)."""
    return pd.DataFrame(
        [
            {
                "Item": item,
                "Verschil": "vergelijkbaar",
                "Effectgrootte": "0.010",
                "_eps2": 0.01,
                "_p": p,
            }
            for item, p in rijen
        ]
    )


def _stappen(succes, demo=None, corr=None):
    bevindingen = genereer_bevindingen(
        succes, demo or {}, correlatie_matrix=corr, perspectief=PERSPECTIEF_DOORSTROOM
    )
    return bevindingen, " ".join(beleidsvervolgstappen(bevindingen))


def test_niets_significant_zegt_geen_enkel_item():
    bevindingen, tekst = _stappen(_succes_tabel([("A", 0.1, 0.4), ("B", 0.05, 0.7)]))
    # De tekstlijst bevat wel een regel ("Geen enkel item verschilt ..."),
    # maar dat mag niet als gevonden item tellen.
    assert len(bevindingen["validiteit"]) == 1
    assert "geen enkel item waarop doorstromers significant hoger" in tekst
    assert "vindt 1 item" not in tekst


def test_alleen_negatieve_richting_wordt_niet_aangeprezen():
    _, tekst = _stappen(_succes_tabel([("A", -0.4, 0.01)]))
    assert "zwaarder meewegen, en bevestig" not in tekst
    assert "scoorden juist de uitvallers hoger" in tekst


def test_telt_alle_significante_items_ook_boven_top3():
    rijen = [(f"I{i}", 0.4, 0.01) for i in range(5)]
    bevindingen, tekst = _stappen(_succes_tabel(rijen))
    assert len(bevindingen["validiteit"]) == 3  # tekst is afgekapt op top=3
    assert "vindt 5 items" in tekst


def test_geen_fairness_verschil_geen_fairness_stap():
    demo = {
        "Geslacht": _demo_tabel([("A", 0.5)]),
        "Vooropleiding": _demo_tabel([("A", 0.8)]),
    }
    bevindingen, tekst = _stappen(_succes_tabel([("A", 0.1, 0.4)]), demo)
    assert len(bevindingen["fairness"]) == 2  # twee 'geen verschil'-regels
    assert "achtergrondgroepen" not in tekst


def test_geen_hoge_correlatie_geen_correlatiestap():
    corr = pd.DataFrame([[1, 0.2], [0.2, 1]], index=["A", "B"], columns=["A", "B"])
    bevindingen, tekst = _stappen(_succes_tabel([("A", 0.1, 0.4)]), corr=corr)
    assert bevindingen["correlatie"]  # 'geen hoge correlaties'-regel
    assert "sterk samenhangen" not in tekst


def test_te_weinig_data():
    _, tekst = _stappen(pd.DataFrame())
    assert "te weinig gestarte studenten" in tekst


def test_radboud_demo_heeft_geen_fairness_stap():
    """De meegeleverde demo meldde '2 items' terwijl er geen enkel
    significant achtergrondverschil is."""
    data, scores = _laad_demodata("demo_radboud_2026")
    df, scores_df = df_from_store(data), scores_df_from_store(scores)
    pop = df[df["groep"].isin(PERSPECTIEF_DOORSTROOM["populatie"])]
    sc = scores_df.merge(pop[["studentnummer", "groep"]], on="studentnummer")
    sc["item_kort"] = sc["item"].apply(shorten_item)
    demo = {
        d["label"]: toets_verschil_per_item(
            demografie_scores(df, scores_df, d), d["kolom"]
        )
        for d in DEMO_DIMENSIES
    }
    bevindingen = genereer_bevindingen(vergelijk_succes_per_item(sc), demo)
    assert bevindingen["tellingen"]["n_fair_sig"] == 0
    assert not any(
        "achtergrondgroepen" in s for s in beleidsvervolgstappen(bevindingen)
    )
