"""Whether a score is playable by an intermediate-to-advanced pianist, hand by hand, and whether
its accompaniment fits the score's own chords. It checks the notes the build plays, and lists the
vocal notes the top of its right hand leaves out."""

from bisect import bisect_left, bisect_right
from collections.abc import Iterator
from dataclasses import dataclass
from itertools import groupby

import mido

from . import melody
from .arrange import separate_restrikes
from .arrangement import (
    ArrangementError,
    Score,
    ScoreNote,
    chord_at,
    chord_pitch_classes,
    notes_of,
)
from .bars import Meter, halves, nearest, where
from .melody import pitch_name
from .notes import seconds_at, tick_in

NOTES_PER_HAND = 7
SPAN_MAX = 19  # semitones, a twelfth: a wider span is flagged
SPAN_WIDE = 16  # a tenth: a wider span is listed, not flagged
JUMPS = ((19, 0.2), (26, 0.36))  # (semitones, seconds): a shift this wide in less time is flagged
JUMP_MAX = 36  # three octaves: a wider shift is flagged at any speed
SUNG_MIN = 0.080  # seconds: a shorter vocal note is a sliver of the transcription, never listed
SUNG_NEAR = 0.070  # seconds: a top right-hand note of its pitch class starting this near plays it

RULES = ("notes", "span", "jump", "crossing", "melody", "harmony")


@dataclass(frozen=True)
class Finding:
    rule: str  # one of RULES
    tick: int
    hand: str  # RH | LH
    detail: str
    flagged: bool  # False for a span listed only: over SPAN_WIDE but not over SPAN_MAX


def _attacks(notes: list[ScoreNote]) -> Iterator[tuple[int, list[ScoreNote], list[ScoreNote]]]:
    """Each attack's tick, the notes struck at it and the notes held there (on <= tick < off),
    from notes sorted by onset."""
    held: list[ScoreNote] = []
    for tick, group in groupby(notes, key=lambda note: note.on_tick):
        struck = list(group)
        held = [note for note in held if note.off_tick > tick] + struck
        yield tick, struck, held


def _hand(
    played: list[ScoreNote], hand: str, tempos: list[tuple[int, float, int]], ticks_per_beat: int
) -> list[Finding]:
    """The notes, span and jump findings at each of one hand's attacks."""
    findings = []
    previous = None  # (seconds, centre) of the hand's previous attack
    for tick, struck, held in _attacks(played):
        pitches = sorted(note.pitch for note in struck)
        # Keys, not notes: a pitch struck twice is flagged on its own below.
        keys = sorted({note.pitch for note in held})
        if len(keys) > NOTES_PER_HAND:
            names = " ".join(pitch_name(key) for key in keys)
            findings.append(Finding("notes", tick, hand, f"{len(keys)} held: {names}", True))
        for doubled in sorted({pitch for pitch in pitches if pitches.count(pitch) > 1}):
            detail = f"{pitch_name(doubled)} struck twice"
            findings.append(Finding("notes", tick, hand, detail, True))
        span = keys[-1] - keys[0]
        if span > SPAN_WIDE:
            detail = f"{span} semitones, {pitch_name(keys[0])} to {pitch_name(keys[-1])}"
            findings.append(Finding("span", tick, hand, detail, span > SPAN_MAX))
        seconds = seconds_at(tempos, ticks_per_beat, tick)
        centre = (pitches[0] + pitches[-1]) / 2
        if previous is not None:
            gap, shift = seconds - previous[0], abs(centre - previous[1])
            if shift > JUMP_MAX or any(shift >= wide and gap < fast for wide, fast in JUMPS):
                detail = f"{shift:g} semitones in {gap * 1000:.0f} ms"
                findings.append(Finding("jump", tick, hand, detail, True))
        previous = seconds, centre
    return findings


