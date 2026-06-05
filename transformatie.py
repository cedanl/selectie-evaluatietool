"""
Functies voor het inlezen van configuratiebestanden, valideren van de
config tegen selectiedata, en het omzetten van breed naar lang formaat.
"""

import base64
import io

import pandas as pd


def _decode_upload(contents: str) -> bytes:
    _, content_string = contents.split(",")
    return base64.b64decode(content_string)


def _find_col(headers: list[str], naam: str) -> str | None:
    """Zoek een kolomnaam via substring match in de headers."""
    for h in headers:
        if naam in str(h):
            return h
    return None


def parse_csv_or_excel(contents: str, filename: str) -> pd.DataFrame:
    raw = _decode_upload(contents)
    if filename.endswith((".xlsx", ".xls")):
        return pd.read_excel(io.BytesIO(raw))
    decoded = raw.decode("utf-8")
    sep = ";" if decoded[:500].count(";") > decoded[:500].count(",") else ","
    return pd.read_csv(io.StringIO(decoded), sep=sep)


def parse_selectiedata(contents: str, config: dict) -> pd.DataFrame:
    raw = _decode_upload(contents)
    blad = config.get("blad_naam") or 0
    header_rij = int(config.get("header_rij", 1)) - 1
    return pd.read_excel(io.BytesIO(raw), sheet_name=blad, header=header_rij)


def lees_config(contents: str) -> dict:
    raw = _decode_upload(contents)
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
    kolommen_df = kolommen_df.dropna(subset=[kolommen_df.columns[0]])
    kolommen_df = kolommen_df[kolommen_df.iloc[:, 0].astype(str).str.strip() != ""]

    veld_namen = ["kolom_naam", "instrument", "item", "criterium"]
    kolommen = []
    for idx, rij in kolommen_df.iterrows():
        entry = {}
        for i, veld in enumerate(veld_namen):
            if i < len(rij) and pd.notna(rij.iloc[i]):
                entry[veld] = str(rij.iloc[i]).strip()
            else:
                entry[veld] = ""
        kolommen.append(entry)

    return {**instellingen, "kolommen": kolommen}


def valideer_config(config: dict, selectiedata_contents: str) -> list[dict]:
    resultaten = []
    raw = _decode_upload(selectiedata_contents)
    xls = pd.ExcelFile(io.BytesIO(raw))

    blad = config.get("blad_naam", "")
    if blad and blad in xls.sheet_names:
        resultaten.append({"check": f"Blad '{blad}' gevonden", "ok": True})
    elif blad:
        resultaten.append(
            {"check": f"Blad '{blad}' niet gevonden in data", "ok": False}
        )
        return resultaten

    header_rij = int(config.get("header_rij", 1)) - 1
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

    kolommen = config.get("kolommen", [])
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
    for kol in kolommen:
        actual = _find_col(headers, kol["kolom_naam"])
        if actual and actual in df_sample.columns:
            col_data = df_sample[actual].dropna()
            if not col_data.empty:
                numeric = pd.to_numeric(col_data, errors="coerce")
                pct_numeriek = numeric.notna().sum() / len(col_data)
                if pct_numeriek < 0.5:
                    niet_numeriek.append(kol["kolom_naam"])

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
    jaar_raw = config.get("jaar", "")
    jaar = int(float(jaar_raw)) if jaar_raw else None
    kolommen = config.get("kolommen", [])

    headers = list(selectiedata_df.columns.astype(str))

    id_col_actual = _find_col(headers, id_kolom) if id_kolom else None
    if not id_col_actual:
        raise ValueError(f"ID-kolom '{id_kolom}' niet gevonden")

    # Build column mapping: actual df column -> config metadata
    col_mapping = []
    for kol in kolommen:
        data_col = _find_col(headers, kol["kolom_naam"])
        if data_col is not None:
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
    melted = melted.dropna(subset=["score"])
    melted["score"] = melted["score"].astype(float)
    melted = melted.rename(columns={id_col_actual: "studentnummer"})

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
