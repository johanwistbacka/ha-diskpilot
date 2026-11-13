"""Local collection and optimisation, independent of Home Assistant."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import uuid4

MAX_SECONDS = 8 * 3600
MAX_ENERGY_WH = 50_000


def finite(value: Any) -> float:
    """Accept a finite number, never booleans, NaN or infinity."""
    if isinstance(value, bool):
        raise ValueError("Expected a number")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("Expected a finite number")
    return number


def timestamp(value: Any) -> float:
    """Require timezone information; never guess across daylight saving."""
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError("Timestamps must include a UTC offset")
    return value.timestamp()


@dataclass
class Run:
    """One observed run. Its label is separate from the measured curve."""

    started_at: float
    duration_seconds: float = 0
    energy_wh: list[float] = field(default_factory=list)
    run_id: str = field(default_factory=lambda: uuid4().hex)
    program: str | None = None
    issues: list[str] = field(default_factory=list)
    note: str = ""
    source: str = "live"
    meter_energy_kwh: float | None = None
    meter_note: str = ""

    def add(self, start: float, end: float, watts: float) -> None:
        """Integrate atomically; never mutate a curve beyond the reload contract."""
        start, end, watts = finite(start), finite(end), finite(watts)
        if (
            watts < 0
            or start < self.started_at
            or end < start
            or end - self.started_at > MAX_SECONDS
        ):
            raise ValueError("Invalid integration interval")
        updates = []
        while start < end:
            offset = max(0, start - self.started_at)
            index = int(offset // 60)
            edge = min(end, self.started_at + (index + 1) * 60)
            if edge <= start:
                raise ValueError("Invalid integration precision")
            updates.append((index, finite((watts / 3600) * (edge - start))))
            start = edge
        curve = list(self.energy_wh)
        for index, value in updates:
            while len(curve) <= index:
                curve.append(0.0)
            curve[index] = finite(curve[index] + value)
        total = sum(curve)
        if not math.isfinite(total) or total > MAX_ENERGY_WH:
            raise ValueError("Invalid energy curve")
        self.energy_wh = curve
        self.duration_seconds = end - self.started_at

    def as_dict(self) -> dict:
        """Return JSON-safe storage."""
        return {
            "run_id": self.run_id,
            "started_at": self.started_at,
            "duration_seconds": self.duration_seconds,
            "energy_wh": list(self.energy_wh),
            "program": self.program,
            "issues": list(self.issues),
            "note": self.note,
            "source": self.source,
            "meter_energy_kwh": self.meter_energy_kwh,
            "meter_note": self.meter_note,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Run:
        """Validate persisted or imported curves before learning from them."""
        run = cls(**data)
        run.started_at = finite(run.started_at)
        run.duration_seconds = finite(run.duration_seconds)
        if not 0 < run.duration_seconds <= MAX_SECONDS:
            raise ValueError("Duration must be between 0 and 8 hours")
        if len(run.energy_wh) != math.ceil(run.duration_seconds / 60):
            raise ValueError("One energy value is required for each minute")
        run.energy_wh = [finite(value) for value in run.energy_wh]
        if min(run.energy_wh) < 0 or sum(run.energy_wh) > MAX_ENERGY_WH:
            raise ValueError("Invalid energy curve")
        if run.program is not None and (
            not isinstance(run.program, str)
            or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", run.program)
        ):
            raise ValueError("Unknown program")
        if not isinstance(run.note, str) or len(run.note) > 500:
            raise ValueError("Note must be at most 500 characters")
        if run.meter_energy_kwh is not None:
            run.meter_energy_kwh = finite(run.meter_energy_kwh)
            if run.meter_energy_kwh < 0:
                raise ValueError("Invalid measured energy")
        if not isinstance(run.issues, list) or not all(
            isinstance(issue, str) for issue in run.issues
        ):
            raise ValueError("Invalid quality flags")
        return run


class Collector:
    """Detect activity with hysteresis and keep low-power tails intact."""

    def __init__(self, start_w=5.0, stop_w=1.0, stop_seconds=600, start_seconds=30):
        self.start_w = start_w
        self.stop_w = stop_w
        self.stop_seconds = stop_seconds
        self.start_seconds = start_seconds
        self.candidate: Run | None = None
        self.active: Run | None = None
        self.last_t: float | None = None
        self.last_w: float | None = None
        self.pending_end: float | None = None
        self.end_curve: list[float] | None = None
        # On first setup/restart a high reading may be mid-program.
        self.armed = False
        self.blocked = False

    def sample(self, now: float, watts: float | None) -> Run | None:
        """Process a reading or a known unavailable state."""
        if self.last_t is not None and now <= self.last_t:
            return None
        if watts is not None:
            try:
                watts = finite(watts)
            except ValueError, TypeError, OverflowError:
                watts = None
            if watts is not None and watts < 0:
                watts = None
        completed = None
        if self.active is not None and self.last_t is not None:
            gap = now - self.last_t
            end = min(now, self.active.started_at + MAX_SECONDS)
            if self.last_w is not None and gap <= 180:
                try:
                    self.active.add(self.last_t, end, self.last_w)
                except ValueError, TypeError, OverflowError:
                    self._issue("invalid_energy")
                    self._pad(end)
            else:
                self._issue("missing_data")
                self._pad(end)
                self.pending_end = None
            if watts is None:
                self._issue("missing_data")
                self.pending_end = None
            elif watts < self.stop_w:
                if self.pending_end is None:
                    self.pending_end = now
                    self.end_curve = list(self.active.energy_wh)
                elif now - self.pending_end >= self.stop_seconds:
                    self.active.duration_seconds = self.pending_end - self.active.started_at
                    self.active.energy_wh = self.end_curve or []
                    completed = self.active
                    self.active = None
                    self.pending_end = None
            else:
                self.pending_end = None
            if self.active and now - self.active.started_at >= MAX_SECONDS:
                self._issue("maximum_duration")
                completed, self.active = self.active, None
                self.armed = False
                self.blocked = True
                self.pending_end = None
        if watts is not None and watts < self.stop_w:
            self.armed = True
            self.blocked = False
        if self.active is None:
            self._consider_start(now, watts)
        self.last_t, self.last_w = now, watts
        if completed and (completed.duration_seconds < 120 or sum(completed.energy_wh) < 1):
            completed.issues.append("too_short")
        return completed

    def _consider_start(self, now: float, watts: float | None) -> None:
        """Confirm sustained activity; retain the first high sample and its energy.

        A button press followed by display/delay power is discarded. Candidates
        never enter persisted runs. Unknown data or a gap breaks confirmation.
        """
        continuous = (
            self.last_t is not None
            and now - self.last_t <= 180
            and self.last_w is not None
            and self.last_w > self.start_w
        )
        if watts is None or (
            self.last_t is not None and now - self.last_t > 180 and watts > self.start_w
        ):
            self.armed = False
        if self.blocked or watts is None or watts <= self.start_w:
            self.candidate = None
            return
        if self.candidate is not None and not continuous:
            self.candidate = None
        if self.candidate is None:
            self.candidate = Run(started_at=now)
            if not self.armed:
                self.candidate.issues.append("start_not_observed")
        else:
            try:
                self.candidate.add(self.last_t, now, self.last_w)
            except ValueError, TypeError, OverflowError:
                if "invalid_energy" not in self.candidate.issues:
                    self.candidate.issues.append("invalid_energy")
                self.candidate.duration_seconds = now - self.candidate.started_at
                count = math.ceil(self.candidate.duration_seconds / 60)
                self.candidate.energy_wh.extend(
                    [0.0] * max(0, count - len(self.candidate.energy_wh))
                )
        if now - self.candidate.started_at >= self.start_seconds:
            self.active, self.candidate = self.candidate, None
            self.pending_end = None

    def _issue(self, issue: str) -> None:
        if self.active and issue not in self.active.issues:
            self.active.issues.append(issue)

    def _pad(self, end: float) -> None:
        if self.active:
            self.active.duration_seconds = end - self.active.started_at
            count = math.ceil(self.active.duration_seconds / 60)
            self.active.energy_wh.extend([0.0] * max(0, count - len(self.active.energy_wh)))


@dataclass(frozen=True)
class Profile:
    """Average minute energy; longest observed duration preserves the tail."""

    energy_wh: tuple[float, ...]
    duration_seconds: float
    count: int
    min_kwh: float
    max_kwh: float


def profile_for(runs: list[Run], program: str) -> Profile | None:
    """Only explicitly labelled, complete runs contribute."""
    selected = [r for r in runs if r.program == program and not r.issues]
    if not selected:
        return None
    duration = max(r.duration_seconds for r in selected)
    values = tuple(
        sum(r.energy_wh[i] if i < len(r.energy_wh) else 0 for r in selected) / len(selected)
        for i in range(math.ceil(duration / 60))
    )
    totals = [sum(r.energy_wh) / 1000 for r in selected]
    return Profile(values, duration, len(selected), min(totals), max(totals))


@dataclass(frozen=True)
class Price:
    """One price interval, in configured currency per kWh."""

    start: float
    end: float
    value: float


def parse_prices(attributes: dict, config: dict) -> list[Price]:
    """Read explicitly configured lists; reject ambiguous or overlapping data."""
    rows = []
    for name in config["price_attributes"].split(","):
        value = attributes.get(name.strip())
        if value is None:
            continue
        if not isinstance(value, list):
            raise ValueError("Price attributes must contain lists")
        rows.extend(value)
    multiplier = finite(config["price_multiplier"])
    if multiplier <= 0:
        raise ValueError("Price multiplier must be positive")
    result = []
    for row in rows:
        start, end = timestamp(row[config["start_key"]]), timestamp(row[config["end_key"]])
        value = finite(row[config["value_key"]]) * multiplier
        if end <= start or not math.isfinite(value):
            raise ValueError("Invalid price interval")
        result.append(Price(start, end, value))
    result.sort(key=lambda p: p.start)
    if any(a.end > b.start for a, b in zip(result, result[1:], strict=False)):
        raise ValueError("Overlapping price intervals")
    return result


def cost_at(profile: Profile, start: float, prices: list[Price]) -> float | None:
    """Split every minute at actual tariff boundaries; require full coverage."""
    price_index = 0
    while price_index < len(prices) and prices[price_index].end <= start:
        price_index += 1
    total = 0.0
    for index, wh in enumerate(profile.energy_wh):
        cursor = start + index * 60
        end = start + min((index + 1) * 60, profile.duration_seconds)
        seconds = end - cursor
        while cursor < end:
            if price_index == len(prices) or prices[price_index].start > cursor + 1e-6:
                return None
            price = prices[price_index]
            edge = min(end, price.end)
            if edge <= cursor:
                price_index += 1
                continue
            total += wh / 1000 * (edge - cursor) / seconds * price.value
            cursor = edge
            if cursor >= price.end:
                price_index += 1
    return total


def optimise(profile: Profile, now: float, deadline: float, prices: list[Price]) -> dict:
    """Find the lowest cost on a minute grid, also considering start now."""
    direct = cost_at(profile, now, prices)
    best_start = None
    best_cost = None
    candidates = [now]
    candidates.extend(range(math.ceil(now / 60) * 60, int(deadline) + 1, 60))
    for start in candidates:
        if start + profile.duration_seconds > deadline:
            continue
        cost = cost_at(profile, start, prices)
        if cost is not None and (best_cost is None or cost < best_cost - 1e-10):
            best_start, best_cost = start, cost
    return {
        "optimal_start": best_start,
        "optimal_end": best_start + profile.duration_seconds if best_start is not None else None,
        "cost": best_cost,
        "cost_now": direct,
        "saving": direct - best_cost if direct is not None and best_cost is not None else None,
    }
