"""Exercise the installed HA version without a fixture package pinning older HA."""

import sys
from pathlib import Path

import pytest
from homeassistant.config_entries import ConfigEntries
from homeassistant.core import HomeAssistant
from homeassistant.helpers import frame

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture
async def hass(tmp_path):
    instance = HomeAssistant(str(tmp_path))
    instance.config.time_zone = "Europe/Stockholm"
    frame.async_setup(instance)
    instance.config_entries = ConfigEntries(instance, {})
    yield instance
    await instance.async_stop(force=True)
