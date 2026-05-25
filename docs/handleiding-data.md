# Handleiding: data klaarmaken voor de evaluatietool

De evaluatietool werkt met twee bestanden die je als instelling zelf aanlevert:

- `selectiescores_voorbeeld.csv` - scores op instrument-, item- en criterium-niveau
- `EV_*.csv` - raw 1CHO-uitvoer voor je opleiding

Uit deze twee bestanden wordt `analysedata.csv` gegenereerd, het bestand dat je in het dashboard uploadt.

---

## Wat wordt er verwacht

### Selectiescores

Een rij per kandidaat per instrument per item per criterium. Elke combinatie van kandidaat, instrument, item en criterium is een unieke rij.

Verplichte kolommen:

| Kolom | Type | Beschrijving |
|---|---|---|
| `kandidaat_id` | integer | Unieke identifier per kandidaat |
| `persoonsgebonden_nummer` | float | Koppelsleutel naar 1CHO (leeg als niet geselecteerd) |
| `selectiejaar` | integer | Jaar van de selectieprocedure |
| `opleiding` | tekst | Naam van de opleiding |
| `instellingscode` | tekst | Instelling-identifier |
| `instrument` | tekst | Naam van het selectie-instrument, bijvoorbeeld `interview` |
| `item` | tekst | Onderdeel binnen het instrument, bijvoorbeeld `vraag_1` |
| `criterium` | tekst | Beoordelingscriterium voor dit item, bijvoorbeeld `inhoud` |
| `score` | getal | Score op dit criterium |
| `selectie_uitkomst` | tekst | `geselecteerd` / `reserve` / `niet geselecteerd` |

Scheidingsteken: puntkomma (`;`). Bestandsformaat: CSV.

Voorbeeld van een paar rijen:

```
kandidaat_id;persoonsgebonden_nummer;selectiejaar;opleiding;instellingscode;instrument;item;criterium;score;selectie_uitkomst
10001;10001.0;2024;B Gezondheidswetenschappen;UNI01;interview;vraag_1;inhoud;7.2;geselecteerd
10001;10001.0;2024;B Gezondheidswetenschappen;UNI01;interview;vraag_1;presentatie;6.8;geselecteerd
10001;10001.0;2024;B Gezondheidswetenschappen;UNI01;motivatiebrief;motivatie;kwaliteit;7.0;geselecteerd
10002;;2024;B Gezondheidswetenschappen;UNI01;interview;vraag_1;inhoud;4.9;niet geselecteerd
```

Kandidaat 10002 heeft geen `persoonsgebonden_nummer` omdat die niet geselecteerd is en dus niet in 1CHO voorkomt.

### 1CHO-data

Het raw EV-bestand van 1cijferho voor je opleiding. Dat bestand heeft een naam als `EV_DEMO_selectieopleiding.csv` en bevat een rij per student per inschrijvingsjaar. De koppelsleutel is `persoonsgebonden_nummer`.

---

## Hoe je eigen data omzet

### Stap 1 - Controleer je scorebestand

Open je scorebestand en ga na of je de kolommen `instrument`, `item` en `criterium` hebt. Veel instellingen slaan scores op in een breed formaat (een kolom per instrument of per beoordelaar). Dat moet worden omgezet naar lang formaat.

Als je data er zo uitziet:

```
kandidaat_id;interview_vraag1_inhoud;interview_vraag1_presentatie;motivatiebrief_motivatie
10001;7.2;6.8;7.0
```

Dan moet je dit omzetten naar:

```
kandidaat_id;instrument;item;criterium;score
10001;interview;vraag_1;inhoud;7.2
10001;interview;vraag_1;presentatie;6.8
10001;motivatiebrief;motivatie;kwaliteit;7.0
```

In Python doe je dat met `pd.melt` of `pd.wide_to_long`. In Excel kun je Power Query gebruiken om kolommen te unpivoten.

### Stap 2 - Voeg verplichte kolommen toe

Zorg dat elk van de tien verplichte kolommen aanwezig is. Vul `persoonsgebonden_nummer` alleen in voor kandidaten die geselecteerd zijn en daadwerkelijk zijn ingeschreven.

### Stap 3 - Sla op als CSV met puntkomma

Gebruik puntkomma als scheidingsteken. In Excel: "Opslaan als" en kies "CSV (gescheiden door lijstscheidingsteken)". Controleer het scheidingsteken in de regionale instellingen van je computer als je komma's krijgt in plaats van puntkomma's.

### Stap 4 - Koppel aan 1CHO

Voer de koppelstap uit om `analysedata.csv` te genereren. Daarvoor gebruik je het koppelscript dat bij je instelling beschikbaar is. Het koppelscript:

1. Leest je selectiescores en berekent gemiddelden per instrument
2. Leest het EV-bestand van 1CHO
3. Koppelt op `persoonsgebonden_nummer`
4. Bepaalt de uitkomstgroep (niet gestart / gestart niet naar jaar 2 / doorgestroomd)
5. Schrijft `analysedata.csv`

### Stap 5 - Upload in het dashboard

Open de evaluatietool, klik op "blader" of sleep `analysedata.csv` naar het uploadvak. Bij een fout zie je welke kolommen ontbreken.

---

## Veelgemaakte fouten

**Verkeerd scheidingsteken.** Het bestand gebruikt komma's terwijl puntkomma's verwacht worden, of andersom. Controleer dit door het CSV-bestand te openen in een teksteditor.

**Kolom ontbreekt.** Het bestand heeft wel scores maar mist `selectie_uitkomst` of `kandidaat_id`. Voeg de kolom toe of hernoem de bestaande kolom naar de verwachte naam.

**Breed formaat in plaats van lang formaat.** Een kolom per instrument in plaats van een rij per instrument per item per criterium. Zie stap 1 hierboven voor hoe je dit omzet.

**Persoonsgebonden nummer als integer opgeslagen.** Sommige exporttools ronden het getal af of verwijderen de decimaal, waardoor koppeling mislukt. Zorg dat het nummer overeenkomt met het formaat in het EV-bestand van 1CHO (float, met of zonder decimaal).

**Meerdere selectiejaren door elkaar.** Als je data van meerdere jaren combineert, zorg dan dat `selectiejaar` voor elke rij correct is ingevuld. Het dashboard groepeert op dit veld.

**Kandidaten zonder selectie_uitkomst.** Zorg dat de kolom geen lege waarden heeft. Gebruik `niet geselecteerd` voor kandidaten die de procedure wel doorliepen maar niet werden geselecteerd.
