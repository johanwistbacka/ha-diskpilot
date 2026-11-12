"""Validated HA actions for one private, reviewable draft per appliance."""

import probatio as vol
from homeassistant.core import SupportsResponse
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.service import async_register_admin_service

from .const import DOMAIN
from .engine import timestamp


def register_registration_services(hass, runtime_for):
    base = {vol.Required("entry_id"): str}
    draft = {**base, vol.Required("draft_id"): str}
    bounds = {vol.Required("started_at"): str, vol.Required("ended_at"): str}

    async def get(call):
        runtime = runtime_for(call)
        if "draft_id" in call.data:
            runtime._draft(call.data["draft_id"])
        return runtime.registration_summary(
            curve=True,
            start=timestamp(call.data["started_at"]) if "started_at" in call.data else None,
            end=timestamp(call.data["ended_at"]) if "ended_at" in call.data else None,
        ) or {"stage": "none"}

    async def start(call):
        return await runtime_for(call).async_start_registration(
            timestamp(call.data["end_at"]) if "end_at" in call.data else None
        )

    async def stop(call):
        return await runtime_for(call).async_stop_registration(call.data["draft_id"])

    async def discard(call):
        return await runtime_for(call).async_discard_registration(call.data["draft_id"])

    async def history(call):
        return await runtime_for(call).async_history_registration(
            timestamp(call.data["started_at"]), timestamp(call.data["ended_at"])
        )

    async def save(call):
        return await runtime_for(call).async_save_registration(
            call.data["draft_id"],
            timestamp(call.data["started_at"]),
            timestamp(call.data["ended_at"]),
            confirmed=call.data["confirmed"],
            profile_id=call.data.get("profile_id"),
            name=call.data.get("name"),
        )

    def add(name, handler, fields):
        async def validated(call):
            try:
                return await handler(call)
            except (ValueError, TypeError, OverflowError) as err:
                raise ServiceValidationError(str(err)) from err

        async_register_admin_service(
            hass,
            DOMAIN,
            name,
            validated,
            schema=vol.Schema(fields),
            supports_response=SupportsResponse.ONLY,
        )

    add(
        "get_registration",
        get,
        {
            **base,
            vol.Optional("draft_id"): str,
            vol.Optional("started_at"): str,
            vol.Optional("ended_at"): str,
        },
    )
    add("start_registration", start, {**base, vol.Optional("end_at"): str})
    add("stop_registration", stop, draft)
    add("discard_registration", discard, draft)
    add("history_registration", history, {**base, **bounds})
    add(
        "save_registration",
        save,
        {
            **draft,
            **bounds,
            vol.Required("confirmed"): bool,
            vol.Optional("profile_id"): str,
            vol.Optional("name"): str,
        },
    )
