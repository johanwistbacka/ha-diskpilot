"""Data-gap quality, crash recovery and imports racing an integration reload."""

import asyncio
import copy
import json
import math
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from custom_components.dishwasher_optimizer.const import DEFAULTS, DOMAIN
from custom_components.dishwasher_optimizer.engine import Collector, profile_for
from custom_components.dishwasher_optimizer.runtime import Runtime

BASE = datetime(2026, 1, 1, tzinfo=UTC)


def test_gap_returning_at_intermediate_power_must_not_certify_unseen_start():
    c = Collector()
    c.sample(0, 0.3)
    c.sample(10, 200)
    c.sample(200, 2.4)  # 190 seconds missing; last observed candidate never confirmed.
    c.sample(210, 200)
    c.sample(240, 200)
    for t in (270, 300, 330):
        c.sample(t, 200)
    c.sample(360, 0.3)
    for t in range(390, 961, 30):
        completed = c.sample(t, 0.3)
        if completed:
            break
    completed.program = "eco"
    assert profile_for([completed], "eco") is None, (
        "A run with an unobserved initial section after a sampling gap was accepted "
        f"as complete: start={completed.started_at}, issues={completed.issues}"
    )


@pytest.mark.parametrize("returned_watts", [1, 2.4, 5, 200])
@pytest.mark.parametrize("pending_before_gap", [False, True])
def test_gap_requires_fresh_standby_before_a_complete_start(returned_watts, pending_before_gap):
    c = Collector()
    c.sample(0, 0.3)
    c.sample(10, 200 if pending_before_gap else 2.4)
    c.sample(200, returned_watts)
    c.sample(210, 200)
    c.sample(240, 200)
    assert c.active is not None
    assert "start_not_observed" in c.active.issues


@pytest.mark.parametrize("standby", [0.3, 0.6])
def test_observed_standby_after_gap_allows_the_next_complete_start(standby):
    c = Collector()
    c.sample(0, 0.3)
    c.sample(10, 200)
    c.sample(200, 2.4)
    c.sample(210, standby)
    c.sample(220, 200)
    c.sample(250, 200)
    assert c.active.started_at == 220 and not c.active.issues


def test_held_delay_power_at_the_gap_limit_preserves_observed_standby():
    c = Collector()
    c.sample(0, 0.3)
    c.sample(10, 2.4)
    c.sample(190, 2.4)
    c.sample(200, 200)
    c.sample(230, 200)
    assert c.active.started_at == 200 and not c.active.issues


async def test_finished_run_must_eventually_be_written_while_idle(hass):
    entry = SimpleNamespace(
        entry_id="review-persistence",
        domain=DOMAIN,
        title="Synthetic",
        data={**DEFAULTS, "power_entity": "sensor.power", "stop_minutes": 2},
        options={},
    )
    r = Runtime(hass, entry)
    # Advance the write throttle alongside synthetic sensor time without changing
    # the event loop clock: Store's real zero-delay writes still run normally.
    previous = 0
    samples = [
        (0, 0.3),
        (10, 200),
        (30, 201),
        (60, 202),
        (90, 200),
        (120, 201),
        (150, 200),
        (155, 0.3),
        (180, 0.3),
        (210, 0.3),
        (240, 0.3),
        (270, 0.3),
        (275, 0.4),
        (300, 0.4),
        (330, 0.4),
    ]
    for seconds, watts in samples:
        if math.isfinite(r._last_save_request):
            r._last_save_request -= seconds - previous
        previous = seconds
        hass.states.async_set("sensor.power", str(watts), {"unit_of_measurement": "W"})
        with patch(
            "custom_components.dishwasher_optimizer.runtime.dt_util.utcnow",
            return_value=BASE + timedelta(seconds=seconds),
        ):
            r.sample()
        await hass.async_block_till_done()
    assert len(r.runs) == 1 and r.collector.active is None
    path = Path(hass.config.path(".storage", f"{DOMAIN}.{entry.entry_id}"))
    persisted = json.loads(await hass.async_add_executor_job(path.read_text))["data"]
    recovered = Runtime(hass, entry)
    await recovered.async_start()
    recovered_issues = list(recovered.runs[0].issues)
    await recovered.async_stop()
    assert persisted["runs"] == [r.runs[0].as_dict()] and not recovered_issues, (
        f"Final completion never scheduled a write: persisted_runs={len(persisted['runs'])}, "
        f"persisted_active={persisted['active'] is not None}, recovered_issues={recovered_issues}"
    )


@pytest.mark.parametrize("existing_profile", [False, True])
async def test_file_import_finishing_after_unload_must_not_modify_storage(hass, existing_profile):
    entry = SimpleNamespace(
        entry_id="review-unload",
        domain=DOMAIN,
        title="Synthetic",
        data={**DEFAULTS, "initial_profile_names": []},
        options={},
    )
    r = Runtime(hass, entry)
    r._state_unsub = lambda: None
    destination = (
        {"profile_id": await r.async_save_profile("Existing destination")}
        if existing_profile
        else {}
    )
    entered, release = asyncio.Event(), asyncio.Event()
    original = hass.async_add_executor_job

    async def delayed_job(fn, *args):
        if getattr(fn, "__name__", "") == "parse_profile_file":
            entered.set()
            await release.wait()
        return await original(fn, *args)

    content = json.dumps(
        {
            "schema_version": 1,
            "profile_name": "Synthetic",
            "runs": [
                {"started_at": "2026-01-01T00:00:00Z", "duration_seconds": 120, "energy_wh": [1, 2]}
            ],
        }
    )
    with patch.object(hass, "async_add_executor_job", side_effect=delayed_job):
        task = asyncio.create_task(r.async_import_file("synthetic.json", content, **destination))
        await entered.wait()
        await r.async_stop()
        replacement = Runtime(hass, entry)
        await replacement.async_start()
        await replacement.async_save_profile("Newer runtime profile")
        before = copy.deepcopy(await replacement.store.async_load())
        release.set()
        result = await asyncio.gather(task, return_exceptions=True)
        after = await r.store.async_load()
        await replacement.async_stop()
    assert isinstance(result[0], ValueError) and after == before, (
        f"Closed runtime accepted import: result={result}, newer_profile_survived="
        f"{set(before['profiles']) <= set(after['profiles'])}"
    )


async def test_file_import_on_closed_runtime_is_rejected_before_parsing(hass):
    entry = SimpleNamespace(
        entry_id="closed-import", domain=DOMAIN, title="Synthetic", data=DEFAULTS, options={}
    )
    r = Runtime(hass, entry)
    r._state_unsub = lambda: None
    await r.async_stop()
    with (
        patch.object(hass, "async_add_executor_job") as executor,
        pytest.raises(ValueError, match="avstängd"),
    ):
        await r.async_import_file("synthetic.json", "{}")
    executor.assert_not_called()
