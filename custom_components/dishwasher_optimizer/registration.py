"""Reviewable measurements: retain held power states, never fill unknown energy."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import UTC
from functools import partial
from uuid import uuid4

from homeassistant.util import dt as dt_util

from .engine import MAX_SECONDS, Run, finite

MAX_POINTS = 60_000


def power_value(state):
    """The historic unit belongs to the historic state, not today's sensor."""
    if state is None:
        return None
    try:
        value = finite(state.state)
        unit = state.attributes.get("unit_of_measurement")
        if value >= 0 and unit in ("W", "kW"):
            return finite(value * (1000 if unit == "kW" else 1))
    except ValueError, TypeError, OverflowError:
        pass
    return None


@dataclass
class Registration:
    """One private draft. Only a separately confirmed Run can enter training."""

    entity_id: str
    started_at: float
    end_at: float
    source: str = "registration"
    stage: str = "recording"
    draft_id: str = field(default_factory=lambda: uuid4().hex)
    points: list[list] = field(default_factory=list)
    gaps: list[list[float]] = field(default_factory=list)
    reason: str = ""

    def as_dict(self):
        return {
            **vars(self),
            "points": [list(p) for p in self.points],
            "gaps": [list(g) for g in self.gaps],
        }

    @classmethod
    def from_dict(cls, data):
        draft = cls(**data)
        draft.started_at, draft.end_at = finite(draft.started_at), finite(draft.end_at)
        if not 0 <= draft.end_at - draft.started_at <= MAX_SECONDS:
            raise ValueError("Invalid registration interval")
        if draft.stage not in ("recording", "review") or len(draft.points) > MAX_POINTS:
            raise ValueError("Invalid registration")
        previous = float("-inf")
        for point in draft.points:
            if len(point) != 2 or not draft.started_at <= finite(point[0]) <= draft.end_at:
                raise ValueError("Invalid registration sample")
            if point[0] <= previous or (point[1] is not None and finite(point[1]) < 0):
                raise ValueError("Invalid registration sample")
            previous = point[0]
        for a, b in draft.gaps:
            if not draft.started_at <= finite(a) < finite(b) <= draft.end_at:
                raise ValueError("Invalid data gap")
        return draft

    @property
    def observed_end(self):
        return self.points[-1][0] if self.points else self.started_at

    def sample(self, now, watts):
        if self.stage != "recording" or now < self.started_at:
            return
        end = min(now, self.end_at)
        if self.points and end <= self.points[-1][0]:
            return
        if len(self.points) >= MAX_POINTS:
            self.stage, self.end_at, self.reason = "review", self.observed_end, "sample_limit"
            return
        if self.points and end - self.points[-1][0] > 180:
            self.gaps.append([self.points[-1][0], end])
        self.points.append([end, watts])
        if now >= self.end_at:
            self.stage, self.reason = "review", "scheduled_end"

    def finish(self, now, watts, reason="manual"):
        self.sample(now, watts)
        if self.reason == "sample_limit":
            return
        self.end_at = self.observed_end
        self.stage, self.reason = "review", reason

    def suggested_bounds(self, start_w, stop_w):
        """Suggest boundaries; the user still reviews them, including low-power tails."""
        start, end = self.started_at, self.observed_end
        active = [t for t, w in self.points[:-1] if w is not None and w > start_w]
        if active:
            start = active[0]
            last = max(t for t, w in self.points[:-1] if w is not None and w > stop_w)
            end = next(
                (t for t, w in self.points if t > last and w is not None and w <= stop_w), end
            )
        return start, end

    def measure(self, start=None, end=None):
        """Integrate at original transitions, splitting at the selected minute boundaries."""
        start = self.started_at if start is None else finite(start)
        end = self.observed_end if end is None else finite(end)
        # Browser Date/ISO timestamps have millisecond precision; HA uses microseconds.
        if abs(start - self.started_at) < 0.001:
            start = self.started_at
        if abs(end - self.observed_end) < 0.001:
            end = self.observed_end
        if not self.started_at <= start < end <= self.observed_end:
            raise ValueError("Välj start och slut inom det registrerade intervallet.")
        run = Run(started_at=start, source=self.source)

        def add_known(a, b, watts):
            try:
                run.add(a, b, watts)
            except ValueError, TypeError, OverflowError:
                if "invalid_energy" not in run.issues:
                    run.issues.append("invalid_energy")

        missing = 0.0
        # Unknown intervals and recorder outages are unioned before integration.
        gaps = list(self.gaps)
        if not self.points or self.points[0][0] > start:
            gaps.append([start, min(end, self.points[0][0] if self.points else end)])
        for (a, w), (b, _) in zip(self.points, self.points[1:], strict=False):
            if w is None:
                gaps.append([a, b])
        unknown = []
        for a, b in sorted((max(start, a), min(end, b)) for a, b in gaps):
            if b <= a:
                continue
            if unknown and a <= unknown[-1][1]:
                unknown[-1][1] = max(unknown[-1][1], b)
            else:
                unknown.append([a, b])
        gap_index = 0
        for (a, w), (b, _) in zip(self.points, self.points[1:], strict=False):
            a, b = max(start, a), min(end, b)
            if b <= a or w is None:
                continue
            cursor = a
            while gap_index < len(unknown) and unknown[gap_index][1] <= a:
                gap_index += 1
            index = gap_index
            while index < len(unknown):
                x, y = unknown[index]
                if x >= b:
                    break
                if x > cursor:
                    add_known(cursor, x, w)
                cursor = max(cursor, y)
                index += 1
            if cursor < b:
                add_known(cursor, b, w)
        missing = sum(b - a for a, b in unknown)
        # Pad only for plotting. An incomplete curve is never eligible for saving.
        run.duration_seconds = end - start
        run.energy_wh.extend([0.0] * (math.ceil(run.duration_seconds / 60) - len(run.energy_wh)))
        if missing:
            run.issues.append("missing_data")
        return run, missing

    def summary(self, start_w=5, stop_w=1, *, curve=False, start=None, end=None):
        result = {
            "draft_id": self.draft_id,
            "stage": self.stage,
            "entity_id": self.entity_id,
            "source": self.source,
            "started_at": self.started_at,
            "end_at": self.end_at,
            "observed_end": self.observed_end,
            "reason": self.reason,
        }
        if curve and self.observed_end > self.started_at:
            run, missing = self.measure(start, end)
            suggested_start, suggested_end = self.suggested_bounds(start_w, stop_w)
            result.update(
                started_at=self.started_at,
                selected_start=run.started_at,
                selected_end=run.started_at + run.duration_seconds,
                duration_seconds=run.duration_seconds,
                energy_wh=run.energy_wh,
                energy_kwh=None if missing or run.issues else sum(run.energy_wh) / 1000,
                issues=list(run.issues),
                missing_seconds=missing,
                gaps=self.gaps,
                suggested_start=suggested_start,
                suggested_end=suggested_end,
            )
        return result


