# Evaluatietool Selectie

Een dashboard dat laat zien hoe goed een selectieprocedure werkt. Het
vergelijkt de scores die studenten bij de selectie haalden met hoe het
daarna ging in hun studie: zijn ze gestart, zijn ze na jaar 1 gestopt,
zijn ze doorgestroomd naar jaar 2, of hebben ze hun diploma gehaald?


## Hoe werkt het?

Je uploadt drie bestanden:

1. **Selectiedata** - het Excel-bestand met de scores van kandidaten
2. **Configuratiebestand** - beschrijft welke kolommen uit het selectiebestand
   gebruikt moeten worden (kun je automatisch laten genereren, zie onder)
3. **1CHO-data** - studiesuccesgegevens: wie is gestart, wie is doorgestroomd

Het dashboard koppelt deze bestanden aan elkaar en toont grafieken en
tabellen waarmee je kunt beoordelen of de selectie voorspellende waarde had.

Welke data je precies nodig hebt, in welk formaat, en waar je het vandaan
haalt staat in de [data-handleiding](docs/data-handleiding.md).


## Opstarten

Je hebt [Python](https://www.python.org/downloads/) en
[uv](https://docs.astral.sh/uv/getting-started/installation/) nodig.
Open een terminal in deze map en voer uit:

```bash
uv sync
uv run python app.py
```

Ga daarna naar http://localhost:8050 in je browser. Je ziet een
uploadscherm waar je bestanden kunt uploaden of demodata kunt laden.


## Demodata uitproberen

Wil je eerst rondkijken zonder eigen data? Kies in het uploadscherm een
van de demobestanden uit het dropdown-menu en klik "Laden". Er zijn
voorbeelden van twee opleidingen.


## Configuratiebestand maken

Het configuratiebestand vertelt de tool welke kolommen uit je selectie-Excel
gebruikt moeten worden en hoe ze heten in het dashboard. Er zijn twee
manieren om er een te maken:

### Automatisch (aanbevolen)

Klik in het uploadscherm op "Of: config automatisch genereren". De tool
leest dan je selectiebestand en probeert zelf uit te zoeken:

- Welk blad de data bevat en op welke rij de kolomnamen staan
- Welke kolom het studentnummer is
- Welke kolommen scores bevatten (tekst- en datumkolommen worden overgeslagen)
- Hoe de scores gegroepeerd moeten worden

Je krijgt een tabel te zien waar je alles nog kunt aanpassen. Als het
er goed uitziet klik je "Bevestig config". Je kunt de config ook
downloaden als Excel, zodat je hem de volgende keer gewoon kunt uploaden.

### Handmatig

Open `docs/config_template.xlsx` en vul de twee tabbladen in:

- **Instellingen**: welke kolom het studentnummer is, op welke rij de
  kolomnamen staan, en welke kolom de totaalscore bevat.
- **Kolommen**: per scorekolom een rij met de kolomnaam, een instrumentnaam,
  een itemnaam, eventueel een criterium, en het type score.

Elke cel in het template heeft een toelichting die uitlegt wat je moet invullen.


## Wat zie je in het dashboard?

Het dashboard heeft vier tabbladen:

**Selectiescores** - Boxplots die laten zien hoe de groepen scoren
op elk onderdeel van de selectie. Als doorstromers structureel hoger
scoren dan uitvallers, dan heeft dat onderdeel voorspellende waarde.

**Samenhang** - Laat zien hoe de selectie-onderdelen onderling samenhangen
(correlatie) en welke onderdelen het sterkst voorspellen of iemand
doorstroomt (regressie).

**Demografisch** - Verdeling per cohort, geslacht, herkomst en vooropleiding.
Hiermee kun je checken of bepaalde groepen over- of ondervertegenwoordigd
zijn.

**VO-cijfer** - Vergelijkt selectiescores met het gemiddelde eindexamencijfer.
Een lage samenhang betekent dat het selectie-onderdeel iets anders meet
dan schoolprestaties.


## De groepen

Het dashboard deelt kandidaten in op basis van hoe het ze verging na de
selectie:

- **Niet gestart** - de kandidaat komt niet voor in de studiedata. Niet
  toegelaten, of wel geselecteerd maar nooit begonnen.
- **Gestart, niet naar jaar 2** - de student is begonnen maar heeft geen
  tweede jaar. Gestopt of overgestapt na het eerste jaar.
- **Doorgestroomd naar jaar 2** - de student heeft zowel jaar 1 als jaar 2
  afgerond.
- **Gestart, diploma gehaald** - de student haalde in het cohortjaar een
  diploma zonder door te stromen naar jaar 2. Dit is de succesmaat voor
  eenjarige opleidingen (zoals masters), waar succes een diploma is in
  plaats van doorstroom naar jaar 2.

Welke groepen voorkomen hangt af van de opleiding. Bij meerjarige
bacheloropleidingen draait het om doorstroom naar jaar 2; bij eenjarige
masters om het behalen van het diploma. De analyses gebruiken alle gestarte
studenten en behandelen zowel doorstroom als diploma als positieve uitkomst,
zodat ze voor beide soorten opleidingen werken.


## Nieuwe opleiding toevoegen

1. Upload je selectiebestand en gebruik de config wizard om een configuratie
   te genereren (of maak er handmatig een).
2. Maak een 1CHO-bestand met minstens de kolommen `persoonsgebonden_nummer`,
   `inschrijvingsjaar` en `eerste_jaar_aan_deze_opleiding_instelling`. De tool
   leidt hier zelf de groep uit af. Optioneel kun je ook `geslacht`,
   `herkomst`, `hoogste_vooropleiding_omschrijving_vooropleiding`,
   `gem_eindcijfer_vo` en `diploma_behaald` toevoegen. Voeg `diploma_behaald`
   toe als het om een eenjarige opleiding gaat waar succes het diploma is in
   plaats van doorstroom naar jaar 2.
3. Upload alle drie de bestanden in het dashboard.


## Demodata opnieuw genereren (alleen voor ontwikkelaars)

De demodata in `data/demo/` wordt meegeleverd met de repository. Als
ontwikkelaar kun je de data opnieuw genereren met de scripts in
`scripts/eenmalig/`. Dit vereist de originele bronbestanden die niet in
de repository staan.
