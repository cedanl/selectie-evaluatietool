"""
1CHO-transformaties: van ruwe inschrijvingsdata naar studiesucces-uitkomst.

Echte 1CHO-data (1 Cijfer Hoger Onderwijs, beheerd door DUO) kent geen
kant-en-klare 'groep'-kolom. Het zijn inschrijvingsgegevens in lang
formaat: een rij per student per inschrijvingsjaar. Of iemand is
doorgestroomd naar jaar 2 leid je af uit het bestaan van een inschrijfrij
in het jaar na het eerste studiejaar.

Deze module bundelt alle 1CHO-logica op een plek:

- `transformeer_cho()` leidt de doorstroomgroep af en wordt door de app
  gebruikt vlak voor `koppel_data()`.
- `bouw_ruwe_cho()` zet demografie + een doorstroom-indicator om in ruwe
  long-format 1CHO en wordt door de datageneratie-scripts gebruikt.

De afleidingslogica volgt de no-fairness-without-awareness pipeline
(R/transform_ev_data.R), waar retentie wordt bepaald met
`any(inschrijvingsjaar == eerste_jaar_aan_deze_opleiding_instelling + 1)`.
"""

import numpy as np
import pandas as pd
from numpy.typing import ArrayLike

from shared import GROEP_VOLGORDE

# Kolommen die een ruw 1CHO-bestand minimaal moet bevatten om de
# doorstroomgroep te kunnen afleiden.
RUWE_CHO_KOLOMMEN = [
    "persoonsgebonden_nummer",
    "inschrijvingsjaar",
    "eerste_jaar_aan_deze_opleiding_instelling",
]

# Demografische kolommen die we ongewijzigd meenemen als ze aanwezig zijn.
_DEMO_KOLOMMEN = ["geslacht", "herkomst", "gem_eindcijfer_vo"]

# Optionele passthrough-kolommen die de rest van de tool nog kan gebruiken.
_META_KOLOMMEN = ["opleiding", "instellingscode"]

# Labels uit shared.GROEP_VOLGORDE zodat de afgeleide groep gegarandeerd
# overeenkomt met de categorieen die koppel_data en de grafieken gebruiken.
_GROEP_GESTART = GROEP_VOLGORDE[1]
_GROEP_DOORGESTROOMD = GROEP_VOLGORDE[2]

_VOOROPL_OMSCHRIJVING_KOLOM = "hoogste_vooropleiding_omschrijving_vooropleiding"


def ontbrekende_cho_kolommen(df: pd.DataFrame) -> list[str]:
    """Geef de verplichte ruwe 1CHO-kolommen die in df ontbreken."""
    return [c for c in RUWE_CHO_KOLOMMEN if c not in df.columns]


def _classificeer_vooropleiding(omschrijving: object) -> str:
    """Vat de lange 1CHO-vooropleidingsomschrijving samen tot een korte
    categorie, zoals transform_ev_data.R doet. Valt terug op de
    oorspronkelijke tekst als er geen standaard-prefix matcht (bijvoorbeeld
    bachelor-namen die als vooropleiding bij een master gelden)."""
    tekst = str(omschrijving).strip().lower()
    if tekst.startswith("vwo"):
        return "VWO"
    if tekst.startswith("havo"):
        return "HAVO"
    if tekst.startswith("mbo"):
        return "MBO"
    if tekst.startswith(("wo", "hbo")):
        return "HO"
    if "buitenlands diploma" in tekst:
        return "Buitenlands diploma"
    # Geen standaard-prefix: geef de originele omschrijving terug met
    # behouden hoofdletters (vandaar opnieuw vanaf omschrijving, niet tekst).
    return str(omschrijving).strip()


