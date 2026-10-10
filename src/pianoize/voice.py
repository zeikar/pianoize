"""Voice candidates on the bass line: leaps between chords, register jumps and a bass that
reaches a chord change late. The rules are in docs/polishing.md."""

import bisect
import math
import statistics
from collections.abc import Iterator
from itertools import pairwise
from typing import NamedTuple

from . import finding, notes
from .chords import ROOT_NAMES
from .finding import Candidate, Cover, Thresholds, grid_time, name, on_beat, on_note
from .timeline import beat_position

_BASS_BELOW = 60  # an attack's lowest note is a bass note only below middle C
_LATE_WITHIN = 1  # beats: a bass pitch class arriving later than this starts a new figure


class Bass(NamedTuple):
    note: notes.Note  # the lowest note of its attack
    position: float  # its onset as a fractional beat
    attack: list[notes.Note]


def bass_line(cover: Cover) -> list[Bass]:
    """The lowest note of each attack of the accompaniment (notes starting within 30 ms of the
    attack's first), when below MIDI 60, by onset."""
    accompaniment = [n for n in cover.played if n.id not in cover.protected]
    line = []
    for attack in notes.clusters(accompaniment):
        lowest = min(attack, key=lambda n: n.pitch)
        if lowest.pitch < _BASS_BELOW:
            line.append(Bass(lowest, beat_position(cover.timeline, lowest.onset), attack))
    return line


def _segment_basses(cover: Cover, limits: Thresholds, line: list[Bass]) -> list[Bass | None]:
    """Each segment's bass note: the lowest bass note starting from `off_grid_ms` before the
    segment start to a beat after it. None under N or when no bass note starts there."""
    onsets = [bass.note.onset for bass in line]
    found: list[Bass | None] = []
    for segment in cover.timeline["segments"]:
        low = bisect.bisect_left(onsets, segment["start_time"] - limits.off_grid_ms / 1000)
        high = bisect.bisect_left(onsets, grid_time(cover.timeline, segment["start_beat"] + 1))
        inside = line[low:high] if segment["chord"] != "N" else []
        found.append(min(inside, key=lambda bass: bass.note.pitch, default=None))
    return found


def _leap(cover: Cover, limits: Thresholds, line: list[Bass]) -> Iterator[Candidate]:
    # Voice leading is the bass's step from chord to chord: a figure inside one chord, an
    # oom-pah or a walk up an arpeggio, is the texture.
    for previous, bass in pairwise(_segment_basses(cover, limits, line)):
        if previous is None or bass is None:
            continue
        jump = bass.note.pitch - previous.note.pitch
        if abs(jump) <= limits.leap_above:
            continue
        measured = {"semitones": jump, "previous": name(cover, previous.note)}
        yield on_note(cover, "voice", "leap", bass.note, bass.position, measured, None)


def _register(cover: Cover, limits: Thresholds, line: list[Bass]) -> Iterator[Candidate]:
    pitches: dict[int, list[int]] = {}
    for bass in line:
        pitches.setdefault(math.floor(bass.position), []).append(bass.note.pitch)
    for beat in sorted(pitches):
        if beat - 1 not in pitches:
            continue
        median = float(statistics.median(pitches[beat]))
        previous = float(statistics.median(pitches[beat - 1]))
        if abs(median - previous) <= limits.register_above:
            continue
        measured = {
            "semitones": round(median - previous, 1),
            "median": round(median, 1),
            "previous_median": round(previous, 1),
        }
        yield on_beat(cover, "voice", "register", beat, measured)


def _arrival(following: list[Bass], bass: int, until: float) -> Bass | None:
    """The first of the bass notes after the first one on the bass pitch class; None when none
    starts by `until` (seconds)."""
    for found in following[1:]:
        if found.note.onset > until:
            return None
        if found.note.pitch % 12 == bass:
            return found
    return None


def _late_note(
    cover: Cover, limits: Thresholds, segment: dict, following: list[Bass], at_change: bool
) -> tuple[notes.Note, float, float] | None:
    """The note on the segment's bass pitch class that comes late, its position and how many
    beats late; None when the bass is in time. `following` starts with the first bass note at the
    change or after it, which is not on the bass pitch class."""
    bass = ROOT_NAMES.index(segment["bass"])
    until = grid_time(cover.timeline, segment["start_beat"] + _LATE_WITHIN)
    arrival = _arrival(following, bass, until + limits.off_grid_ms / 1000)
    if arrival is not None:
        late = round(arrival.position - segment["start_beat"], 3)
        if late >= limits.late_beats:
            return arrival.note, arrival.position, late
    # The bass pitch class struck at the change over a lower note is not the bass either, so a
    # late bass moved onto the change on top of the old one stays flagged under its own id.
    above = [n for n in following[0].attack if n.pitch % 12 == bass]
    if not at_change or not above:
        return None
    note = min(above, key=lambda n: n.pitch)
    return note, beat_position(cover.timeline, note.onset), 0.0


def _bass_late(cover: Cover, limits: Thresholds, line: list[Bass]) -> Iterator[Candidate]:
    onsets = [found.note.onset for found in line]
    for before, segment in pairwise(cover.timeline["segments"]):
        if segment["bass"] is None or segment["bass"] == before["bass"]:
            continue
        start = segment["start_time"]
        # As on the grid, an onset up to off_grid_ms off a beat is played on it: the first bass
        # note may come that early, and the bass that late after the beat that ends the window.
        tolerance = limits.off_grid_ms / 1000
        following = line[bisect.bisect_left(onsets, start - tolerance) :]
        if not following or following[0].note.pitch % 12 == ROOT_NAMES.index(segment["bass"]):
            continue
        first = following[0].note
        at_change = first.onset <= start + tolerance
        found = _late_note(cover, limits, segment, following, at_change)
        if found is None:
            continue
        note, position, late = found
        # With a wrong bass note at the change, moving the bass there only stacks it on top:
        # the agent decides about that note first.
        suggested = (
            None if at_change else finding.move(cover, note, notes.tick_at(cover.midi, start))
        )
        measured = {"late_beats": late, "bass": segment["bass"], "first": name(cover, first)}
        yield on_note(cover, "voice", "bass-late", note, position, measured, suggested)


def find(cover: Cover, limits: Thresholds) -> Iterator[Candidate]:
    """`leap`, `register` and `bass-late` candidates on the accompaniment's bass line."""
    line = bass_line(cover)
    yield from _leap(cover, limits, line)
    yield from _register(cover, limits, line)
    yield from _bass_late(cover, limits, line)
