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
├── app.py                          # Dash dashboard
├── assets/                         # Statische bestanden (CSS, logo)
├── pyproject.toml                  # Python dependencies (uv)
├── uv.lock
├── scripts/
│   └── maak_data.py                # Genereert synthetische data (dev/demo)
└── data/
    └── synthetic/
        ├── selectiedata_voorbeeld.csv         # Synthetische selectiedata (breed: een rij per kandidaat)
        ├── selectiescores_voorbeeld.csv       # Scores per instrument, item en criterium (lang formaat)
        ├── EV_DEMO_selectieopleiding.csv      # Synthetische 1CHO-data (raw EV formaat)
        └── analysedata.csv                    # Startpunt voor het dashboard (selectie + 1CHO gekoppeld)
```

## Gebruik

```bash
uv sync
uv run python app.py
```

De app draait standaard op http://localhost:8050.

## Data

### Selectiedata

De synthetische selectiedata bestaat uit twee bestanden die samen het verwachte
format voor echte data illustreren.

**`selectiedata_voorbeeld.csv`** heeft een rij per kandidaat met geaggregeerde
scores per instrument en een gewogen totaalscore:

| Kolom | Type | Beschrijving |
|---|---|---|
| `kandidaat_id` | integer | Unieke identifier per kandidaat |
| `persoonsgebonden_nummer` | float | Koppelsleutel naar 1CHO (leeg als niet gestart) |
| `selectiejaar` | integer | Jaar van de selectieprocedure |
| `opleiding` | tekst | Naam van de opleiding |
| `instellingscode` | tekst | Instelling-identifier |
| `interview_score` | float | Gemiddelde score over alle interview-items en criteria |
| `motivatiescore` | float | Gemiddelde score over alle motivatiebrief-items en criteria |
| `cv_score` | float | Gemiddelde score over alle cv-items en criteria |
| `totaalscore` | float | Gewogen totaal (interview 50%, motivatiebrief 30%, cv 20%) |
| `rangorde` | integer | Rangorde op basis van totaalscore (1 = hoogste) |
| `selectie_uitkomst` | tekst | geselecteerd / reserve / niet geselecteerd |

Voorbeeld:

```
kandidaat_id;persoonsgebonden_nummer;selectiejaar;opleiding;instellingscode;motivatiescore;cv_score;interview_score;totaalscore;rangorde;selectie_uitkomst
10001;10001.0;2021;B Gezondheidswetenschappen;DEMO;6.85;6.40;7.12;6.96;12;geselecteerd
10002;10002.0;2021;B Gezondheidswetenschappen;DEMO;5.20;5.75;4.98;5.23;87;niet geselecteerd
10003;;2021;B Gezondheidswetenschappen;DEMO;4.90;5.10;5.30;5.13;102;niet geselecteerd
```

**`selectiescores_voorbeeld.csv`** heeft een rij per kandidaat per instrument per
item per criterium en is de granulaire bron waaruit de bovenstaande scores zijn
afgeleid:

| Kolom | Type | Beschrijving |
|---|---|---|
| `kandidaat_id` | integer | Unieke identifier per kandidaat |
| `selectiejaar` | integer | Jaar van de selectieprocedure |
| `instrument` | tekst | interview / motivatiebrief / cv |
| `item` | tekst | Onderdeel binnen het instrument (bijv. vraag_1, motivatie) |
| `criterium` | tekst | Beoordelingscriterium voor dit item (bijv. inhoud, kwaliteit) |
| `score` | float | Score op dit criterium (schaal 1-10) |

Voorbeeld van de granulaire structuur:

```
kandidaat_id;selectiejaar;instrument;item;criterium;score
10001;2021;interview;vraag_1;inhoud;7.2
10001;2021;interview;vraag_1;presentatie;6.8
10001;2021;interview;vraag_2;inhoud;8.1
10001;2021;motivatiebrief;motivatie;kwaliteit;7.0
10001;2021;cv;opleiding;relevantie;6.5
```

De instrumenten in de synthetische data:

| Instrument | Items | Criteria per item |
|---|---|---|
| interview | vraag_1, vraag_2, vraag_3 | inhoud, presentatie |
| motivatiebrief | motivatie, aansluiting | kwaliteit |
| cv | opleiding, ervaring | relevantie |

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
Zorg dat `analysedata.csv` dezelfde kolomstructuur heeft als de synthetische versie.
