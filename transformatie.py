"""
Functies voor het inlezen van configuratiebestanden, valideren van de
config tegen selectiedata, en het omzetten van breed naar lang formaat.
"""

import base64
import io
import re
import zipfile

import pandas as pd

# Tekens die niet geldig zijn in XML 1.0. Excel bewaart ze bij opslaan en
# openpyxl's parser struikelt er dan over met "not well-formed (invalid token)".
_ILLEGALE_XML_TEKENS = re.compile(rb"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def _repareer_xlsx(raw: bytes) -> bytes:
    """Strip illegale XML 1.0-tekens uit alle XML-bestanden in een .xlsx ZIP.

    Werkt in-memory: leest het ZIP-archief, verwijdert de tekens uit elk
    .xml-bestand, en schrijft een schoon ZIP terug. Nodig wanneer een
    Excel-bestand kolomnamen of celwaarden met controle-tekens bevat die
    Excel bij opslaan gewoon bewaart maar die openpyxl's parser doen crashen.

    Een oud .xls-bestand is geen ZIP; dat geven we ongewijzigd terug zodat
    pandas het met xlrd kan lezen.
    """
    if not zipfile.is_zipfile(io.BytesIO(raw)):
        return raw
    src = zipfile.ZipFile(io.BytesIO(raw))
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        for item in src.infolist():
            data = src.read(item.filename)
            if item.filename.endswith(".xml"):
                data = _ILLEGALE_XML_TEKENS.sub(b"", data)
            dst.writestr(item, data)
    return buf.getvalue()


def _decode_upload(contents: str) -> bytes:
    _, content_string = contents.split(",", 1)
    return base64.b64decode(content_string)


def _kandidaat_kolommen(headers: list[str], naam: str) -> list[str]:
    """Headers die bij een configkolomnaam passen, van streng naar los.

    Eerst exacte matches (na strippen), dan hoofdletterongevoelig exact, en
    pas als die er niet zijn alle headers die de naam als substring bevatten.
    Zo pakt 'Item 1' nooit 'Item 10' als 'Item 1' zelf bestaat."""
    naam = str(naam).strip()
    if not naam:
        return []
    exact = [h for h in headers if str(h).strip() == naam]
    if exact:
        return exact
    zonder_hoofdletters = [h for h in headers if str(h).strip().lower() == naam.lower()]
    if zonder_hoofdletters:
        return zonder_hoofdletters
    return [h for h in headers if naam in str(h)]


def _find_col(headers: list[str], naam: str) -> str | None:
    """Zoek de header die bij een configkolomnaam hoort.

    Een substring-match telt alleen als hij eenduidig is: past de naam op
    meerdere headers (bijv. 'studentnr' op 'studentnr_oud' en
    'studentnr_nieuw'), dan geven we None terug in plaats van stil de eerste
    te kiezen. `valideer_config` meldt zulke dubbelzinnige namen apart."""
    kandidaten = _kandidaat_kolommen(headers, naam)
    return kandidaten[0] if len(kandidaten) == 1 else None


def dubbelzinnige_kolommen(headers: list[str], namen: list[str]) -> dict[str, list]:
    """Configkolomnamen die op meer dan één header passen, met die headers."""
    resultaat = {}
    for naam in namen:
        kandidaten = _kandidaat_kolommen(headers, naam)
        if len(kandidaten) > 1:
            resultaat[naam] = kandidaten
    return resultaat


_WAAR_WAARDEN = {"true", "waar", "ja", "yes", "y", "1", "1.0", "x"}


def parse_bool(val) -> bool:
    """Lees een Meenemen-cel (TRUE/FALSE, Ja/Nee, 1/0, ...) als boolean."""
    if isinstance(val, bool):
        return val
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return False
    return str(val).strip().lower() in _WAAR_WAARDEN


def meegenomen_kolommen(config: dict) -> list[dict]:
    """De kolommen waarvoor Meenemen aan staat. Oudere configs zonder
    Meenemen-kolom hebben dit veld niet, dus die tellen standaard mee."""
    return [k for k in config.get("kolommen", []) if k.get("meenemen", True)]


def normaliseer_studentnummer(serie: pd.Series) -> pd.Series:
    """Breng studentnummers naar een vergelijkbare vorm, zodat het koppelen van
    selectiedata en 1CHO robuust is tegen verschillen in type en opmaak: tekst
    versus getal, spaties eromheen, en het '123.0'-artefact dat Excel en CSV van
    gehele getallen maken. Lege waarden worden <NA>."""
    s = serie.astype("string").str.strip().str.replace(r"\.0$", "", regex=True)
    return s.mask(s.isin(["", "nan", "NaN", "<NA>", "None"]))


def parse_jaar(waarde) -> int | None:
    """Haal het jaartal uit een configwaarde. Accepteert 2025, "2025",
    "2025.0" en ook een studiejaar als "2025-2026" (dan telt het eerste jaar).
    Geeft None als er geen viercijferig jaartal in staat."""
    if waarde is None or (isinstance(waarde, float) and pd.isna(waarde)):
        return None
    match = re.search(r"\d{4}", str(waarde))
    return int(match.group()) if match else None


def parse_header_rij(waarde) -> int:
    """Lees de 1-based headerrij uit de config; leeg of onleesbaar wordt 1.
    Accepteert ook "3.0", zoals Excel een getal soms als tekst opslaat."""
    try:
        return max(1, int(float(waarde)))
    except (TypeError, ValueError):
        return 1


def parse_csv_or_excel(contents: str, filename: str) -> pd.DataFrame:
    raw = _decode_upload(contents)
    if filename.lower().endswith((".xlsx", ".xls")):
        return pd.read_excel(io.BytesIO(_repareer_xlsx(raw)))
    # cp1252 vóór latin-1: latin-1 accepteert elke byte en zou dus altijd
    # 'slagen', waardoor Windows-tekens als € en typografische aanhalingstekens
    # stil als stuurtekens zouden worden ingelezen.
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            decoded = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise ValueError(
            "Het CSV-bestand kon niet worden gelezen. Sla het op als UTF-8 en probeer opnieuw."
        )
    sep = ";" if decoded[:500].count(";") > decoded[:500].count(",") else ","
    return pd.read_csv(io.StringIO(decoded), sep=sep)


def parse_selectiedata(contents: str, config: dict) -> pd.DataFrame:
    raw = _repareer_xlsx(_decode_upload(contents))
    blad = config.get("blad_naam") or 0
    header_rij = parse_header_rij(config.get("header_rij")) - 1
    return pd.read_excel(io.BytesIO(raw), sheet_name=blad, header=header_rij)


def lees_config(contents: str) -> dict:
    raw = _repareer_xlsx(_decode_upload(contents))
    xls = pd.ExcelFile(io.BytesIO(raw))

    instellingen_df = pd.read_excel(xls, sheet_name="instellingen", header=None)
    inst = instellingen_df.dropna(subset=[0])
    inst = inst[inst.iloc[:, 0].astype(str).str.strip() != "instelling"]
    instellingen = dict(
        zip(
            inst.iloc[:, 0].astype(str).str.strip().str.lower(),
            inst.iloc[:, 1].fillna("").astype(str).str.strip(),
        )
    )

    kolommen_df = pd.read_excel(xls, sheet_name="kolommen")

    # De kolommen-tab bevat alle kolommen uit het selectiebestand met een
    # Meenemen-boolean voorop. Oudere configs zonder die kolom beginnen met
    # kolom_naam; we lezen positioneel zodat een header als "criterium
    # (optioneel)" geen probleem is, en herkennen het formaat aan de eerste kop.
    heeft_meenemen = str(kolommen_df.columns[0]).strip().lower().startswith("meenemen")
    if heeft_meenemen:
        veld_volgorde = [
            "meenemen",
            "kolom_naam",
            "instrument",
            "item",
            "criterium",
            "schaal",
        ]
        naam_idx = 1
    else:
        veld_volgorde = ["kolom_naam", "instrument", "item", "criterium", "schaal"]
        naam_idx = 0

    kolommen = []
    for _, rij in kolommen_df.iterrows():
        if naam_idx >= len(rij) or pd.isna(rij.iloc[naam_idx]):
            continue
        if str(rij.iloc[naam_idx]).strip() == "":
            continue
        entry = {"meenemen": True}
        for i, veld in enumerate(veld_volgorde):
            waarde = rij.iloc[i] if i < len(rij) else None
            if veld == "meenemen":
                entry["meenemen"] = parse_bool(waarde)
            else:
                entry[veld] = str(waarde).strip() if pd.notna(waarde) else ""
        kolommen.append(entry)

    return {**instellingen, "kolommen": kolommen}


def valideer_config(config: dict, selectiedata_contents: str) -> list[dict]:
    resultaten = []
    raw = _repareer_xlsx(_decode_upload(selectiedata_contents))
    xls = pd.ExcelFile(io.BytesIO(raw))

    blad = config.get("blad_naam", "")
    if blad and blad in xls.sheet_names:
        resultaten.append({"check": f"Blad '{blad}' gevonden", "ok": True})
    elif blad:
        resultaten.append(
            {"check": f"Blad '{blad}' niet gevonden in data", "ok": False}
        )
        return resultaten

    header_rij = parse_header_rij(config.get("header_rij")) - 1
    df = pd.read_excel(xls, sheet_name=blad or 0, header=header_rij, nrows=0)
    headers = list(df.columns.astype(str))

    id_kolom = config.get("koppel_id_kolom", "")
    if id_kolom:
        found = _find_col(headers, id_kolom) is not None
        resultaten.append(
            {
                "check": f"ID-kolom '{id_kolom}' {'gevonden' if found else 'niet gevonden'}",
                "ok": found,
            }
        )

    totaal_kolom = config.get("totaalscore_kolom", "")
    if totaal_kolom:
        found = _find_col(headers, totaal_kolom) is not None
        resultaten.append(
            {
                "check": f"Totaalscore '{totaal_kolom}' {'gevonden' if found else 'niet gevonden'}",
                "ok": found,
            }
        )

    kolommen = meegenomen_kolommen(config)

    namen = [id_kolom] if id_kolom else []
    namen += [kol["kolom_naam"] for kol in kolommen]
    for naam, kandidaten in dubbelzinnige_kolommen(headers, namen).items():
        resultaten.append(
            {
                "check": f"'{naam}' past op meerdere kolommen: "
                f"{', '.join(map(str, kandidaten[:3]))}"
                f"{'...' if len(kandidaten) > 3 else ''}. "
                "Gebruik de exacte kolomnaam in de config.",
                "ok": False,
            }
        )

    # Twee configregels die op dezelfde datakolom uitkomen, zouden dezelfde
    # scores twee keer als apart item meetellen.
    per_datakolom: dict[str, list[str]] = {}
    for kol in kolommen:
        data_col = _find_col(headers, kol["kolom_naam"])
        if data_col is not None:
            per_datakolom.setdefault(data_col, []).append(kol["kolom_naam"])
    for data_col, config_namen in per_datakolom.items():
        if len(config_namen) > 1:
            resultaten.append(
                {
                    "check": f"Configregels {', '.join(config_namen)} wijzen allemaal "
                    f"naar kolom '{data_col}'",
                    "ok": False,
                }
            )

    gevonden = 0
    niet_gevonden = []
    for kol in kolommen:
        if _find_col(headers, kol["kolom_naam"]) is not None:
            gevonden += 1
        else:
            niet_gevonden.append(kol["kolom_naam"])

    if niet_gevonden:
        resultaten.append(
            {
                "check": f"{gevonden} van {len(kolommen)} kolommen gevonden, "
                f"ontbreken: {', '.join(niet_gevonden[:3])}{'...' if len(niet_gevonden) > 3 else ''}",
                "ok": False,
            }
        )
    else:
        resultaten.append(
            {
                "check": f"Alle {len(kolommen)} kolommen gevonden in data",
                "ok": True,
            }
        )

    df_sample = pd.read_excel(xls, sheet_name=blad or 0, header=header_rij)
    n_rijen = len(df_sample)
    resultaten.append(
        {
            "check": f"{n_rijen} kandidaten in selectiebestand",
            "ok": n_rijen > 0,
        }
    )

    if id_kolom:
        id_actual = _find_col(headers, id_kolom)
        if id_actual and id_actual in df_sample.columns:
            n_leeg = int(df_sample[id_actual].isna().sum())
            if n_leeg > 0:
                resultaten.append(
                    {
                        "check": f"{n_leeg} rijen zonder ID-waarde in '{id_kolom}'",
                        "ok": False,
                    }
                )

    niet_numeriek = []
    deels_tekst = []  # (kolom, aantal tekstcellen) bij verder numerieke kolommen
    for kol in kolommen:
        actual = _find_col(headers, kol["kolom_naam"])
        if actual and actual in df_sample.columns:
            col_data = df_sample[actual].dropna()
            if not col_data.empty:
                numeric = pd.to_numeric(col_data, errors="coerce")
                pct_numeriek = numeric.notna().sum() / len(col_data)
                if pct_numeriek < 0.5:
                    niet_numeriek.append(kol["kolom_naam"])
                elif numeric.isna().any():
                    deels_tekst.append((kol["kolom_naam"], int(numeric.isna().sum())))

    if deels_tekst:
        # Geen blokkade: tekstcellen als 'n.v.t.' worden als leeg behandeld,
        # maar de gebruiker moet wel zien dat dat gebeurt.
        beschrijving = ", ".join(f"'{k}' ({n})" for k, n in deels_tekst[:3])
        resultaten.append(
            {
                "check": "Niet-numerieke cellen worden als leeg behandeld in "
                f"{beschrijving}{'...' if len(deels_tekst) > 3 else ''}",
                "ok": True,
                "waarschuwing": True,
            }
        )

    jaar_raw = config.get("jaar", "")
    if str(jaar_raw).strip() and parse_jaar(jaar_raw) is None:
        resultaten.append(
            {
                "check": f"Jaar '{jaar_raw}' bevat geen jaartal; vul bijvoorbeeld 2025 in",
                "ok": False,
            }
        )

    if niet_numeriek:
        resultaten.append(
            {
                "check": f"{len(niet_numeriek)} kolom(men) bevatten geen numerieke data: "
                f"{', '.join(niet_numeriek[:3])}{'...' if len(niet_numeriek) > 3 else ''}",
                "ok": False,
            }
        )

    return resultaten


def transformeer_naar_lang(selectiedata_df: pd.DataFrame, config: dict) -> pd.DataFrame:
    id_kolom = config.get("koppel_id_kolom", "")
    opleiding = config.get("opleiding", "")
    jaar = parse_jaar(config.get("jaar", ""))
    kolommen = meegenomen_kolommen(config)

    headers = list(selectiedata_df.columns.astype(str))

    id_col_actual = _find_col(headers, id_kolom) if id_kolom else None
    if not id_col_actual:
        raise ValueError(f"ID-kolom '{id_kolom}' niet gevonden")

    # Build column mapping: actual df column -> config metadata
    col_mapping = []
    for kol in kolommen:
        data_col = _find_col(headers, kol["kolom_naam"])
        # Een datakolom maar één keer meenemen, ook als meerdere configregels
        # erop uitkomen (valideer_config meldt dat als fout).
        if data_col is not None and data_col not in {dc for dc, _ in col_mapping}:
            col_mapping.append((data_col, kol))

    if not col_mapping:
        return pd.DataFrame()

    data_cols = [dc for dc, _ in col_mapping]
    melted = selectiedata_df[[id_col_actual] + data_cols].melt(
        id_vars=[id_col_actual],
        value_vars=data_cols,
        var_name="_kolom",
        value_name="score",
    )
    # Tekstcellen als 'n.v.t.' of '-' tellen als ontbrekend; valideer_config
    # meldt dat aan de gebruiker.
    melted["score"] = pd.to_numeric(melted["score"], errors="coerce")
    melted = melted.dropna(subset=["score"])
    melted = melted.rename(columns={id_col_actual: "studentnummer"})
    melted["studentnummer"] = normaliseer_studentnummer(melted["studentnummer"])
    melted = melted.dropna(subset=["studentnummer"])

    # Map metadata from config onto each melted row
    meta_lookup = {dc: kol for dc, kol in col_mapping}
    melted["instrument"] = melted["_kolom"].map(lambda c: meta_lookup[c]["instrument"])
    melted["item"] = melted["_kolom"].map(lambda c: meta_lookup[c]["item"])
    melted["criterium"] = melted["_kolom"].map(
        lambda c: meta_lookup[c].get("criterium", "")
    )
    melted["selectiejaar"] = jaar
    melted["opleiding"] = opleiding
    melted["instellingscode"] = config.get("instellingscode", "")

    return melted[
        [
            "studentnummer",
            "selectiejaar",
            "opleiding",
            "instellingscode",
            "instrument",
            "item",
            "criterium",
            "score",
        ]
    ]