def check(score: Score, meter: Meter, tempo_map: list[tuple[int, float, int]]) -> list[Finding]:
    """The findings on the notes the build plays, timed by the cover's tempo map
    (notes.tempo_map). A pitch struck twice in one hand at one tick is flagged: the build would
    cut the first strike to a sliver whose note-off releases the key. A score without notes
    raises ArrangementError, as the build does, rather than reading clean."""
    built = separate_restrikes(notes_of(score, meter), meter)
    if not built:
        raise ArrangementError("the score has no notes")
    findings = []
    for hand in ("RH", "LH"):
        played = [note for note in built if note.hand == hand]
        findings += _hand(played, hand, tempo_map, meter.ticks_per_beat)
    reported = set()  # a held melody note under the same top note is reported once
    for tick, struck, held in _attacks(built):
        right = [note.pitch for note in held if note.hand == "RH"]
        left = [note.pitch for note in held if note.hand == "LH"]
        if right and left and max(left) >= min(right):
            detail = f"top {pitch_name(max(left))} at or above RH bottom {pitch_name(min(right))}"
            findings.append(Finding("crossing", tick, "LH", detail, True))
        for note in held:
            key = note.on_tick, note.pitch, max(right) if right else 0
            if note.role == "M" and note.pitch < key[2] and key not in reported:
                reported.add(key)
                detail = f"{pitch_name(note.pitch)} under {pitch_name(key[2])}"
                findings.append(Finding("melody", tick, note.hand, detail, True))
        for note in struck:
            if note.role != "M" and not note.passing:
                symbol = chord_at(score, meter, tick)
                classes = chord_pitch_classes(symbol)
                if classes is not None and note.pitch % 12 not in classes:
                    detail = f"{note.role} {pitch_name(note.pitch)} over {symbol}"
                    findings.append(Finding("harmony", tick, note.hand, detail, True))
    return findings


def report(findings: list[Finding], meter: Meter) -> str:
    """One line per finding, grouped by rule with each rule's count and flagged count, then
    `problems: K` counting the flagged findings, or `clean` when none is flagged."""
    lines = []
    for rule in RULES:
        found = sorted((f for f in findings if f.rule == rule), key=lambda f: (f.tick, f.hand))
        if found:
            flagged = sum(finding.flagged for finding in found)
            lines.append(f"{rule}: {len(found)} ({flagged} flagged)")
        for finding in found:
            listed = "" if finding.flagged else " (listed, not flagged)"
            place = where(meter, finding.tick)
            lines.append(f"  {place}  {finding.hand}  {rule}  {finding.detail}{listed}")
    problems = sum(finding.flagged for finding in findings)
    lines.append(f"problems: {problems}" if problems else "clean")
    return "\n".join(lines)


def missing(
    score: Score, meter: Meter, tempo_map: list[tuple[int, float, int]], sung: mido.MidiFile
) -> list[melody.Note]:
    """The vocal notes of SUNG_MIN or more, the melody kept to one voice by melody.monophonic,
    that no top right-hand note of their pitch class in any octave starts within SUNG_NEAR of. A
    top note is the highest the right hand holds at one of its attacks, struck there, `M` or `R`:
    the melody is carried on top, so an inner voice plays none. The notes are the build's, timed
    by the cover's tempo map (notes.tempo_map)."""
    built = separate_restrikes(notes_of(score, meter), meter)
    right = []  # (seconds, pitch class) of each top note, by onset
    for tick, _, held in _attacks([note for note in built if note.hand == "RH"]):
        top = max(held, key=lambda note: note.pitch)
        if top.on_tick == tick:  # else a note struck earlier sounds on top of the attack
            right.append((seconds_at(tempo_map, meter.ticks_per_beat, tick), top.pitch % 12))
    onsets = [seconds for seconds, _ in right]
    found = []
    for note in melody.monophonic(melody.notes(sung)):
        if note.offset - note.onset < SUNG_MIN:
            continue
        start = bisect_left(onsets, note.onset - SUNG_NEAR)
        end = bisect_right(onsets, note.onset + SUNG_NEAR)
        if all(pitch_class != note.pitch % 12 for _, pitch_class in right[start:end]):
            found.append(note)
    return found


def missing_report(
    found: list[melody.Note], meter: Meter, tempo_map: list[tuple[int, float, int]]
) -> str:
    """A line per vocal note left out, `bar N pos P  melody missing  E5 (D)`, placed as the dump
    places the melody: by its seconds on the cover's tempo map, each end rounded to the nearest
    half-sixteenth, the duration in sixteenths. Then `melody missing: K`."""
    lines = []
    for note in found:
        on, off = (tick_in(tempo_map, meter.ticks_per_beat, s) for s in (note.onset, note.offset))
        bar, sixteenths = nearest(meter, on)
        duration = (halves(meter, off) - halves(meter, on)) / 2
        name = pitch_name(note.pitch)
        lines.append(f"bar {bar} pos {sixteenths:g}  melody missing  {name} ({duration:g})")
    lines.append(f"melody missing: {len(found)}")
    return "\n".join(lines)
