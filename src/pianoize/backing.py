"""The left hand against the band, for the arranger to fix or justify and never flagged: a note
may stand off the band on purpose, and the transcription can be wrong. The band is tsumugi's
transcription, placed as the dump places it: by its seconds on the cover's tempo map, each end
rounded to the nearest half-sixteenth. At each left-hand attack:

- a band-piano or bass note is held when its rounded onset is at or before the attack's rounded
  tick, its rounded end after it, and it lasts HELD_MIN_HALVES or more; the bass counts only at
  or below BASS_HOME_TOP, its home register;
- the marker in force is the source's last marker at or before the attack, tsumugi's chord guess;
- a struck note is `unbacked` when its pitch class is none of the held notes' or the marker's. A
  note marked `~` is checked only when no left-hand note sounding there sits below it: an invented
  walk-up is still a bass the band doesn't play, a neighbour over a held root is not;
- a struck note, `~` or not, is a `semitone` with a held band-piano note a minor second or a
  minor ninth away, arrange.CLASHES: a major seventh, or a semitone two octaves or more away, is
  the band's own colour, not a rub."""

import re
from bisect import bisect_right
from dataclasses import dataclass

import mido

from . import evidence, grid
from .arrange import CLASHES, separate_restrikes
from .arrangement import Score, notes_of, pitch_class
from .bars import Meter, halves, where
from .melody import pitch_name
from .notes import tick_in
from .playability import _attacks

HELD_MIN_HALVES = 4  # an eighth: a sixteenth run or a sliver is never held
# B2: an octave and a fifth above the open E string's E1 (28 + 19), the range a standard-tuned
# bass's roots sit in. A bass note at C3 or above is a fill or a line.
BASS_HOME_TOP = 47
PIANO_TRACK, BASS_TRACK = grid.DEFAULT_TRACKS  # the band's chords and bass, as build-grid copies

KINDS = ("unbacked", "semitone")

# tsumugi's chord qualities, the text after a marker's `:`, as semitones above the root; the major
# triad is the root alone.
MARKER_QUALITIES = {
    "5": (0, 7),
    "": (0, 4, 7),
    "-5": (0, 4, 6),
    "m": (0, 3, 7),
    "dim": (0, 3, 6),
    "aug": (0, 4, 8),
    "sus2": (0, 2, 7),
    "sus4": (0, 5, 7),
    "6": (0, 4, 7, 9),
    "7": (0, 4, 7, 10),
    "M7": (0, 4, 7, 11),
    "m6": (0, 3, 7, 9),
    "m7": (0, 3, 7, 10),
    "mM7": (0, 3, 7, 11),
    "7-5": (0, 4, 6, 10),
    "m7-5": (0, 3, 6, 10),
    "aug7": (0, 4, 8, 10),
    "augM7": (0, 4, 8, 11),
    "7sus4": (0, 5, 7, 10),
    "dim7": (0, 3, 6, 9),
    "add9": (0, 2, 4, 7),
    "madd9": (0, 2, 3, 7),
    "69": (0, 2, 4, 7, 9),
    "m69": (0, 2, 3, 7, 9),
}
MARKER_TENSIONS = {"9": 2, "b9": 1, "#9": 3, "11": 5, "#11": 6, "13": 9, "b13": 8}

# ROOT[:QUALITY[(TENSIONS)]][/BASS], the root and the bass spelled with # or b, as tsumugi's
# chord-romanizer respells them for the key.
_MARKER = re.compile(r"([A-G])([#b]?)(?::([^/(]*)(?:\(([^)]*)\))?)?(?:/([A-G])([#b]?))?")


@dataclass(frozen=True)
class Item:
    kind: str  # one of KINDS
    tick: int  # the left-hand attack's
    pitch: int
    detail: str


def marker_pitch_classes(text: str) -> frozenset[int] | None:
    """The pitch classes a marker's text backs: its quality's, its tensions and its slash bass, or
    its root and slash bass alone where the tables lack its quality or a tension. None for `N` and
    a text that is no chord."""
    match = _MARKER.fullmatch(text)
    if not match:
        return None
    quality = match[3] or ""
    tensions = match[4].split(",") if match[4] is not None else []
    intervals = [0]
    if quality in MARKER_QUALITIES and all(tension in MARKER_TENSIONS for tension in tensions):
        intervals = [*MARKER_QUALITIES[quality], *(MARKER_TENSIONS[t] for t in tensions)]
    root = pitch_class(match[1], match[2])
    classes = {(root + interval) % 12 for interval in intervals}
    if match[5]:
        classes.add(pitch_class(match[5], match[6]) % 12)
    return frozenset(classes)


