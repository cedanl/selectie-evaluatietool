<div align="center">
  <h1>Selectie Evaluatietool</h1>

  <p>Onderzoek of je selectieprocedure voorspelt welke studenten doorgaan</p>

  <p>
    <a href="#"><img src="https://custom-icon-badges.demolab.com/badge/Windows-0078D6?logo=windows11&logoColor=white" alt="Windows"></a>
    <a href="#"><img src="https://img.shields.io/badge/macOS-000000?logo=apple&logoColor=F0F0F0" alt="macOS"></a>
    <a href="#"><img src="https://img.shields.io/badge/Linux-FCC624?logo=linux&logoColor=black" alt="Linux"></a>
    <img src="https://badgen.net/github/last-commit/cedanl/selectie-evaluatietool" alt="Laatste commit">
    <img src="https://img.shields.io/github/license/cedanl/selectie-evaluatietool" alt="Licentie">
  </p>
</div>

---

Deze tool legt de scores uit een selectieprocedure naast de 1CHO-inschrijvingen
en laat per selectieonderdeel zien of kandidaten die hoger scoorden vaker in
jaar 2 nog ingeschreven staan (bij een eenjarige master: vaker hun diploma
haalden). Je krijgt een dashboard met boxplots, toetsen, correlaties en een
logistische regressie, plus een PDF-rapport om te delen met de opleiding.

De tool draait lokaal in je browser; er gaan geen gegevens de deur uit.

**Voor wie:** institutioneel onderzoekers en BI-medewerkers die met 1CHO werken.
Je hoeft niet te programmeren, maar je moet een paar opdrachten in een terminal
kunnen draaien.

