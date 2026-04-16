# evaluatietool-voorbeeld

Proof-of-concept voor een evaluatietool die selectiedata van opleidingen koppelt
aan 1CHO-data om studiesucces in kaart te brengen.

## Drie groepen

De tool verdeelt kandidaten in drie groepen:

**Niet gestart** - Student is niet geselecteerd, of is geselecteerd maar staat
niet in 1CHO (aanmelding ingetrokken, studie nooit gestart).

**Gestart, niet naar jaar 2** - Student staat wel in 1CHO voor jaar 1, maar heeft
geen jaar-2 rij voor dezelfde opleiding+instelling. Dit is de indicator voor uitval
of overstap na het eerste jaar.

**Doorgestroomd naar jaar 2** - Student heeft zowel een jaar-1 als een jaar-2 rij
in 1CHO.

## Data

De map `data/synthetic/` bevat synthetische voorbeelddata. Echte data nooit
in git zetten.

| Bestand | Inhoud |
|---|---|
| `selectiedata_voorbeeld.csv` | Selectiedata (kandidaten, scores, uitkomsten) |
| `EV_DEMO_selectieopleiding.csv` | 1CHO-stijl inschrijvingsdata (enriched formaat) |
| `gekoppeld.rds` | Gekoppelde dataset met groepsindeling (aangemaakt door koppelscript) |

## Gebruik

Genereer de synthetische data en draai daarna de app:

```r
source("R/maak_selectiedata.R")
source("R/maak_1cho_data.R")
source("R/koppel_en_classificeer.R")
shiny::runApp("app.R")
```

Of via de terminal vanuit de projectmap:

```bash
Rscript R/maak_selectiedata.R
Rscript R/maak_1cho_data.R
Rscript R/koppel_en_classificeer.R
Rscript -e "shiny::runApp('app.R')"
```

## Echte data koppelen

Selectiedata verschilt per opleiding in formaat en variabelen. Pas
`R/maak_selectiedata.R` aan of vervang het door een inleesscript voor
de echte data. Zorg dat de kolom `persoonsgebonden_nummer` in beide datasets
overeenkomt.

De 1CHO-data (`EV_*.csv`) heeft altijd hetzelfde formaat en komt rechtstreeks
uit de output van 1cijferho. Gebruik het enriched-formaat (`EV_*_enriched.csv`).

## Afhankelijkheden

```r
install.packages(c("shiny", "bslib", "tidyverse"))
```