def _held(
    source: mido.MidiFile,
    meter: Meter,
    tempo_map: list[tuple[int, float, int]],
    name: str,
    top: int | None = None,
) -> list[tuple[int, int, int]]:
    """(on_half, off_half, pitch) of each note of the tracks named `name` long enough to be held,
    and with `top` at or below it. A name no track has raises EvidenceError, listing the tracks."""
    held = []
    for note in evidence.track_notes(source, name):
        on, off = (
            halves(meter, tick_in(tempo_map, meter.ticks_per_beat, seconds))
            for seconds in (note.onset, note.offset)
        )
        if off - on >= HELD_MIN_HALVES and (top is None or note.pitch <= top):
            held.append((on, off, note.pitch))
    return held


def _part(source: mido.MidiFile, name: str | None, default: str) -> str | None:
    """The track a part is read from, None for none: for no name, the default, unless no track
    has it, since tsumugi writes a track only for an instrument it hears; for an empty name, none;
    else the name."""
    if name is None:
        return default if any(track.name == default for track in source.tracks) else None
    return name or None


def _markers(
    source: mido.MidiFile, meter: Meter, tempo_map: list[tuple[int, float, int]]
) -> list[tuple[int, str]]:
    """(half, text) of each of the source's markers, by time. A run of spaces or a line break
    reads as one space, as the dump prints a marker, so a text stays one field of its line."""
    return [
        (halves(meter, tick_in(tempo_map, meter.ticks_per_beat, seconds)), " ".join(text.split()))
        for seconds, text in evidence.markers(source)
    ]


def _names(pitches: list[int]) -> str:
    return " ".join(pitch_name(pitch) for pitch in pitches) or "-"


def items(
    score: Score,
    meter: Meter,
    tempo_map: list[tuple[int, float, int]],
    source: mido.MidiFile,
    piano_track: str | None = None,
    bass_track: str | None = None,
) -> list[Item]:
    """The items of the left-hand notes the build plays against the source, on the cover's tempo
    map (notes.tempo_map): by time, `unbacked` before `semitone`, then by pitch. A track name
    passed that no track of the source has raises EvidenceError."""
    piano_name = _part(source, piano_track, PIANO_TRACK)
    bass_name = _part(source, bass_track, BASS_TRACK)
    piano = [] if piano_name is None else _held(source, meter, tempo_map, piano_name)
    bass = [] if bass_name is None else _held(source, meter, tempo_map, bass_name, BASS_HOME_TOP)
    markers = _markers(source, meter, tempo_map)
    starts = [half for half, _ in markers]
    left = [note for note in separate_restrikes(notes_of(score, meter), meter) if note.hand == "LH"]
    found = []
    for tick, struck, sounding in _attacks(left):
        at = halves(meter, tick)
        piano_held = sorted({pitch for on, off, pitch in piano if on <= at < off})
        bass_held = sorted({pitch for on, off, pitch in bass if on <= at < off})
        index = bisect_right(starts, at)
        marker = markers[index - 1][1] if index else None
        marker_classes = None if marker is None else marker_pitch_classes(marker)
        backed = {pitch % 12 for pitch in piano_held + bass_held} | (marker_classes or frozenset())
        for note in struck:
            name = pitch_name(note.pitch)
            lowest = all(other.pitch >= note.pitch for other in sounding)
            if (lowest or not note.passing) and note.pitch % 12 not in backed:
                parts = f"bass {_names(bass_held)}  piano {_names(piano_held)}"
                detail = f"{name}  {parts}  marker {marker or '-'}"
                found.append(Item("unbacked", tick, note.pitch, detail))
            near = [pitch for pitch in piano_held if abs(note.pitch - pitch) in CLASHES]
            if near:
                detail = f"{name} against piano {_names(near)}"
                found.append(Item("semitone", tick, note.pitch, detail))
    return sorted(found, key=lambda item: (item.tick, KINDS.index(item.kind), item.pitch))


def report(found: list[Item], meter: Meter) -> str:
    """A line per item, `bar N pos P  LH  KIND  DETAIL`, then `harmony backing: K unbacked, J
    semitone`."""
    lines = [f"{where(meter, item.tick)}  LH  {item.kind}  {item.detail}" for item in found]
    unbacked, semitone = (sum(item.kind == kind for item in found) for kind in KINDS)
    lines.append(f"harmony backing: {unbacked} unbacked, {semitone} semitone")
    return "\n".join(lines)
