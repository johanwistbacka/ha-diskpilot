"""Synthetic energy tariffs, Nord Pool responses and immutable option transitions."""

import asyncio
from copy import deepcopy
from datetime import date, datetime
from types import SimpleNamespace as NS
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import SupportsResponse

from custom_components.dishwasher_optimizer.config_flow import price_schema, validate_settings
from custom_components.dishwasher_optimizer.const import DEFAULTS
from custom_components.dishwasher_optimizer.engine import Price, Run, cost_at, profile_for
from custom_components.dishwasher_optimizer.price_sources import PriceSources
from custom_components.dishwasher_optimizer.pricing import MarketInputs, grid_prices, source_prices
from custom_components.dishwasher_optimizer.runtime import Runtime

ZONE = ZoneInfo("Europe/Stockholm")
NOW = datetime(2026, 11, 14, 12, tzinfo=ZONE).timestamp()


def period(a=date(2026, 1, 1), b=date(2027, 1, 1)):
    return NS(from_including=a, to_excluding=b)


def component(ref, value, **changes):
    return NS(
        **{
            "reference": ref,
            "valid_period": period(),
            "price": NS(price_inc_vat=value, currency="SEK"),
            "recurring_periods": [],
            "url": None,
            "spot_price_settings": None,
            "priced_period": None,
            "component_type": "fixed",
            "unit": "kWh",
            **changes,
        }
    )


def tariff(*components):
    return NS(
        direction="consumption",
        valid_period=period(),
        energy_price=NS(
            components=list(components) or [component("main", 0.2), component("tax", 0.4)],
            cost_function="sum(energy(c)*price(c))",
        ),
    )


def config(**changes):
    return {
        **DEFAULTS,
        "price_source": "nordpool_sensor",
        "price_entity": "sensor.spot",
        "grid_entry": "grid",
        "contract_markup": 0.08,
        **changes,
    }


def attrs(value=1):
    return {
        "unit_of_measurement": "SEK/kWh",
        "additional_costs_current_hour": 0,
        "raw_today": [
            {
                "start": "2026-11-14T12:00:00+01:00",
                "end": "2026-11-14T12:15:00+01:00",
                "value": value,
            }
        ],
        "raw_tomorrow": [],
    }


def test_hacs_total_price_vat_once_markup_tax_once_and_partial_minute_cost():
    raw = attrs()
    prices, status, basis = source_prices(config(), None, NOW, MarketInputs(raw, tariff(), ZONE))
    assert status == "ok" and prices == [Price(NOW, NOW + 900, pytest.approx(1.68))]
    assert "Eltariff" in basis
    profile = profile_for([Run(0, 90, [10, 5], program="P2")], "P2")
    assert cost_at(profile, NOW, prices) == pytest.approx(0.0252)
    assert raw == attrs()


@pytest.mark.parametrize("mode,expected", [(True, -0.32), (False, -0.57)])
def test_negative_spot_prices_vat_choice_and_discount(mode, expected):
    prices, status, _ = source_prices(
        config(spot_includes_vat=mode), None, NOW, MarketInputs(attrs(-1), tariff(), ZONE)
    )
    assert status == "ok" and prices[0].value == pytest.approx(expected)


def test_core_service_mwh_normalized_before_vat_and_markup():
    data = {
        "prices": [
            {
                "start": "2026-11-14T12:00:00+01:00",
                "end": "2026-11-14T12:15:00+01:00",
                "price": 1000,
            }
        ]
    }
    prices, status, _ = source_prices(
        config(price_source="nordpool_core"), None, NOW, MarketInputs(data, tariff(), ZONE)
    )
    assert status == "ok" and prices[0].value == pytest.approx(1.93)


def test_no_grid_is_explicit_spot_only_not_an_implied_total():
    prices, status, basis = source_prices(config(grid_entry=""), None, NOW, MarketInputs(attrs()))
    assert status == "ok" and prices[0].value == 1.08
    assert "energiskatt ingår inte" in basis


