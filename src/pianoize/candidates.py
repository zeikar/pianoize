"""Candidate problems in a cover for an agent to judge: notes that sound like slips and timing that
stumbles. The kinds, the grid and the thresholds are in docs/polishing.md."""

import bisect
import json
import math
import statistics
from collections import Counter
from collections.abc import Iterator
from dataclasses import asdict, dataclass
from pathlib import Path

import mido

from . import corrections, notes
from .melody import pitch_name
from .score import label
from .timeline import beat_position

CATEGORIES = ("glitch", "timing", "voice", "harmony")

_SIXTEENTHS = 4
_TRIPLETS = 3
_TRIPLET_GAIN = 1 / 3  # the share of a beat's deviation the 3-grid must cut to replace the 4
_TRIPLET_ATTACKS = 2  # so that one stray attack can't switch a beat to triplets
_ROLL_ATTACKS = 3  # two attacks in a row make no roll: one may just be late
_CONTEXT_BEATS = 1


@dataclass(frozen=True)
class Thresholds:
    short_ms: float = 50
    alone_ms: float = 30
    stutter_ms: float = 120
    velocity_above: float = 20
    off_grid_ms: float = 45
    roll_ms: float = 60
    density_factor: float = 3
    density_beats: int = 4
    duration_beats: float = 8


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
    context: list[str]  # the notes starting within a beat of it, one string each
    suggested: dict | None  # an edit in the correction spec's format


@dataclass(frozen=True)
class _Cover:
    midi: mido.MidiFile
    timeline: dict
    played: list[notes.Note]  # by onset
    positions: list[float]  # each note's onset as a fractional beat
    protected: set[str]
    same_pitch: dict[str, tuple[notes.Note | None, notes.Note | None]]  # id -> notes either side


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


def grid_time(timeline: dict, position: float) -> float:
    """Seconds at a fractional beat: the inverse of timeline.beat_position, extrapolated past
    either end with the neighbouring beat interval the same way."""
    beats = timeline["beats"]
    index = min(max(math.floor(position), 0), len(beats) - 2)
    return beats[index] + (position - index) * (beats[index + 1] - beats[index])


def _ms(seconds: float) -> float:
    return round(seconds * 1000, 1)


def _deviation(offsets: list[float], parts: int) -> float:
    return sum(abs(offset - round(offset * parts) / parts) for offset in offsets)


def _divisions(starts: list[float]) -> dict[int, int]:
    """Each beat's subdivisions from its attacks' starts: 4, unless at least two attacks lie
    nearer a triplet line inside the beat than its start or end and the 3-grid cuts their total
    distance to the grid by a third. A beat without attacks is absent and takes 4."""
    offsets: dict[int, list[float]] = {}
    for start in starts:
        beat = math.floor(start)
        offsets.setdefault(beat, []).append(start - beat)
    chosen = {}
    for beat, found in offsets.items():
        inside = sum(1 for offset in found if round(offset * _TRIPLETS) in (1, 2))
        sixteenths = _deviation(found, _SIXTEENTHS)
        triplets = _deviation(found, _TRIPLETS)
        cut = (
            inside >= _TRIPLET_ATTACKS
            and sixteenths > 0
            and triplets <= sixteenths * (1 - _TRIPLET_GAIN)
        )
        chosen[beat] = _TRIPLETS if cut else _SIXTEENTHS
    return chosen


def _line(divisions: dict[int, int], position: float) -> tuple[float, int]:
    """The grid line nearest a position, and the subdivisions of its beat."""
    beat = math.floor(position)
    parts = divisions.get(beat, _SIXTEENTHS)
    return beat + round((position - beat) * parts) / parts, parts


def _step(previous: list[notes.Note], attack: list[notes.Note], gap: float) -> bool | None:
    """True when the attack starts within `gap` of the previous one and lies wholly above it,
    False when wholly below, else None."""
    if attack[0].onset - previous[0].onset > gap:
        return None
    if min(n.pitch for n in attack) > max(n.pitch for n in previous):
        return True
    if max(n.pitch for n in attack) < min(n.pitch for n in previous):
        return False
    return None


def _followers(run: list[list[notes.Note]]) -> set[str]:
    if len(run) < _ROLL_ATTACKS:
        return set()
    return {note.id for attack in run[1:] for note in attack}


def _roll_followers(attacks: list[list[notes.Note]], gap: float) -> set[str]:
    """Ids of the notes of ordered rolls after their first attack.

    A roll is a run of at least three attacks, each starting within `gap` of the previous and
    lying wholly above it throughout or wholly below it throughout. An attack that turns back
    starts a new run with the one before it; one that does neither starts a new run alone."""
    found: set[str] = set()
    run: list[list[notes.Note]] = []
    rising: bool | None = None
    for attack in attacks:
        step = _step(run[-1], attack, gap) if run else None
        if step is not None and rising in (None, step):
            run.append(attack)
        else:
            found |= _followers(run)
            run = [run[-1], attack] if step is not None else [attack]
        rising = step
    return found | _followers(run)


