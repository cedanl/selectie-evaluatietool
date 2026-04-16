# evaluatietool-voorbeeld

Proof-of-concept voor een evaluatietool die selectiedata van opleidingen koppelt
aan 1CHO-data om studiesucces in kaart te brengen.

## Drie groepen

**Niet gestart** — Student is niet geselecteerd, of is geselecteerd maar staat
niet in 1CHO (aanmelding ingetrokken, studie nooit gestart).

**Gestart, niet naar jaar 2** — Student staat in 1CHO voor jaar 1 maar heeft
geen jaar-2 rij voor dezelfde opleiding en instelling. Geen tweede jaar = uitval
of overstap na het eerste jaar.

**Doorgestroomd naar jaar 2** — Student heeft zowel een jaar-1 als een jaar-2 rij
in 1CHO.

## Projectstructuur

```
evaluatietool-voorbeeld/
├── app.py                          # Streamlit dashboard
├── pyproject.toml                  # Python dependencies (uv)
├── uv.lock
└── data/
    └── synthetic/
        ├── selectiedata_voorbeeld.csv         # Synthetische selectiedata
        ├── EV_DEMO_selectieopleiding.csv      # Synthetische 1CHO-data (raw EV formaat)
        └── gekoppeld.parquet                  # Gekoppelde dataset voor het dashboard
```

## Gebruik

```bash
uv sync
uv run streamlit run app.py
```

## Data

### Selectiedata

`selectiedata_voorbeeld.csv` simuleert een veelvoorkomend selectieformat met drie
instrumenten (motivatiebrief, CV, interview) en een gewogen totaalscore. Echte
selectiedata verschilt per opleiding in formaat en variabelen.

### 1CHO-data

`EV_DEMO_selectieopleiding.csv` volgt het raw EV_* formaat van 1cijferho, inclusief
numerieke codes:

| Kolom | Codering |
|---|---|
| `geslacht` | V / M / O |
| `opleidingsvorm` | 1 = voltijd, 2 = deeltijd |
| `opleidingsfase` | B = bachelor, M = master |
| `hoogste_vooropleiding` | numeriek (zie Dec_vooropl.csv van 1cijferho) |
| `herkomst_indikking_volgens_cbs_definitie` | 1 = NL, 2 = westers, 3–7 = niet-westers |
| `indicatie_actief_op_peildatum` | 1 = actief op 1 oktober |
| `soort_inschrijving_continu_type_ho_binnen_ho` | 1 = eerstejaars, 2 = hogerejaars |

De koppelsleutel is `persoonsgebonden_nummer`. In de praktijk moet koppeling via
een beveiligd proces verlopen.

### Echte data gebruiken

Vervang de bestanden in `data/synthetic/` door echte data en pas het koppelproces
aan. De 1CHO-data (`EV_*.csv`) komt rechtstreeks uit de output van 1cijferho.
Zorg dat `gekoppeld.parquet` dezelfde kolomstructuur heeft als de synthetische versie.