- [Checklist: heb je dit klaar?](#checklist-heb-je-dit-klaar)
- [1. Installeren en uitproberen](#1-installeren-en-uitproberen)
- [2. 1CHO omzetten met 1cijferho](#2-1cho-omzetten-met-1cijferho)
- [3. Het selectiebestand](#3-het-selectiebestand)
- [4. De config](#4-de-config)
- [5. Inladen en analyseren](#5-inladen-en-analyseren)
- [De uitkomsten lezen](#de-uitkomsten-lezen)
- [Problemen oplossen](#problemen-oplossen)


## Checklist: heb je dit klaar?

Loop dit na voordat je begint. Bijna alle problemen bij het inladen komen door
een van deze punten.

- [ ] **uv** is geïnstalleerd (zie stap 1), of je mag het installeren.
- [ ] De **1CHO-levering van DUO** (`EV*.asc`, `Bestandsbeschrijving_*.txt`,
      `Dec_*.asc`), en die bevat ook het studiejaar **ná** de start van het
      cohort. Voor het cohort van september 2025 heb je inschrijvingen in
      2026-2027 nodig.
- [ ] Een **koppelbestand** dat het BSN koppelt aan het nummer waarmee het
      selectiebestand werkt (stap 2a). Vaak is dat het studentnummer, maar
      het kan ook een aanvraag- of kandidaatnummer zijn.
- [ ] Het **selectiebestand** van de opleiding: één Excel-bestand, één rij per
      kandidaat, met **alle** kandidaten (ook afgewezen), een kolom met
      het koppelnummer en de scores als getallen.
- [ ] Het 1CHO-bestand is omgezet met 1cijferho en je hebt het bestand dat
      eindigt op **`_enriched.csv`** klaarstaan, met een kolom `studentnummer`
      (stap 2c).
- [ ] Het koppelnummer staat in het selectiebestand en het koppelbestand op
      **precies dezelfde manier** geschreven (geen `s` ervoor, zelfde
      voorloopnullen).
- [ ] Je hebt de [privacy-handleiding](docs/privacy-handleiding.md) met je FG
      of privacy officer doorgenomen.

Stap 1 en 2 doe je één keer voor de hele instelling. Stap 3 tot en met 5 doe je
per opleiding; reken op een half uur per opleiding als de bestanden kloppen.


## 1. Installeren en uitproberen

De tool gebruikt [uv](https://docs.astral.sh/uv/), dat zelf de juiste
Python-versie en pakketten ophaalt. Staat uv nog niet op je computer:

```powershell
# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Open daarna een **nieuwe** terminal, zodat `uv` gevonden wordt. Haal dan de tool
op en start hem:

```bash
git clone https://github.com/cedanl/selectie-evaluatietool.git
cd selectie-evaluatietool
uv run python app.py
```

Geen Git? Download de
[ZIP](https://github.com/cedanl/selectie-evaluatietool/archive/refs/heads/master.zip),
pak hem uit en draai `uv run python app.py` in die map.

De eerste start duurt een paar minuten. Zodra je `Running on
http://127.0.0.1:8050` ziet, open je <http://localhost:8050>. Stoppen doe je
met Ctrl + C.

**Eerst uitproberen.** Kies onderaan het uploadscherm bij **Nog geen eigen
data?** een van de twee verzonnen voorbeelden:

- **Demo Leiden 2026**: eenjarige master Farmacie, 140 kandidaten. Uitkomst:
  diploma gehaald.
- **Demo Radboud 2026**: bachelor Psychologie, 200 kandidaten. Uitkomst: in
  jaar 2 nog ingeschreven.

Klik alle tabbladen een keer door. Dan weet je wat je bij je eigen data krijgt.


## 2. 1CHO omzetten met 1cijferho

De ruwe DUO-levering is fixed-width, gecodeerd en staat op BSN. De
[1cijferho-tool](https://github.com/cedanl/1cijferho) van CEDA zet die om naar
een CSV met leesbare kolommen en jouw koppelnummer erbij. Deze tool leest die
uitvoer rechtstreeks.

### 2a. Koppelbestand

Het koppelbestand verbindt het BSN uit 1CHO met het nummer waarmee de
kandidaten in het selectiebestand staan: het **koppelnummer**. Vaak is dat het
studentnummer, maar gebruikt de opleiding een Studielink-aanvraagnummer of een
eigen kandidaatnummer, dan zet je dát nummer erin.

Een CSV met puntkomma's en deze twee kolommen:

```csv
burgerservicenummer;studentnummer
012345678;1234567
234567890;1234568
```

- **Noem de tweede kolom `studentnummer`, ook als er een ander nummer in
  staat.** 1cijferho verwacht die naam, en deze tool zoekt in de uitvoer naar
  een kolom met die naam.
- Gebruik het nummer precies zoals het in het selectiebestand staat.
- Maak de export direct als CSV en **open hem niet in Excel**: Excel haalt de
  voorloopnul van een BSN weg.
- Neem alle studenten uit de periode van de levering op. Dubbele BSN's laten
  1cijferho stoppen.

### 2b. Omzetten

```bash
git clone https://github.com/cedanl/1cijferho.git
cd 1cijferho
uv sync --extra frontend
uv run streamlit run src/main.py
```

Zet de DUO-bestanden **direct** in `data/01-input` (geen submap) en het
koppelbestand in `data/`, bijvoorbeeld `data/koppeling.csv`. Dan in de browser:

1. **Eigen data uploaden** → **Bestanden controleren** → door naar stap 1.
2. **Extraheren starten**, daarna **Validatie starten**.
3. In stap 3 (Turbo Conversie): kies bij **Instelmodus** de optie
   **Evaluatietool Selectie**, vul bij **Pad naar koppelbestand**
   `data/koppeling.csv` in en klik **Start Turbo Convert**.

Zonder browser kan het ook:

```bash
uv run eencijferho pipeline --input data/01-input --output data/02-output --bsn-mapping-file data/koppeling.csv
```

### 2c. Upload het `_enriched.csv`-bestand

Uit `data/02-output` heb je **`EV..._enriched.csv`** nodig (`_decoded.csv` werkt
ook). Het kale `EV....csv` werkt niet: daarin ontbreken vooropleiding en
opleidingsnaam. Parquet- en VAKHAVW-bestanden gebruikt deze tool niet.

Controleer dat er een kolom **`studentnummer`** in staat, met daarin je
koppelnummer. Ontbreekt die, dan is het koppelen mislukt en vindt de tool
straks niemand terug.

Eén bestand voor de hele instelling is prima (tot 4 GB). Bij het inladen kies
je welke opleiding bij de selectie hoort; het BSN wordt niet ingelezen.


## 3. Het selectiebestand

Er is geen vast formaat: de config (stap 4) beschrijft hoe het bestand van de
opleiding in elkaar zit. Wel moet het bestand aan dit voldoen:

- **Alle kandidaten**, ook wie is afgewezen of niet begon. De tool deelt ze in
  als *niet gestart*; ze tellen niet mee in de vergelijking.
- **Eén rij per kandidaat.** Exacte dubbelen telt de tool één keer; dubbelen met
  verschillende scores blokkeren het inladen.
- **Een kolom met het koppelnummer**: het nummer dat je ook in het
  koppelbestand van stap 2a hebt gebruikt. Welke kolom dat is, geef je aan in
  de config; de naam maakt niet uit.
- **Scores als getallen.** Elke kolom mag een eigen schaal hebben.

Extra tabbladen, een titel boven de tabel of opmaak zijn geen probleem. Namen,
e-mailadressen en opmerkingen haal je er liefst uit.

Twee dingen vertekenen de uitkomsten:

- **Een subtotaal naast zijn onderdelen** telt dezelfde informatie dubbel. Neem
  het subtotaal of de onderdelen mee, niet allebei.
- **Twee versies van dezelfde score** (percentage goed en aantal goed). Kies er
  één.

Voorbeelden staan in de [data-handleiding](docs/data-handleiding.md).


## 4. De config

De config is een klein Excel-bestand dat de tool vertelt welk tabblad en welke
headerrij hij moet lezen, welke kolom het koppelnummer is, en welke kolommen
scores zijn. Je maakt hem één keer per opleiding en hergebruikt hem volgend
jaar.

**Met de wizard (aanbevolen)**

1. Upload in het uploadscherm het selectiebestand (eerste vak).
2. Klik **Config automatisch genereren**.
3. Controleer bovenin: tabblad, headerrij, opleiding, instelling,
   **selectiejaar** (het jaar waarin het cohort begon) en de ID-kolom (de
   kolom met het koppelnummer).
4. Controleer de kolommentabel. **Het vinkje bepaalt welke kolommen als score
   meetellen**; dit is de belangrijkste keuze. De wizard vinkt scorekolommen
   aan en laat ID's, tekst, datums en herkende subtotalen uit. Geef elk
   aangevinkt item een eigen, leesbare naam; die komt in grafieken en het
   rapport. Instrument groepeert items (bijv. *Gesprek*); criterium en schaal
   zijn optioneel.
5. **Bevestig config**, daarna **Download als Excel**. Bewaar dat bestand bij
   het selectiebestand. Volgend jaar upload je het in het tweede vak.

Meldingen over mogelijk dubbele informatie of subtotalen zijn geen fouten, maar
punten om zelf te beoordelen.

**Handmatig.** Vul [`docs/config_template.xlsx`](docs/config_template.xlsx) in;
het tabblad *uitleg* beschrijft elk veld. Kolomnamen moeten letterlijk
overeenkomen met het selectiebestand, inclusief hoofdletters en spaties.


## 5. Inladen en analyseren

1. Upload de drie bestanden: selectiedata, config en het `_enriched.csv` uit
   stap 2.
2. De tool controleert alles: groen is in orde, geel is een waarschuwing, rood
   moet eerst opgelost worden (zie [Problemen oplossen](#problemen-oplossen)).
3. Bevat het 1CHO-bestand meerdere opleidingen, kies dan welke bij deze selectie
   hoort.
4. Je ziet bijvoorbeeld *70 van 200 kandidaten gekoppeld*. Dat is normaal: de
   rest is afgewezen of niet begonnen.
5. Klik **Open dashboard**.

| Tabblad | Wat je ziet |
|---|---|
| **Introductie** | Wat de tool doet en hoe je de tabbladen leest |
| **Wat valt op** | Automatische samenvatting van de opvallendste bevindingen, met vervolgstappen |
| **Selectiescores** | Boxplots per onderdeel voor wie wel en niet doorging, ook naar geslacht of vooropleiding |
| **Demografie** | Per achtergrondkenmerk het aandeel dat doorging |
| **Verschiltoets** | Per onderdeel: Mann-Whitney met effectgrootte en BH-gecorrigeerde p, plus retentie per scoregroep |
| **Correlatie** | Welke onderdelen grotendeels hetzelfde meten |
| **Regressie** | Logistische regressie op gestandaardiseerde scores, per item en gezamenlijk |

**Download rapport (PDF)** zet alles in één document (duurt ongeveer een halve
minuut). Klik na afloop op **Nieuw bestand laden**: dan wordt het geüploade
1CHO-bestand meteen verwijderd, in plaats van na 24 uur.


## De uitkomsten lezen

**De uitkomst is retentie, niet studiesucces.** Doorgegaan betekent: het jaar na
de start nog ingeschreven bij deze opleiding. Wie het eerste jaar overdoet telt
als doorgegaan, wie overstapt als niet doorgegaan. Bij een eenjarige master is
de uitkomst het diploma in het startjaar.

| Groep | Betekenis |
|---|---|
| **Niet gestart** | Niet in 1CHO bij deze opleiding: afgewezen, of toegelaten maar niet begonnen. Zit niet in de vergelijking. |
| **Gestart, niet naar jaar 2** | Begonnen, het jaar daarna niet meer ingeschreven, geen diploma |
| **Doorgestroomd naar jaar 2** | Het jaar na de start nog ingeschreven |
| **Gestart, diploma gehaald** | Eenjarige master: diploma in het startjaar |

**Kanttekeningen**

- **Kleine aantallen.** Met 50 tot 150 gestarte studenten zie je alleen flinke
  verschillen. *Wat valt op* noemt het kleinste effect dat je kon aantonen.
- **Niet significant is niet "werkt niet".** Alleen toegelaten studenten hebben
  een uitkomst (range restriction), dus elk verband lijkt zwakker dan het in de
  hele kandidatengroep is. Schrap geen onderdeel op basis van één nulresultaat.
- **Meervoudig toetsen.** Per tabel is de p-waarde gecorrigeerd met
  Benjamini-Hochberg; sterren en conclusies gebruiken de gecorrigeerde p.
- **De regressie is verkennend.** Bij te weinig events per predictor kiest de
  tool vooraf items op hun univariate p-waarde; de p-waarden van het gezamenlijke
  model zijn dan te optimistisch. De tool meldt dat.
- **Eén cohort is een momentopname.** Herhaal met het volgende cohort voordat je
  de procedure aanpast.
- **Achtergrond** (geslacht, vooropleiding) komt uit 1CHO en is alleen bekend
  voor wie begon. Of de selectie bepaalde groepen vaker afwijst, kan de tool
  niet zien.
- Groepen kleiner dan vijf worden getoond als `< 5`.


## Problemen oplossen

| Melding | Oorzaak | Oplossing |
|---|---|---|
| **Geen overlap tussen selectiedata en 1CHO-data** | De koppelnummers komen niet overeen | Staat er een kolom `studentnummer` in het 1CHO-bestand? Zo niet, draai 1cijferho opnieuw met koppelbestand. Zo wel: bevat het koppelbestand hetzelfde soort nummer als de ID-kolom in de config (studentnummer vs. aanvraagnummer)? Vergelijk een paar nummers uit beide bestanden (prefix, voorloopnullen). |
| **Ontbrekende achtergrondkolommen in 1CHO** | Het kale `EV....csv` is geüpload | Gebruik `EV..._enriched.csv` |
| **Ontbrekende kolommen in 1CHO** | Geen 1cijferho-uitvoer, of het bestand is in Excel bewerkt | Upload het `_enriched.csv` zoals 1cijferho het maakte |
| **Blad / ID-kolom / kolom … niet gevonden** | Tikfout, verkeerd tabblad of verkeerde headerrij | Laat de wizard de config opnieuw maken |
| **… komen bij meer dan één kolom voor** | Twee aangevinkte kolommen met dezelfde itemnaam | Geef elk item een eigen naam |
| **… staan meerdere keren in de selectiedata** | Dubbele kandidaat met verschillende scores | Laat de opleiding uitzoeken welke rij klopt |
| Bijna iedereen **Gestart, niet naar jaar 2** | De levering bevat het jaar na de start nog niet | Gebruik een recentere levering |
| `uv` wordt niet herkend | Terminal was open tijdens de installatie | Open een nieuwe terminal |
| **port 8050 in use** | De tool draait al | Gebruik dat venster, of stop het eerst |

Kom je er niet uit, maak dan een
[issue](https://github.com/cedanl/selectie-evaluatietool/issues) aan met een
schermafdruk van de melding. Stuur nooit echte gegevens mee.

**Volgend jaar:** haal de nieuwste versies op (`git pull` in beide mappen),
zet de nieuwe levering om, hergebruik de config en pas alleen `jaar` aan.
Een patroon dat twee jaar terugkomt, is een steviger basis dan één jaar.


## Meer lezen

- [Data-handleiding](docs/data-handleiding.md): de bestanden in detail
- [Privacy-handleiding](docs/privacy-handleiding.md): wat de tool met gegevens
  doet, met een checklist voor je FG
- [1cijferho documentatie](https://cedanl.github.io/1cijferho/)
- Methodologische keuzes en code-opbouw: [CLAUDE.md](CLAUDE.md)

<details>
<summary>Voor ontwikkelaars</summary>

```bash
uv sync
uv run python app.py          # localhost:8050 (DASH_DEBUG=1 voor de debugger)
uv run pytest -q
uv run ruff format . && uv run ruff check --fix .
```
</details>

---

<div align="center">
  <sub>Ontwikkeld door <a href="https://github.com/cedanl">CEDA NL</a> · MIT-licentie</sub>
</div>
