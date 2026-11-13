# Diskpilot

Diskpilot använder egna namngivna programprofiler för att beräkna billigaste start och elkostnad. Du ser alla program samtidigt. En effektsensor är valfri och behövs bara om du vill samla in nya körningar.

**Beta 0.1.0-beta.2.** Kräver Home Assistant 2026.11 eller senare och är testad lokalt med 2026.11.1. Ingen automatisk start av maskinen. Du väljer profilnamnen själv. Tidigare installerade P2/P3/P4-profiler och deras underlag bevaras vid uppdatering. Ingen personlig mätdata eller förinställd förbrukning följer med koden. Installation i användarens produktionsmiljö är ännu inte verifierad.

## Installation och uppdateringar

**[Installationsguide: nyinstallation, uppdatering, sensorer och dashboard-kort](docs/installation.md)**

Snabbstart för Home Assistant 2026.11 eller senare:

1. Installera **0.1.0-beta.2** via Marketplace med **Pre-release** aktiverat. De fullständiga stegen finns i guiden.
2. Lägg till **Diskpilot** under **Inställningar → Enheter och tjänster → Lägg till integration**. Sensorer och profilnamn är valfria vid start.
3. Lägg till **Diskpilot** i dashboardens kortväljare och tillför egna profilkörningar genom filimport eller registrering.

Guiden innehåller även manuell installation, uppdatering från beta.1 och felsökning. Profilhantering och registreringsåtgärder kräver administratörsbehörighet. Ta en säkerhetskopia före installation eller uppdatering.

