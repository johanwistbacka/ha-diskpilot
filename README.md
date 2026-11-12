# Diskpilot

Diskpilot använder sparade programprofiler för att beräkna billigaste start och elkostnad för P2, P3 och P4. Du ser alla program samtidigt. En effektsensor är valfri och behövs bara om du vill samla in nya körningar.

**Utvecklingsversion.** Kräver Home Assistant 2026.11 eller senare. Ingen automatisk start av maskinen. Programnamnen är tills vidare P2 (70 °C), P3 (snabb) och P4 (Eco). Ingen personlig mätdata eller förinställd förbrukning följer med koden.

## Installation och uppdateringar

I Home Assistant 2026.11 finns Marketplace inbyggd som efterföljare till HACS. Projektet använder samma struktur för en custom integration och ett publikt GitHub-repo.

1. Lägg till `https://github.com/johanwistbacka/ha-diskpilot` som eget repo i Marketplace, typ **Integration**.
2. Installera och starta om Home Assistant.
3. Lägg till **Diskpilot** under Inställningar → Enheter och tjänster.
4. Välj prissensor om du vill beräkna start och kostnad. Effektsensor är valfri och kan lämnas tom för planering med sparade profiler. Lägg till den senare under Konfigurera om du vill samla nya körningar.
5. Lägg till kortet **Diskpilot** i dashboardens kortväljare. Kortets resurs registreras automatiskt när dashboardresurser hanteras via gränssnittet.

Manuell installation: kopiera `custom_components/dishwasher_optimizer` till din Home Assistant-konfiguration under `custom_components/` och starta om.

Ännu finns ingen numrerad release. Använd huvudgrenen för utveckling. Kommande versioner distribueras som GitHub-releaser och kan uppdateras via Marketplace. Lokal historik ligger i Home Assistants `.storage`, utanför integrationskoden, och ersätts inte när koden uppdateras. Ta med `.storage` i dina säkerhetskopior.

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

## Insamling, programbilder och rättelser

När en effektsensor är ansluten börjar insamlingen automatiskt. Effekt över startgränsen (standard 5 W) startar en körning. Under vilogränsen (standard 1 W) i tio minuter bekräftar slutet. Bekräftelsetiden räknas inte in i energi eller programprofil. En lång avslutning kring 3 W behålls i mätningen.

Märk programmet under **Senaste körningarna** i kortet. Märkningen går att ändra eller ta bort. Varje programprofil räknas om från sina märkta, fullständiga körningar. Omärkta körningar används inte för att gissa programnamn.

Du kan fotografera programvalet vid start och senare lämna bilden tillsammans med datum/starttid och exporterad körning för analys. Bilden behöver visa programnumret och eventuella tillval. **Integrationen tolkar eller laddar inte upp bilder.** Bildens filtid ensam är ingen säker märkning, särskilt om maskinen har fördröjd start.

Körningar lagras lokalt med id, starttid, tid till vila, energi per minut, programetikett, anteckning och kvalitetsmarkeringar. Första körningen efter installation kan vara påbörjad redan när insamlingen startar. Den märks då ofullständig. Avbrott, omstarter, byte av effektmätare och kända dataluckor utesluts från inlärning. När effektmätningen är avstängd fortsätter planeringen med de sparade profilerna. Oförändrade sensortillstånd samplas var 30:e sekund. Om en sensor fastnar utan att rapportera `unavailable` kan Diskpilot inte själv upptäcka det.

Som första underlag räcker en märkt körning per program. Kortet visar när uppskattningen bara bygger på en körning. Fler körningar förbättrar medelprofilen. Energiförbrukningens observerade min/max och antal mätningar finns som sensorattribut. Detta är ingen statistisk garanti.

## Dashboard-kort

Kortet ingår i integrationen och uppdateras tillsammans med den. Det visar alla tre programmens kostnad, bästa start, återgång till vila, energi, underlag och besparing mot start nu. Kortet kan också märka de fem senaste körningarna. Äldre körningar nås via åtgärderna nedan.

**Åter i vila betyder inte verifierad färdigtid för disken.** Detta behöver kontrolleras mot maskinens färdigindikering. Kostnaden beräknas från effektsensorn och kan inte verifiera om sensorn mäter hela maskinens förbrukning.

Enkel kortkonfiguration:

```yaml
type: custom:diskpilot-card
title: Diskmaskinen
```

Har du flera maskiner väljer du vilken i kortets visuella inställningar. YAML-baserade dashboardresurser ändras inte automatiskt. Lägg i så fall till modulen `/dishwasher_optimizer/diskpilot-card.js?v=0.0.0` bland dina resurser.

## Åtgärder för export, import och märkning

Alla åtgärder använder `entry_id` för rätt Diskpilot-instans. Det finns som attribut `diskpilot_entry_id` på integrationens sensorer.

| Åtgärd | Indata | Resultat |
|---|---|---|
| `dishwasher_optimizer.get_runs` | `entry_id`, valfria `offset` och `limit` (1–100) | Svar med körningar, inklusive minutenergi i Wh |
| `dishwasher_optimizer.label_run` | `entry_id`, `run_id`, `program` (`P2`, `P3`, `P4` eller `unassigned`), valfri `note` | Uppdaterar etikett och räknar om profiler |
| `dishwasher_optimizer.import_run` | `entry_id`, `started_at` (ISO med tidszon), `duration_seconds`, `energy_wh`, valfritt `program` och `note` | Svar med nytt körnings-id |

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
```

Testerna kontrollerar energi, prisgränser, negativa priser, dataluckor, lagring/omstart, etikettändringar, åtgärder och kortregistrering med riktiga Home Assistant-klasser. Testerna ersätter inte en provinstallation i din Home Assistant.

Officiella referenser: [Marketplace-repon](https://contributors.home-assistant.io/marketplace/reference/repository-structure/), [egna kort](https://contributors.home-assistant.io/frontend/custom-ui/card/), [Home Assistant 2026.11](https://www.home-assistant.io/blog/2026/11/04/release-202611/).
