"""Release regressions: nonfinite sensors never poison storage; services enforce admin."""

import math
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from homeassistant.core import Context, State
from homeassistant.exceptions import Unauthorized

from custom_components.dishwasher_optimizer import _register_services
from custom_components.dishwasher_optimizer.const import DEFAULTS, DOMAIN
from custom_components.dishwasher_optimizer.engine import Collector, Run, profile_for
from custom_components.dishwasher_optimizer.registration import Registration, power_value
from custom_components.dishwasher_optimizer.runtime import Runtime

BASE = datetime(2026, 1, 1, tzinfo=UTC)
T = BASE.timestamp()


def entry():
    return SimpleNamespace(
        entry_id="release-guards",
        domain=DOMAIN,
        title="Test",
        data={**DEFAULTS, "power_entity": "sensor.power"},
        options={},
    )


@pytest.mark.parametrize("value,unit", [("1e308", "kW"), ("inf", "W"), ("nan", "W"), ("-5", "W")])
def test_invalid_converted_power_is_unknown(value, unit):
    assert power_value(State("sensor.power", value, {"unit_of_measurement": unit})) is None


@pytest.mark.parametrize("watts", [1e308, 50_000])
def test_automatic_extreme_energy_always_obeys_storage_contract(watts):
    collector = Collector(stop_seconds=60)
    collector.sample(0, 0.3)
    collector.sample(10, watts)
    for t in range(40, 3701, 30):
        collector.sample(t, watts)
        assert collector.active is not None
        Run.from_dict(collector.active.as_dict())
    collector.sample(3730, 0.3)
    run = collector.sample(3790, 0.3)
    assert run is not None and "invalid_energy" in run.issues
    assert all(math.isfinite(v) for v in run.energy_wh) and sum(run.energy_wh) <= 50_000
    assert Run.from_dict(run.as_dict()).issues
    run.program = "eco"
    assert profile_for([run], "eco") is None


def test_failed_accumulation_is_atomic():
    run = Run(0, 60, [10])
    before = run.as_dict()
    with pytest.raises(ValueError):
        run.add(60, 180, 1e308)
    assert run.as_dict() == before


async def test_runtime_survives_restart_after_extreme_automatic_measurement(hass):
    e = entry()
    r = Runtime(hass, e)

    def sample(at, value, unit="W"):
        hass.states.async_set("sensor.power", str(value), {"unit_of_measurement": unit})
        with patch(
            "custom_components.dishwasher_optimizer.runtime.dt_util.utcnow",
            return_value=BASE + timedelta(seconds=at),
        ):
            r.sample()

    sample(0, 0.3)
    sample(10, 1e308, "kW")
    assert r.collector.last_w is None
    sample(20, 1e308)
    sample(50, 1e308)
    sample(80, 1e308)
    await r.store.async_save(r.storage_data())
    # Active measurements, as well as completed runs, must load safely.
    restored = Runtime(hass, e)
    with patch(
        "custom_components.dishwasher_optimizer.runtime.dt_util.utcnow",
        return_value=BASE + timedelta(seconds=90),
    ):
        await restored.async_start()
    assert restored.runs and "invalid_energy" in restored.runs[0].issues
    assert all(math.isfinite(v) for run in restored.runs for v in run.energy_wh)
    await restored.async_stop()


async def test_numeric_invalid_registration_can_be_reviewed_but_not_trained(hass):
    r = Runtime(hass, entry())
    r.registration = Registration(
        "sensor.power", T, T + 180, stage="review", points=[[T, 1e308], [T + 180, 0.3]]
    )
    summary = r.registration_summary(curve=True)
    assert summary["energy_kwh"] is None and "invalid_energy" in summary["issues"]
    assert all(math.isfinite(v) for v in summary["energy_wh"])
    with pytest.raises(ValueError, match="ofullständig"):
        await r.async_save_registration(
            r.registration.draft_id, T, T + 180, confirmed=True, name="Eco"
        )
    assert not r.runs
    await r.store.async_save(r.storage_data())
    await r.async_discard_registration(r.registration.draft_id)


CALLS = {
    "get_runs": {},
    "get_plan": {},
    "label_run": {"run_id": "old", "program": "unassigned"},
    "import_run": {"started_at": BASE.isoformat(), "duration_seconds": 120, "energy_wh": [1, 2]},
    "save_profile": {"name": "Eco"},
    "preview_profile_file": {"filename": "x.json", "content": "{}"},
    "import_profile_file": {"filename": "x.json", "content": "{}", "name": "Eco"},
    "get_registration": {},
    "start_registration": {},
    "stop_registration": {"draft_id": "draft"},
    "discard_registration": {"draft_id": "draft"},
    "history_registration": {
        "started_at": BASE.isoformat(),
        "ended_at": (BASE + timedelta(seconds=180)).isoformat(),
    },
    "save_registration": {
        "draft_id": "draft",
        "started_at": BASE.isoformat(),
        "ended_at": (BASE + timedelta(seconds=180)).isoformat(),
        "confirmed": True,
        "name": "Eco",
    },
}


@pytest.mark.parametrize("service", list(CALLS))
@pytest.mark.parametrize("identity", ["denied", "unknown", "admin", "system"])
async def test_all_private_services_require_admin_or_system_context(hass, service, identity):
    e = entry()
    r = e.runtime_data = Runtime(hass, e)
    r.runs = [Run(1000, 120, [1, 2])]
    for name in [
        "async_label",
        "async_get_plan",
        "async_preview_file",
        "async_import_file",
        "async_start_registration",
        "async_stop_registration",
        "async_discard_registration",
        "async_history_registration",
        "async_save_registration",
        "async_refresh",
    ]:
        setattr(r, name, AsyncMock(return_value={"ok": True}))
    r.async_save_profile = AsyncMock(return_value="eco")
    r.registration_summary = Mock(return_value={"draft_id": "draft"})
    r.store.async_save = AsyncMock()
    _register_services(hass)
    user = (
        None
        if identity == "unknown"
        else SimpleNamespace(
            is_admin=identity == "admin",
            permissions=SimpleNamespace(check_entity=lambda *args: False),
        )
    )
    auth = SimpleNamespace(async_get_user=AsyncMock(return_value=user))
    context = Context(user_id=None if identity == "system" else identity)
    before = r.storage_data()
    with (
        patch.object(type(hass), "auth", create=True, new=auth),
        patch.object(hass.config_entries, "async_get_entry", return_value=e),
    ):
        call = hass.services.async_call(
            DOMAIN,
            service,
            {"entry_id": e.entry_id, **CALLS[service]},
            blocking=True,
            return_response=service != "label_run",
            context=context,
        )
        if identity in ("denied", "unknown"):
            with pytest.raises(Unauthorized):
                await call
            assert r.storage_data() == before
            assert not r.store.async_save.called
        else:
            await call
    assert auth.async_get_user.call_count == (0 if identity == "system" else 1)
