"""Synthetic start candidates, delayed starts and independent energy accounting."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from custom_components.dishwasher_optimizer.config_flow import settings_schema
from custom_components.dishwasher_optimizer.const import DEFAULTS, DOMAIN
from custom_components.dishwasher_optimizer.engine import Collector, Price, cost_at, profile_for
from custom_components.dishwasher_optimizer.runtime import Runtime
from custom_components.dishwasher_optimizer.sensor import StatusSensor


@pytest.mark.parametrize("seconds", [-1, 121])
def test_confirmation_setting_rejects_out_of_range_values(seconds):
    import probatio as vol

    with pytest.raises(vol.Invalid):
        settings_schema(DEFAULTS)({"start_seconds": seconds})


@pytest.mark.parametrize("seconds", [0, 30, 120])
def test_confirmation_setting_accepts_documented_range(seconds):
    assert settings_schema(DEFAULTS)({"start_seconds": seconds})["start_seconds"] == seconds


@pytest.mark.parametrize("hours", [1, 2, 4])
def test_button_spike_then_delayed_start_is_excluded_from_program(hours):
    c = Collector(stop_seconds=120)
    c.sample(0, 0.3)
    c.sample(10, 18.4)
    assert c.candidate and c.active is None
    c.sample(15, 2.4)
    assert c.candidate is None and c.active is None
    start = 15 + hours * 3600
    for t in range(45, start, 30):
        assert c.sample(t, 2.4) is None
        assert c.active is None and c.candidate is None
    c.sample(start, 50)
    c.sample(start + 10, 600)
    assert c.active is None
    c.sample(start + 30, 1200)
    assert c.active.started_at == start
    assert sum(c.active.energy_wh) == pytest.approx((50 * 10 + 600 * 20) / 3600)
    c.sample(start + 60, 1200)
    c.sample(start + 90, 1200)
    c.sample(start + 120, 0.3)
    c.sample(start + 180, 0.3)
    run = c.sample(start + 240, 0.3)
    assert run.started_at == start and run.duration_seconds == 120
    wh = (50 * 10 + 600 * 20 + 1200 * 90) / 3600
    assert sum(run.energy_wh) == pytest.approx(wh)
    assert not run.issues
    run.program = "eco"
    assert cost_at(profile_for([run], "eco"), start, [Price(0, start + 300, 2)]) == pytest.approx(
        wh / 1000 * 2
    )


@pytest.mark.parametrize("confirm", [0, 5, 30, 120])
def test_confirmation_option_keeps_original_start_and_preconfirmation_energy(confirm):
    c = Collector(start_seconds=confirm)
    c.sample(0, 0.3)
    c.sample(10, 100)
    if confirm:
        assert c.candidate and c.active is None
        # Use variable power: confirmation must integrate intervals, not final W x time.
        c.sample(10 + confirm / 2, 200)
        c.sample(10 + confirm, 300)
    assert c.candidate is None and c.active.started_at == 10
    assert sum(c.active.energy_wh) == pytest.approx((100 + 200) * confirm / 2 / 3600)


@pytest.mark.parametrize("duration", [1, 5, 20, 29.9])
def test_short_repeated_spikes_and_exact_start_threshold_never_form_run(duration):
    c = Collector()
    c.sample(0, 0.3)
    for start in (10, 110, 210):
        c.sample(start, 20)
        c.sample(start + duration, 5)  # Confirmation requires strictly above threshold.
        assert c.active is None and c.candidate is None


@pytest.mark.parametrize("value", [None, -1, float("nan"), float("inf")])
def test_invalid_sample_breaks_candidate_and_does_not_bridge_an_unseen_start(value):
    c = Collector()
    c.sample(0, 0.3)
    c.sample(10, 200)
    c.sample(20, value)
    assert c.active is None and c.candidate is None
    c.sample(30, 200)
    c.sample(60, 200)
    assert c.active.started_at == 30
    assert c.active.issues == ["start_not_observed"]


def test_sample_gap_restarts_candidate_without_inventing_energy():
    c = Collector()
    c.sample(0, 0.3)
    c.sample(10, 200)
    c.sample(191, 300)
    assert c.active is None and c.candidate.started_at == 191
    c.sample(221, 400)
    assert c.active.started_at == 191
    assert sum(c.active.energy_wh) == pytest.approx(300 * 30 / 3600)
    assert c.active.issues == ["start_not_observed"]


def test_low_observation_after_a_gap_arms_a_subsequent_observed_start():
    c = Collector()
    c.sample(0, 0.3)
    c.sample(500, 0.3)
    c.sample(510, 200)
    c.sample(540, 200)
    assert not c.active.issues


def test_pause_within_stop_confirmation_is_kept_after_confirmed_start():
    c = Collector(stop_seconds=120)
    c.sample(0, 0.3)
    c.sample(10, 600)
    c.sample(40, 600)
    c.sample(70, 0.3)
    c.sample(130, 0.3)
    c.sample(170, 1200)
    assert c.active and c.pending_end is None
    c.sample(200, 1200)
    c.sample(230, 0.3)
    c.sample(290, 0.3)
    run = c.sample(350, 0.3)
    assert run.duration_seconds == 220
    assert sum(run.energy_wh) == pytest.approx((600 * 60 + 0.3 * 100 + 1200 * 60) / 3600)


BASE = datetime(2026, 1, 1, tzinfo=UTC)


def runtime_entry():
    return SimpleNamespace(
        entry_id="synthetic-confirmation",
        title="Synthetic",
        domain=DOMAIN,
        data={
            **DEFAULTS,
            "power_entity": "sensor.synthetic_power",
            "energy_entity": "sensor.synthetic_energy",
            "stop_minutes": 2,
        },
        options={},
    )


def sample(runtime, hass, seconds, watts, energy=10):
    hass.states.async_set("sensor.synthetic_power", str(watts), {"unit_of_measurement": "W"})
    hass.states.async_set("sensor.synthetic_energy", str(energy), {"unit_of_measurement": "kWh"})
    with patch(
        "custom_components.dishwasher_optimizer.runtime.dt_util.utcnow",
        return_value=BASE + timedelta(seconds=seconds),
    ):
        runtime.sample()


async def test_meter_baseline_is_first_real_candidate_not_discarded_spike_or_confirmation(hass):
    r = Runtime(hass, runtime_entry())
    sample(r, hass, 0, 0.3, 10)
    sample(r, hass, 10, 18, 10.001)
    sample(r, hass, 15, 2.4, 10.002)
    assert r.collector.active is None
    for t in range(45, 316, 30):
        sample(r, hass, t, 2.4, 10.003)
    sample(r, hass, 345, 200, 10.1)
    assert StatusSensor(r).extra_state_attributes["start_pending"] is True
    assert StatusSensor(r).native_value == "idle"
    sample(r, hass, 375, 200, 10.102)
    assert r._energy_start == 10.1
    for t in [405, 435, 465]:
        sample(r, hass, t, 200, 10.108)
    sample(r, hass, 475, 0.3, 10.11)
    sample(r, hass, 535, 0.3, 10.12)
    sample(r, hass, 595, 0.3, 10.13)
    assert len(r.runs) == 1
    run = r.runs[0]
    assert run.duration_seconds == 130
    assert run.meter_energy_kwh == pytest.approx(0.01)
    assert run.meter_note == "available" and not run.issues
    assert sum(run.energy_wh) == pytest.approx(200 * 130 / 3600)
    await r.store.async_save(r.storage_data())


async def test_restart_discards_unconfirmed_candidate_and_marks_recovery_incomplete(hass):
    e = runtime_entry()
    r = Runtime(hass, e)
    sample(r, hass, 0, 0.3)
    sample(r, hass, 10, 200)
    assert r.collector.candidate and r.storage_data()["active"] is None
    await r.store.async_save(r.storage_data())
    restored = Runtime(hass, e)
    with patch(
        "custom_components.dishwasher_optimizer.runtime.dt_util.utcnow",
        return_value=BASE + timedelta(seconds=30),
    ):
        await restored.async_start()
    assert not restored.runs and restored.collector.candidate
    sample(restored, hass, 60, 200)
    assert restored.collector.active.issues == ["start_not_observed"]
    assert restored.collector.active.started_at == (BASE + timedelta(seconds=30)).timestamp()
    await restored.async_stop()


async def test_manual_registration_can_take_over_pending_start_without_creating_run(hass):
    r = Runtime(hass, runtime_entry())
    sample(r, hass, 0, 0.3)
    sample(r, hass, 10, 200)
    with (
        patch(
            "custom_components.dishwasher_optimizer.runtime.dt_util.utcnow",
            return_value=BASE + timedelta(seconds=20),
        ),
        patch(
            "custom_components.dishwasher_optimizer.runtime.async_track_point_in_utc_time",
            return_value=lambda: None,  # This takeover test uses a fixed historic clock.
        ),
    ):
        await r.async_start_registration()
    assert r.registration.stage == "recording"
    assert r.collector.candidate is None and r.collector.active is None
    assert not r.runs
    await r.async_discard_registration(r.registration.draft_id)


async def test_source_change_discards_pending_start_and_meter_baseline(hass):
    e = runtime_entry()
    r = Runtime(hass, e)
    sample(r, hass, 0, 0.3)
    sample(r, hass, 10, 200)
    e.options = {"power_entity": ""}
    await r.async_apply_options(hass, e)
    assert r.collector.candidate is None and r._candidate_energy is None
    assert not r.runs and StatusSensor(r).native_value == "planner"
    await r.store.async_save(r.storage_data())


async def test_old_entry_without_new_option_uses_default_and_does_not_migrate_runs(hass):
    e = runtime_entry()
    e.data.pop("start_seconds")
    r = Runtime(hass, e)
    assert r.config["start_seconds"] == 30
    sample(r, hass, 0, 0.3)
    sample(r, hass, 10, 200)
    saved = r.storage_data()
    assert saved == {"profiles": r.profiles, "runs": [], "active": None, "registration": None}
    await r.store.async_save(saved)


async def test_counter_changed_during_confirmation_does_not_invent_start_reading(hass, monkeypatch):
    # Options bind real HA event listeners; their queued callbacks share this clock.
    monkeypatch.setattr(
        "custom_components.dishwasher_optimizer.runtime.dt_util.utcnow",
        lambda: BASE + timedelta(seconds=20),
    )
    e = runtime_entry()
    r = Runtime(hass, e)
    sample(r, hass, 0, 0.3, 10)
    sample(r, hass, 10, 200, 10)
    e.options = {"energy_entity": "sensor.new_synthetic_energy"}
    hass.states.async_set("sensor.new_synthetic_energy", "20", {"unit_of_measurement": "kWh"})
    await r.async_apply_options(hass, e)
    sample(r, hass, 40, 200, 10.002)
    sample(r, hass, 70, 200, 10.004)
    sample(r, hass, 100, 200, 10.006)
    sample(r, hass, 130, 0.3, 10.008)
    sample(r, hass, 190, 0.3, 10.009)
    sample(r, hass, 250, 0.3, 10.01)
    assert r.runs[0].meter_energy_kwh is None
    assert r.runs[0].meter_note == "missing_reading"
    assert not r.runs[0].issues
    await r.store.async_save(r.storage_data())
