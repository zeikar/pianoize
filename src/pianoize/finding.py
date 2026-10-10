"""What every candidate kind shares: the thresholds, the candidate record, the cover as the kinds
read it, and how a candidate names its notes and lists the notes around it. The kinds are in
candidates.py, harmony.py and voice.py; docs/polishing.md describes them."""

import bisect
import math
from dataclasses import dataclass

import mido

from . import notes
from .melody import pitch_name
from .score import label
from .timeline import beat_position

_CONTEXT_BEATS = 1


@dataclass(frozen=True)
class Thresholds:
    short_ms: float = 50
    alone_ms: float = 30
    stutter_ms: float = 120
    velocity_above: float = 20
    off_grid_ms: float = 50
    roll_ms: float = 60
    density_factor: float = 3
    density_beats: int = 4
    duration_beats: float = 8
    coverage_below: float = 0.6
    leap_above: int = 12
    register_above: float = 12
    late_beats: float = 0.25


@dataclass(frozen=True)
class Candidate:
    id: str  # {category}:{kind}:{anchor}, the anchor a note id, b{beat} or s{start_beat}
    category: str
    kind: str
    time: float  # seconds
    beat: float  # fractional chordotomy beat
    note: dict | None  # a note candidate's note
    segment: dict | None  # a beat or segment candidate's beats and chord
    measurements: dict  # the key measurement first
    context: list[str]  # the notes around it, one string each
    suggested: dict | None  # an edit in the correction spec's format


@dataclass(frozen=True)
class Cover:
    midi: mido.MidiFile
    timeline: dict
    played: list[notes.Note]  # by onset
    positions: list[float]  # each note's onset as a fractional beat
    protected: set[str]
    same_pitch: dict[str, tuple[notes.Note | None, notes.Note | None]]  # id -> notes either side
    names: dict[str, str]  # each note's id -> the id candidates give it


def _same_pitch(played: list[notes.Note]) -> dict[str, tuple[notes.Note | None, notes.Note | None]]:
    """Each note's id -> the notes of its pitch just before and after it."""
    lines: dict[int, list[notes.Note]] = {}
    for note in played:
        lines.setdefault(note.pitch, []).append(note)
    around = {}
    for line in lines.values():
        for before, note, after in zip([None, *line[:-1]], line, [*line[1:], None], strict=True):
            around[note.id] = (before, after)
    return around


def read(
    midi: mido.MidiFile, timeline: dict, protected: set[str], names: dict[str, str] | None
) -> Cover:
    """The cover as the kinds read it. `names` maps each note's id to the id candidates give it;
    None gives every note its own."""
    played = notes.read(midi)
    positions = [beat_position(timeline, note.onset) for note in played]
    if names is None:
        names = {note.id: note.id for note in played}
    return Cover(midi, timeline, played, positions, protected, _same_pitch(played), names)


def name(cover: Cover, note: notes.Note) -> str:
    """The id a candidate gives a note: every note id in a candidate goes through here, so a run
    on a corrected cover names each note as the original cover does."""
    return cover.names[note.id]


def grid_time(timeline: dict, position: float) -> float:
    """Seconds at a fractional beat: the inverse of timeline.beat_position, extrapolated past
    either end with the neighbouring beat interval the same way."""
    beats = timeline["beats"]
    index = min(max(math.floor(position), 0), len(beats) - 2)
    return beats[index] + (position - index) * (beats[index + 1] - beats[index])


def ms(seconds: float) -> float:
    return round(seconds * 1000, 1)


def window(cover: Cover, center: float) -> range:
    """Indexes of the notes starting within a beat of a position."""
    low = bisect.bisect_left(cover.positions, center - _CONTEXT_BEATS)
    return range(low, bisect.bisect_right(cover.positions, center + _CONTEXT_BEATS))


def clock(seconds: float) -> str:
    """`m:ss.ss`."""
    minutes, rest = divmod(round(seconds, 2), 60)
    return f"{int(minutes)}:{rest:05.2f}"


def context_note(cover: Cover, note: notes.Note) -> str:
    """`t1234p60 1:02.35 C4 120ms v90`, with a trailing `*` when it carries the melody."""
    text = (
        f"{name(cover, note)} {clock(note.onset)} {pitch_name(note.pitch)} "
        f"{round((note.offset - note.onset) * 1000)}ms v{note.velocity}"
    )
    return f"{text} *" if note.id in cover.protected else text


def context(cover: Cover, center: float) -> list[str]:
    return [context_note(cover, cover.played[i]) for i in window(cover, center)]


def on_note(
    cover: Cover,
    category: str,
    kind: str,
    note: notes.Note,
    position: float,
    measurements: dict,
    suggested: dict | None,
) -> Candidate:
    return Candidate(
        id=f"{category}:{kind}:{name(cover, note)}",
        category=category,
        kind=kind,
        time=round(note.onset, 3),
        beat=round(position, 3),
        note={
            "id": name(cover, note),
            "pitch_name": pitch_name(note.pitch),
            "on_tick": note.on_tick,
            "off_tick": note.off_tick,
            "velocity": note.velocity,
            "duration_ms": ms(note.offset - note.onset),
            "protected": note.id in cover.protected,
        },
        segment=None,
        measurements=measurements,
        context=context(cover, position),
        suggested=suggested,
    )


def _chord_at(timeline: dict, beat: int) -> str | None:
    for segment in timeline["segments"]:
        if segment["start_beat"] <= beat < segment["end_beat"]:
            return label(segment)
    return None


def on_beat(cover: Cover, category: str, kind: str, beat: int, measurements: dict) -> Candidate:
    return Candidate(
        id=f"{category}:{kind}:b{beat}",
        category=category,
        kind=kind,
        time=round(grid_time(cover.timeline, beat), 3),
        beat=float(beat),
        note=None,
        segment={
            "start_beat": beat,
            "end_beat": beat + 1,
            "chord": _chord_at(cover.timeline, beat),
        },
        measurements=measurements,
        context=context(cover, beat + 0.5),
        suggested=None,
    )


def move(cover: Cover, note: notes.Note, on_tick: int) -> dict | None:
    """A `modify` edit that moves the note to start at `on_tick`, its length kept; None when the
    moved note would start before tick 0 or overlap a note of its pitch, which the applier
    refuses."""
    off_tick = on_tick + note.off_tick - note.on_tick
    before, after = cover.same_pitch[note.id]
    if (
        on_tick < 0
        or (before is not None and before.off_tick > on_tick)
        or (after is not None and off_tick > after.on_tick)
    ):
        return None
    return {"op": "modify", "note": name(cover, note), "on_tick": on_tick, "off_tick": off_tick}
