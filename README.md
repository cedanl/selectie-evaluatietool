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

Per selectiebestand maakt een analist een configuratiebestand (Excel) met twee
tabbladen:

**Instellingen**: welke kolom is het studentnummer, op welke rij staan de
kolomnamen, welke kolom is de totaalscore.

**Kolommen**: per kolom die meegenomen moet worden een rij met de originele
kolomnaam, een instrumentnaam, een itemnaam, een criterium (optioneel), en
een score-type.

Er is een leeg templatebestand (`config_template.xlsx`) met toelichtingen in
elke cel. De bestaande configs staan in de root:

| Config | Opleiding | Kolommen in config |
|---|---|---|
| `config_FAR_Leiden_2025.xlsx` | Farmacie LUMC 2025 | 11 van 60 |
| `config_FAR_Leiden_2026.xlsx` | Farmacie LUMC 2026 | 12 van 97 |
| `config_Psychologie_2022_2023.xlsx` | Psychologie 2022-2023 | 6 van 9 |
| `config_Psychologie_2026_2027.xlsx` | Psychologie 2026-2027 | 19 van 46 |


## Een nieuwe opleiding toevoegen

1. Open `config_template.xlsx` en vul de twee tabbladen in voor het nieuwe
   selectiebestand.
2. Maak 1CHO-data aan met kolommen: `studentnummer`, `selectiejaar`, `groep`
   (en optioneel `geslacht`, `herkomst`, `hoogste_vooropleiding`,
   `gem_eindcijfer_vo`).
3. Upload de drie bestanden in het dashboard.


## Projectstructuur

```
evaluatietool-voorbeeld/
  app.py                          Dash dashboard
  transformatie.py                Config inlezen, valideren, breed->lang omzetten
  assets/                         Statische bestanden (CSS, logo)
  config_template.xlsx            Leeg configuratiebestand met uitleg
  config_*.xlsx                   Configuratiebestanden per opleiding
  data/
    demo/                         Demodata per opleiding (selectiedata + config + 1cho)
    real/                         Echte selectiebestanden (niet in git)
  scripts/
    maak_data.py                  Genereert demodata voor alle opleidingen
    maak_presentatie.py           Genereert de presentatie (pptx)
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
