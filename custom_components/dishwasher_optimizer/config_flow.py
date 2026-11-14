"""Set up Diskpilot and select existing local sensors."""

import math

import probatio as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import DEFAULTS, DOMAIN
from .profile_files import profile_name


def settings_schema(values, *, setup=False):
    """Use native selectors; all tariff mappings are explicit."""
    fields = {
        vol.Required(
            "price_source", default=values.get("price_source", "sensor")
        ): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=["sensor", "nordpool_sensor", "nordpool_core"],
                translation_key="price_source",
                mode=selector.SelectSelectorMode.DROPDOWN,
            )
        )
    }
    if setup:
        fields[vol.Required("name", default=values.get("name", "Diskmaskin"))] = str
    fields[
        vol.Optional(
            "power_entity", description={"suggested_value": values.get("power_entity") or None}
        )
    ] = selector.EntitySelector(
        selector.EntitySelectorConfig(domain="sensor", device_class="power")
    )
    fields[
        vol.Optional(
            "energy_entity", description={"suggested_value": values.get("energy_entity") or None}
        )
    ] = selector.EntitySelector(
        selector.EntitySelectorConfig(domain="sensor", device_class="energy")
    )
    if setup:
        fields[
            vol.Optional(
                "price_entity", description={"suggested_value": values.get("price_entity") or None}
            )
        ] = selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor"))
    if setup:
        fields[vol.Optional("profile_names")] = selector.TextSelector(
            selector.TextSelectorConfig(multiline=True)
        )
    if not setup:
        for key in ("start_w", "stop_w"):
            fields[vol.Required(key, default=values[key])] = vol.Coerce(float)
        fields[vol.Required("horizon_hours", default=values["horizon_hours"])] = vol.All(
            vol.Coerce(int), vol.Range(min=1, max=48)
        )
        fields[vol.Required("stop_minutes", default=values["stop_minutes"])] = vol.All(
            vol.Coerce(int), vol.Range(min=2, max=30)
        )
        fields[vol.Required("start_seconds", default=values["start_seconds"])] = vol.All(
            vol.Coerce(int), vol.Range(min=0, max=120)
        )
    return vol.Schema(fields)


def price_schema(values):
    """Show only fields used by the selected price source."""
    mode = values["price_source"]
    fields = {}
    if mode != "nordpool_core":
        fields[
            vol.Optional(
                "price_entity", description={"suggested_value": values.get("price_entity") or None}
            )
        ] = selector.EntitySelector(
            selector.EntitySelectorConfig(
                domain="sensor",
                **({"integration": "nordpool"} if mode == "nordpool_sensor" else {}),
            )
        )
    else:
        fields[
            vol.Required(
                "nordpool_entry",
                # HA's initial-form builder requires a default for this required selector.
                default=values.get("nordpool_entry", ""),
            )
        ] = selector.ConfigEntrySelector(selector.ConfigEntrySelectorConfig(integration="nordpool"))
        fields[vol.Required("nordpool_area", default=values["nordpool_area"])] = str
    fields[vol.Required("currency", default=values["currency"])] = str
    if mode == "sensor":
        for key in ("price_attributes", "start_key", "end_key", "value_key"):
            fields[vol.Required(key, default=values[key])] = str
        fields[vol.Required("price_multiplier", default=values["price_multiplier"])] = vol.Coerce(
            float
        )
    else:
        fields[
            vol.Optional(
                "grid_entry", description={"suggested_value": values.get("grid_entry") or None}
            )
        ] = selector.ConfigEntrySelector(selector.ConfigEntrySelectorConfig(integration="eltariff"))
        fields[vol.Required("contract_markup", default=values["contract_markup"])] = vol.Coerce(
            float
        )
        fields[vol.Required("vat_percent", default=values["vat_percent"])] = vol.Coerce(float)
        if mode == "nordpool_sensor":
            fields[vol.Required("spot_includes_vat", default=values["spot_includes_vat"])] = bool
    return vol.Schema(fields)


