# Ändringslogg

## 0.1.0-beta.3 – 2026-11-13

Kräver Home Assistant 2026.11 eller senare. Säkerhetskopiera konfigurationen inklusive `.storage` före uppdatering.

- Kompakt programöversikt med pris och bästa start synliga. Klicka på programmet för att visa energi, sluttid, underlag och besparing. Öppet läge och tangentbordsfokus bevaras när priser uppdateras.
- Bekräfta automatisk diskstart med ihållande aktivitet, standard 30 sekunder och valbart 0–120.
- Korta effekttoppar följda av vänteläge skapar ingen programkörning.
- Bevara den bekräftade körningens ursprungliga start, minutenergi och energimätarställning.
- Visa väntande startbekräftelse i kortet. Oförändrat lagringsformat, import och MIT-licens.
- Installationsguide för nyinstallation, uppdatering, sensorer och kortets resurser.

### Verifiering och begränsningar

- 210 Python-tester och 18 JavaScript-tester samt kod- och syntaxkontroller. En separat lokal HA-kontroll med syntetisk effekt verifierade vänteläge, bekräftad start, slutbekräftelse, starttid och energi mot en oberoende beräkning.
- Befintliga profiler och körningar bevarades i lokaltestet. Ingen WashData-kod, AI-koppling eller nya runtime-beroenden ingår.
- Återgång till beta.2 kräver ingen datamigrering; den äldre koden ignorerar `start_seconds`. Beta.2 börjar samla direkt vid startgränsen och kan därför åter inkludera fördröjd starts vänteläge.
- Bekräftelsen sker vid sensoravläsningar eller den befintliga 30-sekunderstickern. Program med enbart korta startpulser kan behöva kortare bekräftelsetid eller 0. En kandidat sparas inte över omstart; otillräckligt observerad start markeras ofullständig.
- Avslutslogiken är oförändrad. Återgång till vila bevisar inte färdig disk. Produktionsinstallation, fysisk mätarnoggrannhet och riktiga avtalspriser är fortfarande inte verifierade. Den kända begränsningen med täta prisuppdateringar kvarstår.

## 0.1.0-beta.2 – 2026-11-12

Ny beta med registrering av egna programprofiler från effektmätning eller sparad historik. Kräver fortsatt Home Assistant 2026.11 eller senare. Säkerhetskopiera konfigurationen inklusive `.storage` före uppdatering.

- Utökade registreringstester: oberoende energimodell, samtidiga anrop, timerägarskap, avstängning, riktiga SQLite-rader och tidszonsgränser. JavaScript-tidszonstester ingår i CI.
- Rättad UTC-tolkning av Recorders SQLite-tider efter omstart, så att korrekt historik inte felaktigt blir en datalucka.
- Avbrutna timers och anrop som väntar under avstängning kan inte påverka en ny registrering.
- Reglage behåller tangentbordsfokus vid omräkning och prisuppdatering. Sena förhandsvisningssvar kan inte skriva över en ny avgränsning, och ett avslut läst före tillståndshändelsen öppnar en komplett granskning.
- Tvetydiga klockslag avvisas även när sommartidsomställningen är en halvtimme.
- Profil-, export-, import- och registreringsåtgärder kräver administratörsbehörighet. Interna systemanrop följer Home Assistants ordinarie modell.
- Omräknad effekt och ackumulerad energi valideras innan lagring. Ogiltiga eller alltför stora mätningar markeras ofullständiga och kan inte skada nya lagrade kurvor eller användas för inlärning.

- Registrera en ny profilkörning från nu, med manuellt avslut eller valt klockslag, samt hämta tidigare effektdata från Recorder.
- Separat lagrat utkast med kurva, föreslagna och justerbara start-/slutgränser, omräknad energi och uttrycklig bekräftelse före sparande till ny eller befintlig profil.
- Dataluckor och avbrutna utkast utesluts från komplett profilunderlag. Överlappande körningar avvisas och pågående manuell registrering skapar ingen automatisk kopia.

### Verifiering och begränsningar

- 181 Python-tester och 18 JavaScript-tester, kodkontroller, isolerade webbläsarprov samt verkliga lokala HA-prov av Recorder, sparande och omstarter. Testerna använder syntetiska sensorer och priser.
- Befintliga profiler och körningar bevaras. Registrering skapar ett separat utkast och styr inte apparaten. Historik kräver Recorder och detaljerade tillstånd för effektsensorn.
- Högst åtta timmar per registrering. Kända dataluckor, avbrutna utkast och överlappande sparade körningar avvisas som komplett profilunderlag. Gränser och programval måste granskas av användaren.
- Sparade profiler och körningar har samma format som i beta.1. Registreringsutkast stöds inte i beta.1: spara eller kasta dem före återgång och behåll en säkerhetskopia.
- Produktionsinstallation, den riktiga effektmätarens noggrannhet och användarens avtalsprissensor är ännu inte verifierade. Driftbegränsningen med täta prisuppdateringar som beskrivs under beta.1 kvarstår.

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