def _window(cover: _Cover, center: float) -> range:
    """Indexes of the notes starting within a beat of a position."""
    low = bisect.bisect_left(cover.positions, center - _CONTEXT_BEATS)
    return range(low, bisect.bisect_right(cover.positions, center + _CONTEXT_BEATS))


def _clock(seconds: float) -> str:
    minutes, rest = divmod(round(seconds, 2), 60)
    return f"{int(minutes)}:{rest:05.2f}"


def _context_note(cover: _Cover, note: notes.Note) -> str:
    """`t1234p60 1:02.35 C4 120ms v90`, with a trailing `*` when it carries the melody."""
    text = (
        f"{note.id} {_clock(note.onset)} {pitch_name(note.pitch)} "
        f"{round((note.offset - note.onset) * 1000)}ms v{note.velocity}"
    )
    return f"{text} *" if note.id in cover.protected else text


def _context(cover: _Cover, center: float) -> list[str]:
    return [_context_note(cover, cover.played[i]) for i in _window(cover, center)]


def _on_note(
    cover: _Cover,
    category: str,
    kind: str,
    note: notes.Note,
    position: float,
    measurements: dict,
    suggested: dict | None,
) -> Candidate:
    return Candidate(
        id=f"{category}:{kind}:{note.id}",
        category=category,
        kind=kind,
        time=round(note.onset, 3),
        beat=round(position, 3),
        note={
            "id": note.id,
            "pitch_name": pitch_name(note.pitch),
            "on_tick": note.on_tick,
            "off_tick": note.off_tick,
            "velocity": note.velocity,
            "duration_ms": _ms(note.offset - note.onset),
            "protected": note.id in cover.protected,
        },
        segment=None,
        measurements=measurements,
        context=_context(cover, position),
        suggested=suggested,
    )


def _delete(note: notes.Note) -> dict:
    return {"op": "delete", "note": note.id}


def _short(cover: _Cover, limits: Thresholds) -> Iterator[Candidate]:
    onsets = [note.onset for note in cover.played]
    for i, (note, position) in enumerate(zip(cover.played, cover.positions, strict=True)):
        if note.offset - note.onset >= limits.short_ms / 1000:
            continue
        # Sorted by onset, the nearest other onset is a neighbour.
        nearest = min(
            (abs(onsets[j] - note.onset) for j in (i - 1, i + 1) if 0 <= j < len(onsets)),
            default=None,
        )
        if nearest is not None and nearest <= limits.alone_ms / 1000:
            continue
        measured = {
            "duration_ms": _ms(note.offset - note.onset),
            "nearest_onset_ms": None if nearest is None else _ms(nearest),
        }
        yield _on_note(cover, "glitch", "short", note, position, measured, _delete(note))


def _length(note: notes.Note) -> float:
    return note.offset - note.onset


def _stutter(cover: _Cover, limits: Thresholds) -> Iterator[Candidate]:
    for note, position in zip(cover.played, cover.positions, strict=True):
        previous, _ = cover.same_pitch[note.id]
        if previous is None or note.onset - previous.onset > limits.stutter_ms / 1000:
            continue
        # Mostly one strike is a sliver and the other the held note, so the shorter one goes.
        shorter = previous if _length(previous) < _length(note) else note
        measured = {"after_ms": _ms(note.onset - previous.onset), "previous": previous.id}
        yield _on_note(cover, "glitch", "stutter", note, position, measured, _delete(shorter))


def _velocity(cover: _Cover, limits: Thresholds) -> Iterator[Candidate]:
    for i, (note, position) in enumerate(zip(cover.played, cover.positions, strict=True)):
        # The melody is voiced over the accompaniment, so a note is compared with its own role
        # only, and not at all when no note of its role is near.
        melody = note.id in cover.protected
        same = [
            cover.played[j].velocity
            for j in _window(cover, position)
            if j != i and (cover.played[j].id in cover.protected) == melody
        ]
        if not same:
            continue
        median = float(statistics.median(same))
        if note.velocity - median < limits.velocity_above:
            continue
        measured = {
            "velocity": note.velocity,
            "median": round(median, 1),
            "above": round(note.velocity - median, 1),
        }
        suggested = {"op": "modify", "note": note.id, "velocity": round(median)}
        yield _on_note(cover, "glitch", "velocity", note, position, measured, suggested)


def _fits(cover: _Cover, note: notes.Note, on_tick: int, off_tick: int) -> bool:
    """Whether the note moved to these ticks stays clear of the notes of its pitch around it, as
    the applier requires, and starts at tick 0 or later."""
    before, after = cover.same_pitch[note.id]
    return (
        on_tick >= 0
        and (before is None or before.off_tick <= on_tick)
        and (after is None or off_tick <= after.on_tick)
    )


