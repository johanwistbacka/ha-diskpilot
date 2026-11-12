# Ändringslogg

## 0.1.0-beta.1 – 2026-11-12

Första numrerade betan. Kräver Home Assistant 2026.11 eller senare. Aktivera repots Pre-release-val i Marketplace/HACS för att välja betan. Säkerhetskopiera konfigurationen inklusive `.storage` före installation eller uppdatering.

### Funktioner

- Egna namngivna programprofiler som kan skapas och döpas om med bibehållna ID:n och underlag.
- Lokal import av JSON/CSV med förhandsgranskning av antal körningar, energi, längd och första körningens minutkurva. Importen lägger till verkliga körningar; dubbletter och ogiltiga filer avvisas.
- Kostnad och billigaste start beräknas från varje profils tidsfördelade energi och en valbar prissensor med framtida prisintervall. Negativa priser stöds; saknade prisintervall ger ingen kostnadsuppskattning.
- Valfri effektmätare för automatisk insamling av nya körningar. Programvalet märks i efterhand. Avbrutna eller ofullständiga mätningar används inte i profilerna.
- Valfri ackumulerad energisensor som kontroll av effektkurvans totalenergi.
- Inbyggt dashboard-kort med kostnad, startförslag, tid till vila, energi, underlag, filimport och namngivning. Kortets resurs uppdateras när dess JavaScript ändras.
- Lokal instruktion, frivillig exempelprompt och syntetiska filformatsexempel. Ingen AI-koppling, AI-nyckel eller extern analystjänst krävs.

### Verifiering och begränsningar

- Automatiska tester mot Home Assistant 2026.11.1 samt lokala prov av filimport, namnbyte, medelprofiler, dynamiska sensorer och omstart.
- Ingen fjärrstart eller annan styrning av apparater. Egna sensorer och integrationsdata skapas i Home Assistant.
- En profil med en enda körning är en första uppskattning. Tidsgrupper är inte verifierade programnummer.
- Planeringens sluttid avser återgång till vila och använder profilens längsta observerade körning. Detta bevisar inte när disken är färdig.
- Prissensorns format, enheter och avgifter måste stämma. Fördröjd starts vänteläge ingår inte i importerade programkurvor som avgränsats till själva programmet.
- Inga privata mätdata, laboratoriedashboards, kontouppgifter eller avtalsinställningar följer med releasen. Produktionsinstallation är inte genomförd eller verifierad.

### Känd driftbegränsning

En prissensor med mycket täta tillståndsändringar kan köa omberäkningar och fördröja nya kostnadsresultat. Sammanslagning av väntande omberäkningar återstår som en förbättring. Detta är en lågprioriterad uppföljning för den avsedda betaprovningen med få profiler.
