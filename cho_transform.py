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

from shared import (
    GROEP_DIPLOMA,
    GROEP_DOORGESTROOMD,
    GROEP_GESTART_GEEN_VERVOLG,
)

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

_VOOROPL_OMSCHRIJVING_KOLOM = "hoogste_vooropleiding_omschrijving_vooropleiding"

# Optionele kolom die aangeeft of de student in het cohortjaar een diploma
# haalde. Aanwezig bij eenjarige opleidingen (masters) waar succes 'diploma'
# is in plaats van doorstroom naar jaar 2.
_DIPLOMA_KOLOM = "diploma_behaald"


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

    De groep is 'Doorgestroomd naar jaar 2' bij een vervolginschrijving, anders
    'Gestart, diploma gehaald' als er een diploma in het cohortjaar is (kolom
    `diploma_behaald`, voor eenjarige opleidingen), en anders 'Gestart, niet
    naar jaar 2'. Zonder diploma-kolom ontstaan alleen de eerste en laatste.

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

    # Diploma in het cohortjaar (eenjarige opleidingen). Per spell: heeft een
    # van de rijen een diploma?
    heeft_diploma_kolom = _DIPLOMA_KOLOM in df.columns
    if heeft_diploma_kolom:
        df["_diploma_bool"] = df[_DIPLOMA_KOLOM].fillna(False).astype(bool)
        df["_diploma"] = df.groupby(spell_sleutel)["_diploma_bool"].transform("any")

    # Houd alleen de eerstejaars-rij per spell over.
    eerstejaars = (
        df[df["inschrijvingsjaar"] == df["eerste_jaar_aan_deze_opleiding_instelling"]]
        .drop_duplicates(spell_sleutel, keep="first")
        .copy()
    )

    # Doorstroom naar jaar 2 weegt het zwaarst; daarna telt een diploma in het
    # eerste jaar als succes; anders is de student gestopt.
    if heeft_diploma_kolom:
        eerstejaars["groep"] = np.where(
            eerstejaars["_retentie"],
            GROEP_DOORGESTROOMD,
            np.where(
                eerstejaars["_diploma"],
                GROEP_DIPLOMA,
                GROEP_GESTART_GEEN_VERVOLG,
            ),
        )
    else:
        eerstejaars["groep"] = np.where(
            eerstejaars["_retentie"],
            GROEP_DOORGESTROOMD,
            GROEP_GESTART_GEEN_VERVOLG,
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
    doorstroomt: ArrayLike | None = None,
    diploma_behaald: ArrayLike | None = None,
    opleiding: str | None = None,
    instellingscode: str | None = None,
    geslacht: ArrayLike | None = None,
    herkomst: ArrayLike | None = None,
    vooropleiding_omschrijving: ArrayLike | None = None,
    gem_eindcijfer_vo: ArrayLike | None = None,
) -> pd.DataFrame:
    """Bouw synthetische ruwe 1CHO-data in lang formaat.

    Elke ingeschreven student krijgt een eerstejaars-rij. Bij een meerjarige
    opleiding krijgen doorstromers (`doorstroomt=True`) daarnaast een rij voor
    jaar 2. Bij een eenjarige opleiding (master) zet je in plaats daarvan
    `diploma_behaald=True` voor wie het diploma haalde; dat wordt een kolom in
    de data. De uitkomstgroep zit dus NIET kant-en-klaar in de data maar wordt
    afgeleid door `transformeer_cho()`, net als bij echte 1CHO-data.

    `studentnummers` en de meegegeven indicator- en demografie-arrays moeten
    allemaal dezelfde lengte hebben (een waarde per ingeschreven student).
    """
    studentnummers = np.asarray(studentnummers)
    n = len(studentnummers)

    if doorstroomt is None:
        doorstroomt = np.zeros(n, dtype=bool)
    else:
        doorstroomt = np.asarray(doorstroomt, dtype=bool)
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
    if diploma_behaald is not None:
        diploma_behaald = np.asarray(diploma_behaald, dtype=bool)
        if len(diploma_behaald) != n:
            raise ValueError("diploma_behaald moet even lang zijn als studentnummers")
        jaar1[_DIPLOMA_KOLOM] = diploma_behaald

    jaar2 = jaar1[doorstroomt].copy()
    jaar2["inschrijvingsjaar"] = jaar + 1

    lang = pd.concat([jaar1, jaar2], ignore_index=True)
    return lang.sort_values(
        ["persoonsgebonden_nummer", "inschrijvingsjaar"]
    ).reset_index(drop=True)
