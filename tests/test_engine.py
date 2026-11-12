"""Energy conservation, ambiguous data and actual price boundary regressions."""

from dataclasses import replace

import pytest

from custom_components.dishwasher_optimizer.const import DEFAULTS
from custom_components.dishwasher_optimizer.engine import (
    Collector,
    Price,
    Profile,
    Run,
    cost_at,
    optimise,
    parse_prices,
    profile_for,
    timestamp,
)


def test_energy_conservation_with_irregular_samples():
    run = Run(1000)
    run.add(1000, 1027, 100)
    run.add(1027, 1129, 200)
    assert sum(run.energy_wh) == pytest.approx((27 * 100 + 102 * 200) / 3600)
    assert len(run.energy_wh) == 3
    assert run.energy_wh[0] == pytest.approx((27 * 100 + 33 * 200) / 3600)
    assert Run.from_dict(run.as_dict()).energy_wh == run.energy_wh


def test_zero_order_hold_and_trim_confirmation_period():
    collector = Collector(stop_seconds=120)
    collector.sample(0, 0.3)
    collector.sample(10, 200)
    for at in range(40, 611, 30):
        collector.sample(at, 200)
    collector.sample(610, 0.3)  # same timestamp is deliberately ignored
    collector.sample(620, 0.3)
    collector.sample(680, 0.3)
    run = collector.sample(740, 0.3)
    assert run and run.duration_seconds == 610
    assert sum(run.energy_wh) == pytest.approx(200 * 610 / 3600)
    assert not run.issues


def test_low_power_tail_is_kept_and_does_not_split_run():
    collector = Collector(stop_seconds=120)
    collector.sample(0, 0)
    collector.sample(10, 100)
    for at in range(40, 311, 30):
        collector.sample(at, 100)
    collector.sample(320, 3)
    for at in range(350, 901, 30):
        collector.sample(at, 3)
    collector.sample(920, 0.3)
    collector.sample(980, 0.3)
    run = collector.sample(1040, 0.3)
    assert run.duration_seconds == 910
    assert sum(run.energy_wh) == pytest.approx((310 * 100 + 600 * 3) / 3600)


def test_unavailable_data_and_restart_are_not_training_data():
    collector = Collector(stop_seconds=120)
    collector.sample(0, 100)  # Start was not observed.
    collector.sample(60, 100)
    collector.sample(120, None)
    collector.sample(180, 100)
    collector.sample(240, 0)
    collector.sample(300, 0)
    run = collector.sample(360, 0)
    run.program = "P4"
    assert set(run.issues) == {"missing_data", "start_not_observed"}
    assert sum(run.energy_wh) == pytest.approx(100 * 180 / 3600)
    assert profile_for([run], "P4") is None


def test_unknown_resets_stop_confirmation():
    c = Collector(stop_seconds=120)
    c.sample(0, 0)
    c.sample(10, 100)
    for at in range(40, 311, 30):
        c.sample(at, 100)
    c.sample(320, 0)
    c.sample(380, None)
    assert c.sample(440, 0) is None
    assert c.sample(500, 0) is None
    assert c.sample(560, 0) is not None


def test_excessively_long_run_does_not_restart_until_idle():
    c = Collector()
    c.sample(0, 0)
    c.sample(10, 100)
    finished = None
    for at in range(40, 29_011, 30):
        run = c.sample(at, 100)
        finished = run or finished
    assert finished.issues == ["maximum_duration"]
    assert c.active is None


def test_labels_are_reversible_and_mean_preserves_energy():
    a = Run(0, 60, [1], program="P4")
    b = Run(1000, 120, [2, 3], program="P4")
    unknown = Run(2000, 60, [900])
    profile = profile_for([a, b, unknown], "P4")
    assert profile.count == 2
    assert profile.energy_wh == (1.5, 1.5)
    assert sum(profile.energy_wh) == (sum(a.energy_wh) + sum(b.energy_wh)) / 2
    b.program = "P2"
    assert profile_for([a, b], "P4").energy_wh == (1.0,)


def test_cost_splits_minute_at_price_boundary_and_accepts_negative_prices():
    profile = Profile((1000,), 60, 1, 1, 1)
    prices = [Price(0, 30, 2), Price(30, 90, -1)]
    assert cost_at(profile, 0, prices) == pytest.approx(0.5)
    assert cost_at(profile, 30, prices) == -1
    assert cost_at(profile, 31, prices) is None
    assert optimise(profile, 0, 120, prices)["optimal_start"] == 0


def test_optimal_start_uses_whole_profile_not_cheapest_first_quarter():
    profile = Profile((0, 1000), 120, 1, 1, 1)
    prices = [Price(0, 60, -10), Price(60, 120, 10), Price(120, 240, 1)]
    result = optimise(profile, 0, 240, prices)
    assert result["optimal_start"] == 60
    assert result["cost"] == 1
    assert result["cost_now"] == 10
    assert result["saving"] == 9


def test_full_coverage_is_required_even_during_zero_power():
    profile = Profile((0, 1000), 120, 1, 1, 1)
    assert cost_at(profile, 0, [Price(60, 120, 1)]) is None
    assert cost_at(profile, 0, [Price(0, 30, 1), Price(60, 120, 1)]) is None
    assert optimise(profile, 0, 60, [Price(0, 3600, 1)])["cost"] is None


def test_partial_last_minute_is_not_charged_as_full_minute():
    profile = Profile((1000, 500), 90, 1, 1.5, 1.5)
    assert cost_at(profile, 0, [Price(0, 60, 1), Price(60, 90, 2)]) == 2


def test_price_mapping_units_and_daylight_saving_offsets():
    config = {**DEFAULTS, "price_attributes": "raw_today,raw_tomorrow", "price_multiplier": 0.01}
    prices = parse_prices(
        {
            "raw_today": [
                {
                    "start": "2026-10-25T02:00:00+02:00",
                    "end": "2026-10-25T02:00:00+01:00",
                    "value": -50,
                },
            ]
        },
        config,
    )
    assert prices[0].end - prices[0].start == 3600
    assert prices[0].value == -0.5
    with pytest.raises(ValueError):
        timestamp("2026-10-25T02:00:00")
    with pytest.raises(ValueError):
        parse_prices(
            {
                "raw_today": [
                    {
                        "start": "2026-11-01T00:00:00Z",
                        "end": "2026-11-01T00:15:00Z",
                        "value": float("nan"),
                    }
                ]
            },
            config,
        )


def test_reject_overlap_and_invalid_import():
    rows = [{"start": "2026-11-01T00:00:00Z", "end": "2026-11-01T00:15:00Z", "value": 1}]
    with pytest.raises(ValueError, match="Overlapping"):
        parse_prices({"prices": rows * 2}, DEFAULTS)
    for run in [Run(0, 120, [1]), Run(0, 60, [-1]), Run(0, 60, [float("inf")])]:
        with pytest.raises(ValueError):
            Run.from_dict(run.as_dict())


def test_cost_constant_tariff_reconciles_with_total_energy():
    profile = Profile((1, 2, 3, 0.25), 195, 1, 0, 0)
    for start in (0, 17, 61, 123.5):
        assert cost_at(profile, start, [Price(0, 1000, 3)]) == pytest.approx(0.00625 * 3)
    assert cost_at(replace(profile, count=9), 0, [Price(0, 1000, 3)]) == pytest.approx(0.01875)