@pytest.mark.parametrize(
    "changes,status",
    [
        ({"recurring_periods": [object()]}, "grid_unsupported"),
        ({"url": "/prices"}, "grid_unsupported"),
        ({"spot_price_settings": object()}, "grid_unsupported"),
        ({"priced_period": "P1M"}, "grid_unsupported"),
        ({"unit": "kW"}, "grid_unsupported"),
        ({"unit": None}, "grid_unsupported"),
        ({"component_type": "peak"}, "grid_unsupported"),
        ({"price": NS(price_inc_vat=0.2, currency="EUR")}, "currency_mismatch"),
        ({"price": NS(price_inc_vat=float("nan"), currency="SEK")}, "grid_unsupported"),
    ],
)
def test_unsupported_grid_never_silently_becomes_a_static_price(changes, status):
    prices, actual, _ = source_prices(
        config(),
        None,
        NOW,
        MarketInputs(
            attrs(), tariff(component("main", 0.2, **changes), component("tax", 0.4)), ZONE
        ),
    )
    assert actual == status and prices == []


def test_sensor_unit_and_existing_fees_are_not_silently_double_counted():
    for changes, expected in [
        ({"unit_of_measurement": "öre/kWh"}, "currency_mismatch"),
        ({"unit_of_measurement": "EUR/kWh"}, "currency_mismatch"),
        ({"additional_costs_current_hour": 0.1}, "spot_includes_fees"),
    ]:
        prices, status, _ = source_prices(
            config(), None, NOW, MarketInputs({**attrs(), **changes}, tariff(), ZONE)
        )
        assert prices == [] and status == expected


def test_tariff_expiry_and_missing_tax_leave_real_gaps():
    boundary = datetime(2026, 11, 15, tzinfo=ZONE).timestamp()
    t = tariff(
        component("main", 0.2), component("tax", 0.4, valid_period=period(b=date(2026, 11, 15)))
    )
    prices = grid_prices(t, ZONE, "SEK", boundary - 900, boundary + 900)
    assert prices == [Price(boundary - 900, boundary, pytest.approx(0.6))]
    assert grid_prices(t, ZONE, "SEK", boundary, boundary + 900) == []
    t.valid_period = period(b=date(2026, 11, 15))
    assert grid_prices(t, ZONE, "SEK", boundary, boundary + 900) == []


def test_published_future_component_switch_splits_at_local_midnight():
    boundary = datetime(2026, 11, 15, tzinfo=ZONE).timestamp()
    t = tariff(
        component("main", 0.2, valid_period=period(b=date(2026, 11, 15))),
        component("main", 0.3, valid_period=period(a=date(2026, 11, 15))),
        component("tax", 0.4),
    )
    prices = grid_prices(t, ZONE, "SEK", boundary - 900, boundary + 900)
    assert [(p.start, p.end, round(p.value, 2)) for p in prices] == [
        (boundary - 900, boundary, 0.6),
        (boundary, boundary + 900, 0.7),
    ]


@pytest.mark.parametrize("day,hours", [(date(2026, 3, 29), 23), (date(2026, 10, 25), 25)])
def test_fixed_rates_cover_real_dst_day_without_hour_assumptions(day, hours):
    a = datetime.combine(day, datetime.min.time(), tzinfo=ZONE).timestamp()
    end_day = date.fromordinal(day.toordinal() + 1)
    b = datetime.combine(end_day, datetime.min.time(), tzinfo=ZONE).timestamp()
    assert b - a == hours * 3600
    assert grid_prices(tariff(), ZONE, "SEK", a, b) == [Price(a, b, pytest.approx(0.6))]


def test_unknown_formula_duplicate_components_and_missing_validity_rejected():
    for t in [
        tariff(component("main", 0.1), component("main", 0.2), component("tax", 0.4)),
        tariff(
            component("main", 0.1, valid_period=NS(from_including=None, to_excluding=None)),
            component("tax", 0.4),
        ),
    ]:
        assert (
            source_prices(config(), None, NOW, MarketInputs(attrs(), t, ZONE))[1]
            == "grid_unsupported"
        )
    t = tariff()
    t.energy_price.cost_function = "tiered(total_energy)"
    assert (
        source_prices(config(), None, NOW, MarketInputs(attrs(), t, ZONE))[1] == "grid_unsupported"
    )


