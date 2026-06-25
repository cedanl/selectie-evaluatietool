# Evaluatietool Selectie

Veel opleidingen laten niet zomaar iedereen toe. Ze laten kandidaten eerst
een soort toelatingsronde doen: een test, een gesprek, een vragenlijst. Op
basis daarvan kiezen ze wie er mag beginnen. Dat heet selectie.

De grote vraag is: werkt zo'n selectie eigenlijk? Doen de mensen die hoog
scoorden bij de selectie het later ook echt beter in de studie? Of maakt
het weinig uit?

Deze tool helpt je dat uitzoeken. Je geeft hem twee dingen:

1. hoe kandidaten scoorden bij de selectie, en
2. hoe het daarna met ze ging in de studie.

De tool legt die twee naast elkaar en maakt er grafieken en tabellen van.
Zo kun je zien of een hoge selectiescore samenhangt met succes in de studie.


## Hoe werkt het?

Je uploadt drie bestanden:

1. **Selectiedata** - een Excel-bestand met de scores die de kandidaten
   bij de selectie haalden.
2. **Configuratiebestand** - een klein hulpbestandje dat aan de tool uitlegt
   welke kolommen uit het selectiebestand belangrijk zijn. Dit kun je de tool
   ook automatisch laten maken, zie verderop.
3. **1CHO-data** - de gegevens over hoe het de studenten daarna verging: wie
   is begonnen, wie is gestopt, wie is doorgegaan naar het tweede jaar.

De tool koppelt die drie bestanden aan elkaar (welke score hoort bij welke
student) en maakt er overzichten van.

Welke gegevens je precies nodig hebt, in welk formaat, en waar je ze vandaan
haalt, staat in de [data-handleiding](docs/data-handleiding.md).


## Opstarten

