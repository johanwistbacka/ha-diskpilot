"""Read optional HA integrations, with bounded caching and no independent web client."""

import asyncio
from datetime import timedelta
from time import monotonic

from homeassistant.config_entries import ConfigEntryState
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt as dt_util

from .pricing import MarketInputs


class PriceSources:
    """One appliance's raw Nord Pool service cache; tariffs always use current HA data."""

    def __init__(self, hass):
        self.hass = hass
        self.cache = {}

    def loaded(self, identifier, domain):
        entry = self.hass.config_entries.async_get_entry(identifier)
        return (
            entry
            if entry and entry.domain == domain and entry.state is ConfigEntryState.LOADED
            else None
        )

    async def read(self, config, now):
        """Capture immutable provider-owned tariff models and fresh sensor attributes."""
        mode = config["price_source"]
        attributes = None
        if mode == "nordpool_sensor":
            state = self.hass.states.get(config["price_entity"])
            if state is None or state.state in ("unknown", "unavailable"):
                return MarketInputs(error="unavailable")
            attributes = dict(state.attributes)
        elif mode == "nordpool_core":
            if not self.loaded(config["nordpool_entry"], "nordpool"):
                return MarketInputs(error="unavailable")
            zone = await dt_util.async_get_time_zone(self.hass.config.time_zone)
            if zone is None:
                return MarketInputs(error="invalid_format")
            today = dt_util.utc_from_timestamp(now).astimezone(zone).date()
            rows = []
            success = False
            for day in (today, today + timedelta(days=1)):
                key = (
                    config["nordpool_entry"],
                    config["nordpool_area"],
                    config["currency"],
                    day.isoformat(),
                )
                cached = self.cache.get(key)
                if cached and cached[0] > monotonic():
                    data = cached[1]
                else:
                    try:
                        async with asyncio.timeout(15):
                            result = await self.hass.services.async_call(
                                "nordpool",
                                "get_prices_for_date",
                                {
                                    "config_entry": key[0],
                                    "areas": [key[1]],
                                    "currency": key[2],
                                    "date": key[3],
                                },
                                blocking=True,
                                return_response=True,
                            )
                        data = result.get(key[1]) if isinstance(result, dict) else None
                        if not isinstance(data, list):
                            data = None
                    except HomeAssistantError, TimeoutError, ValueError:
                        data = None
                    self.cache[key] = (monotonic() + (900 if data else 60), data)
                if data is not None:
                    success = True
                    if len(data) > 5000 or any(not isinstance(row, dict) for row in data):
                        return MarketInputs(error="invalid_format")
                    rows.extend(dict(row) for row in data)
            # Bound the cache when dates, area, currency or selected entry change.
            keep = {
                (
                    config["nordpool_entry"],
                    config["nordpool_area"],
                    config["currency"],
                    d.isoformat(),
                )
                for d in (today, today + timedelta(days=1))
            }
            self.cache = {key: value for key, value in self.cache.items() if key in keep}
            if not success:
                return MarketInputs(error="unavailable")
            if not self.loaded(config["nordpool_entry"], "nordpool"):
                return MarketInputs(error="unavailable")
            attributes = {"prices": rows}
        else:
            return MarketInputs(error="invalid_format")
        if not config["grid_entry"]:
            return MarketInputs(attributes=attributes)
        if not self.loaded(config["grid_entry"], "eltariff"):
            return MarketInputs(error="grid_unavailable")
        coordinator = self.hass.data.get("eltariff", {}).get(config["grid_entry"])
        if coordinator is None or not getattr(coordinator, "last_update_success", False):
            return MarketInputs(error="grid_unavailable")
        try:
            return MarketInputs(attributes, coordinator.data.snapshot.tariff, coordinator.local_tz)
        except AttributeError:
            return MarketInputs(error="grid_unsupported")
