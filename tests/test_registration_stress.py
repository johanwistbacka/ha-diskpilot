"""Independent integration oracle, timer ownership and concurrent user actions."""

import asyncio
import math
import random
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from custom_components.dishwasher_optimizer.const import DEFAULTS, DOMAIN
from custom_components.dishwasher_optimizer.registration import Registration
from custom_components.dishwasher_optimizer.runtime import Runtime

BASE = datetime(2026, 1, 1, tzinfo=UTC)
T = BASE.timestamp()


def appliance():
    return SimpleNamespace(
        entry_id="stress",
        domain=DOMAIN,
        title="Test",
        data={**DEFAULTS, "initial_profile_names": [], "power_entity": "sensor.power"},
        options={},
    )


def at(second):
    return patch(
        "custom_components.dishwasher_optimizer.runtime.dt_util.utcnow",
        return_value=BASE + timedelta(seconds=second),
    )


def oracle(points, gaps, start, end):
    """Intersect each output minute with a partition independent of Run.add."""
    edges = sorted(
        {
            start,
            end,
            *[t for t, _ in points if start < t < end],
            *[t for g in gaps for t in g if start < t < end],
        }
    )
    energy = [0.0] * math.ceil((end - start) / 60)
    missing = 0
    for a, b in zip(edges, edges[1:], strict=False):
        held = next((w for t, w in reversed(points) if t <= a), None)
        if held is None or any(x < b and y > a for x, y in gaps):
            missing += b - a
            continue
        for i in range(len(energy)):
            seconds = max(0, min(b, start + (i + 1) * 60) - max(a, start + i * 60))
            energy[i] += held * seconds / 3600
    return energy, missing


@pytest.mark.parametrize("seed", range(40))
def test_irregular_power_and_gap_curves_against_independent_oracle(seed):
    rng = random.Random(seed)
    origin = T + rng.random()
    duration = rng.uniform(120, 8 * 3600)
    times = sorted([0, duration, *[rng.uniform(0, duration) for _ in range(24)]])
    points = [[origin + t, rng.choice([None, 0.3, 0.6, 2.4, 5, 200, 1800, 2400])] for t in times]
    gaps = []
    for _ in range(4):
        a, b = sorted(rng.sample(times, 2))
        gaps.append([origin + a, origin + b])
    d = Registration(
        "sensor.power", origin, origin + duration, stage="review", points=points, gaps=gaps
    )
    left, right = sorted(rng.sample(times, 2))
    start, end = origin + left, origin + right
    run, missing = d.measure(start, end)
    expected, unknown = oracle(points, gaps, start, end)
    assert missing == pytest.approx(unknown, abs=1e-6), seed
    assert run.energy_wh == pytest.approx(expected, abs=1e-7), seed
    assert len(run.energy_wh) == math.ceil((end - start) / 60)
    assert bool(run.issues) == (unknown > 0)


async def test_old_timer_callback_cannot_touch_replacement_registration(hass):
    callbacks = []
    cancels = []

    def schedule(hass, callback, deadline):
        def cancel():
            pass

        callbacks.append(callback)
        cancels.append(cancel)
        return cancel

    r = Runtime(hass, appliance())
    hass.states.async_set("sensor.power", ".3", {"unit_of_measurement": "W"})
    with patch(
        "custom_components.dishwasher_optimizer.runtime.async_track_point_in_utc_time",
        side_effect=schedule,
    ):
        with at(0):
            first = await r.async_start_registration(T + 60)
        await r.async_discard_registration(first["draft_id"])
        with at(10):
            await r.async_start_registration(T + 120)
        replacement = r.registration
        before = replacement.as_dict()
        with at(60):
            callbacks[0](BASE + timedelta(seconds=60))
        assert replacement.as_dict() == before, "Cancelled timer mutated the next draft"
        assert r._registration_timer is cancels[1], "Cancelled timer stole the next timer's handle"
        await r.async_discard_registration(replacement.draft_id)


async def test_request_waiting_for_lock_cannot_restart_an_unloaded_runtime(hass):
    r = Runtime(hass, appliance())
    hass.states.async_set("sensor.power", ".3", {"unit_of_measurement": "W"})
    r._state_unsub = lambda: None
    await r._registration_lock.acquire()
    with patch(
        "custom_components.dishwasher_optimizer.runtime.async_track_point_in_utc_time",
        return_value=lambda: None,
    ):
        task = asyncio.create_task(r.async_start_registration())
        await asyncio.sleep(0)
        await r.async_stop()
        r._registration_lock.release()
        try:
            with pytest.raises(ValueError, match="(loaded|avstängd)"):
                await task
            assert r.registration is None and r._registration_timer is None
        finally:
            r._cancel_registration_timer()


async def test_two_simultaneous_saves_make_exactly_one_run(hass):
    r = Runtime(hass, appliance())
    r.registration = Registration(
        "sensor.power", T, T + 180, stage="review", points=[[T, 200], [T + 180, 0.3]]
    )
    identifier = r.registration.draft_id
    results = await asyncio.gather(
        *[
            r.async_save_registration(identifier, T, T + 180, confirmed=True, name="Eco")
            for _ in range(2)
        ],
        return_exceptions=True,
    )
    assert sum(isinstance(value, dict) for value in results) == 1
    assert sum(isinstance(value, ValueError) for value in results) == 1
    assert len(r.runs) == len(r.profiles) == 1
    assert next(iter(r.results.values()))["sample_count"] == 1


@pytest.mark.parametrize("end", [T - 1, T, T + 8 * 3600 + 0.01, float("nan"), float("inf")])
async def test_invalid_deadlines_leave_no_draft_or_timer(hass, end):
    r = Runtime(hass, appliance())
    hass.states.async_set("sensor.power", ".3", {"unit_of_measurement": "W"})
    with at(0), pytest.raises(ValueError):
        await r.async_start_registration(end)
    assert r.registration is None and r._registration_timer is None


async def test_two_simultaneous_starts_only_one_session_wins(hass):
    r = Runtime(hass, appliance())
    hass.states.async_set("sensor.power", ".3", {"unit_of_measurement": "W"})
    with (
        at(0),
        patch(
            "custom_components.dishwasher_optimizer.runtime.async_track_point_in_utc_time",
            return_value=lambda: None,
        ),
    ):
        values = await asyncio.gather(
            r.async_start_registration(T + 120),
            r.async_start_registration(T + 120),
            return_exceptions=True,
        )
        assert sum(isinstance(v, dict) for v in values) == 1
        assert sum(isinstance(v, ValueError) for v in values) == 1
        await r.async_discard_registration(r.registration.draft_id)


async def test_history_reply_after_source_changed_does_not_create_a_draft(hass):
    e = appliance()
    r = Runtime(hass, e)
    entered = asyncio.Event()
    release = asyncio.Event()

    async def history(*args):
        entered.set()
        await release.wait()
        return Registration(
            "sensor.power", T, T + 180, stage="review", points=[[T, 200], [T + 180, 0]]
        )

    with patch(
        "custom_components.dishwasher_optimizer.runtime.history_registration", side_effect=history
    ):
        request = asyncio.create_task(r.async_history_registration(T, T + 180))
        await entered.wait()
        e.options = {"power_entity": "sensor.new_power"}
        await r.async_apply_options(hass, e)
        release.set()
        with pytest.raises(ValueError, match="ändrades"):
            await request
    assert r.registration is None and not r.runs and not r.profiles
    r._state_unsub()
