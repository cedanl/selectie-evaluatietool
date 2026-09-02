<div align="center">
  <h1>Selectie Evaluatietool</h1>

  <p>Onderzoek of je selectieprocedure studiesucces voorspelt</p>

  <p>
    <a href="#"><img src="https://custom-icon-badges.demolab.com/badge/Windows-0078D6?logo=windows11&logoColor=white" alt="Windows"></a>
    <a href="#"><img src="https://img.shields.io/badge/macOS-000000?logo=apple&logoColor=F0F0F0" alt="macOS"></a>
    <a href="#"><img src="https://img.shields.io/badge/Linux-FCC624?logo=linux&logoColor=black" alt="Linux"></a>
    <img src="https://badgen.net/github/last-commit/cedanl/selectie-evaluatietool" alt="Laatste commit">
    <img src="https://badgen.net/github/contributors/cedanl/selectie-evaluatietool" alt="Bijdragers">
    <img src="https://img.shields.io/github/license/cedanl/selectie-evaluatietool" alt="Licentie">
  </p>
</div>

---

Veel opleidingen selecteren kandidaten via een test, gesprek of vragenlijst. Maar **werkt zo'n selectie eigenlijk?** Haalden de studenten die hoog scoorden het ook echt beter?

Deze tool geeft antwoord. Upload je selectiescores en 1CHO-studiedata, en het dashboard legt ze naast elkaar: grafieken, significantietoetsen, correlaties en een regressiemodel dat laat zien welke onderdelen van de selectie iets voorspellen.


## Inhoud

- [Aan de slag](#aan-de-slag)
- [Benodigde bestanden](#benodigde-bestanden)
- [Het configuratiebestand](#het-configuratiebestand)
- [Dashboard](#dashboard)
- [De vier groepen](#de-vier-groepen)
- [Voorbeelddata](#voorbeelddata)


## Aan de slag

Je hebt [Python 3.11+](https://www.python.org/downloads/) en [uv](https://docs.astral.sh/uv/getting-started/installation/) nodig.

```bash
git clone https://github.com/cedanl/selectie-evaluatietool.git
cd selectie-evaluatietool
uv sync
uv run python app.py
```

Open vervolgens [http://localhost:8050](http://localhost:8050) in je browser.

Heb je nog geen eigen data? Kies in het uploadscherm een voorbeeldopleiding en klik op **Laden** om direct te zien hoe het dashboard werkt.


## Benodigde bestanden

Upload drie bestanden om het dashboard te openen:

| Bestand | Formaat | Wat het is |
|---|---|---|
| Selectiedata | `.xlsx` | Scores die kandidaten behaalden bij de selectie |
| Configuratiebestand | `.xlsx` | Vertelt de tool welke kolommen scores zijn en hoe ze heten |
| 1CHO-data | `.csv` (puntkomma) | Inschrijfgegevens per student: wie is gestart, wie doorgestroomd |

De 1CHO-data heeft minimaal drie kolommen nodig: `persoonsgebonden_nummer`, `inschrijvingsjaar` en `eerste_jaar_aan_deze_opleiding_instelling`. Voor de demografietabbladen voeg je ook `geslacht` en `hoogste_vooropleiding_omschrijving_vooropleiding` toe. Heb je een eenjarige opleiding (master) waarbij het diploma het doel is in plaats van doorstroom naar jaar 2, voeg dan ook `diploma_behaald` toe.

Meer over de verwachte formats staat in de [data-handleiding](docs/data-handleiding.md).


## Het configuratiebestand

Het configuratiebestand koppelt de kolomnamen uit je selectie-Excel aan instrumenten, items en een scorebereik. Er zijn twee manieren om er een te maken.

### Automatisch (aanbevolen)

Klik op **Config automatisch genereren** in het uploadscherm. De wizard bekijkt je selectiebestand en stelt zelf voor:

- op welk tabblad de data staat en op welke rij de kolomnamen beginnen
- welke kolom het studentnummer bevat
- welke kolommen scores zijn, en wat hun bereik is
- hoe items bij elkaar horen per instrument

Je krijgt een tabel te zien die je nog kunt aanpassen. Klik op **Bevestig config** als alles klopt. Je kunt het resultaat ook downloaden als Excel — handig voor de volgende keer.

### Handmatig

Open `docs/config_template.xlsx`. Het heeft twee tabbladen:

- **Instellingen** — studentnummerkolom, tabbladnaam, headerrij en eventueel een totaalscorekolom
- **Kolommen** — één rij per kolom; zet scorekolommen op `WAAR` en de rest op `ONWAAR`, en vul per scorekolom instrument, item, criterium en schaal in

Elke cel bevat een toelichting.


## Dashboard

Het dashboard opent op een **Introductie**-tab met context en een uitleg per tabblad. Daarna volgen zes inhoudelijke tabbladen:

| Tabblad | Wat je ziet |
|---|---|
| **Wat valt op** | Automatisch gegenereerde samenvatting van de opvallendste bevindingen, rechtstreeks uit de berekeningen |
| **Selectiescores** | Boxplots per item per groep; deel studenten op naar doorstroom of achtergrondkenmerk (geslacht, vooropleiding) |
| **Demografie** | Per achtergrondkenmerk: welk aandeel van elke groep stroomde door naar jaar 2 |
| **Verschiltoets** | Per item: is het verschil tussen groepen significant of toeval? Met effectgrootte en p-waarde |
| **Correlatie** | Kleurenkaart van de samenhang tussen items — handig om te zien welke items hetzelfde meten |
| **Regressie** | Welke items voorspellen studiesucces het sterkst, apart en gezamenlijk |

Het dashboard genereert ook een **PDF-rapport** met alle analyses. Klik op de downloadknop rechtsbovenin.


## De vier groepen

De tool verdeelt alle kandidaten in vier groepen op basis van hun studiepad:

| Groep | Betekenis |
|---|---|
| **Niet gestart** | Kandidaat staat niet in de 1CHO-data: niet toegelaten, of niet ingeschreven |
| **Gestart, niet naar jaar 2** | Gestart maar na jaar 1 gestopt of overgestapt |
| **Doorgestroomd naar jaar 2** | Jaar 1 afgerond en doorgegaan naar jaar 2 |
| **Gestart, diploma gehaald** | Diploma behaald zonder jaar 2 — voor eenjarige opleidingen zoals een master |

Bij meerjarige opleidingen draait de analyse om doorstroom naar jaar 2. Bij eenjarige opleidingen om het diploma. De tool behandelt beide als "het is goed gegaan".


## Voorbeelddata

Er zitten twee fictieve datasets in de repository:

- **Farmacie master** (Universiteit Westerveld, 140 kandidaten) — eenjarige opleiding, uitkomst is diploma
- **Psychologie bachelor** (Hogeschool Zandstad, 200 kandidaten) — meerjarige opleiding, uitkomst is doorstroom naar jaar 2

Kies een van beide in het uploadscherm om het dashboard zonder eigen data te verkennen.

---

<div align="center">
  <sub>Ontwikkeld door <a href="https://github.com/cedanl">CEDA NL</a> · <a href="docs/data-handleiding.md">Data-handleiding</a> · MIT-licentie</sub>
</div>
