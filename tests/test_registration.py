"""Measured integration, review gates, drafts, lifecycle and the actual HA actions."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from homeassistant.exceptions import ServiceValidationError

from custom_components.dishwasher_optimizer import _register_services
from custom_components.dishwasher_optimizer.const import DEFAULTS, DOMAIN
from custom_components.dishwasher_optimizer.engine import Run
from custom_components.dishwasher_optimizer.registration import Registration, history_registration
from custom_components.dishwasher_optimizer.runtime import Runtime

BASE = datetime(2026, 1, 1, tzinfo=UTC)
T = BASE.timestamp()


@pytest.fixture(autouse=True)
def fixed_registration_scheduler():
    """Synthetic January timestamps must not trigger November's real event loop.

    The scheduled callback is exercised separately against the running HA lab.
    """
    with patch(
        "custom_components.dishwasher_optimizer.runtime.async_track_point_in_utc_time",
        return_value=lambda: None,
    ):
        yield


def entry():
    return SimpleNamespace(
        entry_id="registration-test",
        domain=DOMAIN,
        title="Test",
        data={**DEFAULTS, "initial_profile_names": [], "power_entity": "sensor.power"},
        options={},
    )


def now(at):
    return patch(
        "custom_components.dishwasher_optimizer.runtime.dt_util.utcnow",
        return_value=BASE + timedelta(seconds=at),
    )


def sample(hass, runtime, at, value):
    hass.states.async_set("sensor.power", str(value), {"unit_of_measurement": "W"})
    with now(at):
        runtime.sample()


def test_trim_integrates_original_transitions_and_partial_minutes():
    # 20 s waiting; two different powers inside a single output minute.
    draft = Registration(
        "sensor.power",
        0,
        200,
        stage="review",
        points=[[0, 2.4], [20, 120], [50, 240], [140, 0.3], [200, 0.3]],
    )
    assert draft.suggested_bounds(5, 1) == (20, 140)
    run, missing = draft.measure(35, 155)
    assert missing == 0
    assert run.energy_wh == pytest.approx(
        [(15 * 120 + 45 * 240) / 3600, (45 * 240 + 15 * 0.3) / 3600]
    )
    assert run.duration_seconds == 120
    assert Run.from_dict(run.as_dict()).energy_wh == run.energy_wh
    assert draft.points[0] == [0, 2.4]
    snapshot = draft.as_dict()
    snapshot["points"][0][1] = 999
    assert draft.points[0][1] == 2.4


def test_gaps_are_unioned_and_never_reported_as_zero_energy():
    d = Registration(
        "sensor.power",
        0,
        300,
        stage="review",
        points=[[0, 60], [60, None], [120, 120], [300, 0]],
        gaps=[[50, 80], [70, 130]],
    )
    run, missing = d.measure()
    assert missing == 80  # 50..130, not double-counted
    assert sum(run.energy_wh) == pytest.approx((50 * 60 + 170 * 120) / 3600)
    assert d.summary(curve=True)["energy_kwh"] is None
    assert d.measure(130, 300)[1] == 0
    with pytest.raises(ValueError):
        d.measure(-1, 200)
    with pytest.raises(ValueError):
        d.measure(100, 100)


def test_live_gap_deadline_and_no_extrapolation_past_deadline():
    d = Registration("sensor.power", 0, 600, points=[[0, 120]])
    d.sample(30, 120)
    d.sample(240, 120)
    assert d.gaps == [[30, 240]]
    d.sample(300, 120)
    d.sample(600, 0.3)
    d.sample(620, 999)
    assert d.stage == "review" and d.observed_end == 600
    assert d.measure()[1] == 510  # includes the unsampled 300..600 outage


async def test_manual_draft_is_not_training_until_confirmed_and_survives_restart(hass):
    e = entry()
    r = Runtime(hass, e)
    sample(hass, r, 0, 0.3)
    with now(10):
        result = await r.async_start_registration()
    identifier = result["draft_id"]
    for at, power in [
        (40, 2.4),
        (70, 120),
        (100, 120),
        (130, 240),
        (160, 240),
        (190, 240),
        (220, 0.3),
        (250, 0.3),
    ]:
        sample(hass, r, at, power)
    assert r.runs == [] and r.profiles == {}
    with now(260):
        summary = await r.async_stop_registration(identifier)
    assert summary["suggested_start"] == T + 70 and summary["suggested_end"] == T + 220
    with pytest.raises(ValueError, match="granska"):
        await r.async_save_registration(identifier, T + 70, T + 220, name="Eco")
    assert r.profiles == {} and r.runs == []
    # A completed draft restores independently of the current sensor state.
    r2 = Runtime(hass, e)
    with now(270):
        await r2.async_start()
    assert r2.registration.draft_id == identifier
    saved = await r2.async_save_registration(
        identifier, T + 70, T + 220, confirmed=True, name="Eco"
    )
    assert r2.runs[0].duration_seconds == 150
    assert sum(r2.runs[0].energy_wh) == pytest.approx((60 * 120 + 90 * 240) / 3600)
    assert r2.results[saved["profile_id"]]["sample_count"] == 1
    assert r2.registration is None
    with pytest.raises(ValueError, match="ändrats"):
        await r2.async_save_registration(
            identifier, T + 70, T + 220, confirmed=True, name="Dubblett"
        )
    await r2.async_stop()


async def test_restart_of_active_draft_does_not_teach_or_resume(hass):
    e = entry()
    r = Runtime(hass, e)
    sample(hass, r, 0, 0.3)
    with now(10):
        await r.async_start_registration()
    sample(hass, r, 40, 120)
    await r.store.async_save(r.storage_data())
    r2 = Runtime(hass, e)
    with now(60):
        await r2.async_start()
    assert r2.registration.stage == "review" and r2.registration.reason == "interrupted"
    assert r2.runs == [] and r2.profiles == {}
    with pytest.raises(ValueError, match="ofullständig"):
        await r2.async_save_registration(
            r2.registration.draft_id, T + 10, T + 40, confirmed=True, name="Eco"
        )
    await r.async_discard_registration(r.registration.draft_id)
    await r2.async_stop()


async def test_overlaps_and_invalid_targets_never_partially_save(hass):
    r = Runtime(hass, entry())
    d = Registration("sensor.power", T, T + 180, stage="review", points=[[T, 120], [T + 180, 0.3]])
    r.registration = d
    r.runs = [Run(T + 30, 120, [1, 2])]
    with pytest.raises(ValueError, match="överlappar"):
        await r.async_save_registration(d.draft_id, T, T + 180, confirmed=True, name="Eco")
    assert r.registration is d and not r.profiles and len(r.runs) == 1
    r.runs = []
    with pytest.raises(ValueError, match="befintlig"):
        await r.async_save_registration(d.draft_id, T, T + 180, confirmed=True, profile_id="gone")
    with pytest.raises(ValueError):
        await r.async_save_registration(d.draft_id, T, T + 180, confirmed=True, name="  ")
    assert r.runs == [] and r.profiles == {}


async def test_live_requires_available_meter_and_rejects_second_draft(hass):
    r = Runtime(hass, entry())
    with pytest.raises(ValueError, match="effektsensor"):
        await r.async_start_registration()
    sample(hass, r, 0, 0.3)
    with now(10):
        await r.async_start_registration()
    with pytest.raises(ValueError, match="utkast"):
        await r.async_start_registration()
    await r.async_discard_registration(r.registration.draft_id)
    assert r.registration is None and r._registration_timer is None


async def test_scheduled_finish_clips_exactly_and_cancels_timer(hass):
    r = Runtime(hass, entry())
    sample(hass, r, 0, 0.3)
    with now(10):
        await r.async_start_registration(T + 180)
    for at in (40, 70, 100, 130, 160):
        sample(hass, r, at, 120)
    sample(hass, r, 190, 120)
    assert r.registration.stage == "review" and r.registration.observed_end == T + 180
    assert r._registration_timer is None
    assert r.runs == []
    await r.store.async_save(r.storage_data())


async def test_history_optional_missing_recorder_and_future_interval(hass):
    with pytest.raises(ValueError, match="Recorder"):
        await history_registration(hass, "sensor.power", T, T + 180)
    with pytest.raises(ValueError, match="avslutat"):
        await history_registration(hass, "sensor.power", T, T + 9 * 3600)


async def test_real_service_validation_preview_and_confirmed_append(hass):
    e = entry()
    r = e.runtime_data = Runtime(hass, e)
    r.registration = Registration(
        "sensor.power", T, T + 180, stage="review", points=[[T, 120], [T + 180, 0.3]]
    )
    _register_services(hass)

    async def call(service, **data):
        return await hass.services.async_call(
            DOMAIN, service, {"entry_id": e.entry_id, **data}, blocking=True, return_response=True
        )

    with patch.object(hass.config_entries, "async_get_entry", return_value=e):
        preview = await call("get_registration")
        assert preview["energy_kwh"] == 0.006
        assert r.profiles == {} and r.runs == []
        data = {
            "draft_id": r.registration.draft_id,
            "started_at": BASE.isoformat(),
            "ended_at": (BASE + timedelta(seconds=180)).isoformat(),
            "name": "Eco",
        }
        with pytest.raises(ServiceValidationError):
            await call("save_registration", confirmed=False, **data)
        result = await call("save_registration", confirmed=True, **data)
        assert r.results[result["profile_id"]]["sample_count"] == 1
        assert (await call("get_registration"))["stage"] == "none"


async def test_append_to_existing_profile_rebuilds_mean_without_overwriting(hass):
    r = Runtime(hass, entry())
    profile = await r.async_save_profile("Eco")
    r.runs = [Run(T - 86400, 180, [1, 2, 3], program=profile)]
    r.registration = Registration(
        "sensor.power", T, T + 180, stage="review", points=[[T, 240], [T + 180, 0.3]]
    )
    await r.async_save_registration(
        r.registration.draft_id, T, T + 180, confirmed=True, profile_id=profile
    )
    assert list(r.profiles) == [profile]
    assert r.runs[0].energy_wh == [1, 2, 3]
    assert r.results[profile]["sample_count"] == 2
    assert r.results[profile]["energy_kwh"] == pytest.approx(0.009)


async def test_a_gap_blocks_confirmation_but_can_be_trimmed_outside_program(hass):
    r = Runtime(hass, entry())
    r.registration = Registration(
        "sensor.power",
        T,
        T + 300,
        stage="review",
        points=[[T, None], [T + 60, 120], [T + 300, 0.3]],
    )
    identifier = r.registration.draft_id
    with pytest.raises(ValueError, match="ofullständig"):
        await r.async_save_registration(identifier, T, T + 300, confirmed=True, name="Eco")
    assert not r.runs and not r.profiles
    await r.async_save_registration(identifier, T + 60, T + 300, confirmed=True, name="Eco")
    assert r.runs[0].duration_seconds == 240 and not r.runs[0].issues


async def test_changing_meter_finishes_draft_without_blending_sources(hass):
    e = entry()
    r = Runtime(hass, e)
    sample(hass, r, 0, 0.3)
    with now(10):
        await r.async_start_registration()
    sample(hass, r, 40, 120)
    e.options = {"power_entity": "sensor.other"}
    with now(60):
        await r.async_apply_options(hass, e)
    assert r.registration.entity_id == "sensor.power"
    assert r.registration.stage == "review" and r.registration.reason == "measurement_changed"
    assert r._registration_timer is None and not r.runs
    r._state_unsub()


def test_browser_millisecond_boundaries_are_clamped_without_inventing_energy():
    start = T + 0.123456
    d = Registration(
        "sensor.power",
        start,
        start + 180,
        stage="review",
        points=[[start, 120], [start + 180, 0.3]],
    )
    measured, missing = d.measure(T + 0.123, T + 180.123)
    assert measured.started_at == start and measured.duration_seconds == 180
    assert missing == 0 and sum(measured.energy_wh) == pytest.approx(6)
