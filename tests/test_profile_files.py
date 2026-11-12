"""File contracts, energy preservation, rejection and optional AI independence."""

import json
from pathlib import Path

import pytest

from custom_components.dishwasher_optimizer.engine import Price, cost_at, profile_for
from custom_components.dishwasher_optimizer.profile_files import parse_profile_file

WWW = Path(__file__).resolve().parents[1] / "custom_components" / "dishwasher_optimizer" / "www"


def payload(**changes):
    run = {
        "started_at": "2026-01-01T00:00:00+01:00",
        "duration_seconds": 150,
        "energy_wh": [0.5, 2, 0.25],
    }
    run.update(changes)
    return {"schema_version": 1, "profile_name": "Eco", "runs": [run]}


def test_documented_csv_and_json_have_identical_energy_and_partial_minute():
    _, json_runs = parse_profile_file("profile.json", (WWW / "example-profile.json").read_text())
    name, csv_runs = parse_profile_file("profile.csv", (WWW / "example-profile.csv").read_text())
    assert name is None
    for run in [*json_runs, *csv_runs]:
        assert run.duration_seconds == 150
        assert run.energy_wh == [0.5, 2, 0.25]
        run.program = "my_profile"
        p = profile_for([run], "my_profile")
        assert cost_at(p, 0, [Price(0, 150, 2)]) == pytest.approx(0.00275 * 2)
    assert json_runs[0].started_at == csv_runs[0].started_at


@pytest.mark.parametrize(
    "changes",
    [
        {"started_at": "2026-01-01T00:00:00"},
        {"duration_seconds": 180.1},
        {"duration_seconds": 0},
        {"duration_seconds": 28801},
        {"energy_wh": [1, -1, 1]},
        {"energy_wh": [1, float("nan"), 1]},
        {"energy_wh": [1, float("inf"), 1]},
        {"energy_wh": [True, 1, 1]},
        {"energy_wh": [1]},
        {"energy_wh": [50001, 1, 1]},
    ],
)
def test_bad_measurements_are_rejected(changes):
    with pytest.raises(ValueError):
        parse_profile_file("profile.json", json.dumps(payload(**changes)))


@pytest.mark.parametrize(
    "content",
    [
        "started_at,offset_seconds,interval_seconds,energy_wh\n2026-01-01T00:00:00Z,60,60,1\n",
        "started_at,offset_seconds,interval_seconds,energy_wh\n2026-01-01T00:00:00Z,0,30,1\n2026-01-01T00:00:00Z,60,60,1\n",
        "started_at,offset_seconds,interval_seconds,energy_wh\n2026-01-01T00:00:00Z,0,61,1\n",
        "entity_id,state,last_changed\nsensor.power,200,2026-01-01T00:00:00Z\n",
    ],
)
def test_raw_history_gaps_and_wrong_intervals_are_not_silently_guessed(content):
    with pytest.raises(ValueError):
        parse_profile_file("profile.csv", content)


def test_multiple_complete_runs_and_duplicate_start_times():
    data = payload()
    data["runs"].append({**data["runs"][0], "started_at": "2026-01-02T00:00:00+01:00"})
    assert len(parse_profile_file("profile.json", json.dumps(data))[1]) == 2
    data["runs"][1]["started_at"] = data["runs"][0]["started_at"]
    with pytest.raises(ValueError, match="samma starttid"):
        parse_profile_file("profile.json", json.dumps(data))


def test_size_limits_are_bytes_and_bom_is_supported():
    with pytest.raises(ValueError, match="512 KiB"):
        parse_profile_file("profile.json", "å" * 300_000)
    assert parse_profile_file("profile.JSON", "\ufeff" + json.dumps(payload()))[0] == "Eco"
    with pytest.raises(ValueError):
        parse_profile_file("profile.txt", json.dumps(payload()))


def test_unclosed_csv_header_quote_is_reported_as_a_validation_error():
    with pytest.raises(ValueError, match="CSV"):
        parse_profile_file("profile.csv", '"started_at,offset_seconds,interval_seconds,energy_wh\n')
