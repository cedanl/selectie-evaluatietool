# evaluatietool-voorbeeld

Proof-of-concept voor een evaluatietool die selectiedata van opleidingen koppelt
aan 1CHO-data om studiesucces in kaart te brengen.

## Drie groepen

**Niet gestart** — Student is niet geselecteerd, of is geselecteerd maar staat
niet in 1CHO (aanmelding ingetrokken, studie nooit gestart).

**Gestart, niet naar jaar 2** — Student staat wel in 1CHO voor jaar 1, maar heeft
geen jaar-2 rij voor dezelfde opleiding+instelling. Geen tweede jaar = uitval of
overstap na het eerste jaar.

**Doorgestroomd naar jaar 2** — Student heeft zowel een jaar-1 als een jaar-2 rij
in 1CHO.

## Projectstructuur

```
evaluatietool-voorbeeld/
├── app.py                          # Streamlit dashboard
├── pyproject.toml                  # Python dependencies (uv)
├── scripts/
│   └── maak_data.py                # Genereert synthetische selectie- en 1CHO-data
└── data/
    └── synthetic/                  # Output van maak_data.py (lokaal, niet in git)
        ├── selectiedata_voorbeeld.csv
        ├── EV_DEMO_selectieopleiding.csv   # Raw EV formaat (zelfde als 1cijferho output)
        └── gekoppeld.parquet               # Gekoppelde dataset voor het dashboard
```

## Gebruik

```bash
# Eenmalig opzetten
uv sync

# Synthetische data aanmaken
uv run python scripts/maak_data.py

# Dashboard starten
uv run streamlit run app.py
```

## Data

### Selectiedata

Selectiedata verschilt per opleiding in formaat en variabelen. De synthetische
data in `data/synthetic/selectiedata_voorbeeld.csv` simuleert een veelvoorkomend
format met drie selectie-instrumenten (motivatiebrief, CV, interview) en een
gewogen totaalscore.

Kolommen: `kandidaat_id`, `persoonsgebonden_nummer`, `selectiejaar`, `opleiding`,
`geslacht`, `leeftijd`, `herkomst`, `hoogste_vooropleiding`, `gem_eindcijfer_vo`,
`motivatiescore`, `cv_score`, `interview_score`, `totaalscore`, `rangorde`,
`selectie_uitkomst`.

### 1CHO-data

De 1CHO-data (`EV_DEMO_selectieopleiding.csv`) volgt het raw EV_* formaat van
1cijferho, inclusief numerieke codes:

| Kolom | Codering |
|---|---|
| `geslacht` | V / M / O |
| `opleidingsvorm` | 1 = voltijd, 2 = deeltijd |
| `opleidingsfase` | B = bachelor, M = master |
| `hoogste_vooropleiding` | 402-502 (zie Dec_vooropl.csv van 1cijferho) |
| `herkomst_indikking_volgens_cbs_definitie` | 1 = NL, 2 = westers, 3-7 = niet-westers |
| `indicatie_actief_op_peildatum` | 1 = actief op 1 oktober |
| `soort_inschrijving_continu_type_ho_binnen_ho` | 1 = eerstejaars, 2 = hogerejaars |

De koppelsleutel tussen selectiedata en 1CHO is `persoonsgebonden_nummer`.
In de praktijk moet dit via een beveiligd koppelproces verlopen.

### Echte data koppelen

Vervang de data-generatie in `scripts/maak_data.py` door inleesscripts voor de
echte bestanden. De 1CHO-data (`EV_*_enriched.csv` of raw `EV_*.csv`) komt
rechtstreeks uit de output van 1cijferho. Gebruik `decodeer_cho()` in het script
om raw codes om te zetten naar leesbare waarden voor het dashboard.

## Afhankelijkheden

```
streamlit, pandas, numpy, plotly
```

Beheerd via uv (`pyproject.toml`).