def transformeer_cho(ruwe_df: pd.DataFrame) -> pd.DataFrame:
    """Leid per student de doorstroomgroep af uit ruwe 1CHO-inschrijvingen.

    Verwacht lang formaat (een rij per inschrijvingsjaar). Retourneert een
    rij per student met de afgeleide kolom `groep` plus `studentnummer`,
    `selectiejaar` en de demografische/meta-kolommen die aanwezig zijn.

    Studenten die helemaal niet in 1CHO voorkomen worden hier niet
    aangeraakt; die krijgen later in `koppel_data()` de groep 'Niet gestart'.
    """
    ontbreekt = ontbrekende_cho_kolommen(ruwe_df)
    if ontbreekt:
        raise ValueError(
            "Ruwe 1CHO-data mist verplichte kolommen: " + ", ".join(ontbreekt)
        )

    df = ruwe_df.rename(columns={"persoonsgebonden_nummer": "studentnummer"})
    df["inschrijvingsjaar"] = pd.to_numeric(df["inschrijvingsjaar"], errors="coerce")
    df["eerste_jaar_aan_deze_opleiding_instelling"] = pd.to_numeric(
        df["eerste_jaar_aan_deze_opleiding_instelling"], errors="coerce"
    )

    # Retentie wordt per opleiding-spell bepaald, niet alleen per student: een
    # student kan meerdere opleidingen/instromen hebben en elke spell heeft een
    # eigen eerste jaar. De groep-sleutel is studentnummer + opleiding (indien
    # aanwezig) + het eerste jaar van die spell.
    spell_sleutel = ["studentnummer"]
    for kol in ("opleidingscode_naam_opleiding", "opleiding"):
        if kol in df.columns:
            spell_sleutel.append(kol)
            break
    spell_sleutel.append("eerste_jaar_aan_deze_opleiding_instelling")

    # Retentie: bestaat er binnen de spell een inschrijfrij in het jaar na het
    # eerste jaar?
    df["_is_jaar2"] = (
        df["inschrijvingsjaar"] == df["eerste_jaar_aan_deze_opleiding_instelling"] + 1
    )
    df["_retentie"] = df.groupby(spell_sleutel)["_is_jaar2"].transform("any")

    # Houd alleen de eerstejaars-rij per spell over.
    eerstejaars = (
        df[df["inschrijvingsjaar"] == df["eerste_jaar_aan_deze_opleiding_instelling"]]
        .drop_duplicates(spell_sleutel, keep="first")
        .copy()
    )

    eerstejaars["groep"] = np.where(
        eerstejaars["_retentie"],
        _GROEP_DOORGESTROOMD,
        _GROEP_GESTART,
    )
    eerstejaars["selectiejaar"] = eerstejaars[
        "eerste_jaar_aan_deze_opleiding_instelling"
    ].astype("Int64")

    if _VOOROPL_OMSCHRIJVING_KOLOM in eerstejaars.columns:
        eerstejaars["hoogste_vooropleiding"] = eerstejaars[
            _VOOROPL_OMSCHRIJVING_KOLOM
        ].map(_classificeer_vooropleiding)

    uit_kolommen = ["studentnummer", "selectiejaar", "groep"]
    for kol in [*_META_KOLOMMEN, "hoogste_vooropleiding", *_DEMO_KOLOMMEN]:
        if kol in eerstejaars.columns:
            uit_kolommen.append(kol)

    return eerstejaars[uit_kolommen].reset_index(drop=True)


def bouw_ruwe_cho(
    studentnummers: ArrayLike,
    *,
    jaar: int,
    doorstroomt: ArrayLike,
    opleiding: str | None = None,
    instellingscode: str | None = None,
    geslacht: ArrayLike | None = None,
    herkomst: ArrayLike | None = None,
    vooropleiding_omschrijving: ArrayLike | None = None,
    gem_eindcijfer_vo: ArrayLike | None = None,
) -> pd.DataFrame:
    """Bouw synthetische ruwe 1CHO-data in lang formaat.

    Elke ingeschreven student krijgt een eerstejaars-rij; doorstromers
    krijgen daarnaast een rij voor jaar 2. De doorstroomgroep zit dus NIET
    als kolom in de data maar wordt afgeleid uit de inschrijfjaren, net als
    bij echte 1CHO-data. Het resultaat is bedoeld om door `transformeer_cho()`
    te worden verwerkt.

    `studentnummers`, `doorstroomt` en de optionele demografie-arrays moeten
    allemaal dezelfde lengte hebben (een waarde per ingeschreven student).
    """
    studentnummers = np.asarray(studentnummers)
    doorstroomt = np.asarray(doorstroomt, dtype=bool)
    n = len(studentnummers)
    if len(doorstroomt) != n:
        raise ValueError("doorstroomt moet even lang zijn als studentnummers")

    jaar1 = pd.DataFrame(
        {
            "persoonsgebonden_nummer": studentnummers,
            "inschrijvingsjaar": jaar,
            "opleidingsvorm": "voltijd",
            "eerste_jaar_aan_deze_opleiding_instelling": jaar,
        }
    )
    if opleiding is not None:
        jaar1["opleidingscode_naam_opleiding"] = opleiding
        jaar1["opleiding"] = opleiding
    if instellingscode is not None:
        jaar1["instellingscode"] = instellingscode
    if geslacht is not None:
        jaar1["geslacht"] = np.asarray(geslacht)
    if herkomst is not None:
        jaar1["herkomst"] = np.asarray(herkomst)
    if vooropleiding_omschrijving is not None:
        jaar1[_VOOROPL_OMSCHRIJVING_KOLOM] = np.asarray(vooropleiding_omschrijving)
    if gem_eindcijfer_vo is not None:
        jaar1["gem_eindcijfer_vo"] = np.asarray(gem_eindcijfer_vo)

    jaar2 = jaar1[doorstroomt].copy()
    jaar2["inschrijvingsjaar"] = jaar + 1

    lang = pd.concat([jaar1, jaar2], ignore_index=True)
    return lang.sort_values(
        ["persoonsgebonden_nummer", "inschrijvingsjaar"]
    ).reset_index(drop=True)