def loaded(domain):
    return NS(domain=domain, state=ConfigEntryState.LOADED, data={"areas": ["SE3"]})


async def test_core_cache_retries_empty_tomorrow_and_expires_without_network_storm(hass):
    calls = []
    clock = [0.0]

    async def response(call):
        calls.append(dict(call.data))
        return {
            "SE3": []
            if len(calls) == 2
            else [{"start": "2026-11-14T12:00Z", "end": "2026-11-14T12:15Z", "price": 1000}]
        }

    hass.services.async_register(
        "nordpool", "get_prices_for_date", response, supports_response=SupportsResponse.ONLY
    )
    reader = PriceSources(hass)
    cfg = config(price_source="nordpool_core", nordpool_entry="np", grid_entry="")
    with (
        patch.object(hass.config_entries, "async_get_entry", return_value=loaded("nordpool")),
        patch(
            "custom_components.dishwasher_optimizer.price_sources.monotonic",
            side_effect=lambda: clock[0],
        ),
    ):
        assert (await reader.read(cfg, NOW)).error is None
        for _ in range(5):
            await reader.read(cfg, NOW)
        assert len(calls) == 2
        clock[0] = 61
        await reader.read(cfg, NOW)
        assert len(calls) == 3
        clock[0] = 901
        await reader.read(cfg, NOW)
        assert len(calls) == 4
    assert calls[0]["date"] == "2026-11-14" and calls[1]["date"] == "2026-11-15"


async def test_core_wrong_shape_and_unloaded_integration_never_publish_stale_cache(hass):
    async def response(call):
        return {"SE3": [5]}

    hass.services.async_register(
        "nordpool", "get_prices_for_date", response, supports_response=SupportsResponse.ONLY
    )
    reader = PriceSources(hass)
    cfg = config(price_source="nordpool_core", nordpool_entry="np", grid_entry="")
    with patch.object(hass.config_entries, "async_get_entry", return_value=loaded("nordpool")):
        assert (await reader.read(cfg, NOW)).error == "invalid_format"
    with patch.object(hass.config_entries, "async_get_entry", return_value=None):
        assert (await reader.read(cfg, NOW)).error == "unavailable"


async def test_grid_data_is_read_from_selected_loaded_entry_and_not_today_power_schedule(hass):
    hass.states.async_set("sensor.spot", "1", attrs())
    t = tariff()
    hass.data["eltariff"] = {
        "grid": NS(
            last_update_success=True,
            local_tz=ZONE,
            data=NS(snapshot=NS(tariff=t)),
            today_schedule=[{"price_inc_vat": 999}],
        )
    }
    reader = PriceSources(hass)
    with patch.object(hass.config_entries, "async_get_entry", return_value=loaded("eltariff")):
        inputs = await reader.read(config(), NOW)
    assert source_prices(config(), None, NOW, inputs)[0][0].value == pytest.approx(1.68)
    hass.data["eltariff"]["grid"].last_update_success = False
    with patch.object(hass.config_entries, "async_get_entry", return_value=loaded("eltariff")):
        assert (await reader.read(config(), NOW)).error == "grid_unavailable"


async def test_config_change_during_await_cannot_publish_old_price_plan(hass):
    entry = NS(entry_id="race", title="Test", data=config(grid_entry=""), options={})
    runtime = Runtime(hass, entry)
    runtime.profiles = {"eco": "Eco"}
    runtime.runs = [Run(0, 60, [10], program="eco")]
    ready, release = asyncio.Event(), asyncio.Event()

    async def delayed(cfg, now):
        ready.set()
        await release.wait()
        return MarketInputs(attrs())

    with patch.object(runtime.price_sources, "read", side_effect=delayed):
        task = asyncio.create_task(runtime.async_refresh())
        await ready.wait()
        runtime.config = {**runtime.config, "contract_markup": 0.5}
        release.set()
        await task
    assert runtime._planning is None and runtime.plan_revision == 0
    before = deepcopy(runtime.storage_data())
    with patch.object(runtime.price_sources, "read", return_value=MarketInputs(attrs())):
        await runtime.async_refresh()
    assert runtime._planning["prices"][0].value == 1.5
    assert runtime.storage_data() == before


