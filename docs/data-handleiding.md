# Welke data heb je nodig?

De tool werkt met drie bestanden. Hieronder lees je per bestand wat erin
moet staan, in welk formaat, en waar je het vandaan haalt. Klinkt veel,
maar in de praktijk is het overzichtelijk. Lees het rustig door.


## 1. Selectiedata

Dit is het bestand met de resultaten van de selectie. Elke rij is een
kandidaat, en de kolommen bevatten de scores die bij de selectie zijn
gemeten. Denk aan toetsscores, een beoordeling van een gesprek, een
motivatiescore of een cijfer voor een portfolio.

Dit bestand krijg je meestal van de opleiding zelf, van de afdeling die de
selectie regelt, of van een extern testbureau dat de toetsen afneemt.

**Formaat:** Excel (.xlsx of .xls)

**Wat moet erin staan:**

- Een kolom met een uniek nummer per kandidaat (bijvoorbeeld studentnummer
  of aanvraagnummer). Met dit nummer koppelt de tool later de selectiescore
  aan de studiegegevens van diezelfde persoon.
- Een of meer kolommen met scores. Elke score mag een eigen schaal hebben.
  De ene kolom mag van 1 tot 10 lopen, de andere in percentages, en weer
  een andere in een of ander puntenaantal. Dat geeft niet.
- Eventueel een totaalscore.

Het is geen probleem als er ook andere kolommen in staan, zoals namen,
e-mailadressen of datums. De tool slaat die vanzelf over.

**Voorbeeld:**

Stel, een opleiding Farmacie selecteert met een competentietest, een
gesprek en een test waarin je inschat hoe je in lastige situaties zou
handelen. Dan zou het selectiebestand er zo uit kunnen zien:

| Studentnummer | ct_reflecteren | ct_steunzoeken | Gesprek_B1 | sjts_totaal | Totaalscore |
|---|---|---|---|---|---|
| 12345678 | 7.2 | 6.8 | 2 | 85 | 72.5 |
| 23456789 | 5.1 | 7.3 | 3 | 91 | 68.0 |
| 34567890 | 8.0 | 8.1 | 1 | 78 | 80.2 |

Een opleiding Psychologie die alleen een kennistoets, een matchingscore en
een cijferlijst gebruikt, heeft een heel ander bestand:

| Studentnummer | Toetsscore | Matchingscore | Cijferlijstscore |
|---|---|---|---|
| 12345678 | 7.0 | 8.5 | 6.8 |
| 23456789 | 6.2 | 7.0 | 7.5 |

Elke opleiding heeft dus zijn eigen selectiebestand. De tool snapt dankzij
het configuratiebestand (zie hieronder) hoe jouw bestand in elkaar zit.

**Handig om te weten:**

- Het bestand mag meerdere tabbladen hebben. De tool vraagt welk tabblad je
  wilt gebruiken.
- De kolomnamen hoeven niet op de eerste regel te staan. Staat er bovenaan
  bijvoorbeeld een titel of een lege regel, dan geef je gewoon aan op welke
  regel de echte kolomnamen beginnen.
- Je hoeft het bestand niet eerst op te schonen. Laat het zoals het is en
  laat de config wizard uitzoeken welke kolommen scores zijn.


## 2. Configuratiebestand

Het configuratiebestand is een hulpbestandje dat de tool vertelt welke
kolommen uit het selectiebestand belangrijk zijn en hoe ze in het dashboard
moeten heten.

Het makkelijkst is om dit bestand automatisch te laten maken. Klik in het
uploadscherm op "Of: config automatisch genereren". De tool leest dan je
selectiebestand, zoekt zelf de scorekolommen op, en laat je het resultaat
controleren en bijschaven. Daarna kun je het bestand downloaden als Excel,
zodat je het de volgende keer meteen kunt gebruiken.

Je kunt het ook met de hand maken op basis van `docs/config_template.xlsx`.
In de README staat hoe dat werkt.

**Formaat:** Excel (.xlsx)


## 3. 1CHO-data (studiegegevens)