def validate_settings(hass, data, entry_id=None, *, prices=True):
    """Check units and parameters, but allow temporarily unavailable sensors."""
    if data.get("power_entity"):
        power = hass.states.get(data["power_entity"])
        if power is None or power.attributes.get("unit_of_measurement") not in ("W", "kW"):
            return {"base": "invalid_power"}
        for existing in hass.config_entries.async_entries(DOMAIN):
            existing_power = existing.options.get("power_entity", existing.data.get("power_entity"))
            if existing.entry_id != entry_id and existing_power == data["power_entity"]:
                return {"base": "power_in_use"}
    if (
        prices
        and data["price_source"] != "nordpool_core"
        and data.get("price_entity")
        and hass.states.get(data["price_entity"]) is None
    ):
        return {"price_entity": "invalid_price"}
    if data.get("energy_entity"):
        energy = hass.states.get(data["energy_entity"])
        if energy is None or energy.attributes.get("unit_of_measurement") not in ("Wh", "kWh"):
            return {"energy_entity": "invalid_energy"}
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
    if data["price_source"] not in ("sensor", "nordpool_sensor", "nordpool_core"):
        return {"base": "invalid_settings"}
    if prices and data["price_source"] != "sensor":
        if (
            not math.isfinite(data["contract_markup"])
            or not math.isfinite(data["vat_percent"])
            or not 0 <= data["vat_percent"] <= 100
            or abs(data["contract_markup"]) > 1000
        ):
            return {"base": "invalid_settings"}
        if data["price_source"] == "nordpool_sensor":
            state = hass.states.get(data["price_entity"])
            if (
                state is None
                or state.attributes.get("unit_of_measurement") != f"{data['currency'].upper()}/kWh"
            ):
                return {"price_entity": "invalid_spot"}
        for key, domain in (("nordpool_entry", "nordpool"), ("grid_entry", "eltariff")):
            if key == "nordpool_entry" and data["price_source"] != "nordpool_core":
                continue
            if key == "grid_entry" and not data[key]:
                continue
            selected = hass.config_entries.async_get_entry(data[key])
            if selected is None or selected.domain != domain:
                return {key: "invalid_source"}
            if domain == "nordpool" and data["nordpool_area"].upper() not in selected.data.get(
                "areas", []
            ):
                return {"nordpool_area": "invalid_area"}
    return {}


class DiskpilotConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Create an appliance planner with optional power collection."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            data = {**DEFAULTS, **user_input}
            errors = validate_settings(self.hass, data, prices=data["price_source"] == "sensor")
            try:
                names = [
                    profile_name(name)
                    for name in data.pop("profile_names", "").splitlines()
                    if name.strip()
                ]
                if len(names) > 50 or len({name.casefold() for name in names}) != len(names):
                    raise ValueError("Invalid profile names")
                data["initial_profile_names"] = names
            except ValueError:
                errors["profile_names"] = "invalid_profiles"
            if not errors:
                if data["price_source"] != "sensor":
                    self._pending = data
                    return await self.async_step_prices()
                return self.async_create_entry(title=data["name"], data=data)
        return self.async_show_form(
            step_id="user", data_schema=settings_schema(user_input or {}, setup=True), errors=errors
        )

    async def async_step_prices(self, user_input=None):
        return await _price_step(self, user_input, options=False)

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
            self._pending = {
                **values,
                **user_input,
                "power_entity": user_input.get("power_entity", ""),
                "energy_entity": user_input.get("energy_entity", ""),
            }
            errors = validate_settings(
                self.hass, self._pending, self.config_entry.entry_id, prices=False
            )
            if not errors:
                return await self.async_step_prices()
        return self.async_show_form(
            step_id="init",
            last_step=False,
            data_schema=settings_schema({**values, **(user_input or {})}),
            errors=errors,
        )

    async def async_step_prices(self, user_input=None):
        return await _price_step(self, user_input, options=True)


async def _price_step(flow, user_input, *, options):
    values = flow._pending
    errors = {}
    if user_input is not None:
        values = {**values, **user_input}
        values["currency"] = values["currency"].upper()
        values["nordpool_area"] = values["nordpool_area"].upper()
        if values["price_source"] != "nordpool_core":
            values["price_entity"] = user_input.get("price_entity", "")
        if values["price_source"] != "sensor":
            values["grid_entry"] = user_input.get("grid_entry", "")
        errors = validate_settings(
            flow.hass, values, flow.config_entry.entry_id if options else None
        )
        if not errors:
            return flow.async_create_entry(title="" if options else values["name"], data=values)
    return flow.async_show_form(step_id="prices", data_schema=price_schema(values), errors=errors)