def test_price_schema_only_shows_selected_mode_and_legacy_validation_unchanged(hass):
    for mode in ["sensor", "nordpool_sensor", "nordpool_core"]:
        keys = {str(k) for k in price_schema(config(price_source=mode)).schema}
        assert ("price_attributes" in keys) == (mode == "sensor")
        assert ("grid_entry" in keys) == (mode != "sensor")
        assert ("nordpool_entry" in keys) == (mode == "nordpool_core")
        if mode == "nordpool_core":
            entry_key = next(
                k
                for k in price_schema(config(price_source=mode)).schema
                if str(k) == "nordpool_entry"
            )
            assert (
                entry_key.default() == ""
            )  # Required selector must render before any choice exists.
    assert validate_settings(hass, DEFAULTS) == {}
    assert validate_settings(hass, config(grid_entry="")) == {"price_entity": "invalid_price"}
    hass.states.async_set("sensor.spot", "1", attrs())
    assert not validate_settings(hass, config(grid_entry=""))
    assert validate_settings(hass, config(contract_markup=float("nan"), grid_entry="")) == {
        "base": "invalid_settings"
    }


async def test_real_options_flow_preserves_hidden_mapping_then_switches_back(hass, monkeypatch):
    from unittest.mock import AsyncMock

    from homeassistant import loader
    from homeassistant.config_entries import ConfigEntry

    from custom_components.dishwasher_optimizer.const import DOMAIN

    loader.async_setup(hass)
    await hass.config_entries.async_initialize()
    monkeypatch.setattr("homeassistant.config_entries.async_process_deps_reqs", AsyncMock())
    e = ConfigEntry(
        version=1,
        minor_version=1,
        domain=DOMAIN,
        title="Test",
        data={**DEFAULTS, "price_attributes": "custom_prices", "value_key": "total"},
        options={},
        source="user",
        unique_id=None,
        discovery_keys={},
        subentries_data=None,
    )
    np = ConfigEntry(
        version=1,
        minor_version=1,
        domain="nordpool",
        title="NP",
        data={"areas": ["SE3"]},
        options={},
        source="user",
        unique_id=None,
        discovery_keys={},
        subentries_data=None,
    )
    with patch.object(hass.config_entries, "async_setup", new=AsyncMock(return_value=True)):
        await hass.config_entries.async_add(e)
        await hass.config_entries.async_add(np)
    result = await hass.config_entries.options.async_init(e.entry_id)
    assert result["step_id"] == "init"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"price_source": "nordpool_core"}
    )
    assert result["step_id"] == "prices"
    assert not e.options
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "nordpool_entry": np.entry_id,
            "nordpool_area": "SE3",
            "currency": "SEK",
            "contract_markup": -0.03,
            "vat_percent": 25,
        },
    )
    assert result["type"] == "create_entry"
    assert e.options["price_source"] == "nordpool_core"
    assert e.options["contract_markup"] == -0.03
    assert e.options["grid_entry"] == ""
    assert e.options["price_attributes"] == "custom_prices" and e.options["value_key"] == "total"
    result = await hass.config_entries.options.async_init(e.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"price_source": "sensor"}
    )
    assert result["step_id"] == "prices"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "currency": "SEK",
            "price_attributes": "custom_prices",
            "start_key": "start",
            "end_key": "end",
            "value_key": "total",
            "price_multiplier": 1,
        },
    )
    assert result["type"] == "create_entry" and e.options["price_source"] == "sensor"


