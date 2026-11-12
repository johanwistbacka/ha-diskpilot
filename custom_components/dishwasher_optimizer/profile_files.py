"""Parse local profile files without network access, AI, or executable templates."""

from __future__ import annotations

import csv
import io
import json

from .engine import Run, finite, timestamp

MAX_FILE_BYTES = 512 * 1024
MAX_FILE_RUNS = 100


def profile_name(value: str) -> str:
    """Keep user-facing names separate from stable profile identifiers."""
    if not isinstance(value, str):
        raise ValueError("Profilnamnet måste vara text.")
    value = value.strip()
    if not value or len(value) > 80 or any(ord(c) < 32 for c in value):
        raise ValueError("Ange ett profilnamn med 1–80 tecken på en rad.")
    return value


def _run(data: dict) -> Run:
    if (
        not isinstance(data, dict)
        or not {"started_at", "duration_seconds", "energy_wh"} <= data.keys()
    ):
        raise ValueError("Varje körning behöver started_at, duration_seconds och energy_wh.")
    if set(data) - {"started_at", "duration_seconds", "energy_wh", "note"}:
        raise ValueError("Körningen innehåller okända fält. Använd det dokumenterade filformatet.")
    if not isinstance(data["energy_wh"], list):
        raise ValueError("energy_wh måste vara en lista med energi i Wh per minut.")
    try:
        return Run.from_dict(
            Run(
                started_at=timestamp(data["started_at"]),
                duration_seconds=finite(data["duration_seconds"]),
                energy_wh=data["energy_wh"],
                note=data.get("note", ""),
                source="file",
            ).as_dict()
        )
    except (ValueError, TypeError, OverflowError) as err:
        raise ValueError(f"Ogiltig körning: {err}") from err


def parse_profile_file(filename: str, content: str) -> tuple[str | None, list[Run]]:
    """Read canonical JSON or minute-energy CSV, never paths or remote URLs."""
    if not isinstance(content, str) or len(content.encode("utf-8")) > MAX_FILE_BYTES:
        raise ValueError("Filen får vara högst 512 KiB.")
    if not content.strip():
        raise ValueError("Filen är tom.")
    content = content.lstrip("\ufeff")
    name = None
    if filename.lower().endswith(".json"):
        try:
            data = json.loads(content)
        except (ValueError, RecursionError) as err:
            raise ValueError("Filen är inte giltig JSON.") from err
        if (
            not isinstance(data, dict)
            or type(data.get("schema_version")) is not int
            or data["schema_version"] != 1
        ):
            raise ValueError("JSON-filen behöver schema_version: 1.")
        if set(data) - {"schema_version", "profile_name", "runs"}:
            raise ValueError("JSON-filen innehåller okända fält.")
        if "profile_name" in data:
            name = profile_name(data["profile_name"])
        rows = data.get("runs")
        if not isinstance(rows, list) or not 1 <= len(rows) <= MAX_FILE_RUNS:
            raise ValueError("Filen ska innehålla 1–100 kompletta körningar.")
        runs = [_run(row) for row in rows]
    elif filename.lower().endswith(".csv"):
        reader = csv.DictReader(io.StringIO(content), strict=True)
        expected = ["started_at", "offset_seconds", "interval_seconds", "energy_wh"]
        grouped = {}
        try:
            if reader.fieldnames != expected:
                raise ValueError("CSV-rubriken ska vara: " + ",".join(expected))
            for row in reader:
                if set(row) != set(expected):
                    raise ValueError("En CSV-rad har fel antal kolumner.")
                start = timestamp(row["started_at"])
                group = grouped.setdefault(start, [])
                if len(grouped) > MAX_FILE_RUNS or len(group) >= 480:
                    raise ValueError(
                        "Filen överskrider gränsen 100 körningar eller 8 timmar per körning."
                    )
                group.append(
                    (
                        finite(row["offset_seconds"]),
                        finite(row["interval_seconds"]),
                        finite(row["energy_wh"]),
                    )
                )
        except (csv.Error, ValueError, TypeError, OverflowError) as err:
            raise ValueError(f"Ogiltig CSV-rad: {err}") from err
        runs = []
        for start, intervals in grouped.items():
            for index, (offset, duration, _) in enumerate(intervals):
                if (
                    offset != index * 60
                    or not 0 < duration <= 60
                    or (index < len(intervals) - 1 and duration != 60)
                ):
                    raise ValueError(
                        "CSV-intervall måste följa varandra utan luckor: 0, 60, 120 … sekunder. Endast sista minuten får vara kortare."
                    )
            duration = intervals[-1][0] + intervals[-1][1]
            runs.append(
                Run.from_dict(
                    Run(
                        started_at=start,
                        duration_seconds=duration,
                        energy_wh=[row[2] for row in intervals],
                        source="file",
                    ).as_dict()
                )
            )
        if not runs:
            raise ValueError("CSV-filen saknar körningar.")
    else:
        raise ValueError("Välj en .json- eller .csv-fil.")
    starts = sorted(run.started_at for run in runs)
    if any(b - a < 1 for a, b in zip(starts, starts[1:], strict=False)):
        raise ValueError("Filen innehåller flera körningar med samma starttid.")
    return name, runs


def import_summary(name: str | None, runs: list[Run]) -> dict:
    """Preview exactly the measured curves that would be added."""
    energies = [sum(run.energy_wh) / 1000 for run in runs]
    durations = [run.duration_seconds / 60 for run in runs]
    return {
        "profile_name": name,
        "run_count": len(runs),
        "energy_min_kwh": min(energies),
        "energy_max_kwh": max(energies),
        "energy_mean_kwh": sum(energies) / len(energies),
        "duration_min_minutes": min(durations),
        "duration_max_minutes": max(durations),
        "first_curve_energy_wh": list(runs[0].energy_wh),
        "warning": "En körning ger en första uppskattning."
        if len(runs) == 1
        else "Kontrollera att samtliga körningar hör till samma profil.",
    }
