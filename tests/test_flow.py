"""Run the real config-flow manager with host dependencies already provisioned."""

from unittest.mock import AsyncMock, patch

from homeassistant import loader


async def test_real_config_flow_shows_sensor_selectors_and_rejects_wrong_unit(hass):
    loader.async_setup(hass)
    await hass.config_entries.async_initialize()
    # HTTP/frontend bootstrap is tested separately; this test must not install
    # optional host packages or open a listening port.
    with patch("homeassistant.config_entries.async_process_deps_reqs", new=AsyncMock()):
        result = await hass.config_entries.flow.async_init(
            "dishwasher_optimizer", context={"source": "user"}
        )
    assert result["type"] == "form"
    assert result["step_id"] == "user"
    hass.states.async_set("sensor.wrong", "100", {"unit_of_measurement": "kWh"})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"name": "Test", "power_entity": "sensor.wrong"}
    )
    assert result["type"] == "form"
    assert result["errors"] == {"base": "invalid_power"}