def _off_grid(
    cover: _Cover,
    limits: Thresholds,
    timed: list[tuple[notes.Note, float]],
    divisions: dict[int, int],
) -> Iterator[Candidate]:
    for note, position in timed:
        line, parts = _line(divisions, position)
        target = grid_time(cover.timeline, line)
        if abs(note.onset - target) <= limits.off_grid_ms / 1000:
            continue
        on_tick = notes.tick_at(cover.midi, target)
        off_tick = on_tick + note.off_tick - note.on_tick
        suggested = None
        if _fits(cover, note, on_tick, off_tick):
            suggested = {"op": "modify", "note": note.id, "on_tick": on_tick, "off_tick": off_tick}
        measured = {
            "off_ms": _ms(note.onset - target),
            "subdivisions": parts,
            "grid_beat": round(line, 3),
        }
        yield _on_note(cover, "timing", "off-grid", note, position, measured, suggested)


def _chord_at(timeline: dict, beat: int) -> str | None:
    for segment in timeline["segments"]:
        if segment["start_beat"] <= beat < segment["end_beat"]:
            return label(segment)
    return None


def _density(
    cover: _Cover, limits: Thresholds, starts: list[float], divisions: dict[int, int]
) -> Iterator[Candidate]:
    # An attack counts in the beat of its nearest grid line, so one played a little early still
    # counts on its beat.
    counts = Counter(math.floor(_line(divisions, start)[0]) for start in starts)
    if not counts:
        return
    first, last = min(counts), max(counts)
    for beat in range(first, last + 1):
        around = [
            counts[b]
            for b in range(beat - limits.density_beats, beat + limits.density_beats + 1)
            if b != beat and first <= b <= last
        ]
        if not around:
            continue
        median = float(statistics.median(around))
        # A dip needs a median of at least the factor, so at least one attack was expected.
        spike = median >= 1 and counts[beat] >= limits.density_factor * median
        dip = median >= limits.density_factor and counts[beat] <= median / limits.density_factor
        if not (spike or dip):
            continue
        yield Candidate(
            id=f"timing:density:b{beat}",
            category="timing",
            kind="density",
            time=round(grid_time(cover.timeline, beat), 3),
            beat=float(beat),
            note=None,
            segment={
                "start_beat": beat,
                "end_beat": beat + 1,
                "chord": _chord_at(cover.timeline, beat),
            },
            measurements={"attacks": counts[beat], "median": median},
            context=_context(cover, beat + 0.5),
            suggested=None,
        )


def _duration(cover: _Cover, limits: Thresholds) -> Iterator[Candidate]:
    for note, position in zip(cover.played, cover.positions, strict=True):
        length = beat_position(cover.timeline, note.offset) - position
        if length <= limits.duration_beats:
            continue
        end = grid_time(cover.timeline, position + limits.duration_beats)
        off_tick = notes.tick_at(cover.midi, end)
        suggested = None
        # A cut that rounds onto the note's own end would change nothing.
        if note.on_tick < off_tick < note.off_tick:
            suggested = {"op": "modify", "note": note.id, "off_tick": off_tick}
        measured = {"beats": round(length, 3)}
        yield _on_note(cover, "timing", "duration", note, position, measured, suggested)


def find(
    midi: mido.MidiFile, timeline: dict, protected: set[str], thresholds: Thresholds
) -> list[Candidate]:
    """Every candidate in a cover, by time then id. `protected` holds the ids of the notes that
    carry the melody (notes.protected); `timeline` gives the beats the grid divides."""
    played = notes.read(midi)
    positions = [beat_position(timeline, note.onset) for note in played]
    cover = _Cover(midi, timeline, played, positions, protected, _same_pitch(played))
    attacks = notes.clusters(played)
    followers = _roll_followers(attacks, thresholds.roll_ms / 1000)
    # The grid and density see each attack once by its first note; rolls only by their first.
    starts = [
        beat_position(timeline, attack[0].onset)
        for attack in attacks
        if attack[0].id not in followers
    ]
    divisions = _divisions(starts)
    timed = [(n, p) for n, p in zip(played, positions, strict=True) if n.id not in followers]
    found = [
        *_short(cover, thresholds),
        *_stutter(cover, thresholds),
        *_velocity(cover, thresholds),
        *_off_grid(cover, thresholds, timed, divisions),
        *_density(cover, thresholds, starts, divisions),
        *_duration(cover, thresholds),
    ]
    return sorted(found, key=lambda candidate: (candidate.time, candidate.id))


def to_json(candidates: list[Candidate], inputs: dict[str, Path], thresholds: Thresholds) -> str:
    """The finder's output file: each input's path and SHA-256 (name -> path, in order), the
    thresholds and the candidates."""
    data = {
        "inputs": {
            name: {"path": str(path), "sha256": corrections.sha256(path)}
            for name, path in inputs.items()
        },
        "thresholds": asdict(thresholds),
        "candidates": [asdict(candidate) for candidate in candidates],
    }
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"
