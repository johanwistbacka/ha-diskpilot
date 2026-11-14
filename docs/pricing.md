# Priser och avtal

Gäller kommande **0.1.0-beta.6**, ännu inte publicerad. Home Assistant 2026.11 eller senare krävs.

Öppna **Inställningar → Enheter och tjänster → Diskpilot → Konfigurera**. Välj priskälla och tryck **Nästa**. Sparade profiler, märkningar och körningar bevaras när du ändrar avtal. Effekt- och energimätare är fortsatt valfria. Integrationen skapar inga hjälpsensorer.

## Välj priskälla

| Val | Underlag och inställningar |
| --- | --- |
| Färdig totalprislista | Befintligt flöde. Välj en sensor med tidsatta framtida intervall och ange attribut, start/slut, prisfält och omräkning. Diskpilot använder värdena som de är och lägger inte till moms, nätavgift eller påslag. |
| Nord Pool-sensor (HACS) | Välj spotprissensorn från HACS-integrationen Nord Pool. Den ska ha `raw_today`/`raw_tomorrow` med `start`, `end`, `value` och enheten `SEK/kWh` för SEK (motsvarande för annan valuta). Ange om priserna redan innehåller moms. |
| Nord Pool (inbyggd i Home Assistant) | Välj en installerad Nord Pool-integration, ett elområde som är konfigurerat där och valutakod. Diskpilot hämtar idag/imorgon via `nordpool.get_prices_for_date`, räknar om valuta/MWh till valuta/kWh och lägger till vald moms. |

I Nord Pool-lägena kan du välja en installerad **Eltariff-nätkälla** och ange **avtalspåslag inklusive moms**, i valuta/kWh. För SEK är exempelvis ett påslag på 8 öre **0.08**. Det är ett räkneexempel, inte ett förinställt eller verifierat avtalspris. Rabatter kan anges som negativa påslag. Ange påslaget enligt ditt aktuella elhandelsavtal; ett avtalsbyte behöver inte en ny apparat eller nya profiler.

HACS-källan ska innehålla enbart spotpris, med eller utan moms enligt kryssrutan. Ta bort egna extraavgifter i Nord Pool-sensorn innan du använder den här kombinationen. Icke-noll `additional_costs_current_hour` avvisas, men det bevisar inte att en egen framtidsmall är fri från extraavgifter. Välj annars **Färdig totalprislista** för ett redan komplett avtalspris. Detta undviker dubbelräkning.

## Så räknas priset

I Nord Pool-lägena:

**spotpris inklusive moms + Eltariffs nätöverföring och energiskatt inklusive moms + avtalspåslag inklusive moms**.

Moms läggs bara på spotpris som saknar moms. Eltariffs komponentpriser inklusive moms används direkt. Väljer du ingen nätkälla omfattar priset endast spotpris och påslag; kortets programdetaljer visar detta uttryckligen. Fasta månads-/årsavgifter och effektavgifter ingår inte i körkostnaden.

Kostnaden beräknas med profilens uppmätta energi för varje minut, uppdelad vid prisgränser. Negativa priser stöds. Hela körningen måste ha täckning för att få en kostnad och föreslagen billigaste start. Uppgifter som ännu inte publicerats extrapoleras inte. Priskurvan och alla program använder samma sammansatta prislista.

## Eltariffs första stöd

Adaptern använder redan hämtade tariffmodeller i den installerade Eltariff-integrationen. Den är lokalt provad mot **Eltariff 0.5.0**. Inga externa anrop, körbara prisuttryck eller extra paket läggs till av nätadaptern. Om Eltariffs interna modell ändras kan stödet behöva uppdateras; okänt format avvisas.

Denna version stöder fasta energikomponenter med explicita giltighetsdatum, enheten kWh, matchande valuta och den enkla summan av energi × pris. Nätöverföring (`main`) och energiskatt (`tax`) måste båda finnas för intervallet. Publicerade datumbyten inom den valda tariffen stöds, men Diskpilot byter inte automatiskt tariff-ID när ett avtal löper ut.

Tidsstyrda/återkommande eller dynamiska nätenergipriser, spotkopplade nätkomponenter och andra beräkningsformler stöds ännu inte. De ger ett statusmeddelande och ingen kostnad. Eltariffs `today_schedule` och `get_schedule` beskriver effekttariffer och används inte som energiprisprognos. Ett ensamt aktuellt `Energy price total`-sensorvärde projiceras inte över framtiden.

## Uppdatering, felsökning och återgång

Nord Pools inbyggda service anropas genom Home Assistant med högst 15 sekunders väntan per datum. Dagsresultat återanvänds i upp till 15 minuter; tomma/felande svar provas igen efter en minut. Om morgondagen saknas kan dagens täckta körningar fortfarande beräknas. Om den valda integrationen blir otillgänglig visas inga gamla, antagna kostnader som nya priser.

Kontrollera först **Priskälla**, vald integration/elområde, valuta, moms och avtalspåslag. Kontrollera sedan att Eltariff är laddad och har en giltig, stödd energitariff. Ett tydligt fel visas vid saknade källor, fel valuta, avgifter i spotkällan, nätformat som saknar stöd och utgångna giltighetsdatum. Vid avtalsbyte visas att priserna uppdateras medan tidigare kostnader rensas.

Befintliga installationer börjar fortsatt i **Färdig totalprislista**. Ingen datamigrering krävs. Före återgång till beta.5: välj detta läge igen och återställ den tidigare prissensorns attributmappning. Beta.5 känner inte till de nya källvalen. Starta om Home Assistant och ladda om webbläsaren efter kodbyte; profiler och körningar ligger kvar utanför integrationskoden.

## Källor och verifiering

Nord Pool-tjänsten följer [Home Assistants dokumenterade åtgärd](https://www.home-assistant.io/actions/nordpool.get_prices_for_date/). HACS-formatet följer [Nord Pool-sensorns kod](https://github.com/custom-components/nordpool/blob/master/custom_components/nordpool/sensor.py). Nätadaptern läser [Eltariffs tariffmodeller](https://github.com/elden1337/ha-eltariff/tree/main/custom_components/eltariff/api/models) strukturellt. Ingen upstream-kod eller community-profil kopieras; Diskpilots MIT-licens är oförändrad.

Automatiska tester använder syntetiska mätningar. Det lokala provet med verklig Nord Pool och Eltariff visar att kopplingen och beräkningen fungerar i den provade versionen. Det verifierar inte användarens avtalspåslag, faktura eller produktionsinstallation.