def _read_history(hass, entity_id, start, end):
    """Run exclusively on Recorder's database executor, with historic attributes."""
    from homeassistant.components.recorder.db_schema import RecorderRuns
    from homeassistant.components.recorder.history import get_significant_states_with_session
    from homeassistant.helpers.recorder import session_scope

    def utc_stamp(value):
        # Recorder stores UTC; SQLite drops tzinfo. as_utc would assume HA local time.
        return value.replace(tzinfo=UTC).timestamp() if value.tzinfo is None else value.timestamp()

    with session_scope(hass=hass, read_only=True) as session:
        states = get_significant_states_with_session(
            hass,
            session,
            dt_util.utc_from_timestamp(start),
            dt_util.utc_from_timestamp(end),
            [entity_id],
            include_start_time_state=True,
            significant_changes_only=False,
        ).get(entity_id, [])
        if len(states) >= MAX_POINTS:
            raise ValueError("För många mätpunkter. Välj ett kortare intervall.")
        points = [[max(start, s.last_updated.timestamp()), power_value(s)] for s in states]
        # A held sensor state is valid between updates, but never across an HA outage.
        runs = (
            session.query(RecorderRuns)
            .filter(
                RecorderRuns.start < dt_util.utc_from_timestamp(end),
                (RecorderRuns.end.is_(None))
                | (RecorderRuns.end > dt_util.utc_from_timestamp(start)),
            )
            .order_by(RecorderRuns.start)
            .all()
        )
        coverage = [
            (
                max(start, utc_stamp(r.start)),
                min(end, utc_stamp(r.end) if r.end else end),
            )
            for r in runs
        ]
    gaps, cursor = [], start
    for a, b in coverage:
        if a > cursor:
            gaps.append([cursor, a])
        cursor = max(cursor, b)
    if cursor < end:
        gaps.append([cursor, end])
    # End sentinel has no energy of its own.
    if points:
        points.append([end, points[-1][1]])
    return points, gaps


async def history_registration(hass, entity_id, start, end):
    from homeassistant.helpers.recorder import get_instance

    if not 0 < end - start <= MAX_SECONDS or end > dt_util.utcnow().timestamp():
        raise ValueError("Välj ett avslutat intervall på högst åtta timmar.")
    try:
        recorder = get_instance(hass)
    except KeyError as err:
        raise ValueError("Home Assistants Recorder behövs för att använda historik.") from err
    if not recorder.entity_filter(entity_id) or not recorder.recording:
        raise ValueError("Effektsensorn måste ingå i aktiv historiklagring (Recorder).")
    points, gaps = await recorder.async_add_executor_job(
        partial(_read_history, hass, entity_id, start, end)
    )
    if not points:
        raise ValueError("Ingen effekthistorik hittades för intervallet.")
    return Registration.from_dict(
        Registration(
            entity_id,
            start,
            end,
            source="history",
            stage="review",
            points=points,
            gaps=gaps,
        ).as_dict()
    )
