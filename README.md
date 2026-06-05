# evaluatietool-voorbeeld

Evaluatietool die selectiedata van opleidingen koppelt aan 1CHO-data om
studiesucces in kaart te brengen. Werkt met elk selectiebestand, zolang er
een configuratiebestand bij zit dat beschrijft welke kolommen meegenomen
moeten worden.

Getest met vier bestanden van twee opleidingen:
- Farmacie LUMC 2025 (master, 60 kolommen, gesprekken + diploma)
- Farmacie LUMC 2026 (master, 97 kolommen, digitale toetsen)
- Psychologie Leiden 2022-2023 (bachelor, 9 kolommen, geaggregeerde scores)
- Psychologie Leiden 2026-2027 (bachelor, 46 kolommen, vakscores + matching)


## Gebruik

```bash
uv sync
uv run python app.py
```

De app draait op http://localhost:8050 en toont een uploadscherm. Upload drie
bestanden: het selectiebestand, het configuratiebestand en de 1CHO-data. Of
kies een van de demobestanden om het dashboard te verkennen.


## Drie groepen

**Niet gestart** -- Kandidaat staat niet in 1CHO. Niet toegelaten, of wel
geselecteerd maar nooit gestart.

**Gestart, niet naar jaar 2** -- Student staat in 1CHO voor jaar 1 maar heeft
geen jaar-2 rij. Uitval of overstap na het eerste jaar.

**Doorgestroomd naar jaar 2** -- Student heeft zowel een jaar-1 als een jaar-2
rij in 1CHO.


## Dashboard

Vier tabbladen:

1. **Selectiescores** -- Boxplots per item met de drie groepen, filters op
   instrument/criterium/cohort/geslacht/vooropleiding, tabel met gemiddelden
   en SD per groep.

2. **Samenhang** -- Correlatiematrix tussen items (heatmap), logistische
   regressie met doorstroom als uitkomst (coefficient, odds ratio, p-waarde,
   pseudo R-kwadraat).

3. **Demografisch** -- Verdeling per cohort (gestapeld staafdiagram), geslacht,
   herkomst en vooropleiding per groep. Data uit 1CHO.

4. **VO-cijfer** -- Scatterplot en Pearson r per item vs. het gemiddelde
   VO-eindcijfer. Lage correlatie = het item meet iets anders dan
   schoolprestaties.


## Configuratiebestand

Het configuratiebestand beschrijft welke kolommen uit het selectiebestand
meegenomen worden in de analyse. Er zijn twee manieren om er een te maken:

### Config wizard (aanbevolen)

Klik in het uploadscherm op "Of: config automatisch genereren". De wizard
leest het selectiebestand en detecteert automatisch:

- Welk blad en welke headerrij gebruikt moet worden
- De ID-kolom (studentnummer) en totaalscorekolom
- Welke kolommen scorekolommen zijn (filtert admin-, datum- en tekstkolommen)
- Instrument-groepering op basis van kolomnaam-prefixen
- Score-type op basis van kolomnaam en waardebereik

Controleer het resultaat in de bewerkbare tabel, pas instrumentnamen, items
en criteria aan waar nodig, en klik "Bevestig config". De config kan daarna
als Excel gedownload worden om later opnieuw te uploaden.

### Handmatig

Een configuratie-Excel heeft twee tabbladen:

**Instellingen**: welke kolom is het studentnummer, op welke rij staan de
kolomnamen, welke kolom is de totaalscore.

**Kolommen**: per kolom die meegenomen moet worden een rij met de originele
kolomnaam, een instrumentnaam, een itemnaam, een criterium (optioneel), en
een score-type.

Er is een leeg templatebestand (`config_template.xlsx`) met toelichtingen in
elke cel.


## Een nieuwe opleiding toevoegen

1. Upload het selectiebestand en gebruik de config wizard om een config te
   genereren, of maak er handmatig een op basis van `config_template.xlsx`.
2. Maak 1CHO-data aan met kolommen: `studentnummer`, `selectiejaar`, `groep`
   (en optioneel `geslacht`, `herkomst`, `hoogste_vooropleiding`,
   `gem_eindcijfer_vo`).
3. Upload de drie bestanden in het dashboard.


## Projectstructuur

```
evaluatietool-voorbeeld/
  app.py                          Dash dashboard
  config_wizard.py                Config wizard: autodetectie en UI
  transformatie.py                Config inlezen, valideren, breed->lang omzetten
  assets/                         Statische bestanden (CSS, logo)
  data/
    demo/                         Demodata per opleiding (selectiedata + config + 1cho)
  scripts/
    maak_data.py                  Genereert demodata voor alle opleidingen
    maak_template.py              Genereert config_template.xlsx
    update_configs.py             Genereert config-bestanden per opleiding
```


## Demodata genereren

```bash
uv run python scripts/maak_data.py
```

Dit kopieert selectiedata en configs naar `data/demo/` subdirectories en
genereert synthetische 1CHO-data voor elke opleiding. De demodata is
beschikbaar in het uploadscherm.
