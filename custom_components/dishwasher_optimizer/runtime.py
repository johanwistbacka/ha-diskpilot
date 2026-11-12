"""Home Assistant event handling and private, versioned local storage."""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_state_change_event, async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import DEFAULTS, DOMAIN, PROGRAMS
from .engine import Collector, Run, finite, optimise, parse_prices, profile_for

_LOGGER = logging.getLogger(__name__)


class Runtime:
    """Own one appliance's collector and price calculations."""

    def __init__(self, hass, entry):
        self.hass, self.entry = hass, entry
        self.config = {**DEFAULTS, **entry.data, **entry.options}
        self.store = Store(hass, 1, f"{DOMAIN}.{entry.entry_id}", private=True)
        self.runs: list[Run] = []
        self.collector = Collector()
        self.results = {}
        self.price_status = "not_configured"
        self.source_status = "unknown"
        self.signal = f"{DOMAIN}_{entry.entry_id}"
        self._unsub = []
        self._lock = asyncio.Lock()
        self._closed = False
        self._last_save_request = float("-inf")

    async def async_start(self):
        """Recover safely; never teach from an interrupted measurement."""
        saved = await self.store.async_load() or {}
        self.runs = [Run.from_dict(row) for row in saved.get("runs", [])]
        if (active := saved.get("active")) and active["duration_seconds"] > 0:
            run = Run.from_dict(active)
            if "interrupted" not in run.issues:
                run.issues.append("interrupted")
            self.runs.append(run)
        self._bind_states()
        self._unsub.append(async_track_time_interval(self.hass, self._tick, timedelta(seconds=30)))
        self.sample()
        await self.async_refresh()

    def _bind_states(self):
        if getattr(self, "_state_unsub", None):
            self._state_unsub()
        entities = [self.config["power_entity"]] if self.config["power_entity"] else []
        if self.config["price_entity"]:
            entities.append(self.config["price_entity"])
        self._state_unsub = (
            async_track_state_change_event(self.hass, entities, self._state_changed)
            if entities
            else lambda: None
        )

    @callback
    def _state_changed(self, event):
        if event.data["entity_id"] == self.config["power_entity"]:
            self.sample()
        else:
            self.hass.async_create_task(self.async_refresh())

    @callback
    def _tick(self, now):
        self.sample()
        self.hass.async_create_task(self.async_refresh())

    @callback
    def sample(self):
        """Timers also sample unchanged states; unavailable is never treated as zero."""
        if not self.config["power_entity"]:
            self.source_status = "not_configured"
            return
        was_active = self.collector.active is not None
        watts = None
        state = self.hass.states.get(self.config["power_entity"])
        self.source_status = "unavailable"
        if state is not None:
            try:
                value = finite(state.state)
                unit = state.attributes.get("unit_of_measurement")
                if unit in ("W", "kW") and value >= 0:
                    watts = value * (1000 if unit == "kW" else 1)
                    self.source_status = "ok"
                else:
                    self.source_status = "invalid_unit_or_value"
            except ValueError, TypeError, OverflowError:
                pass
        if self.collector.active is None:
            self.collector.start_w = self.config["start_w"]
            self.collector.stop_w = self.config["stop_w"]
            self.collector.stop_seconds = self.config["stop_minutes"] * 60
        if run := self.collector.sample(dt_util.utcnow().timestamp(), watts):
            self.runs.append(run)
        if was_active or self.collector.active is not None:
            self.schedule_save()
        async_dispatcher_send(self.hass, self.signal)

    def storage_data(self):
        active = self.collector.active
        return {
            "runs": [run.as_dict() for run in self.runs],
            "active": active.as_dict() if active else None,
        }

    @callback
    def schedule_save(self):
        # A debounce would postpone every write while the sensor changes rapidly.
        now = self.hass.loop.time()
        if now - self._last_save_request >= 30:
            self._last_save_request = now
            self.store.async_delay_save(self.storage_data, 0)

    async def async_apply_options(self, hass, entry):
        previous_power = self.config["power_entity"]
        self.config = {**DEFAULTS, **entry.data, **entry.options}
        if self.config["power_entity"] != previous_power:
            # A source change must never blend measurements from two meters.
            active = self.collector.active
            if active is not None and active.duration_seconds > 0:
                active.issues.append("measurement_changed")
                self.runs.append(active)
            self.collector = Collector()
            self.source_status = "unknown" if self.config["power_entity"] else "not_configured"
            await self.store.async_save(self.storage_data())
        self._bind_states()
        await self.async_refresh()

    async def async_refresh(self):
        async with self._lock:
            if self._closed:
                return
            profiles = {program: profile_for(self.runs, program) for program in PROGRAMS}
            prices = []
            self.price_status = "not_configured"
            if self.config["price_entity"]:
                self.price_status = "unavailable"
                state = self.hass.states.get(self.config["price_entity"])
                if state is not None and state.state not in ("unknown", "unavailable"):
                    try:
                        prices = parse_prices(state.attributes, self.config)
                        self.price_status = "ok" if prices else "no_intervals"
                    except ValueError, TypeError, KeyError, OverflowError:
                        self.price_status = "invalid_format"
            now = dt_util.utcnow().timestamp()
            deadline = now + self.config["horizon_hours"] * 3600

            def calculate():
                return {
                    program: optimise(profile, now, deadline, prices)
                    for program, profile in profiles.items()
                    if profile is not None and prices
                }

            calculated = await self.hass.async_add_executor_job(calculate)
            self.results = {}
            for program, profile in profiles.items():
                result = calculated.get(program, {})
                self.results[program] = {
                    **result,
                    "sample_count": profile.count if profile else 0,
                    "energy_kwh": sum(profile.energy_wh) / 1000 if profile else None,
                    "duration_minutes": profile.duration_seconds / 60 if profile else None,
                    "energy_min_kwh": profile.min_kwh if profile else None,
                    "energy_max_kwh": profile.max_kwh if profile else None,
                    "status": (
                        (
                            "needs_labelled_run"
                            if self.config["power_entity"]
                            else "needs_saved_profile"
                        )
                        if profile is None
                        else self.price_status
                        if self.price_status != "ok"
                        else "ok"
                        if result.get("cost") is not None
                        else "insufficient_price_coverage"
                    ),
                }
            if not self._closed:
                async_dispatcher_send(self.hass, self.signal)

    def summaries(self):
        return [
            {
                "run_id": run.run_id,
                "started_at": dt_util.utc_from_timestamp(run.started_at).isoformat(),
                "duration_minutes": round(run.duration_seconds / 60, 1),
                "energy_kwh": round(sum(run.energy_wh) / 1000, 5),
                "program": run.program,
                "issues": list(run.issues),
                "note": run.note,
            }
            for run in sorted(self.runs, key=lambda run: run.started_at, reverse=True)[:10]
        ]

    async def async_stop(self):
        self._closed = True
        self._state_unsub()
        for unsub in self._unsub:
            unsub()
        await self.store.async_save(self.storage_data())

    async def async_label(self, run_id, program, note=None):
        """Relabelling rebuilds profiles from source runs, so corrections undo cleanly."""
        run = next((run for run in self.runs if run.run_id == run_id), None)
        if run is None:
            raise ValueError("Unknown run")
        run.program = None if program == "unassigned" else program
        if note is not None:
            run.note = note
        await self.store.async_save(self.storage_data())
        await self.async_refresh()
