"""Scoring whether a result kept the original's harmony, checkpoint by checkpoint.

A chord passes when its root and triad class match, and its bass too where the original is
inverted; it is looked up at the same time within one beat either way (docs/evaluation.md).
"""

import bisect
import statistics
from dataclasses import dataclass

from pianoize.checkpoints import Checkpoint, Excluded
from pianoize.chords import INTERVALS, parse_chord
from pianoize.timeline import beat_time

# Every quality's first three tones are its triad, so a seventh or an added tone falls away.
# The suspensions keep their own classes, so one matches only the same suspension.
_TRIAD_CLASSES = {
    (0, 4, 7): "maj",
    (0, 3, 7): "min",
    (0, 3, 6): "dim",
    (0, 4, 8): "aug",
    (0, 2, 7): "sus2",
    (0, 5, 7): "sus4",
}

# Timeline times are rounded to the millisecond.
_ROUNDING = 0.001


@dataclass(frozen=True)
class ScoredSegment:
    start_beat: int
    original: str  # slash form, e.g. C:maj/E
    shown: str | None  # the chosen result chord, else the one sounding; None when nothing does
    passed: bool
    exact: bool
    excluded: bool  # shown, not counted


@dataclass(frozen=True)
class ScoredCheckpoint:
    checkpoint: Checkpoint
    segments: list[ScoredSegment]

    @property
    def passed(self) -> bool:
        return all(s.passed for s in self.segments if not s.excluded)


@dataclass(frozen=True)
class Row:
    checkpoints: list[ScoredCheckpoint]
    grid_distance: float


def triad(label: str) -> tuple[int | None, str]:
    """(root pitch class, triad class); (None, "N") for N."""
    parsed = parse_chord(label)
    if parsed is None:
        return None, "N"
    root, quality = parsed
    if quality not in INTERVALS:
        raise ValueError(f"{label}: unknown chord quality {quality!r}")
    return root, _TRIAD_CLASSES[INTERVALS[quality][:3]]


def _inverted(segment: dict) -> bool:
    return segment["inversion"] not in ("root", None)


def passes(original: dict, result: dict) -> bool:
    """Two segments: the same root and triad class, and the original's bass where it's inverted."""
    if triad(original["chord"]) != triad(result["chord"]):
        return False
    return not _inverted(original) or result["bass"] == original["bass"]


def exact(original: dict, result: dict) -> bool:
    """Two segments: the same chord label and the same bass."""
    return original["chord"] == result["chord"] and original["bass"] == result["bass"]


def window(original: dict, segment: dict) -> tuple[float, float]:
    """The times a result chord may start and still arrive with this segment."""
    start = segment["start_beat"]
    # Rounded back to milliseconds, or 2.55 + 0.001 would fall just short of 2.551.
    return (
        round(beat_time(original, start - 1) - _ROUNDING, 3),
        round(beat_time(original, start + 1) + _ROUNDING, 3),
    )


def _sounding(timeline: dict, time: float) -> dict | None:
    return next((s for s in timeline["segments"] if s["start_time"] <= time < s["end_time"]), None)


def _held(original: dict, result: dict, segment: dict) -> dict | None:
    """The result chord sounding at the segment's start, when it passes this segment and the one
    before: a held chord keeps passing across a boundary the pass rule doesn't see, such as a
    seventh coming or going or a bass move under a root-position chord. The song's first segment
    has no boundary to cross."""
    held = _sounding(result, segment["start_time"])
    if held is None or not passes(segment, held):
        return None
    before = next((s for s in original["segments"] if s["end_beat"] == segment["start_beat"]), None)
    if before is not None and not passes(before, held):
        return None
    return held


def candidates(original: dict, result: dict, segment: dict, held: dict | None) -> list[dict]:
    """The result segments starting within one beat of this segment, and the held one, in time
    order. `held` is the result chord `_held` found for this segment, or None."""
    low, high = window(original, segment)
    return [s for s in result["segments"] if low <= s["start_time"] <= high or s is held]


def _label(segment: dict) -> str:
    if _inverted(segment):
        return f"{segment['chord']}/{segment['bass']}"
    return segment["chord"]


def _grid_distance(original: dict, result: dict) -> float:
    """Median seconds from each result beat to the nearest original beat: how far apart the two
    analyses' beat grids sit, not whether the chords line up."""
    beats = original["beats"]
    distances = []
    for time in result["beats"]:
        i = bisect.bisect_left(beats, time)
        distances.append(min(abs(time - beats[j]) for j in (i - 1, i) if 0 <= j < len(beats)))
    return statistics.median(distances)


def _inside(start_beat: int, span: Checkpoint | Excluded) -> bool:
    return span.start_beat <= start_beat < span.end_beat


def score(
    original: dict, checkpoints: list[Checkpoint], excluded: list[Excluded], result: dict
) -> Row:
    # One pass over the original's segments in time order chooses a result chord for every
    # segment some checkpoint covers, so a segment's result doesn't depend on how the checkpoints
    # are split or overlap. `last`, the chord chosen last, keeps one result chord from being taken
    # twice or out of order: excluded and failed segments carry it on, an unscored segment
    # starts it again.
    scored = []
    last = None
    for segment in original["segments"]:
        start = segment["start_beat"]
        if not any(_inside(start, c) for c in checkpoints):
            last = None
            continue
        held = _held(original, result, segment)
        chosen = None
        for c in candidates(original, result, segment, held):
            in_order = last is None or (
                c["start_time"] >= last["start_time"] and (c is not last or c is held)
            )
            if in_order and passes(segment, c):
                chosen = c
                break
        shown = chosen if chosen is not None else _sounding(result, segment["start_time"])
        scored.append(
            ScoredSegment(
                start_beat=start,
                original=_label(segment),
                shown=_label(shown) if shown is not None else None,
                passed=chosen is not None,
                exact=chosen is not None and exact(segment, chosen),
                excluded=any(_inside(start, e) for e in excluded),
            )
        )
        if chosen is not None:
            last = chosen
    return Row(
        [ScoredCheckpoint(c, [s for s in scored if _inside(s.start_beat, c)]) for c in checkpoints],
        _grid_distance(original, result),
    )
