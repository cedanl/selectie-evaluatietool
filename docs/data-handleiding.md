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

Staan er ook andere kolommen in, zoals namen, e-mailadressen of datums, dan
analyseert de tool die niet. Hij leest ze wel in, dus haal persoonsgegevens
die je niet nodig hebt er liever uit (zie de
[privacy-handleiding](privacy-handleiding.md)).

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
uploadscherm op "Config automatisch genereren". De tool leest dan je
selectiebestand, zoekt zelf de scorekolommen op, en laat je het resultaat
controleren en bijschaven. Daarna kun je het bestand downloaden als Excel,
zodat je het de volgende keer meteen kunt gebruiken.

Je kunt het ook met de hand maken op basis van `docs/config_template.xlsx`.
In de README staat hoe dat werkt.

**Formaat:** Excel (.xlsx)

### Geen dubbele informatie

Neem geen kolommen mee die statistisch (bijna) hetzelfde zeggen over een
kandidaat. Bijvoorbeeld: een toets die zowel "percentage goed" als "aantal
goed" rapporteert, meet in de praktijk hetzelfde ten opzichte van de andere
kandidaten (wie hoger scoort op de een, scoort ook hoger op de ander).
Zulke kolommen allebei meenemen voegt geen nieuwe informatie toe, maar kan
wel de samenhangsanalyse en regressie vertekenen. Kies een van de twee,
meestal de kolom die het meest gangbaar is om te rapporteren.

De config wizard signaleert kolomparen die zeer sterk met elkaar
samenhangen (r ≥ 0,95) als waarschuwing, maar controleert dit niet
uitputtend; gebruik ook je eigen kennis van hoe de scores zijn opgebouwd.


## 3. 1CHO-data (studiegegevens)

Dit bestand vertelt wat er na de selectie met de studenten is gebeurd: wie
is begonnen aan de opleiding, wie is na het eerste jaar gestopt, en wie is
doorgegaan naar het tweede jaar.

1CHO is een afkorting van "1 Cijfer Hoger Onderwijs". Het is een landelijke
verzameling studiegegevens die door DUO wordt beheerd (DUO is de
overheidsdienst die onder andere studiefinanciering en
studentgegevens regelt).

**Let op: je uploadt hier niet het ruwe DUO-bestand.** DUO levert
1CHO-data op BSN, niet op studentnummer, en met codes in plaats van
omschrijvingen. Zet de levering eerst om met de
[1cijferho-tool](https://github.com/cedanl/1cijferho) van CEDA, met de
instelmodus **Evaluatietool Selectie** en een koppelbestand
BSN → studentnummer. Upload daarna het bestand dat eindigt op
**`_enriched.csv`** (of `_decoded.csv`). De [README](../README.md#stap-2-de-1cho-data-klaarmaken-met-de-1cijferho-tool)
beschrijft dit stap voor stap.

De tool herkent de uitvoer van de 1cijferho-tool vanzelf:

- de kolom `studentnummer` (die de 1cijferho-tool toevoegt met het
  koppelbestand) wordt de koppelsleutel, in plaats van het DUO-nummer in
  `persoonsgebonden_nummer`;
- bij masters leidt de tool `diploma_behaald` af uit `diplomajaar`. Dat is
  een studiejaar, net als `inschrijvingsjaar`; het diploma telt alleen als
  het in het studiejaar van de start is gehaald.

Maak je het bestand op een andere manier, zorg dan dat het de kolommen
hieronder heeft.

**Formaat:** CSV of Excel (.csv, .txt, .xlsx, .xls), tot 4 GB

### Hoe het 1CHO-bestand is opgebouwd

Het 1CHO-bestand bevat inschrijfgegevens, zoals DUO ze registreert. Het belangrijkste om te snappen is dit: er staat **een
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
| `persoonsgebonden_nummer` of `studentnummer` | Hetzelfde nummer als het studentnummer in de selectiedata. Staan beide erin (zoals bij de 1cijferho-tool), dan telt `studentnummer`. | 12345678 |
| `inschrijvingsjaar` | Het jaar van deze inschrijfregel | 2026 |
| `eerste_jaar_aan_deze_opleiding_instelling` | Het eerste jaar dat de student aan deze opleiding stond | 2026 |
| `geslacht` | Man, vrouw of anders | vrouw |
| `hoogste_vooropleiding_omschrijving_vooropleiding` | De opleiding die de student hiervoor deed (1CHO-omschrijving) | vwo profiel natuur & gezondheid |

Geslacht en vooropleiding zijn nodig voor de analyses naar achtergrond; zonder
die kolommen opent het dashboard niet. De lange omschrijving van de
vooropleiding wordt automatisch ingekort tot een korte categorie (VWO, HAVO,
MBO, HO, Buitenlands diploma).

**Optionele kolommen:**

| Kolom | Wat het is | Voorbeeld |
|---|---|---|
| `opleidingscode_naam_opleiding` | Naam van de opleiding. Nodig als het bestand meerdere opleidingen bevat: de tool vraagt dan welke bij de selectie hoort. | B Psychologie |
| `diploma_behaald` | Of de student in het cohortjaar een diploma haalde (voor eenjarige opleidingen). Ontbreekt deze, dan leidt de tool hem bij masters af uit `diplomajaar` en `opleidingsfase_actueel`. | True |
| `instellingscode` | Code of naam van de instelling | 21RI |

Andere kolommen (de uitvoer van de 1cijferho-tool heeft er zo'n 180) laat de
tool bij het inlezen weg.

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

Upload je een 1CHO-bestand van de hele instelling, dan kiest de tool alleen
de inschrijvingen die bij deze selectie horen:

- **Opleiding**: de tool zoekt de opleiding uit je config op in het
  1CHO-bestand. Lukt dat niet eenduidig, dan verschijnt bij het uploaden een
  keuzemenu "Welke opleiding in het 1CHO-bestand hoort bij deze selectie?".
  Inschrijvingen bij andere opleidingen tellen niet mee; een afgewezen
  kandidaat die elders begon, blijft dus **niet gestart**.
- **Cohort**: inschrijvingen die vóór het selectiejaar begonnen (een eerdere
  poging) tellen niet mee.
- **Meerdere inschrijvingen**: blijven er dan nog meerdere over, dan telt de
  inschrijving die het dichtst bij het selectiejaar begon.

Wat er is weggefilterd, zie je in de meldingen onder de 1CHO-upload.


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

Met geslacht en vooropleiding erbij (zo ziet een bruikbaar bestand eruit):

```
persoonsgebonden_nummer;inschrijvingsjaar;eerste_jaar_aan_deze_opleiding_instelling;geslacht;hoogste_vooropleiding_omschrijving_vooropleiding
12345678;2026;2026;vrouw;vwo profiel natuur & gezondheid
12345678;2027;2026;vrouw;vwo profiel natuur & gezondheid
23456789;2026;2026;man;havo profiel economie & maatschappij
```

Let op: de puntkomma (;) tussen de waarden is de standaard. Een komma werkt
ook.
