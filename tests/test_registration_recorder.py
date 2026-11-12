"""Exercise real SQLite Recorder run rows with Home Assistant's local timezone."""

from contextlib import nullcontext
from datetime import UTC, datetime, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest
from homeassistant.components.recorder.db_schema import RecorderRuns
from homeassistant.core import State
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from custom_components.dishwasher_optimizer.registration import Registration, _read_history


@pytest.mark.parametrize("zone", ["UTC", "Europe/Stockholm", "Asia/Kathmandu"])
@pytest.mark.parametrize("outage", [False, True])
def test_sqlite_utc_rows_never_use_the_ha_local_timezone(zone, outage):
    base = datetime(2026, 1, 1, tzinfo=UTC)
    engine = create_engine("sqlite://")
    RecorderRuns.__table__.create(engine)
    with Session(engine) as session:
        if outage:
            session.add_all(
                [
                    RecorderRuns(
                        start=base - timedelta(seconds=60), end=base + timedelta(seconds=240)
                    ),
                    RecorderRuns(
                        start=base + timedelta(seconds=300), end=base + timedelta(seconds=700)
                    ),
                ]
            )
        else:
            session.add(
                RecorderRuns(start=base - timedelta(seconds=60), end=base + timedelta(seconds=700))
            )
        session.commit()
        session.expunge_all()
        rows = session.query(RecorderRuns).all()
        assert rows[0].start.tzinfo is None, "SQLite reproduction requires actual naive UTC rows"
        state = State(
            "sensor.power",
            "200",
            {"unit_of_measurement": "W"},
            last_updated=base - timedelta(seconds=10),
        )
        with (
            patch(
                "homeassistant.helpers.recorder.session_scope", return_value=nullcontext(session)
            ),
            patch(
                "homeassistant.components.recorder.history.get_significant_states_with_session",
                return_value={"sensor.power": [state]},
            ),
            patch("homeassistant.util.dt.DEFAULT_TIME_ZONE", ZoneInfo(zone)),
        ):
            points, gaps = _read_history(
                None, "sensor.power", base.timestamp(), base.timestamp() + 600
            )
        expected = [[base.timestamp() + 240, base.timestamp() + 300]] if outage else []
        assert gaps == expected
        draft = Registration(
            "sensor.power",
            base.timestamp(),
            base.timestamp() + 600,
            stage="review",
            points=points,
            gaps=gaps,
        )
        run, missing = draft.measure()
        assert missing == (60 if outage else 0)
        assert sum(run.energy_wh) == pytest.approx(200 * (600 - missing) / 3600)
    engine.dispose()