Dit bestand vertelt wat er na de selectie met de studenten is gebeurd: wie
is begonnen aan de opleiding, wie is na het eerste jaar gestopt, en wie is
doorgegaan naar het tweede jaar.

1CHO is een afkorting van "1 Cijfer Hoger Onderwijs". Het is een landelijke
verzameling studiegegevens die door DUO wordt beheerd (DUO is de
overheidsdienst die onder andere studiefinanciering en
studentgegevens regelt). Je hogeschool of universiteit kan deze gegevens
opvragen. Je kunt ook de
[1cijferho tool](https://github.com/cedanl/1cijferho) van CEDA gebruiken om
de juiste kolommen uit de 1CHO-bestanden te halen.

**Formaat:** CSV of Excel (.csv, .xlsx, .xls)

### Hoe het 1CHO-bestand is opgebouwd

Het 1CHO-bestand komt precies zoals DUO het levert: het zijn
inschrijfgegevens. Het belangrijkste om te snappen is dit: er staat **een
regel per student per studiejaar**, niet een regel per student. Een student
die twee jaar ingeschreven stond, heeft dus twee regels.

Er is geen kolom die meteen zegt of iemand is doorgestroomd. Dat is met
opzet zo. Of een studie goed liep, is namelijk niet iets vasts dat je
gewoon kunt opzoeken. Je leidt het af uit het patroon van inschrijvingen:
stond iemand het jaar daarna nog steeds ingeschreven, of niet? De tool doet
die afleiding voor je (zie "Hoe bepaalt de tool de doorstroom?" hieronder).

**Verplichte kolommen:**

| Kolom | Wat het is | Voorbeeld |
|---|---|---|
| `persoonsgebonden_nummer` | Hetzelfde nummer als het studentnummer in de selectiedata | 12345678 |
| `inschrijvingsjaar` | Het jaar van deze inschrijfregel | 2026 |
| `eerste_jaar_aan_deze_opleiding_instelling` | Het eerste jaar dat de student aan deze opleiding stond | 2026 |

**Optionele kolommen:**

| Kolom | Wat het is | Voorbeeld |
|---|---|---|
| `geslacht` | Man, vrouw of anders | vrouw |
| `herkomst` | Achtergrond van de student | Nederlands |
| `hoogste_vooropleiding_omschrijving_vooropleiding` | De opleiding die de student hiervoor deed (1CHO-omschrijving) | vwo profiel natuur/gezondheid |
| `gem_eindcijfer_vo` | Gemiddeld eindexamencijfer op de middelbare school | 7.3 |
| `diploma_behaald` | Of de student in het cohortjaar een diploma haalde (voor eenjarige opleidingen) | True |

Deze kolommen zijn niet verplicht. Maar als ze erin staan, kun je in het
dashboard filteren op geslacht en vooropleiding, en krijg je extra grafieken
over de samenstelling van de groep en over de eindexamencijfers. De lange
omschrijving van de vooropleiding wordt automatisch ingekort tot een korte
categorie (VWO, HAVO, MBO, HO).

### Hoe bepaalt de tool de doorstroom?

De tool kijkt per student naar de studiejaren en deelt iedereen in een van
deze groepen in:

- `Doorgestroomd naar jaar 2` - er is een regel in het jaar na het eerste
  studiejaar (dus `eerste_jaar_aan_deze_opleiding_instelling + 1`). De
  student studeerde dat jaar dus nog.
- `Gestart, diploma gehaald` - er is geen vervolgjaar, maar de student
  haalde in het cohortjaar wel een diploma (kolom `diploma_behaald`). Dit is
  bedoeld voor opleidingen van een jaar, zoals een master, waar geen tweede
  jaar bestaat en het diploma dus het doel is.
- `Gestart, niet naar jaar 2` - er is wel een regel in het eerste jaar, maar
  geen vervolgregel in jaar 2 en geen diploma. De student is dus gestopt.
- `Niet gestart` - de kandidaat staat wel in de selectiedata, maar komt
  helemaal niet voor in de 1CHO-data. Niet toegelaten, of wel toegelaten maar
  nooit begonnen.

Doorstromen naar jaar 2 telt het zwaarst, daarna telt een diploma in het
eerste jaar als succes. Zit er geen `diploma_behaald`-kolom in je
1CHO-data, dan ontstaan alleen de groepen rond doorstroom naar jaar 2.

Een voorbeeld met twee studenten:

```
persoonsgebonden_nummer;inschrijvingsjaar;eerste_jaar_aan_deze_opleiding_instelling
11111111;2026;2026
11111111;2027;2026
22222222;2026;2026
```

- Student 11111111 heeft twee regels: 2026 (het eerste jaar) en 2027. Omdat
  er een regel is in het jaar na het eerste jaar (2027), is deze student
  **doorgestroomd**.
- Student 22222222 heeft alleen een regel in 2026 en geen vervolg in 2027,
  dus **gestart, niet naar jaar 2**.
- Een kandidaat die wel in de selectiedata zit maar hier helemaal niet in
  voorkomt, wordt **niet gestart**.

### Studenten met meer dan een opleiding

Soms staat een student voor meerdere opleidingen ingeschreven, bijvoorbeeld
bij een dubbele studie. De doorstroom wordt dan **per opleiding apart**
bepaald, niet voor de student als geheel. Iemand kan dus bij de ene opleiding
doorstromen en bij de andere stoppen. De tool kijkt daarvoor naar de
combinatie van studentnummer, opleiding en eerste studiejaar. Bevat jouw
1CHO-bestand maar een opleiding, dan hoef je je hier niets van aan te
trekken; dan heeft elke student vanzelf maar een studieloopbaan.


## Hoe koppelt de tool de bestanden?

De tool legt de selectiedata en de 1CHO-data naast elkaar en zoekt bij
elke kandidaat de bijbehorende studiegegevens. Dat doet hij via het
studentnummer (in de 1CHO-data heet die kolom `persoonsgebonden_nummer`).
Kandidaten die wel in de selectiedata staan maar niet in de 1CHO-data,
worden vanzelf ingedeeld als "Niet gestart".

Let er wel op dat het studentnummer in beide bestanden op precies dezelfde
manier is geschreven. Heeft het ene bestand voorloopnullen (0012345) en het
andere niet (12345), dan ziet de tool ze als twee verschillende personen en
worden ze niet aan elkaar gekoppeld.


## Voorbeelden

### Selectiedata (Excel)

Een simpel selectiebestand zou er zo uit kunnen zien:

| Studentnummer | Toetsscore | Motivatiescore | Gespreksbeoordeling | Totaalscore |
|---|---|---|---|---|
| 12345678 | 7.0 | 8.5 | 2 | 72.5 |
| 23456789 | 6.2 | 7.0 | 3 | 68.0 |
| 34567890 | 8.0 | 9.1 | 1 | 80.2 |

In het echt hebben selectiebestanden vaak tientallen kolommen, waarvan maar
een deel scores zijn. Dat is prima. De config wizard haalt de scorekolommen
er vanzelf uit.

### 1CHO-data (CSV)

Een minimaal 1CHO-bestand. Let op de opbouw met een regel per studiejaar:
student 12345678 heeft twee regels (2026 en 2027) en is dus doorgestroomd;
student 23456789 heeft alleen een regel in 2026 en is gestart maar niet
doorgestroomd:

```
persoonsgebonden_nummer;inschrijvingsjaar;eerste_jaar_aan_deze_opleiding_instelling
12345678;2026;2026
12345678;2027;2026
23456789;2026;2026
```

Student 34567890 staat hier niet tussen. Als die wel in de selectiedata
zit, wordt hij vanzelf "Niet gestart".

Met optionele kolommen erbij:

```
persoonsgebonden_nummer;inschrijvingsjaar;eerste_jaar_aan_deze_opleiding_instelling;geslacht;hoogste_vooropleiding_omschrijving_vooropleiding;gem_eindcijfer_vo
12345678;2026;2026;vrouw;vwo profiel natuur/gezondheid;7.3
12345678;2027;2026;vrouw;vwo profiel natuur/gezondheid;7.3
23456789;2026;2026;man;havo;6.8
```

Let op: de puntkomma (;) tussen de waarden is de standaard. Een komma werkt
ook.