async def test_setup_nordpool_sensor_keeps_profiles_and_validates_actual_input_units(hass):
    from unittest.mock import AsyncMock

    from homeassistant import loader

    loader.async_setup(hass)
    await hass.config_entries.async_initialize()
    hass.states.async_set("sensor.spot", "1", attrs())
    with (
        patch("homeassistant.config_entries.async_process_deps_reqs", new=AsyncMock()),
        patch.object(hass.config_entries, "async_setup", new=AsyncMock(return_value=True)),
    ):
        result = await hass.config_entries.flow.async_init(
            "dishwasher_optimizer", context={"source": "user"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"name": "Disk", "price_source": "nordpool_sensor", "profile_names": "Eco\nSnabb"},
        )
        assert result["step_id"] == "prices"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "price_entity": "sensor.spot",
                "currency": "SEK",
                "spot_includes_vat": True,
                "vat_percent": 25,
                "contract_markup": 0.1,
            },
        )
        assert result["type"] == "create_entry"
    assert result["data"]["initial_profile_names"] == ["Eco", "Snabb"]
    assert result["data"]["price_source"] == "nordpool_sensor"


async def test_contract_options_invalidate_old_costs_without_mutating_measurements(hass):
    entry = NS(entry_id="contract-switch", title="Test", data=DEFAULTS, options={})
    runtime = Runtime(hass, entry)
    await runtime.async_start()
    runtime.profiles = {"eco": "Eco"}
    runtime.runs = [Run(0, 60, [10], program="eco")]
    runtime.collector.active = Run(NOW, 30, [0.5])
    before = deepcopy(runtime.storage_data())
    runtime.results = {"eco": {"cost": 99}}
    runtime._planning = {"old": True}
    ready, release = asyncio.Event(), asyncio.Event()

    async def delayed(cfg, now):
        ready.set()
        await release.wait()
        return MarketInputs(attrs())

    entry.options = config(grid_entry="", contract_markup=0.5)
    with patch.object(runtime.price_sources, "read", side_effect=delayed):
        task = asyncio.create_task(runtime.async_apply_options(hass, entry))
        await ready.wait()
        assert runtime._planning is None and runtime.results == {}
        assert runtime.price_status == "updating"
        release.set()
        await task
    assert runtime.storage_data() == before
    assert (await runtime.async_get_plan(NOW))["profiles"][0]["selected_cost"] == pytest.approx(
        0.015
    )
    await runtime.async_stop()


async def test_midnight_core_cache_uses_new_local_dates_and_drops_old_keys(hass):
    calls = []

    async def response(call):
        calls.append(call.data["date"])
        return {"SE3": []}

    hass.services.async_register(
        "nordpool", "get_prices_for_date", response, supports_response=SupportsResponse.ONLY
    )
    reader = PriceSources(hass)
    cfg = config(price_source="nordpool_core", nordpool_entry="np", grid_entry="")
    before = datetime(2026, 11, 14, 23, 59, tzinfo=ZONE).timestamp()
    after = datetime(2026, 11, 15, 0, 1, tzinfo=ZONE).timestamp()
    with patch.object(hass.config_entries, "async_get_entry", return_value=loaded("nordpool")):
        await reader.read(cfg, before)
        await reader.read(cfg, after)
    assert calls == ["2026-11-14", "2026-11-15", "2026-11-16"]
    assert {key[-1] for key in reader.cache} == {"2026-11-15", "2026-11-16"}


async def test_core_unload_during_service_await_is_rejected(hass):
    source = loaded("nordpool")

    async def response(call):
        source.state = ConfigEntryState.NOT_LOADED
        return {"SE3": [{"start": "2026-11-14T12:00Z", "end": "2026-11-14T12:15Z", "price": 1000}]}

    hass.services.async_register(
        "nordpool", "get_prices_for_date", response, supports_response=SupportsResponse.ONLY
    )
    reader = PriceSources(hass)
    with patch.object(hass.config_entries, "async_get_entry", return_value=source):
        result = await reader.read(
            config(price_source="nordpool_core", nordpool_entry="np", grid_entry=""), NOW
        )
    assert result.error == "unavailable"
