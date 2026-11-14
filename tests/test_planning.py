"""Read-only card planning against synthetic minute curves and interval prices."""

from copy import deepcopy
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from homeassistant.exceptions import ServiceValidationError

from custom_components.dishwasher_optimizer import _register_services
from custom_components.dishwasher_optimizer.const import DEFAULTS, DOMAIN
from custom_components.dishwasher_optimizer.engine import Run, cost_at, profile_for
from custom_components.dishwasher_optimizer.planning import planning_view, prepare_plan
from custom_components.dishwasher_optimizer.runtime import Runtime
from custom_components.dishwasher_optimizer.sensor import StatusSensor

NOW = datetime(2026, 11, 14, 10, tzinfo=UTC).timestamp()
CONFIG = {**DEFAULTS, "price_entity": "sensor.price"}


def intervals(gap=False):
    return {
        "prices": [
            {
                "start": datetime.fromtimestamp(NOW - 900, UTC).isoformat(),
                "end": datetime.fromtimestamp(NOW + 900, UTC).isoformat(),
                "value": 2,
            },
            {
                "start": datetime.fromtimestamp(NOW + (1000 if gap else 900), UTC).isoformat(),
                "end": datetime.fromtimestamp(NOW + 3600, UTC).isoformat(),
                "value": -1,
            },
        ]
    }


def runs():
    return [Run(1000, 90, [10, 5], program="eco", note="private note")]


def test_selected_cost_uses_same_engine_partial_minute_and_negative_prices():
    source = runs()
    plan = prepare_plan(source, {"eco": "Eco"}, CONFIG, intervals(), NOW)
    view = planning_view(plan, NOW, NOW + 870)
    row = view["profiles"][0]
    # 30 sec at 2 SEK and 60 sec at -1 SEK, constant 600 W => zero.
    assert row["selected_cost"] == pytest.approx(0)
    assert row["selected_cost"] == cost_at(profile_for(source, "eco"), NOW + 870, plan["prices"])
    assert row["energy_kwh"] == 0.015
    assert row["duration_seconds"] == 90
    assert row["cost"] == -0.015
    assert row["optimal_start"] == NOW + 900
    assert row["selected_end"] == NOW + 960
    assert "private note" not in str(view)
    assert "runs" not in view
    row["energy_wh"][0] = 999
    assert planning_view(plan, NOW, NOW)["profiles"][0]["energy_wh"] == [10, 5]


@pytest.mark.parametrize(
    "attributes,status",
    [(None, "unavailable"), ({}, "no_intervals"), ({"prices": "bad"}, "invalid_format")],
)
def test_absent_prices_leave_curve_without_fabricated_cost(attributes, status):
    plan = prepare_plan(runs(), {"eco": "Eco", "empty": "Empty"}, CONFIG, attributes, NOW)
    view = planning_view(plan, NOW, NOW)
    assert view["price_status"] == status
    assert view["profiles"][0]["selected_cost"] is None
    assert view["profiles"][0]["energy_wh"] == [10, 5]
    assert view["profiles"][1]["status"] == "needs_saved_profile"


def test_gaps_never_become_zero_and_view_does_not_change_optimum():
    plan = prepare_plan(runs(), {"eco": "Eco"}, CONFIG, intervals(True), NOW)
    before = deepcopy(plan)
    view = planning_view(plan, NOW, NOW + 880)
    assert view["profiles"][0]["selected_cost"] is None
    assert len(view["prices"]) == 2
    assert plan == before
    assert view["profiles"][0]["cost"] == -0.015


async def test_runtime_plan_is_transient_without_meter_or_recorder_arrays(hass):
    entry = SimpleNamespace(entry_id="plan", title="Plan", data=CONFIG, options={})
    runtime = Runtime(hass, entry)
    await runtime.async_start()
    runtime.profiles = {"eco": "Eco"}
    runtime.runs = runs()
    hass.states.async_set("sensor.price", "2", intervals())
    with patch(
        "custom_components.dishwasher_optimizer.runtime.dt_util.utcnow",
        return_value=datetime.fromtimestamp(NOW, UTC),
    ):
        await runtime.async_refresh()
        before = deepcopy(runtime.storage_data())
        results = deepcopy(runtime.results)
        view = await runtime.async_get_plan(NOW + 900)
        assert view["profiles"][0]["selected_cost"] == -0.015
        assert (await runtime.async_get_plan())["selected_start"] == NOW
    assert runtime.storage_data() == before
    assert runtime.results == results
    attrs = StatusSensor(runtime).extra_state_attributes
    assert attrs["plan_revision"] == view["revision"]
    assert not {"prices", "energy_wh"} & attrs.keys()
    await runtime.async_stop()
    with pytest.raises(ValueError, match="stäng"):
        await runtime.async_get_plan()


async def test_inflight_read_rejects_unload_and_keeps_snapshot_revision(hass):
    entry = SimpleNamespace(entry_id="plan-race", title="Plan", data=CONFIG, options={})
    runtime = Runtime(hass, entry)
    await runtime.async_start()
    runtime.profiles = {"eco": "Eco"}
    runtime.runs = runs()
    hass.states.async_set("sensor.price", "2", intervals())
    await runtime.async_refresh()
    revision = runtime.plan_revision
    executor = hass.async_add_executor_job

    async def refresh_during_view(func, *args):
        if func is planning_view:
            runtime.plan_revision += 1
        return await executor(func, *args)

    with patch.object(hass, "async_add_executor_job", side_effect=refresh_during_view):
        assert (await runtime.async_get_plan(NOW))["revision"] == revision

    async def unload_during_view(func, *args):
        result = await executor(func, *args)
        runtime._closed = True
        return result

    with patch.object(hass, "async_add_executor_job", side_effect=unload_during_view):
        with pytest.raises(ValueError, match="stäng"):
            await runtime.async_get_plan(NOW)


async def test_service_rejects_naive_start_and_accepts_offset(hass):
    entry = SimpleNamespace(
        entry_id="plan-service", title="Plan", domain=DOMAIN, data=CONFIG, options={}
    )
    entry.runtime_data = Runtime(hass, entry)
    _register_services(hass)
    with patch.object(hass.config_entries, "async_get_entry", return_value=entry):
        with pytest.raises(ServiceValidationError):
            await hass.services.async_call(
                DOMAIN,
                "get_plan",
                {"entry_id": entry.entry_id, "started_at": "2026-11-14T12:00"},
                blocking=True,
                return_response=True,
            )
        result = await hass.services.async_call(
            DOMAIN,
            "get_plan",
            {"entry_id": entry.entry_id, "started_at": "2026-11-14T12:00+01:00"},
            blocking=True,
            return_response=True,
        )
    assert result["selected_start"] == datetime(2026, 11, 14, 11, tzinfo=UTC).timestamp()
