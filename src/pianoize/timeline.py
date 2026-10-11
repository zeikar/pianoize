"""Reading chordotomy's schema-11 chord timeline."""

import bisect
import json
import math
from itertools import pairwise
from pathlib import Path

from .chords import INVERSIONS, ROOT_NAMES, is_label

SCHEMA_VERSION = 11
KEYS = [f"{root}:{mode}" for mode in ("maj", "min") for root in ROOT_NAMES]


class TimelineError(ValueError):
    pass


def load(path: str | Path) -> dict:
    """Read a timeline, refusing any schema other than 11."""
    path = Path(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"), parse_constant=_refuse_constant)
    except ValueError as exc:  # also undecodable bytes
        raise TimelineError(f"{path}: not valid JSON ({exc})") from exc
    reason = _version_problem(data)
    if reason:
        raise TimelineError(f"{path}: {reason}")
    return data


def _refuse_constant(name: str):
    # Python reads NaN and Infinity, and would write them back; the browser's JSON.parse refuses
    # them, so the viewer could not open the file.
    raise ValueError(f"{name} is not a JSON number")


def _version_problem(data) -> str | None:
    version = data.get("schema_version", "missing") if isinstance(data, dict) else "missing"
    if version != SCHEMA_VERSION:
        return f"schema_version is {version}, pianoize reads {SCHEMA_VERSION}"
    return None


def require_beats(data: dict, path: str | Path) -> None:
    """Raise TimelineError unless the timeline has the two beats beat_position needs."""
    if len(data["beats"]) < 2:
        raise TimelineError(f"{path}: the timeline has {len(data['beats'])} beats, needs two")


def beat_position(timeline: dict, seconds: float) -> float:
    """Fractional beat at a time, interpolated between beats and extrapolated past either end with
    the neighbouring beat interval. The timeline needs at least two beats."""
    beats = timeline["beats"]
    index = min(max(bisect.bisect_right(beats, seconds) - 1, 0), len(beats) - 2)
    return index + (seconds - beats[index]) / (beats[index + 1] - beats[index])


def beat_time(timeline: dict, index: int) -> float:
    """Seconds at a beat index; below 0 is the first beat, at or past the last the audio's end."""
    beats = timeline["beats"]
    if index < 0:
        return beats[0]
    if index >= len(beats):
        return timeline["source"]["duration"]
    return beats[index]


# The checks below port timelineProblem from chordotomy's viewer/core.js for schema 11, so a
# timeline pianoize writes is one the viewer opens. Its messages are the viewer's.


def _integer(value) -> bool:
    return type(value) is int  # a bool is no integer, as in JS


def _number(value) -> bool:
    """JS's Number.isFinite on what JSON.parse reads: an int or float finite as a double, never a
    bool."""
    if type(value) not in (int, float):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:  # an int past the largest double, which JSON.parse reads as Infinity
        return False


def _text_or_null(value) -> bool:
    return value is None or isinstance(value, str)


_SEGMENT_FIELDS = {
    "start_beat": _integer,
    "end_beat": _integer,
    "start_time": _number,
    "end_time": _number,
    "candidates": lambda value: isinstance(value, list) and all(map(is_label, value)),
    "inversion": lambda value: value is None or value in (*INVERSIONS, "non_chord"),
    "numeral": _text_or_null,
    "role": _text_or_null,
    "function": _text_or_null,
    "target": _text_or_null,
    "edited": lambda value: isinstance(value, bool),
}
_REGION_FIELDS = {"start_beat": _integer, "end_beat": _integer, "label": lambda v: v in KEYS}


def _invalid_field(item: dict, fields: dict) -> str | None:
    return next(
        (name for name, ok in fields.items() if name not in item or not ok(item[name])), None
    )


def problem(data) -> str | None:
    """Why chordotomy's viewer would refuse to open a timeline, in its words, or None when it
    opens it. Schema 11 only."""
    reason = _version_problem(data)
    if reason:
        return f"This timeline's {reason}."
    beats, segments = data.get("beats"), data.get("segments")
    if not isinstance(segments, list) or not isinstance(beats, list):
        return "This timeline has no beats or segments list."
    if not all(map(_number, beats)):
        return "This timeline has a beat that isn't a time."
    source = data.get("source")
    if not isinstance(source, dict) or not _number(source.get("duration")):
        return "This timeline has no source duration."
    if "url" not in source or not _text_or_null(source["url"]):
        return "This timeline's source has a missing or invalid url."
    generator = data.get("generator")
    engine = generator.get("engine") if isinstance(generator, dict) else None
    if not (
        isinstance(engine, dict)
        and isinstance(engine.get("name"), str)
        and isinstance(engine.get("version"), str)
    ):
        return "This timeline's generator has a missing or invalid engine."
    key = data.get("global_key")
    if key is not None:
        label = key.get("label") if isinstance(key, dict) else None
        if label not in KEYS:
            return f"This timeline has a key chordotomy doesn't write: global_key {label}."
        candidates = key.get("candidates")
        if key.get("source") not in ("estimated", "given") or not (
            isinstance(candidates, list) and all(candidate in KEYS for candidate in candidates)
        ):
            return "This timeline's key has a missing or invalid source or candidates."
    if any(later <= earlier for earlier, later in pairwise(beats)):
        return "This timeline's beats aren't in ascending order."
    for index, segment in enumerate(segments):
        where = f"segment {index + 1}"
        if not isinstance(segment, dict):
            return f"This timeline's {where} isn't an object."
        chord, bass = segment.get("chord", "missing"), segment.get("bass", "missing")
        if not is_label(chord):
            return f"This timeline has a chord chordotomy doesn't write: chord {chord}."
        if bass is not None and bass not in ROOT_NAMES:
            return f"This timeline has a note chordotomy doesn't write: bass {bass}."
        field = _invalid_field(segment, _SEGMENT_FIELDS)
        if field:
            return f"This timeline's {where} has a missing or invalid {field}."
        tiling = _tiling_problem(segments, index, len(beats), where)
        if tiling:
            return tiling
        start, end = segment["start_beat"], segment["end_beat"]
        if index == len(segments) - 1:
            end_time = source["duration"]
        else:  # JS reads undefined past the list, which matches no time
            end_time = beats[end] if end < len(beats) else None
        # Exact float comparison, as the viewer makes it: times are copied from beats, never
        # computed.
        if segment["start_time"] != beats[start] or segment["end_time"] != end_time:
            return f"This timeline's {where} has times that don't match its beats."
    return _regions_problem(key, data.get("key_regions"), len(beats), segments)


def _tiling_problem(spans: list[dict], index: int, total: int, where: str) -> str | None:
    """Why a segment or key region doesn't take its place in a gapless tiling of the beats."""
    start, end = spans[index]["start_beat"], spans[index]["end_beat"]
    if start < 0 or end <= start or end > total:
        return f"This timeline's {where} lies outside its beats."
    if start != (spans[index - 1]["end_beat"] if index else 0):
        return f"This timeline's {where} doesn't start where the one before it ends."
    if index == len(spans) - 1 and end != total:
        return f"This timeline's {where} stops short of the last beat."
    return None


def _regions_problem(key, regions, total: int, segments: list[dict]) -> str | None:
    if not isinstance(regions, list):
        return "This timeline has no key_regions list."
    if key is None:
        return "This timeline has key regions but no key." if regions else None
    if not regions:
        return "This timeline has a key but no key regions."
    segment_starts = {segment["start_beat"] for segment in segments}
    for index, region in enumerate(regions):
        where = f"key region {index + 1}"
        if not isinstance(region, dict):
            return f"This timeline's {where} isn't an object."
        field = _invalid_field(region, _REGION_FIELDS)
        if field:
            return f"This timeline's {where} has a missing or invalid {field}."
        tiling = _tiling_problem(regions, index, total, where)
        if tiling:
            return tiling
        # The viewer plays a segment in the key at its start, so a change inside one is missed.
        if index and region["start_beat"] not in segment_starts:
            return f"This timeline's {where} starts inside a segment."
    if key["source"] == "given" and len(regions) != 1:
        return f"This timeline's given key must be one region, not {len(regions)}."
    if len(regions) == 1 and regions[0]["label"] != key["label"]:
        return (
            f"This timeline's key region is labelled {regions[0]['label']}, "
            f"but its key is {key['label']}."
        )
    return None
