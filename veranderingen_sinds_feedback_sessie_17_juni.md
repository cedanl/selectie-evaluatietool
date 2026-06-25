# Veranderingen sinds de feedbacksessie van 17 juni

Korte samenvatting van wat er aan de evaluatietool is veranderd na de feedbacksessie van 17 juni 2026. Gebaseerd op de commits tot en met 25 juni 2026.

## Toegankelijker voor een breed publiek

- Uitleg en labels herschreven zodat ook mensen zonder statistiekachtergrond ze begrijpen.
- Overal consequent het woord "item" gebruikt in plaats van "onderdeel".
- Het label "Univariate regressie" vervangen door "Elk onderdeel apart".

## Nieuwe introductietab

- Een introductietab die in gewone taal uitlegt wat de tool doet, hoe het werkt en welke groepen worden vergeleken.
- De groepsuitleg is aangescherpt. De tool kijkt alleen naar studenten die zich daadwerkelijk hebben ingeschreven en dus in 1CHO staan, en vergelijkt daarbinnen studiesucces met uitval. Kandidaten die niet zijn begonnen worden uit de analyse gehaald.

## Configuratie makkelijker maken

- De losse configuratie-tab is uit het dashboard gehaald.
- De config-wizard is nu een schermvullende, stapsgewijze pagina met duidelijkere knoppen en uitleg.
- In de wizard is de Meenemen-dropdown vervangen door een checkbox en is er een schaalveld toegevoegd.
- Let op: aan de configuratie-aanpak wordt nog gewerkt, dit kan nog veranderen.

## Tab "Wat valt op" opnieuw opgebouwd

- De bevindingen zijn opgesplitst in twee duidelijke delen. Eerst de selectiescores en studiesucces (verschiltoets, regressie, correlatie), daarna de achtergrondkenmerken (geslacht, vooropleiding). Eerst stond dit door elkaar.
- Een inklapbare uitleg "Verschiltoets of regressie: wat zegt wat?" legt uit waarom de verschiltoets per item bij kleine groepen het betrouwbaarste signaal is en het gezamenlijke model alleen een aanvulling.
- Onderaan staat nu een opvallend blauw beleidsblok "Vervolgstappen voor beleid". Dat koppelt de conclusie aan de resultaten: bij een significant effect is het advies anders dan wanneer er niets wordt gevonden.

## Demografie en eerlijkheid duidelijker

- De gebruikte toets wordt nu benoemd (chi-kwadraat, Kruskal-Wallis).
- Op de Demografie-tab wordt de chi-kwadraatuitkomst getoond en is de eerlijkheidssectie hernoemd.

## Opschoning en onderhoud

- app.py opgesplitst in losse modules per tabblad.
- Demodata herzien en ongebruikte 1CHO-kolommen verwijderd.
- Verouderde fictieve datageneratoren en eenmalige scripts verwijderd.
- Hardgecodeerde groepslabels vervangen door gedeelde constanten, en de deserialisatie van de scores-store ontdubbeld.
- Projectdocumentatie (CLAUDE.md en README) bijgewerkt.

## Voorbereiding test met echte data

- Voor de testsessie met Radboud en Leiden zijn configs klaargezet: Farmacie master voor Leiden, en twee formaten voor Radboud Psychologie.
- Er is een generieke instructie geschreven om het dashboard met echte data te draaien, inclusief hoe je de 1CHO-data uit de 1cijferho-evaluatietool haalt.
- Deze bestanden staan lokaal en buiten git, omdat er straks persoonsgegevens bij komen.
