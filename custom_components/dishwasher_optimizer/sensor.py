"""Status and one optimal-cost sensor for every program."""

from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.util import dt as dt_util

from .const import DOMAIN, PROGRAMS, VERSION


async def async_setup_entry(hass, entry, async_add_entities):
    runtime = entry.runtime_data
    async_add_entities([StatusSensor(runtime), *(ProgramSensor(runtime, p) for p in PROGRAMS)])


class BaseSensor(SensorEntity):
    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(self, runtime, key, name):
        self.runtime = runtime
        self._attr_unique_id = f"{runtime.entry.entry_id}_{key}"
        self._attr_name = name
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, runtime.entry.entry_id)},
            name=runtime.entry.title,
            manufacturer="Diskpilot",
            model="Local optimiser",
            sw_version=VERSION,
        )

    async def async_added_to_hass(self):
        self.async_on_remove(
            async_dispatcher_connect(self.hass, self.runtime.signal, self.async_write_ha_state)
        )


class StatusSensor(BaseSensor):
    _attr_icon = "mdi:dishwasher"

    def __init__(self, runtime):
        super().__init__(runtime, "status", "Diskpilot")

    @property
    def native_value(self):
        if self.runtime.source_status != "ok":
            return "source_unavailable"
        return "running" if self.runtime.collector.active else "idle"

    @property
    def extra_state_attributes(self):
        return {
            "diskpilot_entry_id": self.runtime.entry.entry_id,
            "price_status": self.runtime.price_status,
            "source_status": self.runtime.source_status,
            "run_count": len(self.runtime.runs),
            "unlabelled_runs": sum(r.program is None for r in self.runtime.runs),
            "recent_runs": self.runtime.summaries(),
            "version": VERSION,
        }


class ProgramSensor(BaseSensor):
    _attr_icon = "mdi:cash-clock"

    def __init__(self, runtime, program):
        super().__init__(runtime, f"{program}_cost", f"{PROGRAMS[program]} kostnad")
        self.program = program

    @property
    def native_value(self):
        value = self.runtime.results.get(self.program, {}).get("cost")
        return round(value, 4) if value is not None else None

    @property
    def native_unit_of_measurement(self):
        return self.runtime.config["currency"]

    @property
    def extra_state_attributes(self):
        result = dict(self.runtime.results.get(self.program, {}))
        for key in ("optimal_start", "optimal_end"):
            value = result.get(key)
            result[key] = (
                dt_util.utc_from_timestamp(value).isoformat() if value is not None else None
            )
        return {
            **result,
            "diskpilot_entry_id": self.runtime.entry.entry_id,
            "program": self.program,
            "program_name": PROGRAMS[self.program],
            "currency": self.native_unit_of_measurement,
            "horizon_hours": self.runtime.config["horizon_hours"],
            "duration_basis": "return_to_standby",
            "profile_quality": "no_data"
            if not result.get("sample_count")
            else "single_run"
            if result["sample_count"] == 1
            else "learning",
        }
