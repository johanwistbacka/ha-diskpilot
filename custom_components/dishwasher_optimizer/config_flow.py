"""Set up Diskpilot and select existing local sensors."""

import math

import probatio as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import DEFAULTS, DOMAIN


def settings_schema(values, *, setup=False):
    """Use native selectors; all tariff mappings are explicit."""
    fields = {}
    if setup:
        fields[vol.Required("name", default=values.get("name", "Diskmaskin"))] = str
        fields[vol.Required("power_entity")] = selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor", device_class="power")
        )
    fields[
        vol.Optional(
            "price_entity", description={"suggested_value": values.get("price_entity") or None}
        )
    ] = selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor"))
    if not setup:
        for key in ("price_attributes", "start_key", "end_key", "value_key", "currency"):
            fields[vol.Required(key, default=values[key])] = str
        for key in ("price_multiplier", "start_w", "stop_w"):
            fields[vol.Required(key, default=values[key])] = vol.Coerce(float)
        fields[vol.Required("horizon_hours", default=values["horizon_hours"])] = vol.All(
            vol.Coerce(int), vol.Range(min=1, max=48)
        )
        fields[vol.Required("stop_minutes", default=values["stop_minutes"])] = vol.All(
            vol.Coerce(int), vol.Range(min=2, max=30)
        )
    return vol.Schema(fields)


def validate_settings(hass, data):
    """Check units and parameters, but allow temporarily unavailable sensors."""
    power = hass.states.get(data["power_entity"])
    if power is None or power.attributes.get("unit_of_measurement") not in ("W", "kW"):
        return {"base": "invalid_power"}
    if data.get("price_entity") and hass.states.get(data["price_entity"]) is None:
        return {"price_entity": "invalid_price"}
    if (
        not all(math.isfinite(data[k]) for k in ("price_multiplier", "start_w", "stop_w"))
        or not 0 < data["price_multiplier"] <= 1000
        or not 0 < data["stop_w"] < data["start_w"] <= 50_000
        or not data["currency"].isascii()
        or not data["currency"].isalpha()
        or len(data["currency"]) != 3
        or not all(
            data[k].strip() for k in ("price_attributes", "start_key", "end_key", "value_key")
        )
    ):
        return {"base": "invalid_settings"}
    return {}


class DiskpilotConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Create one collector for each selected power sensor."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            data = {**DEFAULTS, **user_input}
            errors = validate_settings(self.hass, data)
            if not errors:
                await self.async_set_unique_id(data["power_entity"])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=data["name"], data=data)
        return self.async_show_form(
            step_id="user", data_schema=settings_schema(user_input or {}, setup=True), errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Options are applied live so changing prices doesn't interrupt a run."""
        return DiskpilotOptionsFlow()


class DiskpilotOptionsFlow(config_entries.OptionsFlow):
    """Change price inputs and collection thresholds without deleting history."""

    async def async_step_init(self, user_input=None):
        values = {**DEFAULTS, **self.config_entry.data, **self.config_entry.options}
        errors = {}
        if user_input is not None:
            # Omitting the optional entity explicitly disables optimisation.
            user_input = {**user_input, "price_entity": user_input.get("price_entity", "")}
            errors = validate_settings(self.hass, {**values, **user_input})
            if not errors:
                user_input["currency"] = user_input["currency"].upper()
                return self.async_create_entry(title="", data=user_input)
        return self.async_show_form(
            step_id="init",
            data_schema=settings_schema({**values, **(user_input or {})}),
            errors=errors,
        )
