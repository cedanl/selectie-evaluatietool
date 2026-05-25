# Handleiding: data klaarmaken voor de evaluatietool

De evaluatietool werkt met twee bestanden die je samen in het dashboard uploadt:

- `selectiescores.csv` - scores per kandidaat op instrument-, item- en criterium-niveau
- `1cho_data.csv` - studieuitkomsten en achtergrondkenmerken per kandidaat uit 1CHO

De bestanden worden in het dashboard gekoppeld op `studentnummer`. Zorg dat dit veld in beide bestanden overeenkomt.

---

## Wat wordt er verwacht

### Selectiescores

Een rij per kandidaat per instrument per item per criterium. Elke combinatie van kandidaat, instrument, item en criterium is een unieke rij.

Verplichte kolommen:

| Kolom | Type | Beschrijving |
|---|---|---|
| `studentnummer` | integer | Unieke identifier per kandidaat |
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
studentnummer;persoonsgebonden_nummer;selectiejaar;opleiding;instellingscode;instrument;item;criterium;score;selectie_uitkomst
10001;10001.0;2024;B Gezondheidswetenschappen;UNI01;interview;vraag_1;inhoud;7.2;geselecteerd
10001;10001.0;2024;B Gezondheidswetenschappen;UNI01;interview;vraag_1;presentatie;6.8;geselecteerd
10001;10001.0;2024;B Gezondheidswetenschappen;UNI01;motivatiebrief;motivatie;kwaliteit;7.0;geselecteerd
10002;;2024;B Gezondheidswetenschappen;UNI01;interview;vraag_1;inhoud;4.9;niet geselecteerd
```

Kandidaat 10002 heeft geen `persoonsgebonden_nummer` omdat die niet geselecteerd is en dus niet in 1CHO voorkomt.

### Studiesuccesdata

Een rij per kandidaat. Bevat de studieuitkomst en demografische achtergrondkenmerken uit 1CHO. Dit bestand wordt gegenereerd door het koppelscript van je instelling.

Verplichte kolommen:

| Kolom | Type | Beschrijving |
|---|---|---|
| `studentnummer` | integer | Koppelsleutel met selectiescores |
| `selectiejaar` | integer | Jaar van de selectieprocedure |
| `groep` | tekst | `Niet gestart` / `Gestart, niet naar jaar 2` / `Doorgestroomd naar jaar 2` |

Aanbevolen kolommen (voor demografische analyses):

| Kolom | Type | Beschrijving |
|---|---|---|
| `opleiding` | tekst | Naam van de opleiding |
| `instellingscode` | tekst | Instelling-identifier |
| `geslacht` | tekst | Geslacht van de kandidaat |
| `herkomst` | tekst | Herkomst volgens CBS-definitie |
| `hoogste_vooropleiding` | tekst | Hoogste vooropleiding voor het HO |
| `gem_eindcijfer_vo` | getal | Gemiddeld eindexamencijfer VO |
| `instroom_type` | tekst | `direct` / `tussenjaar` / `switcher` |

Scheidingsteken: puntkomma (`;`). Bestandsformaat: CSV.

Voorbeeld:

```
studentnummer;selectiejaar;opleiding;instellingscode;groep;geslacht;herkomst;hoogste_vooropleiding;gem_eindcijfer_vo;instroom_type
10001;2024;B Gezondheidswetenschappen;UNI01;Niet gestart;;;;; 
10003;2024;B Gezondheidswetenschappen;UNI01;Doorgestroomd naar jaar 2;vrouw;Nederland;vwo profiel natuur & gezondheid;7.4;direct
10005;2024;B Gezondheidswetenschappen;UNI01;Gestart, niet naar jaar 2;man;Nederland;vwo profiel cultuur & maatschappij;6.8;direct
```

Kandidaten die niet gestart zijn hebben geen 1CHO-gegevens; die kolommen blijven leeg.

De `studentnummer` in dit bestand moet overeenkomen met de `studentnummer` in het selectiescoresbestand. Het dashboard koppelt de twee bestanden op dit veld.

---

## Hoe je eigen data omzet

### Stap 1 - Controleer je scorebestand

Open je scorebestand en ga na of je de kolommen `instrument`, `item` en `criterium` hebt. Veel instellingen slaan scores op in een breed formaat (een kolom per instrument of per beoordelaar). Dat moet worden omgezet naar lang formaat.

Als je data er zo uitziet:

```
studentnummer;interview_vraag1_inhoud;interview_vraag1_presentatie;motivatiebrief_motivatie
10001;7.2;6.8;7.0
```

Dan moet je dit omzetten naar:

```
studentnummer;instrument;item;criterium;score
10001;interview;vraag_1;inhoud;7.2
10001;interview;vraag_1;presentatie;6.8
10001;motivatiebrief;motivatie;kwaliteit;7.0
```

In Python doe je dat met `pd.melt` of `pd.wide_to_long`. In Excel kun je Power Query gebruiken om kolommen te unpivoten.

### Stap 2 - Voeg verplichte kolommen toe

Zorg dat elk van de tien verplichte kolommen aanwezig is. Vul `persoonsgebonden_nummer` alleen in voor kandidaten die geselecteerd zijn en daadwerkelijk zijn ingeschreven.

### Stap 3 - Sla op als CSV met puntkomma

Gebruik puntkomma als scheidingsteken. In Excel: "Opslaan als" en kies "CSV (gescheiden door lijstscheidingsteken)". Controleer het scheidingsteken in de regionale instellingen van je computer als je komma's krijgt in plaats van puntkomma's.

### Stap 4 - Maak 1cho_data.csv

Voer het koppelscript van je instelling uit. Het script:

1. Leest het EV-bestand van 1CHO voor je opleiding
2. Bepaalt per kandidaat de uitkomstgroep op basis van jaar-1 en jaar-2 inschrijvingen
3. Decodeert de numerieke 1CHO-codes naar leesbare waarden
4. Koppelt op `persoonsgebonden_nummer` en schrijft `1cho_data.csv`

Het resultaat heeft een rij per kandidaat, met `studentnummer` als koppelsleutel naar je selectiescores.

### Stap 5 - Upload beide bestanden in het dashboard

Open de evaluatietool. Upload eerst `selectiescores.csv`, dan `1cho_data.csv` (of andersom). Het dashboard koppelt de bestanden zodra beide geladen zijn. Bij een fout zie je welke kolommen ontbreken.

---

## Veelgemaakte fouten

**Verkeerd scheidingsteken.** Het bestand gebruikt komma's terwijl puntkomma's verwacht worden, of andersom. Controleer dit door het CSV-bestand te openen in een teksteditor.

**Kolom ontbreekt.** Het bestand heeft wel scores maar mist `selectie_uitkomst` of `studentnummer`. Voeg de kolom toe of hernoem de bestaande kolom naar de verwachte naam.

**Breed formaat in plaats van lang formaat.** Een kolom per instrument in plaats van een rij per instrument per item per criterium. Zie stap 1 hierboven voor hoe je dit omzet.

**Kandidaat_id stemt niet overeen tussen de twee bestanden.** De koppeling mislukt als `studentnummer` in selectiescores.csv andere waarden heeft dan in 1cho_data.csv. Controleer dat beide bestanden uit hetzelfde systeem komen en dezelfde nummering gebruiken.

**Meerdere selectiejaren door elkaar.** Als je data van meerdere jaren combineert, zorg dan dat `selectiejaar` voor elke rij correct is ingevuld. Het dashboard groepeert op dit veld.

**Kandidaten zonder selectie_uitkomst.** Zorg dat de kolom geen lege waarden heeft. Gebruik `niet geselecteerd` voor kandidaten die de procedure wel doorliepen maar niet werden geselecteerd.
