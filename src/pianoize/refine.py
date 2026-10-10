"""Refined harmony timelines: chordotomy's timeline with the chords an agent decided over beat
ranges, checked by the viewer's rules. The edits file is in docs/polishing.md."""

import copy
import json
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path

from . import files, timeline
from .chords import ROOT_NAMES, inversion, is_label
from .corrections import sha256

_KEYS = {"inputs", "edits"}
_NEEDS = ("start_beat", "end_beat", "chord", "bass", "reason")
_TAKES = {*_NEEDS, "readings"}
# chordotomy's harmonic analysis is not ported: the viewer's reanalyze() recomputes these from the
# chords on the first edit there, and its timelineProblem accepts null.
_ANALYSIS = ("numeral", "role", "function", "target")


class RefineError(ValueError):
    pass


@dataclass(frozen=True)
class Edit:
    start_beat: int
    end_beat: int  # exclusive
    chord: str
    bass: str | None
    reason: str


def _changes(edit: Edit, segment: dict) -> bool:
    """Whether the edit covers part of the segment and gives it another chord or bass."""
    return (
        edit.start_beat < segment["end_beat"]
        and segment["start_beat"] < edit.end_beat
        and (edit.chord, edit.bass) != (segment["chord"], segment["bass"])
    )


def _edit(item, where: str, original: dict) -> Edit:
    if not isinstance(item, dict):
        raise RefineError(f"{where} must be an object")
    for key in _NEEDS:
        if key not in item:
            raise RefineError(f"{where} is missing {key!r}")
    extra = sorted(set(item) - _TAKES)
    if extra:
        raise RefineError(f"{where} does not take {', '.join(extra)}")
    start, end, chord, bass, reason = (item[key] for key in _NEEDS)
    total = len(original["beats"])
    if not (type(start) is int and type(end) is int and 0 <= start < end <= total):
        raise RefineError(
            f"{where}: beats {start!r}-{end!r} are not inside the timeline (0-{total})"
        )
    if not is_label(chord):
        raise RefineError(f"{where}: chord {chord!r} is not N or a sharp root and a known quality")
    if bass is not None and bass not in ROOT_NAMES:
        raise RefineError(f"{where}: bass {bass!r} must be a sharp root or null")
    if chord == "N" and bass is not None:
        raise RefineError(f"{where}: N takes no bass")
    if not isinstance(reason, str) or not reason.strip():
        raise RefineError(f"{where}: reason must be a non-empty string")
    if not isinstance(item.get("readings", {}), dict):
        raise RefineError(f"{where}: readings must be an object")
    edit = Edit(start, end, chord, bass, reason)
    if not any(_changes(edit, segment) for segment in original["segments"]):
        raise RefineError(
            f"{where}: changes nothing: beats {start}-{end} already have chord {chord} "
            f"and bass {'null' if bass is None else bass}"
        )
    return edit


def load_edits(path: str | Path, timeline_path: str | Path, original: dict) -> list[Edit]:
    """Read and validate the edits for the timeline loaded from timeline_path; see
    docs/polishing.md for the rules."""
    reason = timeline.problem(original)
    if reason:
        raise RefineError(f"{timeline_path}: {reason}")
    path = Path(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:  # also undecodable bytes
        raise RefineError(f"{path}: not valid JSON ({exc})") from exc
    if not isinstance(data, dict):
        raise RefineError(f"{path} must be an object")
    extra = sorted(set(data) - _KEYS)
    if extra:
        raise RefineError(f"the edits file does not take {', '.join(extra)}")
    inputs = data.get("inputs")
    entry = inputs.get("timeline") if isinstance(inputs, dict) else None
    digest = sha256(timeline_path)
    if not isinstance(entry, dict) or entry.get("sha256") != digest:
        raise RefineError(f"inputs.timeline: sha256 does not match {timeline_path} ({digest})")
    items = data.get("edits", [])
    if not isinstance(items, list):
        raise RefineError("edits must be a list")
    edits = [_edit(item, f"edits[{index}]", original) for index, item in enumerate(items)]
    # Sorted by start, any overlap shows between neighbours.
    order = sorted(range(len(edits)), key=lambda index: edits[index].start_beat)
    for first, second in pairwise(order):
        if edits[second].start_beat < edits[first].end_beat:
            later, earlier = max(first, second), min(first, second)
            raise RefineError(
                f"edits[{later}]: beats {edits[later].start_beat}-{edits[later].end_beat} "
                f"overlap edits[{earlier}] ({edits[earlier].start_beat}-{edits[earlier].end_beat})"
            )
    return edits


def apply(original: dict, edits: list[Edit]) -> tuple[dict, int]:
    """The refined timeline, a copy of the original, and how many of its segments the edits set.

    A segment is cut where an edit that changes it starts or ends; both parts keep its fields and
    take their times from the beats, as the viewer's split does. A part inside such an edit takes
    its chord and bass, with their inversion, `edited: true` and no numeral, role, function or
    target. A part already on the edit's chord and bass is left as it is, as the viewer leaves a
    chord picked again.
    """
    result = copy.deepcopy(original)
    segments = []
    changed = 0
    for segment in result["segments"]:
        start, end = segment["start_beat"], segment["end_beat"]
        changing = [edit for edit in edits if _changes(edit, segment)]
        cuts = {start, end}
        for edit in changing:
            cuts |= {max(edit.start_beat, start), min(edit.end_beat, end)}
        for low, high in pairwise(sorted(cuts)):
            part = copy.deepcopy(segment)
            part.update(
                start_beat=low,
                end_beat=high,
                start_time=timeline.beat_time(result, low),
                end_time=timeline.beat_time(result, high),
            )
            edit = next((e for e in changing if e.start_beat <= low and high <= e.end_beat), None)
            if edit is not None:
                part.update(
                    chord=edit.chord,
                    bass=edit.bass,
                    inversion=inversion(edit.chord, edit.bass),
                    edited=True,
                    **dict.fromkeys(_ANALYSIS),
                )
                changed += 1
            segments.append(part)
    result["segments"] = segments
    reason = timeline.problem(result)
    if reason:
        raise RefineError(f"the refined timeline would not open in the viewer: {reason}")
    return result, changed


def write(data: dict, out: Path) -> None:
    """Write the timeline as chordotomy writes one, so that a failed write leaves any existing file
    as it was."""
    # NaN and Infinity are refused: the browser's JSON.parse can't read them.
    try:
        text = json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False)
    except ValueError as exc:
        raise RefineError(f"the refined timeline holds a number JSON can't write: {exc}") from exc
    # As chordotomy's CLI: indented, UTF-8 characters as themselves, a trailing newline, and a lone
    # surrogate (from a path that was not UTF-8) written back as the JSON escape it was read from.
    encoded = (text + "\n").encode("utf-8", "backslashreplace")
    files.write_all({out: lambda path: path.write_bytes(encoded)})
