"""Serve the bundled card and register a dashboard resource once."""

import logging
from hashlib import sha256
from pathlib import Path

from homeassistant.components.http import StaticPathConfig
from homeassistant.components.lovelace import DOMAIN as LOVELACE_DOMAIN
from homeassistant.components.lovelace.resources import ResourceStorageCollection

from .const import DOMAIN, VERSION

_LOGGER = logging.getLogger(__name__)
CARD_PATH = f"/{DOMAIN}/diskpilot-card.js"


def _card_revision():
    """Invalidate every module URL when any bundled JavaScript file changes."""
    digest = sha256()
    for name in (
        "diskpilot-card.js",
        "profile-manager.js",
        "profile-registration.js",
        "plan-view.js",
        "plan-data.js",
    ):
        digest.update((Path(__file__).parent / "www" / name).read_bytes())
    return digest.hexdigest()[:16]


async def async_setup_card(hass):
    """Register only our own resource; existing dashboards remain user-controlled."""
    data = hass.data.setdefault(DOMAIN, {})
    if data.get("card_registered"):
        return
    await hass.http.async_register_static_paths(
        [
            StaticPathConfig(
                CARD_PATH,
                str(Path(__file__).parent / "www" / "diskpilot-card.js"),
                False,
            ),
            *[
                StaticPathConfig(
                    f"/{DOMAIN}/{name}",
                    str(Path(__file__).parent / "www" / name),
                    False,
                )
                for name in (
                    "plan-view.js",
                    "plan-data.js",
                    "profile-manager.js",
                    "profile-registration.js",
                    "profile-import.html",
                    "profile-prompt.txt",
                    "example-profile.json",
                    "example-profile.csv",
                )
            ],
        ]
    )
    lovelace = hass.data[LOVELACE_DOMAIN]
    resources = lovelace.resources
    if isinstance(resources, ResourceStorageCollection):
        await resources.async_get_info()
        revision = await hass.async_add_executor_job(_card_revision)
        url = f"{CARD_PATH}?v={VERSION}&rev={revision}"
        item = next(
            (i for i in resources.async_items() if i["url"].split("?")[0] == CARD_PATH),
            None,
        )
        if item is None:
            await resources.async_create_item({"res_type": "module", "url": url})
        elif item["url"] != url:
            await resources.async_update_item(item["id"], {"res_type": "module", "url": url})
    else:
        _LOGGER.info("Add the dashboard module resource %s manually in YAML mode", CARD_PATH)
    data["card_registered"] = True
