# Registrera profil

Tillgängligt från **0.1.0-beta.2** i kortets **Registrera profil**. Funktionen styr aldrig apparaten och använder ingen AI-tjänst.

Registreringsåtgärder och profiländringar kräver administratörsbehörighet i Home Assistant.

Välj den egna apparatens effektsensor (W eller kW) under integrationens inställningar. Effektsensorn behövs för registrering; befintlig filimport och planering fungerar fortfarande utan mätare. En ackumulerad energisensor ersätter inte effektkurvan i dessa flöden.

## Registrera nu

1. Välj en befintlig profil eller ange namnet på en ny.
2. Välj att avsluta själv eller ange datum och klockslag för avslut.
3. Starta registreringen före programmet. Välj program och starta själva apparaten som vanligt.
4. Tryck **Avsluta och granska**, eller invänta det valda klockslaget. Registreringen avslutas senast efter åtta timmar.
5. Granska den registrerade kurvan och de föreslagna gränserna. Ta bort eventuell väntetid vid fördröjd start och viloläge efter programmet. En lång avslutning med låg effekt kan fortfarande höra till programmet.
6. Kontrollera profilnamnet, bekräfta att hela körningen hör dit och tryck **Spara körning**.

Registrering behöver inte Recorder. Utkastet och dess mätpunkter sparas separat från profilernas körningar. Att stänga webbläsaren avbryter inte insamlingen. Bara ett utkast åt gången tillåts per apparat. Granska eller kasta det innan du börjar ett nytt.

Registreringen kan inte startas mitt i en redan automatiskt registrerad körning. Den körningen kan märkas under **Senaste körningarna**. Under en manuell registrering skapas ingen separat automatisk kopia av samma körning.

## Använd historik

Välj **Använd historik** och ange start- och sluttid för ett avslutat intervall på högst åtta timmar. Intervall och planerat avslut tolkas i **Home Assistants tidszon**, som visas i formuläret. I den upprepade timmen vid vintertidsbyte behöver du välja gränser utanför den tvetydiga timmen. Åtgärdernas ISO-format kan också användas med uttrycklig UTC-offset.

Den konfigurerade effektsensorn måste ingå i aktiv Recorder-lagring och dess detaljerade tillståndshistorik måste finnas kvar. Långtidsstatistik med timmedelvärden ersätter inte minutkurvan. Saknad historik ger ett felmeddelande, aldrig en antagen förbrukning.

Historikflödet använder samma granskning som en ny registrering. Ingen körning läggs till profilen när historiken hämtas.

## Granskning och datakvalitet

- Energin räknas om på servern från de ursprungliga effektövergångarna när start/slut ändras, även inne i en minut. Profilens underlag får en energipost per relativ minut och en eventuell sista delminut.
- Föreslagna gränser börjar vid första effekten över startgränsen och slutar vid vila efter den sista aktiva fasen. De är granskningsförslag, ingen automatisk klassificering av program eller garanti att disken är färdig.
- Numeriskt ogiltiga mätningar och kurvor över 50 kWh blir ofullständigt underlag och kan inte läras in. Ogiltiga värden görs inte om till uppmätt nollförbrukning.
- Kända `unknown`/`unavailable`-tillstånd, ogiltiga enheter, avbrott i lokal sampling längre än tre minuter och kända uppehåll mellan Recorder-körningar behandlas som dataluckor. Markerad energi visas inte som komplett om markeringen innehåller en lucka.
- En lucka utanför själva programmet kan beskäras bort. Ett registreringsutkast som avbrutits av omstart eller byte av effektsensor behålls för granskning men kan inte sparas som komplett. Gör då en ny registrering eller hämta hela programmet från historiken.
- Oväntad avstängning kan förlora de senaste cirka 30 sekunderna av ett pågående utkast. En planerad eller manuell avslutning sparas direkt. Efter omstart återupptas aldrig en pågående registrering automatiskt.
- Ett valt intervall som överlappar en redan sparad körning avvisas. Märk den befintliga körningen i stället. Befintliga mätningar skrivs inte över eller raderas.
- Underlag kortare än två minuter eller under 1 Wh avvisas. Högst 60 000 mätpunkter per utkast och 50 profiler per apparat. Gränsen på åtta timmar gäller både registrering och profilformatet.
- En sensor som visar ett felaktigt men giltigt, oförändrat värde kan inte upptäckas enbart från kurvan. Recorder-uppehåll utan spår i historiken och fysisk mätarnoggrannhet kan inte verifieras av Diskpilot.

Granskningsrutan måste bekräftas igen efter ändrad avgränsning, profil eller profilnamn. Först därefter tillförs körningen profilens medelkurva och kostnadsberäkning. Bekräftelsen kan inte upphäva kända dataluckor eller avbrott.

## Åtgärder

Alla åtgärder använder `entry_id` och ger svar. Tidpunkter anges som ISO 8601 med UTC-offset. Profilnamn och profil-ID fungerar som vid filimport.

| Åtgärd | Övriga indata | Resultat |
|---|---|---|
| `start_registration` | valfritt `end_at` | Startar utkast, returnerar `draft_id` |
| `get_registration` | valfria `draft_id`, `started_at`, `ended_at` | Aktuellt utkast, kurva, energi och kvalitetsuppgifter; sparar inte |
| `stop_registration` | `draft_id` | Avslutar insamlingen och öppnar granskning |
| `discard_registration` | `draft_id` | Tar bort bara detta utkast |
| `history_registration` | `started_at`, `ended_at` | Hämtar granskningsutkast ur Recorder |
| `save_registration` | `draft_id`, `started_at`, `ended_at`, `confirmed: true`, samt `profile_id` eller `name` | Sparar en kontrollerad körning och uppdaterar profilen |

Domän: `dishwasher_optimizer`. Ett gammalt `draft_id` kan inte spara eller kasta ett nyare utkast. Servern räknar och validerar det valda intervallet på nytt vid sparande.
