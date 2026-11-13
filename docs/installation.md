# Installera Diskpilot

Anvisningarna gäller **0.1.0-beta.2** och Home Assistant **2026.11 eller senare**. Diskpilot installeras som en integration. Dashboard-kortet följer med samma paket.

[Tillbaka till README](../README.md) · [Hämta beta.2](https://github.com/johanwistbacka/ha-diskpilot/releases/tag/0.1.0-beta.2)

## Innan du börjar

- Logga in som administratör. Installation, profilhantering, import och registrering kräver administratörsbehörighet.
- Ta en Home Assistant-säkerhetskopia som inkluderar konfigurationen och `.storage`. Spara återställningsnyckeln. Se [Home Assistants backupguide](https://www.home-assistant.io/common-tasks/general/backups/).
- Avsluta eventuell pågående registrering och granska eller kasta utkastet före uppdatering.

Du kan börja utan sensorer och lägga till dem senare. Förbrukningsprofiler följer inte med installationen; du tillför egna körningar genom filimport eller registrering.

## 1. Installera genom Marketplace

Marketplace är inbyggd från Home Assistant 2026.11 och ersätter HACS. Stegen nedan följer [Home Assistants Marketplace-anvisningar](https://www.home-assistant.io/integrations/marketplace/).

1. Öppna **Inställningar → Marketplace** och välj **Add from link / Lägg till från länk**.
2. Ange `https://github.com/johanwistbacka/ha-diskpilot` och välj **Lägg till**. Anslut GitHub om du blir ombedd. Välj typen **Integration** om Marketplace frågar.
3. Öppna **Inställningar → Enheter och tjänster → Marketplace** och välj repots enhet. Aktivera den inaktiverade entiteten **Pre-release** och slå sedan på dess brytare.
4. Återgå till repots sida i Marketplace och installera **0.1.0-beta.2**.
5. Starta om Home Assistant.

**Pre-release har två steg:** att aktivera entiteten i dess inställningar och därefter slå på brytaren. En aktiverad men avstängd brytare visar fortfarande inte betaversioner.

Om Diskpilot redan är installerat, följ i stället [uppdateringsstegen](#uppdatera-från-beta1-eller-en-annan-version).

## 2. Lägg till integrationen

Öppna **Inställningar → Enheter och tjänster → Lägg till integration** och sök efter **Diskpilot**. Om installationsdialogen redan öppnats efter nedladdningen kan du fortsätta där.

Ge apparaten ett namn, exempelvis *Diskmaskin*, och välj det du vill använda:

| Fält | Användning |
|---|---|
| Prissensor | Valfri. Behövs för kostnad och bästa start. Måste ha framtida prisintervall; enbart ett aktuellt pris räcker inte. |
| Effektsensor | Valfri. Behövs för att registrera nya körningar eller läsa deras effekt ur historiken. Välj sensorn för själva apparaten, i W eller kW. |
| Energisensor | Valfri ackumulerad energimätare för samma apparat, i Wh eller kWh. Används som kontroll vid automatisk insamling och ersätter inte effektkurvan. |
| Profilnamn | Valfria namn, ett per rad. Kan lämnas tomt och läggas till senare. Ett namn ensamt innehåller ingen förbrukningskurva. |

Spara konfigurationen. Sensorer och prisformat kan ändras senare genom **Konfigurera** på Diskpilot-integrationen. Där anges exempelvis vilka prisattribut som ska läsas och om priser behöver räknas om från öre till kronor. Se [prissensorns format](../README.md#prissensor).

## 3. Lägg till dashboard-kortet

Kortresursen registreras automatiskt när Home Assistant hanterar dashboardresurserna via gränssnittet. [Home Assistants kortguide](https://www.home-assistant.io/dashboards/cards/) beskriver redigering av dashboards.

1. Öppna den dashboard där kortet ska visas och gå till redigeringsläget.
2. Välj **Lägg till kort** och sök efter **Diskpilot**.
3. Välj rätt Diskpilot-instans om du har flera apparater och spara kortet.

Du kan också lägga till ett manuellt kort med följande YAML:

```yaml
type: custom:diskpilot-card
title: Diskmaskinen
```

Om du hanterar resurser i YAML behöver du själv lägga till denna post i din befintliga resurslista:

```yaml
- url: /dishwasher_optimizer/diskpilot-card.js?v=0.1.0-beta.2
  type: module
```

Ladda om dashboarden efter att resursen lagts till. Kortet installeras tillsammans med integrationen och behöver inget separat frontend-repo.

## 4. Lägg till första profilunderlaget

Öppna kortet och välj ett av alternativen:

- **Profiler och filimport:** importera en egen JSON- eller CSV-fil enligt [filformatet](profile-import.md). Välj profil och bekräfta märkningen.
- **Registrera profil → Registrera nu:** ange profil, starta registreringen före apparaten och avsluta manuellt eller vid ett valt klockslag. Granska kurvan före sparande.
- **Registrera profil → Använd historik:** välj start och slut för ett tidigare program. Detaljerade effektvärden måste finnas i Home Assistants Recorder. Se [registreringsguiden](profile-registration.md).

När profilen har en komplett körning visar kortet energi, tid och antal underlag. Kostnad och bästa start visas när giltiga prisintervall täcker hela körningen. Utan prissensor kan du fortfarande bygga profiler. Utan effektsensor kan du använda filimport och planera med sparade profiler.

Diskpilot startar aldrig själva apparaten. Profilnamnet och att hela körningen tillhör rätt profil bekräftas av dig.

## Uppdatera från beta.1 eller en annan version

1. Avsluta och granska pågående registrering. Ta en säkerhetskopia.
2. Öppna Diskpilot i Marketplace. Kontrollera att **Pre-release** är på och välj uppdatering till **0.1.0-beta.2**.
3. Starta om Home Assistant och ladda om dashboarden.
4. Kontrollera att dina profilnamn och antalet körningar finns kvar.

Du behöver inte lägga till integrationen på nytt. Sparade profiler och körningar från beta.1 bevaras vid en normal uppdatering. Beta.2 kräver administratör för profil- och registreringsåtgärder.

För återställning och återgång, se [säkerhetskopia och återgång](../README.md#säkerhetskopia-och-återgång). Registreringsutkast stöds inte i beta.1.

## Manuell installation

Använd detta alternativ om du installerar utan Marketplace:

1. Hämta **Source code (zip)** från [beta.2-releasen](https://github.com/johanwistbacka/ha-diskpilot/releases/tag/0.1.0-beta.2) och packa upp arkivet.
2. Kopiera hela mappen `custom_components/dishwasher_optimizer` till din Home Assistant-konfigurationsmapp, under `custom_components/`. Ta med mappen `www` och alla dess filer.
3. Kontrollera att sökvägen är `custom_components/dishwasher_optimizer/manifest.json`, utan en extra `ha-diskpilot-…`-mapp mellan nivåerna. Konfigurationsmappen är den som innehåller `configuration.yaml`.
4. Starta om Home Assistant och fortsätt med [att lägga till integrationen](#2-lägg-till-integrationen).

Vid manuell uppdatering ersätter du integrationsmappen med samma mapp från den valda versionen. Behåll konfigurationens `.storage` och övriga integrationer. Starta om och ladda om dashboarden.

## Om något inte syns eller fungerar

| Symtom | Kontrollera |
|---|---|
| Beta.2 visas inte | Att entiteten **Pre-release** är aktiverad och brytaren på för rätt repo. |
| Diskpilot saknas under Lägg till integration | Att Home Assistant startats om och att `manifest.json` ligger på rätt nivå. |
| Kortet saknas eller visar `Custom element doesn't exist: diskpilot-card` | Att integrationen är tillagd, att dashboarden laddats om och att resursen är registrerad som `module`. Kontrollera resurslistan om du hanterar den i YAML. |
| Kostnaden visas som ett streck | Att profilen har en komplett körning och prissensorn har giltiga framtida intervall för hela programmet. Kontrollera prisformatet under Konfigurera. |
| Registrering är otillgänglig | Att en effektsensor är vald och visar giltigt värde i W eller kW. För historik krävs också Recorder-data. |
| En åtgärd nekas | Att du är inloggad som administratör. |

Vid ett integrationsfel finns loggen under **Inställningar → System → Loggar**. Sök efter `dishwasher_optimizer` eller Diskpilot och ange versionen när du rapporterar ett problem. Dela inte åtkomstnycklar eller hela `.storage`-filer.