Je hebt twee programma's nodig:
[Python](https://www.python.org/downloads/) en
[uv](https://docs.astral.sh/uv/getting-started/installation/). Volg de
links om ze te installeren.

Open daarna een terminal in deze map en typ:

```bash
uv sync
uv run python app.py
```

De eerste regel haalt eenmalig alles op wat de tool nodig heeft. De tweede
regel start de tool. Ga vervolgens in je browser naar
http://localhost:8050. Je ziet dan een scherm waar je je bestanden kunt
uploaden, of voorbeelddata kunt laden om mee te oefenen.


## Eerst even rondkijken met voorbeelddata

Heb je nog geen eigen data, of wil je gewoon zien hoe het werkt? Kies dan
in het uploadscherm een van de voorbeelden uit het uitklapmenu en klik op
"Laden". Er zitten twee voorbeeldopleidingen in. De cijfers daarin zijn
verzonnen, dus je kunt er vrij mee experimenteren.


## Het configuratiebestand

Het configuratiebestand is een klein hulpbestandje. Het vertelt de tool
welke kolommen uit je selectie-Excel scores zijn, en hoe die in het
dashboard moeten heten. Zonder dit bestand weet de tool niet welke kolom
wat betekent. Er zijn twee manieren om er een te maken.

### Automatisch (makkelijkst)

Klik in het uploadscherm op "Of: config automatisch genereren". De tool
bekijkt dan zelf je selectiebestand en probeert uit te zoeken:

- op welk tabblad de gegevens staan en op welke regel de kolomnamen staan;
- welke kolom het studentnummer bevat;
- welke kolommen scores zijn (kolommen met tekst of datums worden
  overgeslagen);
- hoe de scores bij elkaar horen.

Daarna krijg je een tabel te zien die je nog helemaal mag aanpassen.
Klopt alles? Klik dan op "Bevestig config". Je kunt het bestand ook
downloaden als Excel, zodat je het de volgende keer gewoon kunt uploaden
zonder opnieuw te hoeven instellen.

### Handmatig

Open `docs/config_template.xlsx`. Dat bestand heeft twee tabbladen die je
invult:

- **Instellingen**: welke kolom het studentnummer is, op welke regel de
  kolomnamen staan, en welke kolom de totaalscore bevat.
- **Kolommen**: voor elke scorekolom een regel met de kolomnaam, een
  instrumentnaam, een itemnaam, eventueel een criterium en de schaal
  (het bereik van de scores, bijvoorbeeld 1-7 of 0-100).

In elke cel van het template staat een toelichting die uitlegt wat je
moet invullen.


## Wat zie je in het dashboard?

Het dashboard opent op een Introductie-tab met uitleg en context, gevolgd
door zes inhoudelijke tabbladen. Hieronder staat per inhoudelijk tabblad
wat je ziet en hoe je het leest.

### Wat valt op

Dit is de samenvatting. De tool zet hier automatisch de opvallendste
bevindingen op een rij, rechtstreeks uit de berekeningen op jouw data. Er
wordt niets bijbedacht: elke regel volgt uit een gemeten verschil of een
p-waarde. Handig om in een oogopslag te zien wat er speelt voordat je de
losse tabbladen induikt.

### Selectiescores

Hier zie je per item van de selectie hoe de verschillende groepen
studenten scoorden. Dat gebeurt met een boxplot. Een boxplot is een
manier om in een oogopslag te laten zien hoe een groep scoorde: waar de
meeste mensen zitten, en hoe ver de uitschieters uit elkaar liggen.

Bovenaan kies je waarop je de studenten wilt opdelen: of ze met de
opleiding zijn gestart, of ze doorstroomden naar jaar 2, of een
achtergrondkenmerk zoals geslacht of vooropleiding.

De vraag die je jezelf stelt: scoorden de studenten die het later goed
deden, ook hoger bij de selectie? Als de groep doorstromers duidelijk
hoger ligt dan de groep uitvallers, dan zegt dat item van de
selectie kennelijk iets zinnigs.

### Demografie

Hier zie je hoe achtergrondkenmerken (geslacht, vooropleiding) samenhangen
met de studieuitkomst. Per kenmerk laat een tabel zien welk aandeel van
elke groep doorstroomde naar jaar 2. Handig om te checken of de selectie
voor de ene groep anders uitpakt dan voor de andere.

### Verschiltoets

Dit tabblad toetst per item of de scores echt verschillen tussen
groepen, of dat het toeval kan zijn. Je kiest of je kijkt naar doorstroom
naar jaar 2 (voorspelt het item studiesucces?) of naar een
achtergrondkenmerk (maakt het item onbedoeld onderscheid?).

Per item zie je hoe groot het verschil is, hoe sterk dat effect is, en
of het significant is. Een ster betekent dat het verschil waarschijnlijk
niet op toeval berust.

### Correlatie

"Correlatie" betekent: hangen twee dingen met elkaar samen, gaan ze samen
op en neer? Dit tabblad laat met een kleurenkaart zien welke
selectie-items op elkaar lijken. Als twee items sterk
samenhangen, meten ze waarschijnlijk bijna hetzelfde, en hoef je ze
misschien niet allebei af te nemen. Hangen ze juist weinig samen, dan
vullen ze elkaar aan.

### Regressie

Dit tabblad laat zien welke items van de selectie het sterkst
voorspellen of een student de opleiding succesvol vervolgt: doorstroom naar
het tweede jaar, of een diploma bij eenjarige opleidingen. Bovenaan staan
de items die er het meest toe lijken te doen.

Let op: dit werkt het best bij grote groepen. Bij kleine groepen (denk aan
enkele tientallen studenten) zijn de uitkomsten wankel en moet je ze zien
als een hint, niet als een hard bewijs.


## De groepen

De tool verdeelt de kandidaten in groepen, op basis van hoe het ze na de
selectie verging:

- **Niet gestart** - de kandidaat komt niet voor in de studiedata. Die is
  dus niet toegelaten, of wel toegelaten maar nooit begonnen.
- **Gestart, niet naar jaar 2** - de student is wel begonnen, maar is na
  het eerste jaar gestopt of overgestapt naar iets anders.
- **Doorgestroomd naar jaar 2** - de student heeft het eerste jaar afgerond
  en is doorgegaan naar het tweede jaar.
- **Gestart, diploma gehaald** - de student haalde in hetzelfde jaar een
  diploma zonder een tweede jaar te doen. Dit geldt voor opleidingen die
  maar een jaar duren (zoals een master), waar het diploma het doel is en
  niet doorstromen naar jaar 2.

Welke groepen je tegenkomt hangt af van de opleiding. Bij een meerjarige
opleiding draait het om doorstromen naar het tweede jaar. Bij een
eenjarige opleiding draait het om het halen van het diploma. De tool
behandelt beide als "het is goed gegaan", zodat de analyses voor allebei
de soorten opleidingen kloppen.


## Een nieuwe opleiding toevoegen

1. Upload je selectiebestand en laat de tool er automatisch een
   configuratiebestand bij maken (of maak er handmatig een).
2. Maak een 1CHO-bestand met in elk geval deze kolommen:
   `persoonsgebonden_nummer`, `inschrijvingsjaar` en
   `eerste_jaar_aan_deze_opleiding_instelling`. Uit die drie leidt de tool
   zelf af in welke groep een student valt. Je mag er ook nog
   `geslacht`, `hoogste_vooropleiding_omschrijving_vooropleiding` en
   `diploma_behaald` aan toevoegen. Geslacht en vooropleiding gebruikt de
   tool op het tabblad Demografie en in de verschiltoets. Voeg
   `diploma_behaald` toe als het om een eenjarige opleiding gaat waar het
   diploma het doel is in plaats van doorstroom naar jaar 2.
3. Upload alle drie de bestanden in het dashboard.


## Voorbeelddata opnieuw maken (alleen voor ontwikkelaars)

De voorbeelddata in `data/demo/` zit standaard in de repository. Als
ontwikkelaar kun je die opnieuw aanmaken met de scripts in
`scripts/eenmalig/`. Daarvoor heb je de originele bronbestanden nodig,
en die zitten niet in de repository.
