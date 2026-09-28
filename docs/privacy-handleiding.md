# Privacy-handleiding

Deze tool koppelt selectiegegevens aan inschrijvingsgegevens uit 1CHO. Dat
zijn persoonsgegevens, en je gebruikt ze voor een ander doel dan waarvoor ze
zijn verzameld: de selectiegegevens zijn verzameld om kandidaten toe te laten,
niet om de selectie achteraf te evalueren. Deze handleiding helpt je het gesprek
te voeren met je privacy officer of functionaris gegevensbescherming (FG).

> **Dit is geen juridisch advies.** De instelling is verantwoordelijk voor de
> verwerking en beslist zelf, samen met de FG. Deze notitie beschrijft wat de
> tool doet en welke vragen je vooraf beantwoord wilt hebben.


## Wat de tool met de gegevens doet

- **Alles blijft lokaal.** De tool draait op je eigen computer
  (`localhost:8050`). Er gaat geen data naar internet, naar CEDA of naar een
  andere partij. De tool haalt geen gegevens op en stuurt er geen weg.
- **Selectiedata en config** worden in het geheugen van de app ingelezen en
  niet naar schijf geschreven.
- **Het 1CHO-bestand** wordt, omdat het groot kan zijn, tijdelijk op schijf
  gezet in de tijdelijke map van het besturingssysteem
  (`selectie-evaluatietool-uploads`). Het wordt verwijderd zodra je op
  **Nieuw bestand laden** klikt. Sluit je de app zonder dat te doen, dan ruimt
  de tool bestanden ouder dan 24 uur op bij de volgende start.
- **Alleen de benodigde kolommen.** Uit 1CHO leest de tool alleen de kolommen
  die hij gebruikt (studentnummer, inschrijvingsjaren, opleiding, geslacht,
  vooropleiding, diploma). Andere kolommen worden niet ingelezen.
- **Uitkomsten zijn geaggregeerd.** Dashboard en PDF-rapport tonen groepen,
  geen individuele studenten. Aantallen onder de 5 worden afgeschermd (als
  `< 5`), zodat een student in een kleine groep niet herleidbaar is.
- **Het PDF-rapport** sla je zelf op. Vanaf dat moment valt het onder de
  regels van je instelling voor het delen en bewaren van documenten.


## Welke gegevens heb je nodig, en welke niet

Lever niet meer aan dan nodig is (dataminimalisatie).

| Nodig | Niet nodig, haal eruit |
|---|---|
| Studentnummer (om te koppelen) | Naam, e-mailadres, adres, telefoonnummer |
| Selectiescores per onderdeel | Geboortedatum, BSN |
| Inschrijvingsjaren uit 1CHO | Vrije-tekstvelden en opmerkingen van beoordelaars |
| Geslacht en vooropleiding (voor de achtergrondanalyse) | Andere 1CHO-kolommen |

Staan er namen of e-mailadressen in je selectiebestand, verwijder die kolommen
dan voor je het bestand in de tool laadt, of vink ze in de config niet aan. Een
kolom die niet is aangevinkt wordt niet geanalyseerd, maar wordt wel ingelezen;
eruit halen is dus veiliger.


## Checklist voor het gesprek met de FG

Neem deze vragen door voordat je de tool met echte data gebruikt.

1. **Doel.** Wat is het doel van de evaluatie? Bijvoorbeeld: nagaan of de
   selectieprocedure doet wat ze moet doen, als onderdeel van kwaliteitszorg.
   Leg het doel vast.
2. **Grondslag.** Op welke grondslag verwerkt de instelling deze gegevens voor
   dit doel? Bij onderwijsinstellingen is dat meestal de wettelijke taak
   (algemeen belang), maar de FG stelt dat vast.
3. **Verenigbaar doel.** De gegevens zijn verzameld voor toelating. Is
   evaluatie van de selectie daarmee verenigbaar (AVG art. 6 lid 4)? Denk aan
   het verband tussen beide doelen, de verwachtingen van kandidaten, en de
   waarborgen hieronder.
4. **Informeren.** Staat in de privacyverklaring voor kandidaten dat
   selectiegegevens ook worden gebruikt om de procedure te evalueren? Zo niet:
   aanvullen voor volgende cohorten.
5. **1CHO-voorwaarden.** Onder welke voorwaarden ontvangt je instelling 1CHO
   van DUO, en valt dit gebruik daaronder?
6. **DPIA.** Is een gegevensbeschermingseffectbeoordeling nodig (AVG art. 35)?
   Het koppelen van bronnen en het gebruik van gegevens over studievoortgang
   kunnen daar aanleiding toe geven. Misschien is er al een DPIA voor
   onderwijsanalyses waar dit onder valt.
7. **Wie mag erbij.** Wie werkt met de ruwe bestanden, en op welke computer?
   Gebruik een beheerde werkplek, geen privécomputer.
8. **Bewaartermijn.** Hoe lang bewaar je de gekoppelde bestanden en het
   rapport? De tool bewaart zelf niets langer dan nodig, maar de bronbestanden
   die je hebt klaargezet wel.
9. **Delen van het rapport.** Met wie deel je het PDF-rapport (opleidings-
   commissie, examencommissie, directie)? Het rapport bevat geen individuele
   gegevens en schermt kleine aantallen af, maar een opleiding met weinig
   studenten blijft gevoelig.
10. **Achtergrondkenmerken.** Geslacht en vooropleiding gebruikt de tool om
    te controleren of de selectie onbedoeld onderscheid maakt. Leg vast dat
    deze analyse daarvoor bedoeld is en niet voor beslissingen over
    individuele kandidaten.


## Wat de tool niet doet

- De tool neemt geen beslissingen over kandidaten en is daar niet voor
  bedoeld. Gebruik de uitkomsten niet om individuele kandidaten te beoordelen.
- De tool pseudonimiseert niet. Wil je dat, vervang de studentnummers dan in
  beide bestanden op dezelfde manier voordat je ze inlaadt; de koppeling werkt
  dan nog steeds.
