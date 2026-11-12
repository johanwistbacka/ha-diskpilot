"""Use actual HA 2026.11 classes for storage, services and resource registration."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.components.lovelace.resources import (
    ResourceStorageCollection,
    ResourceYAMLCollection,
)
from homeassistant.core import Context
from homeassistant.exceptions import ServiceValidationError
from homeassistant.util import dt as dt_util

from custom_components.dishwasher_optimizer import _register_services
from custom_components.dishwasher_optimizer.config_flow import validate_settings
from custom_components.dishwasher_optimizer.const import DEFAULTS, DOMAIN
from custom_components.dishwasher_optimizer.engine import Run
from custom_components.dishwasher_optimizer.frontend import CARD_PATH, async_setup_card
from custom_components.dishwasher_optimizer.runtime import Runtime
from custom_components.dishwasher_optimizer.sensor import ProgramSensor, StatusSensor


def entry():
    return SimpleNamespace(
        entry_id="appliance-one",
        title="Diskmaskin",
        domain=DOMAIN,
        data={**DEFAULTS, "power_entity": "sensor.dishwasher_power"},
        options={},
    )


async def test_storage_survives_restart_and_label_correction(hass):
    e = entry()
    hass.states.async_set("sensor.dishwasher_power", "0.3", {"unit_of_measurement": "W"})
    runtime = Runtime(hass, e)
    await runtime.async_start()
    run = Run(1000, 120, [1, 2])
    runtime.runs.append(run)
    await runtime.async_label(run.run_id, "P4", "Program från foto")
    assert runtime.results["P4"]["sample_count"] == 1
    assert runtime.results["P2"]["sample_count"] == 0
    assert runtime.results["P4"]["status"] == "not_configured"
    await runtime.async_stop()

    replacement = Runtime(hass, e)
    await replacement.async_start()
    assert replacement.runs[0].energy_wh == [1, 2]
    assert replacement.runs[0].note == "Program från foto"
    await replacement.async_label(run.run_id, "P2")
    assert replacement.results["P4"]["sample_count"] == 0
    assert replacement.results["P2"]["sample_count"] == 1
    await replacement.async_label(run.run_id, "unassigned")
    assert replacement.results["P2"]["sample_count"] == 0
    await replacement.async_stop()


async def test_active_restart_is_retained_but_excluded_from_training(hass):
    e = entry()
    runtime = Runtime(hass, e)
    await runtime.store.async_save(
        {"runs": [], "active": Run(1000, 120, [1, 2], program="P4").as_dict()}
    )
    await runtime.async_start()
    assert runtime.runs[0].issues == ["interrupted"]
    assert runtime.results["P4"]["sample_count"] == 0
    await runtime.async_stop()


async def test_configurable_price_sensor_and_no_price_extrapolation(hass):
    e = entry()
    e.options = {
        "price_entity": "sensor.contract_price",
        "price_attributes": "next_prices",
        "value_key": "total",
        "price_multiplier": 0.01,
    }
    now = dt_util.utcnow().timestamp()

    def iso(t):
        return dt_util.utc_from_timestamp(t).isoformat()

    hass.states.async_set(
        "sensor.contract_price",
        "100",
        {
            "next_prices": [
                {"start": iso(now - 60), "end": iso(now + 3600), "total": 100},
            ]
        },
    )
    runtime = Runtime(hass, e)
    runtime.runs = [Run(1000, 120, [500, 500], program="P4")]
    await runtime.async_refresh()
    assert runtime.results["P4"]["cost"] == pytest.approx(1)
    assert runtime.results["P4"]["energy_kwh"] == 1
    sensor = ProgramSensor(runtime, "P4")
    assert sensor.native_value == 1
    assert sensor.extra_state_attributes["optimal_start"].endswith("+00:00")
    hass.states.async_set(
        "sensor.contract_price",
        "100",
        {
            "next_prices": [
                {"start": iso(now), "end": iso(now + 30), "total": 100},
            ]
        },
    )
    await runtime.async_refresh()
    assert runtime.results["P4"]["status"] == "insufficient_price_coverage"
    assert ProgramSensor(runtime, "P4").native_value is None
    assert ProgramSensor(runtime, "P2").extra_state_attributes["status"] == "needs_labelled_run"


async def test_kw_conversion_and_unavailable_not_zero(hass):
    runtime = Runtime(hass, entry())
    hass.states.async_set("sensor.dishwasher_power", "0.2", {"unit_of_measurement": "kW"})
    runtime.sample()
    assert runtime.collector.last_w == 200
    assert runtime.collector.active.issues == ["start_not_observed"]
    hass.states.async_set("sensor.dishwasher_power", "unavailable", {"unit_of_measurement": "kW"})
    runtime.sample()
    assert runtime.collector.last_w is None
    assert "missing_data" in runtime.collector.active.issues
    assert StatusSensor(runtime).native_value == "source_unavailable"
    await runtime.store.async_save(runtime.storage_data())


async def test_card_resource_registration_is_idempotent(hass):
    resources = ResourceStorageCollection(
        hass, SimpleNamespace(async_load=AsyncMock(return_value={}))
    )
    hass.data["lovelace"] = SimpleNamespace(resources=resources)
    with patch.object(
        type(hass),
        "http",
        create=True,
        new=SimpleNamespace(async_register_static_paths=AsyncMock()),
    ):
        await async_setup_card(hass)
        assert resources.async_items()[0]["url"].startswith(CARD_PATH)
        assert resources.async_items()[0]["type"] == "module"
        await async_setup_card(hass)
        assert len(resources.async_items()) == 1
        hass.http.async_register_static_paths.assert_awaited_once()


async def test_card_yaml_resources_are_not_overwritten(hass):
    resources = ResourceYAMLCollection([{"url": "/existing.js", "type": "module"}])
    hass.data["lovelace"] = SimpleNamespace(resources=resources)
    with patch.object(
        type(hass),
        "http",
        create=True,
        new=SimpleNamespace(async_register_static_paths=AsyncMock()),
    ):
        await async_setup_card(hass)
    assert resources.async_items() == [{"url": "/existing.js", "type": "module"}]


async def test_real_service_registry_label_import_export(hass):
    e = entry()
    runtime = Runtime(hass, e)
    e.runtime_data = runtime
    _register_services(hass)
    with patch.object(hass.config_entries, "async_get_entry", return_value=e):
        imported = await hass.services.async_call(
            DOMAIN,
            "import_run",
            {
                "entry_id": e.entry_id,
                "started_at": "2026-11-11T23:00:00+01:00",
                "duration_seconds": 120,
                "energy_wh": [1, 2],
                "program": "P4",
            },
            blocking=True,
            return_response=True,
            context=Context(),
        )
        await hass.services.async_call(
            DOMAIN,
            "label_run",
            {
                "entry_id": e.entry_id,
                "run_id": imported["run_id"],
                "program": "P3",
            },
            blocking=True,
        )
        result = await hass.services.async_call(
            DOMAIN,
            "get_runs",
            {
                "entry_id": e.entry_id,
            },
            blocking=True,
            return_response=True,
        )
        assert result["runs"][0]["program"] == "P3"
        assert result["runs"][0]["energy_wh"] == [1, 2]
        with pytest.raises(ServiceValidationError, match="already exists"):
            await hass.services.async_call(
                DOMAIN,
                "import_run",
                {
                    "entry_id": e.entry_id,
                    "started_at": "2026-11-11T23:00:00+01:00",
                    "duration_seconds": 120,
                    "energy_wh": [1, 2],
                },
                blocking=True,
                return_response=True,
            )


async def test_config_rejects_ambiguous_power_units_and_reversed_thresholds(hass):
    config = {**DEFAULTS, "power_entity": "sensor.dishwasher_power"}
    hass.states.async_set("sensor.dishwasher_power", "10", {"unit_of_measurement": "W"})
    assert not validate_settings(hass, config)
    assert validate_settings(hass, {**config, "stop_w": 100})
    hass.states.async_set("sensor.dishwasher_power", "10", {"unit_of_measurement": "kWh"})
    assert validate_settings(hass, config) == {"base": "invalid_power"}


async def test_frequent_measurements_do_not_postpone_storage_forever(hass):
    runtime = Runtime(hass, entry())
    with patch.object(runtime.store, "async_delay_save") as save:
        runtime.schedule_save()
        runtime.schedule_save()
        runtime.schedule_save()
        assert save.call_count == 1
        # Simulate the next checkpoint without sleeping or changing the event loop.
        runtime._last_save_request -= 31
        runtime.schedule_save()
        assert save.call_count == 2
        assert save.call_args.args[1] == 0


async def test_importing_older_history_does_not_hide_newest_runs(hass):
    runtime = Runtime(hass, entry())
    newest = Run(3000, 60, [1])
    runtime.runs = [newest, Run(2000, 60, [1]), Run(1000, 60, [1])]
    assert runtime.summaries()[0]["run_id"] == newest.run_id


async def test_planner_starts_without_meter_and_keeps_imported_profiles(hass):
    e = entry()
    e.data = {**DEFAULTS, "name": "Planerare"}
    assert not validate_settings(hass, e.data)
    runtime = Runtime(hass, e)
    await runtime.store.async_save({"runs": [Run(1000, 120, [1, 2], program="P4").as_dict()]})
    await runtime.async_start()
    assert StatusSensor(runtime).native_value == "planner"
    assert StatusSensor(runtime).extra_state_attributes["measurement_enabled"] is False
    assert runtime.results["P4"]["sample_count"] == 1
    assert runtime.results["P2"]["status"] == "needs_saved_profile"
    assert runtime.collector.active is None
    await runtime.async_stop()


async def test_meter_can_be_added_and_removed_without_losing_profiles(hass):
    e = entry()
    e.data = {**DEFAULTS, "name": "Planerare"}
    hass.states.async_set("sensor.dishwasher_power", "0.3", {"unit_of_measurement": "W"})
    runtime = Runtime(hass, e)
    await runtime.async_start()
    reference = Run(1000, 120, [1, 2], program="P4")
    runtime.runs.append(reference)
    e.options = {"power_entity": "sensor.dishwasher_power"}
    await runtime.async_apply_options(hass, e)
    runtime.sample()
    assert runtime.collector.armed
    runtime.collector.active = Run(2000, 120, [3, 4])
    e.options = {"power_entity": ""}
    await runtime.async_apply_options(hass, e)
    assert StatusSensor(runtime).native_value == "planner"
    assert runtime.collector.active is None
    assert runtime.runs[-1].issues == ["measurement_changed"]
    assert runtime.results["P4"]["sample_count"] == 1
    assert runtime.runs[0].energy_wh == reference.energy_wh
    await runtime.async_stop()


async def test_two_entries_cannot_capture_from_same_meter(hass):
    original = entry()
    config = {**DEFAULTS, "power_entity": "sensor.dishwasher_power"}
    hass.states.async_set("sensor.dishwasher_power", "0.3", {"unit_of_measurement": "W"})
    with patch.object(hass.config_entries, "async_entries", return_value=[original]):
        assert validate_settings(hass, config) == {"base": "power_in_use"}
        assert not validate_settings(hass, config, original.entry_id)
        original.options = {"power_entity": ""}
        assert not validate_settings(hass, config)
