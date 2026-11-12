"""Diskpilot: local dishwasher measurements and tariff optimisation."""

import probatio as vol
from homeassistant.core import SupportsResponse
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN, PROGRAMS
from .engine import Run, timestamp
from .frontend import async_setup_card
from .runtime import Runtime

PLATFORMS = ["sensor"]


async def async_setup_entry(hass, entry):
    """Set up a collector, its sensors and the shared card."""
    runtime = Runtime(hass, entry)
    entry.runtime_data = runtime
    await runtime.async_start()
    try:
        await async_setup_card(hass)
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except Exception:
        await runtime.async_stop()
        raise
    entry.async_on_unload(entry.add_update_listener(runtime.async_apply_options))
    if not hass.services.has_service(DOMAIN, "get_runs"):
        _register_services(hass)
    return True


async def async_unload_entry(hass, entry):
    if await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await entry.runtime_data.async_stop()
        return True
    return False


def _register_services(hass):
    def runtime_for(call):
        entry = hass.config_entries.async_get_entry(call.data["entry_id"])
        if entry is None or entry.domain != DOMAIN or not getattr(entry, "runtime_data", None):
            raise ServiceValidationError("Diskpilot is not loaded")
        runtime = entry.runtime_data
        if runtime._closed:
            raise ServiceValidationError("Diskpilot is not loaded")
        return runtime

    async def get_runs(call):
        runtime = runtime_for(call)
        offset, limit = call.data["offset"], call.data["limit"]
        runs = sorted(runtime.runs, key=lambda run: run.started_at, reverse=True)
        return {"total": len(runs), "runs": [r.as_dict() for r in runs[offset : offset + limit]]}

    async def label_run(call):
        try:
            await runtime_for(call).async_label(
                call.data["run_id"], call.data["program"], call.data.get("note")
            )
        except ValueError as err:
            raise ServiceValidationError(str(err)) from err

    async def import_run(call):
        runtime = runtime_for(call)
        try:
            run = Run.from_dict(
                Run(
                    started_at=timestamp(call.data["started_at"]),
                    duration_seconds=call.data["duration_seconds"],
                    energy_wh=call.data["energy_wh"],
                    program=call.data.get("program"),
                    note=call.data.get("note", ""),
                    source="import",
                ).as_dict()
            )
        except (ValueError, TypeError, OverflowError) as err:
            raise ServiceValidationError(str(err)) from err
        if any(abs(r.started_at - run.started_at) < 1 for r in runtime.runs):
            raise ServiceValidationError("A run already exists at this start time")
        runtime.runs.append(run)
        await runtime.store.async_save(runtime.storage_data())
        await runtime.async_refresh()
        return {"run_id": run.run_id}

    base = {vol.Required("entry_id"): str}
    hass.services.async_register(
        DOMAIN,
        "get_runs",
        get_runs,
        schema=vol.Schema(
            {
                **base,
                vol.Optional("offset", default=0): vol.All(vol.Coerce(int), vol.Range(min=0)),
                vol.Optional("limit", default=10): vol.All(
                    vol.Coerce(int), vol.Range(min=1, max=100)
                ),
            }
        ),
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        "label_run",
        label_run,
        schema=vol.Schema(
            {
                **base,
                vol.Required("run_id"): str,
                vol.Required("program"): vol.In([*PROGRAMS, "unassigned"]),
                vol.Optional("note"): vol.All(str, vol.Length(max=500)),
            }
        ),
    )
    hass.services.async_register(
        DOMAIN,
        "import_run",
        import_run,
        schema=vol.Schema(
            {
                **base,
                vol.Required("started_at"): str,
                vol.Required("duration_seconds"): vol.Coerce(float),
                vol.Required("energy_wh"): vol.All(
                    cv.ensure_list, [vol.Coerce(float)], vol.Length(min=1, max=480)
                ),
                vol.Optional("program"): vol.In(list(PROGRAMS)),
                vol.Optional("note"): vol.All(str, vol.Length(max=500)),
            }
        ),
        supports_response=SupportsResponse.ONLY,
    )
