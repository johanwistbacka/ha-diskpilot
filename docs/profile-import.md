# Egna profilfiler

Diskpilot kräver ingen AI-koppling. Du kan skapa CSV/JSON-filer själv, med ett eget verktyg eller frivilligt med en AI-tjänst. [Exempelprompten](../custom_components/dishwasher_optimizer/www/profile-prompt.txt) hjälper till att analysera en historikexport. Samma instruktion och prompt finns via **Profiler och filimport** i kortet.

## Från historik till profil

1. Exportera apparatens effektdata. Ange sensor, enhet, tidszon och de programval du faktiskt känner till.
2. Identifiera kompletta körningar. Behåll kända dataluckor, avbrott och osäkra programetiketter i en separat rapport. Effektkurvan kan föreslå likheter men bevisar inte programnamnet.
3. Beräkna energi per relativ minut. Med effekt i W och tid i sekunder är energin i Wh `effekt × tid / 3600`. Källans verkliga tidsavstånd måste användas. Eventuella antaganden om oförändrade tillstånd ska redovisas.
4. Skapa en fil per bekräftad profil. Flera verkliga körningar kan ingå i samma fil. Exportera inte en medelkurva som om den vore en verklig körning.
5. Öppna **Profiler och filimport** i kortet och välj filen. Kontrollera förhandsgranskningen, välj en befintlig profil eller namnge en ny, bekräfta programetiketten och importera.

Filen behandlas i Home Assistant. Diskpilot skickar inte innehållet till någon AI-tjänst. Den frivilliga prompten är ett arbetsunderlag för en tjänst du själv väljer.

## JSON, version 1

[Ladda ned ett syntetiskt JSON-exempel](../custom_components/dishwasher_optimizer/www/example-profile.json). Exemplet är en formatbeskrivning och innehåller ingen verklig apparatprofil.

```json
{
  "schema_version": 1,
  "profile_name": "Eco",
  "runs": [
    {
      "started_at": "2026-01-01T00:00:00+01:00",
      "duration_seconds": 150,
      "energy_wh": [0.5, 2.0, 0.25],
      "note": "Syntetiskt formatsexempel"
    }
  ]
}
```

- `schema_version` är heltalet `1`. `profile_name` är valfritt i filen och kan anges i kortet.
- `started_at` är körningens verkliga starttid med UTC-offset eller `Z`.
- `duration_seconds` är större än noll och högst 28800 sekunder (8 timmar).
- `energy_wh` är energi i **Wh per minut**, inte effekt i W. Antal poster ska vara `ceil(duration_seconds / 60)`. Den sista posten avser bara återstående delminut.
- `note` är valfri och får vara högst 500 tecken. Inga andra fält stöds i körningsobjekten.
- 1–100 körningar per fil, högst 512 KiB. Alla energivärden ska vara ändliga och icke-negativa. Högst 50000 Wh per körning.

## CSV

[Motsvarande syntetiska CSV-exempel](../custom_components/dishwasher_optimizer/www/example-profile.csv):

```csv
started_at,offset_seconds,interval_seconds,energy_wh
2026-01-01T00:00:00+01:00,0,60,0.5
2026-01-01T00:00:00+01:00,60,60,2.0
2026-01-01T00:00:00+01:00,120,30,0.25
```

Använd UTF-8, kommatecken som avskiljare och punkt som decimaltecken. Rubrikerna måste stämma exakt. Upprepa starttiden på varje rad som hör till körningen. `offset_seconds` är 0, 60, 120 … i ordning. `interval_seconds` är 60 utom för en eventuell sista delminut, som måste vara större än noll och högst 60. Inga luckor eller överlapp accepteras. Flera körningar kan följa efter varandra i samma fil.

En rå Home Assistant-export med exempelvis `entity_id,state,last_changed` är inte detta profilformat. Den måste först analyseras och omvandlas. Filimporten gör ingen automatisk programidentifiering.

## Vad förhandsgranskningen visar

Du ser antal körningar, energi och varaktighetens min/max samt den första körningens minutkurva. Formatkontrollen verifierar struktur och gränsvärden. Den kan inte bevisa att mätaren, programetiketten eller källans tidszon är rätt.

Import lägger till körningar i profilens underlag. Befintliga körningar skrivs inte över. En redan lagrad starttid avvisas även om filen väljs till ett annat profilnamn. Alla körningar valideras innan något sparas; en felaktig fil ger ingen delvis genomförd import.

Du kan skapa nya profiler och byta namn utan att förlora underlaget. Programprofiler och historik ligger lokalt i Home Assistants lagring och följer med vid ändringar av prissensor eller avtal.
