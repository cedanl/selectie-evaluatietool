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

### Hoe 1CHO-data is opgebouwd

1CHO-data komt zoals DUO die levert: inschrijvingsgegevens. Het belangrijkste
om te begrijpen is dat er **een rij per student per inschrijvingsjaar** in
staat, niet een rij per student. Een student die twee jaar ingeschreven
staat, heeft dus twee rijen.

Er zit geen kolom in die meteen zegt of iemand is doorgestroomd. Dat is een
bewuste eigenschap van 1CHO: studiesucces is geen vast kenmerk van een
persoon, maar iets dat je afleidt uit het patroon van inschrijvingen. De
tool doet die afleiding voor je (zie "Hoe wordt de doorstroom bepaald?"
hieronder).

**Verplichte kolommen:**

| Kolom | Wat het is | Voorbeeld |
|---|---|---|
| `persoonsgebonden_nummer` | Hetzelfde nummer als de studentnummer in de selectiedata | 12345678 |
| `inschrijvingsjaar` | Het jaar van deze inschrijfrij | 2026 |
| `eerste_jaar_aan_deze_opleiding_instelling` | Het eerste jaar dat de student aan deze opleiding stond | 2026 |

**Optionele kolommen:**

| Kolom | Wat het is | Voorbeeld |
|---|---|---|
| `geslacht` | Man, vrouw, of anders | vrouw |
| `herkomst` | Etnische of culturele achtergrond | Nederlands |
| `hoogste_vooropleiding_omschrijving_vooropleiding` | Vooropleiding voor de studie (1CHO-omschrijving) | vwo profiel natuur/gezondheid |
| `gem_eindcijfer_vo` | Gemiddeld eindexamencijfer | 7.3 |

Deze kolommen zijn niet verplicht, maar als ze aanwezig zijn kun je in het
dashboard filteren op geslacht en vooropleiding, en zie je extra grafieken
over demografie en VO-cijfers. De lange vooropleidingsomschrijving wordt
automatisch teruggebracht tot een korte categorie (VWO, HAVO, MBO, HO).

### Hoe wordt de doorstroom bepaald?

De tool kijkt per student naar de inschrijfjaren en deelt iedereen in een
van drie groepen in:

- `Doorgestroomd naar jaar 2` - er is een inschrijfrij in het jaar na het
  eerste studiejaar (`eerste_jaar_aan_deze_opleiding_instelling + 1`).
- `Gestart, niet naar jaar 2` - wel een rij in het eerste jaar, maar geen
  vervolgrij in jaar 2.
- `Niet gestart` - de kandidaat staat wel in de selectiedata maar komt niet
  voor in de 1CHO-data.

Een voorbeeld. Hieronder staan drie kandidaten:

```
persoonsgebonden_nummer;inschrijvingsjaar;eerste_jaar_aan_deze_opleiding_instelling
11111111;2026;2026
11111111;2027;2026
22222222;2026;2026
```

- Student 11111111 heeft twee rijen: 2026 (eerste jaar) en 2027. Omdat er een
  rij is in `eerste_jaar + 1` (2027), is deze student **doorgestroomd**.
- Student 22222222 heeft alleen een rij in 2026 en geen vervolg in 2027, dus
  **gestart, niet naar jaar 2**.
- Een kandidaat die wel in de selectiedata zit maar hier helemaal niet
  voorkomt, wordt **niet gestart**.

### Studenten met meer dan een opleiding

Soms staat een student voor meerdere opleidingen ingeschreven, bijvoorbeeld
bij een dubbele studie. De doorstroom wordt dan **per opleiding apart**
bepaald, niet voor de student als geheel. Iemand kan dus bij de ene opleiding
doorstromen en bij de andere stoppen. Daarvoor kijkt de tool naar de
combinatie van studentnummer, opleiding en eerste studiejaar. Als je
1CHO-bestand maar een opleiding bevat, hoef je je hier niets van aan te
trekken; dan heeft elke student vanzelf maar een loopbaan.


## Hoe worden de bestanden gekoppeld?

De tool koppelt de selectiedata aan de 1CHO-data via het studentnummer
(in de 1CHO-data heet die kolom `persoonsgebonden_nummer`). Kandidaten die
wel in de selectiedata staan maar niet in de 1CHO-data worden automatisch
ingedeeld als "Niet gestart".

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

Een minimaal 1CHO-bestand. Let op het lange formaat: student 12345678 heeft
twee rijen (2026 en 2027) en is dus doorgestroomd; student 23456789 heeft
alleen een rij in 2026 en is gestart maar niet doorgestroomd:

```
persoonsgebonden_nummer;inschrijvingsjaar;eerste_jaar_aan_deze_opleiding_instelling
12345678;2026;2026
12345678;2027;2026
23456789;2026;2026
```

Student 34567890 staat hier niet tussen; als die wel in de selectiedata zit,
wordt hij automatisch "Niet gestart".

Met optionele kolommen:

```
persoonsgebonden_nummer;inschrijvingsjaar;eerste_jaar_aan_deze_opleiding_instelling;geslacht;hoogste_vooropleiding_omschrijving_vooropleiding;gem_eindcijfer_vo
12345678;2026;2026;vrouw;vwo profiel natuur/gezondheid;7.3
12345678;2027;2026;vrouw;vwo profiel natuur/gezondheid;7.3
23456789;2026;2026;man;havo;6.8
```

Let op: de puntkomma (;) als scheidingsteken is de standaard. Komma's
werken ook.