Den numrerade betan finns under [GitHub Releases](https://github.com/johanwistbacka/ha-diskpilot/releases/tag/0.1.0-beta.2) och är markerad som pre-release. Marketplace/HACS hämtar integrationsfilerna från den valda taggen; någon separat ZIP-asset krävs inte. Huvudgrenen används för fortsatt utveckling. Se [ändringsloggen](CHANGELOG.md).

### Säkerhetskopia och återgång

Ta en Home Assistant-säkerhetskopia före installation eller uppdatering, inklusive konfigurationens `.storage`, och spara återställningsnyckeln. Lokal historik och profiler ligger i `.storage`, utanför integrationskoden, och ersätts inte vid en normal koduppdatering.

Återgång från beta.2 till beta.1: sparade profiler och körningar har samma format, men registreringsutkast stöds inte i beta.1. Spara eller kasta utkast före återgång och behåll säkerhetskopian.

Om problem uppstår kan Diskpilot inaktiveras under Enheter och tjänster och Home Assistant startas om. Om gränssnittet inte går att nå, använd din befintliga filåtkomst för att flytta integrationsmappen `custom_components/dishwasher_optimizer` ut ur `custom_components` och starta om. Behåll `.storage` för en senare ominstallation. Återställ säkerhetskopian om hela installationen behöver återställas. Återgång till äldre utvecklingskod kräver en matchande säkerhetskopia när dess lagringsformat inte stöder egna profil-ID:n.

## Prissensor

Under **Konfigurera** kan du lägga till, byta eller ta bort effektsensor utan att förlora sparade profiler. Saknar du en programprofil visas detta tydligt; koden gissar inte förbrukningen. Sparade uppmätta kurvor kan importeras med åtgärden nedan. Ingen fysisk mätare krävs för att använda dem.

Under **Konfigurera** kan du byta prissensor och ange vilka attribut och fältnamn den använder. Ett aktuellt pris som ensamt sensorvärde räcker inte för optimering. Sensorn behöver innehålla framtida prisintervall, exempelvis:

```yaml
prices:
  - start: '2026-01-01T00:00:00+01:00'
    end: '2026-01-01T00:15:00+01:00'
    value: 1.25
```

Exemplet beskriver formatet och innehåller inga aktuella priser. Standard är attributet `prices` och fälten `start`, `end`, `value`. Om din sensor använder `raw_today` och `raw_tomorrow` anger du `raw_today,raw_tomorrow`. Listorna sammanfogas. Fältnamnen kan ändras, men godtyckliga malluttryck körs inte.

- Tidsstämplar måste innehålla tidszon/UTC-offset. Datetime-värden från integrationer stöds också.
- Värden ska vara numeriska, ändliga och utan överlappande intervall. Negativa priser stöds.
- Ange omräkning **1** för SEK/kWh, **0.01** för öre/kWh eller **0.001** för SEK/MWh.
- Använd ditt rörliga avtalspris med de avgifter du vill räkna med. Diskpilot lägger inte till moms, skatt eller påslag själv.
- Priser måste finnas för hela den beräknade körningen. Saknade eller felaktiga intervall ger ingen kostnad, aldrig antagna nollpriser.

Din specifika avtalsprissensor behöver fortfarande kontrolleras mot detta format. Andra format kräver en adapter eller en separat sensors attribut med normaliserade intervall.

## Egna profiler och filimport

Öppna **Profiler och filimport** i kortet för att skapa och namnge profiler, byta namn eller ladda upp egna CSV/JSON-filer. Filen kontrolleras först och du får se antal körningar, energi, längd och den första körningens kurva. Välj profil och bekräfta märkningen innan något importeras.

**Ingen AI-koppling krävs.** Importen och kostnadsberäkningen sker i Home Assistant. En rå historikexport behöver först omvandlas till det dokumenterade profilformatet. Du kan göra detta själv eller frivilligt använda instruktionen och exempelprompten i valfri AI-tjänst.

- [Instruktion och filformat](docs/profile-import.md)
- [Frivillig exempelprompt](custom_components/dishwasher_optimizer/www/profile-prompt.txt)
- [Syntetiskt JSON-exempel](custom_components/dishwasher_optimizer/www/example-profile.json)
- [Motsvarande CSV-exempel](custom_components/dishwasher_optimizer/www/example-profile.csv)

Instruktionen och prompten nås också från kortet i den lokala installationen. Namngivna profiler kan skapas utan anslutna effekt- eller energisensorer. Högst 50 profiler per apparat. Nya körningar läggs till underlaget; inga tidigare körningar skrivs över. Dubbletter av starttid avvisas innan importen ändrar något.

Vid uppdatering från den tidigare utvecklingsversionen bevaras profilernas ID och entiteter. Nya egna profil-ID:n kräver denna kodversion; återgång till äldre kod kräver en matchande säkerhetskopia av integrationsdata.

## Insamling, programbilder och rättelser

Från beta.2 finns **Registrera profil** i kortet: registrera från nu med manuellt eller tidsbestämt avslut, eller välj ett tidigare intervall ur Home Assistants Recorder. Båda flödena ger ett separat utkast med kurva och justerbara gränser. Körningen tillförs först efter granskning och bekräftelse, till en ny eller befintlig profil. Se [registreringsflödet och begränsningarna](docs/profile-registration.md).

När en effektsensor är ansluten börjar insamlingen automatiskt. Effekt över startgränsen (standard 5 W) startar en körning. Under vilogränsen (standard 1 W) i tio minuter bekräftar slutet. Bekräftelsetiden räknas inte in i energi eller programprofil. En lång avslutning kring 3 W behålls i mätningen.

Märk programmet under **Senaste körningarna** i kortet. Märkningen går att ändra eller ta bort. Varje programprofil räknas om från sina märkta, fullständiga körningar. Omärkta körningar används inte för att gissa programnamn.

Du kan fotografera programvalet vid start och senare lämna bilden tillsammans med datum/starttid och exporterad körning för analys. Bilden behöver visa programnumret och eventuella tillval. **Integrationen tolkar eller laddar inte upp bilder.** Bildens filtid ensam är ingen säker märkning, särskilt om maskinen har fördröjd start.

Körningar lagras lokalt med id, starttid, tid till vila, energi per minut, programetikett, anteckning och kvalitetsmarkeringar. Första körningen efter installation kan vara påbörjad redan när insamlingen startar. Den märks då ofullständig. Avbrott, omstarter, byte av effektmätare och kända dataluckor utesluts från inlärning. När effektmätningen är avstängd fortsätter planeringen med de sparade profilerna. Oförändrade sensortillstånd samplas var 30:e sekund. Om en sensor fastnar utan att rapportera `unavailable` kan Diskpilot inte själv upptäcka det.

En valfri ackumulerad energisensor i Wh eller kWh används som kontroll vid registrerade körningar. Mätarställningar jämförs vid start och första återgång till vila. Saknade värden eller en mätaråterställning redovisas separat och ersätter inte effektkurvan. Uppdateringsintervall kan ge skillnader mellan energimätaren och den integrerade kurvan.

Som första underlag räcker en märkt körning per program. Kortet visar när uppskattningen bara bygger på en körning. Fler körningar förbättrar medelprofilen. Energiförbrukningens observerade min/max och antal mätningar finns som sensorattribut. Detta är ingen statistisk garanti.

## Dashboard-kort

Kortet ingår i integrationen och uppdateras tillsammans med den. Det visar alla profilernas kostnad, bästa start, återgång till vila, energi, underlag och besparing mot start nu. När effektmätning är aktiverad kan kortet också märka de fem senaste körningarna. Äldre körningar nås via åtgärderna nedan.

**Åter i vila betyder inte verifierad färdigtid för disken.** Detta behöver kontrolleras mot maskinens färdigindikering. Kostnaden beräknas från profilens uppmätta tidskurva och kan inte verifiera om sensorn mäter hela maskinens förbrukning.

Enkel kortkonfiguration:

```yaml
type: custom:diskpilot-card
title: Diskmaskinen
```

Har du flera maskiner väljer du vilken i kortets visuella inställningar. YAML-baserade dashboardresurser ändras inte automatiskt. Lägg i så fall till modulen `/dishwasher_optimizer/diskpilot-card.js?v=0.1.0-beta.2` bland dina resurser.

## Åtgärder för export, import och märkning

Profilhantering, filimport, export och registreringsåtgärder kräver en inloggad Home Assistant-administratör. Interna system- och automationsanrop utan användarkontext följer Home Assistants vanliga behörighetsmodell. Kostnadsentiteter kan visas enligt dashboardens vanliga entitetsbehörigheter.

Alla åtgärder använder `entry_id` för rätt Diskpilot-instans. Det finns som attribut `diskpilot_entry_id` på integrationens sensorer.

| Åtgärd | Indata | Resultat |
|---|---|---|
| `dishwasher_optimizer.get_runs` | `entry_id`, valfria `offset` och `limit` (1–100) | Svar med körningar, inklusive minutenergi i Wh |
| `dishwasher_optimizer.label_run` | `entry_id`, `run_id`, `program` (profilens ID eller `unassigned`), valfri `note` | Uppdaterar etikett och räknar om profiler |
| `dishwasher_optimizer.import_run` | `entry_id`, `started_at` (ISO med tidszon), `duration_seconds`, `energy_wh`, valfritt `program` och `note` | Svar med nytt körnings-id |

Profilerna med namn och stabila ID:n finns i statusentitetens attribut `profiles`. De äldre P2/P3/P4-ID:na fungerar fortsatt i befintliga installationer.

| Åtgärd | Indata | Resultat |
|---|---|---|
| `dishwasher_optimizer.save_profile` | `entry_id`, `name`, valfritt `profile_id` för namnbyte | Profilens ID; befintliga körningar bevaras |
| `dishwasher_optimizer.preview_profile_file` | `entry_id`, `filename`, `content` | Granskningsdata, utan att spara |
| `dishwasher_optimizer.import_profile_file` | Samma filuppgifter och antingen `profile_id` eller `name` | Sparar kontrollerade körningar till profilen |

Filinnehåll öppnas aldrig som filväg eller URL. Högst 512 KiB och 100 körningar per fil. Felaktiga filer eller redan importerade starttider avvisas för hela omgången.

Importformatet kräver en energipost i Wh per relativ minut, inklusive en eventuell sista delminut. Antalet poster måste vara `ceil(duration_seconds/60)`. Importerade körningar kan vara omärkta. Återimport av samma starttid avvisas. Maximalt åtta timmar per körning.

## Beräkning och begränsningar

Energin integreras med föregående effektvärde fram till nästa mätning och delas vid minutgränser. Medelprofilen bevarar medelenergin. Den längsta observerade tiden används för att behålla avslutningen; detta är inte en garanti för framtida programtid. En sista delminut fördelas över sin verkliga varaktighet.

Optimeringen provar start nu och minutgränser fram till vald sluttidsgräns, 1–48 timmar framåt. Varje minut delas vid prisgränser. Elpriset extrapoleras inte. Framtida priser som ännu inte publicerats kan senare ge en annan rekommendation. Tysta källfel och mätarens noggrannhet ligger utanför vad koden kan verifiera. Programtillval bör jämföras innan olika körningar slås ihop under samma etikett.

Första versionen har ingen fjärrstart, automatisk bildtolkning, automatisk programklassificering, nattliga tidsfönster eller separat färdigtid. Den skickar ingen mätdata till externa tjänster. GitHub/Marketplace hanterar hämtning av kod, inte analys av körningar.

## Lokal provmiljö

En separat Home Assistant med testsensorer kan startas med `sh dev/run-local.sh`. Se [anvisningar för lokal testmiljö](dev/README.md). Ingen av hemmets sensorer behövs för att prova integrationen och kortet. Testdata sparas privat och följer inte med i GitHub-repot.

## Utveckling

Python 3.14 och Home Assistant 2026.11.1:

```sh
python3.14 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/pytest -q
node --test tests/frontend-registration-time.mjs
```

Testerna kontrollerar energi, prisgränser, negativa priser, dataluckor, lagring/omstart, etikettändringar, åtgärder och kortregistrering med riktiga Home Assistant-klasser. Testerna ersätter inte en provinstallation i din Home Assistant.

Registreringstesterna omfattar också oregelbundna effektkurvor jämförda med en separat integrationsmodell, samtidiga start-/spara-anrop, gamla timeranrop och avstängning under ett väntande anrop. SQLite-tester använder riktiga Recorder-tabellrader för att kontrollera UTC och avbrott efter omstart i flera tidszoner. JavaScript-testerna kräver Node.js 22 eller senare och kontrollerar lokala datum, sommartidsluckor och upprepade klockslag, inklusive halvtimmesomställningar. De körs även i GitHub-kontrollerna.

Officiella referenser: [Marketplace-repon](https://contributors.home-assistant.io/marketplace/reference/repository-structure/), [egna kort](https://contributors.home-assistant.io/frontend/custom-ui/card/), [Home Assistant 2026.11](https://www.home-assistant.io/blog/2026/11/04/release-202611/).
