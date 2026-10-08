"""Reading chordotomy's schema-11 chord timeline."""

import json
from pathlib import Path

SCHEMA_VERSION = 11


class TimelineError(ValueError):
    pass


def load(path: str | Path) -> dict:
    """Read a timeline, refusing any schema other than 11."""
    path = Path(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise TimelineError(f"{path}: not valid JSON ({exc})") from exc
    version = data.get("schema_version", "missing") if isinstance(data, dict) else "missing"
    if version != SCHEMA_VERSION:
        raise TimelineError(f"{path}: schema_version is {version}, pianoize reads {SCHEMA_VERSION}")
    return data


def beat_time(timeline: dict, index: int) -> float:
    """Seconds at a beat index; below 0 is the first beat, at or past the last the audio's end."""
    beats = timeline["beats"]
    if index < 0:
        return beats[0]
    if index >= len(beats):
        return timeline["source"]["duration"]
    return beats[index]
