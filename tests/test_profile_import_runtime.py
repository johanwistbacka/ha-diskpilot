"""Preview is read-only, batch imports are validated and profile IDs survive edits."""

import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from custom_components.dishwasher_optimizer.const import DEFAULTS, DOMAIN
from custom_components.dishwasher_optimizer.runtime import Runtime
from custom_components.dishwasher_optimizer.sensor import ProgramSensor


def entry(names=None):
    return SimpleNamespace(
        entry_id="custom-profiles",
        title="Apparat",
        domain=DOMAIN,
        data={**DEFAULTS, "initial_profile_names": names or []},
        options={},
    )


def content(start="2026-01-01T00:00:00Z"):
    return json.dumps(
        {
            "schema_version": 1,
            "profile_name": "Mitt Eco",
            "runs": [
                {
                    "started_at": start,
                    "duration_seconds": 150,
                    "energy_wh": [0.5, 2, 0.25],
                }
            ],
        }
    )


async def test_new_install_has_user_named_profiles_and_stable_ids_after_restart(hass):
    e = entry(["Snabb 30", "Eco tyst"])
    runtime = Runtime(hass, e)
    await runtime.async_start()
    expected = dict(runtime.profiles)
    assert list(expected.values()) == ["Snabb 30", "Eco tyst"]
    assert not {"P2", "P3", "P4"} & expected.keys()
    await runtime.async_stop()
    restored = Runtime(hass, e)
    await restored.async_start()
    assert restored.profiles == expected
    await restored.async_stop()


async def test_file_preview_never_creates_profile_or_measurements(hass):
    runtime = Runtime(hass, entry())
    await runtime.async_start()
    preview = await runtime.async_preview_file("profile.json", content())
    assert preview["run_count"] == 1
    assert preview["energy_mean_kwh"] == 0.00275
    assert preview["duration_min_minutes"] == 2.5
    assert runtime.profiles == {} and runtime.runs == []
    await runtime.async_stop()


async def test_import_rename_append_and_restart_preserve_id_and_energy(hass):
    e = entry()
    runtime = Runtime(hass, e)
    await runtime.async_start()
    imported = await runtime.async_import_file("profile.json", content())
    identifier = imported["profile_id"]
    sensor = ProgramSensor(runtime, identifier)
    unique_id = sensor.unique_id
    assert runtime.profiles[identifier] == "Mitt Eco"
    assert runtime.results[identifier]["energy_kwh"] == 0.00275
    await runtime.async_save_profile("Eco med eget namn", identifier)
    assert sensor.unique_id == unique_id
    assert sensor.name == "Eco med eget namn kostnad"
    await runtime.async_import_file(
        "profile.json", content("2026-01-02T00:00:00Z"), profile_id=identifier
    )
    assert runtime.results[identifier]["sample_count"] == 2
    await runtime.async_stop()
    restored = Runtime(hass, e)
    await restored.async_start()
    assert restored.profiles == {identifier: "Eco med eget namn"}
    assert [r.energy_wh for r in restored.runs] == [[0.5, 2, 0.25]] * 2
    assert restored.results[identifier]["sample_count"] == 2
    await restored.async_stop()


async def test_invalid_batch_and_duplicate_do_not_partially_modify_history(hass):
    runtime = Runtime(hass, entry())
    await runtime.async_start()
    data = json.loads(content())
    data["runs"].append(
        {"started_at": "2026-01-02T00:00:00Z", "duration_seconds": 60, "energy_wh": [-1]}
    )
    with pytest.raises(ValueError):
        await runtime.async_import_file("bad.json", json.dumps(data))
    assert runtime.runs == [] and runtime.profiles == {}
    result = await runtime.async_import_file("good.json", content())
    before = runtime.storage_data()
    with pytest.raises(ValueError, match="samma starttid"):
        await runtime.async_import_file(
            "duplicate.json", content(), profile_id=result["profile_id"]
        )
    assert runtime.storage_data() == before
    with pytest.raises(ValueError):
        await runtime.async_save_profile("  ")
    with pytest.raises(ValueError):
        await runtime.async_save_profile("mitt eco")
    await runtime.async_stop()


@pytest.mark.parametrize(
    "end_reading,expected,status", [(100.01, 0.01, "available"), (5, None, "counter_reset")]
)
async def test_optional_energy_counter_uses_first_standby_and_preserves_power_curve(
    hass, end_reading, expected, status
):
    e = entry()
    e.data.update(power_entity="sensor.power", energy_entity="sensor.energy", stop_minutes=2)
    runtime = Runtime(hass, e)
    base = datetime(2026, 1, 1, tzinfo=UTC)

    def sample(at, power, energy):
        hass.states.async_set("sensor.power", str(power), {"unit_of_measurement": "W"})
        hass.states.async_set("sensor.energy", str(energy), {"unit_of_measurement": "kWh"})
        with patch(
            "custom_components.dishwasher_optimizer.runtime.dt_util.utcnow",
            return_value=base + timedelta(seconds=at),
        ):
            runtime.sample()

    sample(0, 0.3, 100)
    sample(10, 200, 100)
    for at in (40, 70, 100, 130):
        sample(at, 200, 100)
    sample(140, 0.3, end_reading)
    sample(200, 0.3, end_reading + 0.1)
    sample(260, 0.3, end_reading + 0.2)
    run = runtime.runs[0]
    assert run.duration_seconds == 130
    assert sum(run.energy_wh) == pytest.approx(200 * 130 / 3600)
    assert run.meter_note == status
    assert not run.issues
    if expected is None:
        assert run.meter_energy_kwh is None
    else:
        assert run.meter_energy_kwh == pytest.approx(expected)
    await runtime.store.async_save(runtime.storage_data())
