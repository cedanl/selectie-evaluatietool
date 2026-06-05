# Welke data heb je nodig?

De evaluatietool verwacht drie bestanden. Hieronder staat per bestand wat
erin moet staan, welk formaat het moet hebben, en waar je het vandaan haalt.


## 1. Selectiedata

Dit is het bestand met de resultaten van de selectieprocedure. Elke rij is
een kandidaat, en de kolommen bevatten de scores die bij de selectie zijn
gemeten. Denk aan toetsscores, gesprekbeoordelingen, motivatiescores, of
cijfers van een portfolio-beoordeling.

Dit bestand krijg je meestal van de opleiding zelf, van de afdeling die de
selectie organiseert, of van een extern testbureau dat de afnames doet.

**Formaat:** Excel (.xlsx of .xls)

**Wat moet erin staan:**

- Een kolom met een uniek nummer per kandidaat (bijvoorbeeld studentnummer
  of aanvraagnummer). Dit nummer wordt gebruikt om de selectiedata te
  koppelen aan de studiesuccesdata.
- Een of meer kolommen met scores. Elk type score mag een andere schaal
  hebben (bijvoorbeeld 1-10, percentages, of schaalscore).
- Optioneel een totaalscore.

Het maakt niet uit als er ook andere kolommen in staan, zoals namen,
e-mailadressen, of datums. De tool slaat die automatisch over.

**Voorbeeld:**

Stel een opleiding Farmacie selecteert kandidaten met een competentietest,
een gesprek en een situational judgement test. Dan zou het selectiebestand
er zo uit kunnen zien:

| Studentnummer | ct_reflecteren | ct_steunzoeken | Gesprek_B1 | sjts_totaal | Totaalscore |
|---|---|---|---|---|---|
| 12345678 | 7.2 | 6.8 | 2 | 85 | 72.5 |
| 23456789 | 5.1 | 7.3 | 3 | 91 | 68.0 |
| 34567890 | 8.0 | 8.1 | 1 | 78 | 80.2 |

Bij een opleiding Psychologie met alleen een kennistoets, matchingscore en
cijferlijst ziet het er heel anders uit:

| Studentnummer | Toetsscore | Matchingscore | Cijferlijstscore |
|---|---|---|---|
| 12345678 | 7.0 | 8.5 | 6.8 |
| 23456789 | 6.2 | 7.0 | 7.5 |

Elke opleiding heeft een ander selectiebestand. De tool past zich aan via
het configuratiebestand (zie hieronder).

**Tips:**

- Het bestand mag meerdere bladen hebben. De tool vraagt welk blad je wilt
  gebruiken.
- De kolomnamen hoeven niet op de eerste rij te staan. Als er bijvoorbeeld
  een titel of lege rij boven de kolomnamen staat, kun je aangeven op welke
  rij de echte kolomnamen beginnen.
- Je hoeft het bestand niet op te schonen. Laat het zoals het is en laat de
  config wizard uitzoeken welke kolommen scores bevatten.


## 2. Configuratiebestand

Het configuratiebestand vertelt de tool welke kolommen uit het
selectiebestand meegenomen moeten worden en hoe ze heten in het dashboard.

Je kunt dit bestand automatisch laten genereren via de config wizard in
het uploadscherm (klik op "Of: config automatisch genereren"). De wizard
leest het selectiebestand, detecteert de scorekolommen, en laat je het
resultaat controleren en aanpassen. Daarna kun je de config downloaden
als Excel zodat je hem later opnieuw kunt gebruiken.

Je kunt ook handmatig een configuratiebestand maken op basis van
`docs/config_template.xlsx`. Zie de README voor meer uitleg.

**Formaat:** Excel (.xlsx)


## 3. 1CHO-data (studiesucces)

Dit bestand bevat de studiesuccesgegevens: wie is begonnen met de
opleiding, wie is na het eerste jaar gestopt, en wie is doorgestroomd
naar jaar 2.

De afkorting 1CHO staat voor "1 Cijfer HO" (1 Cijfer Hoger Onderwijs),
een landelijke dataset die door DUO wordt beheerd. Je hogeschool of
universiteit kan deze data opvragen, of je kunt de
[1cijferho tool](https://github.com/cedanl/1cijferho) van CEDA gebruiken
om de juiste kolommen uit de 1CHO-bestanden te halen.

**Formaat:** CSV of Excel (.csv, .xlsx, .xls)

**Verplichte kolommen:**

| Kolom | Wat het is | Voorbeeld |
|---|---|---|
| `studentnummer` | Hetzelfde nummer als in de selectiedata | 12345678 |
| `selectiejaar` | Het jaar van de selectie | 2026 |
| `groep` | Studiesucces-uitkomst | zie onder |

De kolom `groep` moet een van deze drie waarden bevatten:

- `Niet gestart` - de kandidaat is niet begonnen met de opleiding
- `Gestart, niet naar jaar 2` - begonnen maar na jaar 1 gestopt
- `Doorgestroomd naar jaar 2` - zowel jaar 1 als jaar 2 afgerond

**Optionele kolommen:**

| Kolom | Wat het is | Voorbeeld |
|---|---|---|
| `geslacht` | Man, vrouw, of anders | vrouw |
| `herkomst` | Etnische of culturele achtergrond | Nederlands |
| `hoogste_vooropleiding` | Vooropleiding voor de studie | VWO |
| `gem_eindcijfer_vo` | Gemiddeld eindexamencijfer | 7.3 |

Deze kolommen zijn niet verplicht, maar als ze aanwezig zijn kun je in het
dashboard filteren op geslacht en vooropleiding, en zie je extra grafieken
over demografie en VO-cijfers.


## Hoe worden de bestanden gekoppeld?

De tool koppelt de selectiedata aan de 1CHO-data via het studentnummer.
Kandidaten die wel in de selectiedata staan maar niet in de 1CHO-data
worden automatisch ingedeeld als "Niet gestart".

Zorg ervoor dat het studentnummer in beide bestanden hetzelfde formaat
heeft. Als het ene bestand voorloopnullen gebruikt (0012345) en het andere
niet (12345), dan worden ze niet aan elkaar gekoppeld.


## Voorbeelden

### Selectiedata (Excel)

Een simpel selectiebestand zou er zo uit kunnen zien:

| Studentnummer | Toetsscore | Motivatiescore | Gespreksbeoordeling | Totaalscore |
|---|---|---|---|---|
| 12345678 | 7.0 | 8.5 | 2 | 72.5 |
| 23456789 | 6.2 | 7.0 | 3 | 68.0 |
| 34567890 | 8.0 | 9.1 | 1 | 80.2 |

In de praktijk bevatten selectiebestanden vaak tientallen kolommen, waarvan
maar een deel scores zijn. Dat is prima. De config wizard filtert de
scorekolommen er automatisch uit.

### 1CHO-data (CSV)

Een minimaal 1CHO-bestand:

```
studentnummer;selectiejaar;groep
12345678;2026;Doorgestroomd naar jaar 2
23456789;2026;Gestart, niet naar jaar 2
34567890;2026;Niet gestart
```

Met optionele kolommen:

```
studentnummer;selectiejaar;groep;geslacht;hoogste_vooropleiding;gem_eindcijfer_vo
12345678;2026;Doorgestroomd naar jaar 2;vrouw;VWO;7.3
23456789;2026;Gestart, niet naar jaar 2;man;VWO;6.8
34567890;2026;Niet gestart;vrouw;HAVO + propedeuse;6.5
```

Let op: de puntkomma (;) als scheidingsteken is de standaard. Komma's
werken ook.
