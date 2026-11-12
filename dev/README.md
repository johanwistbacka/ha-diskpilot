# Lokal Home Assistant för Diskpilot

Starta från projektmappen:

```sh
sh dev/run-local.sh
```

Detta skapar vid behov en separat Python-miljö i `.venv`, installerar Home Assistant 2026.11.1 och startar på **http://127.0.0.1:8124**. Stoppa med Ctrl+C i terminalen där den körs. Miljön använder inte Home Assistants vanliga konfigurationsmapp. Ingen automatisk upptäckt av nätverkets enheter är aktiverad i testkonfigurationen.

Konfiguration, databas, konton och inlärda testprofiler ligger i `private/local-hass`, som inte ingår i Git. Integrationskoden länkas från projektets `custom_components`, så Python-ändringar slår igenom efter omstart. Ändra inställningar för denna instans i dess egen `configuration.yaml`. Mallen i `dev/` skrivs bara dit vid första starten.

Testsensorerna är:

- `sensor.diskpilot_test_power`: effekt från hjälparen `input_number.diskpilot_test_power`.
- `sensor.diskpilot_test_price`: 48 timmars syntetiska kvartspriser, inklusive negativa priser.
- `script.diskpilot_simulate_cycle`: 200 W i 2 minuter och 10 sekunder, följt av 0,3 W. Styr ingen fysisk maskin.

Välj testsensorerna när du lägger till Diskpilot. Prisformatets standardvärden passar testprissensorn. För snabbare manuell provning kan integrationens inställning **Bekräfta viloläge** sättas till två minuter. Då tar en simulerad komplett körning drygt fyra minuter att registrera.

En dashboard med syntetiska programprofiler är en demonstration av integrationen. Testvärden är inte mätningar av användarens diskmaskin och ska inte exporteras till en riktig installations inlärningshistorik. Testmiljön avgör inte heller om en riktig elprissensor använder rätt avtalspris eller om en fysisk effektmätare registrerar hela maskinens last.

Första starten kan behöva hämta Home Assistants komponentberoenden. Python måste finnas på datorn som `python3.14`; annan sökväg kan anges med `DISKPILOT_PYTHON`. En redan förberedd separat Python-miljö kan användas med `DISKPILOT_VENV`.
