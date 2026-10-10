"""Candidate problems in a cover for an agent to judge: notes that sound like slips and timing that
stumbles, here; harmony and voice leading in harmony.py and voice.py. The kinds, the grid and the
thresholds are in docs/polishing.md."""

import json
import math
import statistics
from collections import Counter
from collections.abc import Iterator
from dataclasses import asdict
from pathlib import Path

import mido

from . import corrections, finding, harmony, notes, voice
from .finding import Candidate, Cover, Thresholds, grid_time, ms, name, on_note
from .timeline import beat_position

CATEGORIES = ("glitch", "timing", "voice", "harmony")

_SIXTEENTHS = 4
_TRIPLETS = 3
_TRIPLET_GAIN = 1 / 3  # the share of a beat's deviation the 3-grid must cut to replace the 4
_TRIPLET_ATTACKS = 2  # so that one stray attack can't switch a beat to triplets
_ROLL_ATTACKS = 3  # two attacks in a row make no roll: one may just be late


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


def _delete(cover: Cover, note: notes.Note) -> dict:
    return {"op": "delete", "note": name(cover, note)}


def _short(cover: Cover, limits: Thresholds) -> Iterator[Candidate]:
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
            "duration_ms": ms(note.offset - note.onset),
            "nearest_onset_ms": None if nearest is None else ms(nearest),
        }
        yield on_note(cover, "glitch", "short", note, position, measured, _delete(cover, note))


def _length(note: notes.Note) -> float:
    return note.offset - note.onset


def _stutter(cover: Cover, limits: Thresholds) -> Iterator[Candidate]:
    deleted: set[str] = set()
    for note, position in zip(cover.played, cover.positions, strict=True):
        previous, _ = cover.same_pitch[note.id]
        if previous is None or note.onset - previous.onset > limits.stutter_ms / 1000:
            continue
        # Mostly one strike is a sliver and the other the held note, so the shorter one goes.
        shorter = previous if _length(previous) < _length(note) else note
        # Of three quick strikes the middle one can be the shorter of both pairs: one edit per note.
        suggested = None if shorter.id in deleted else _delete(cover, shorter)
        deleted.add(shorter.id)
        measured = {"after_ms": ms(note.onset - previous.onset), "previous": name(cover, previous)}
        yield on_note(cover, "glitch", "stutter", note, position, measured, suggested)


def _velocity(cover: Cover, limits: Thresholds) -> Iterator[Candidate]:
    for i, (note, position) in enumerate(zip(cover.played, cover.positions, strict=True)):
        # The melody is voiced over the accompaniment, so a note is compared with its own role
        # only, and not at all when no note of its role is near.
        melody = note.id in cover.protected
        same = [
            cover.played[j].velocity
            for j in finding.window(cover, position)
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
        suggested = {"op": "modify", "note": name(cover, note), "velocity": round(median)}
        yield on_note(cover, "glitch", "velocity", note, position, measured, suggested)


def _off_grid(
    cover: Cover,
    limits: Thresholds,
    timed: list[tuple[notes.Note, float]],
    divisions: dict[int, int],
) -> Iterator[Candidate]:
    for note, position in timed:
        line, parts = _line(divisions, position)
        target = grid_time(cover.timeline, line)
        if abs(note.onset - target) <= limits.off_grid_ms / 1000:
            continue
        suggested = finding.move(cover, note, notes.tick_at(cover.midi, target))
        measured = {
            "off_ms": ms(note.onset - target),
            "subdivisions": parts,
            "grid_beat": round(line, 3),
        }
        yield on_note(cover, "timing", "off-grid", note, position, measured, suggested)


def _density(
    cover: Cover, limits: Thresholds, starts: list[float], divisions: dict[int, int]
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
        measured = {"attacks": counts[beat], "median": median}
        yield finding.on_beat(cover, "timing", "density", beat, measured)


def _duration(cover: Cover, limits: Thresholds) -> Iterator[Candidate]:
    for note, position in zip(cover.played, cover.positions, strict=True):
        # Rounded as printed: a note cut to the nearest tick may end a hair past the limit.
        length = round(beat_position(cover.timeline, note.offset) - position, 3)
        if length <= limits.duration_beats:
            continue
        end = grid_time(cover.timeline, position + limits.duration_beats)
        off_tick = notes.tick_at(cover.midi, end)
        suggested = None
        # A cut that rounds onto the note's own end would change nothing.
        if note.on_tick < off_tick < note.off_tick:
            suggested = {"op": "modify", "note": name(cover, note), "off_tick": off_tick}
        measured = {"beats": length}
        yield on_note(cover, "timing", "duration", note, position, measured, suggested)


def find(
    midi: mido.MidiFile,
    timeline: dict,
    protected: set[str],
    thresholds: Thresholds,
    names: dict[str, str] | None = None,
) -> list[Candidate]:
    """Every candidate in a cover, by time then id. `protected` holds the ids of the notes that
    carry the melody (notes.protected); `timeline` gives the beats the grid divides and the chords.
    `names` maps each note's id to the one candidates report, the original cover's for a cover a
    spec corrected (corrections.apply's identity map); by default a note keeps its own."""
    cover = finding.read(midi, timeline, protected, names)
    played, positions = cover.played, cover.positions
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
        *harmony.find(cover, thresholds),
        *voice.find(cover, thresholds),
    ]
    return sorted(found, key=lambda candidate: (candidate.time, candidate.id))


def to_json(candidates: list[Candidate], inputs: dict[str, Path], thresholds: Thresholds) -> str:
    """The finder's output file: each input's path and SHA-256 (name -> path, in order), the
    thresholds and the candidates."""
    data = {
        "inputs": {
            role: {"path": str(path), "sha256": corrections.sha256(path)}
            for role, path in inputs.items()
        },
        "thresholds": asdict(thresholds),
        "candidates": [asdict(candidate) for candidate in candidates],
    }
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"
