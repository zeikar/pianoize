"""Melody MIDI against a chord timeline: how many melody notes clash with the chord under them."""

from dataclasses import dataclass
from typing import NamedTuple

import mido

from .chords import ROOT_NAMES, chord_pitch_classes
from .score import label
from .timeline import beat_time


class Note(NamedTuple):
    onset: float  # seconds
    offset: float
    pitch: int


# Notes this close together are one attack spread by the transcriber, not two melody notes.
_SAME_ONSET = 0.030
_DRUM_CHANNEL = 9


def notes(midi: mido.MidiFile) -> list[Note]:
    """Every note of every track by onset, without drums; see docs/evaluation.md for the pairing."""
    open_notes: dict[tuple[int, int], float] = {}
    found: list[Note] = []
    now = 0.0
    for message in midi:  # iterating a MidiFile merges the tracks and applies the tempo map
        now += message.time
        if message.is_meta or message.type not in ("note_on", "note_off"):
            continue
        if message.channel == _DRUM_CHANNEL:
            continue
        key = (message.channel, message.note)
        starts = message.type == "note_on" and message.velocity > 0
        if key in open_notes:
            found.append(Note(open_notes.pop(key), now, message.note))
        if starts:
            open_notes[key] = now
    found.extend(Note(onset, now, pitch) for (_, pitch), onset in open_notes.items())
    return sorted(found)


def monophonic(melody: list[Note]) -> list[Note]:
    """One voice: of notes starting within 30 ms of each other the highest stays, and each note
    ends at the next one's onset. Basic Pitch is polyphonic and GAME can double a voice."""
    groups: list[list[Note]] = []
    for note in sorted(melody):
        if groups and note.onset - groups[-1][0].onset <= _SAME_ONSET:
            groups[-1].append(note)
        else:
            groups.append([note])
    kept = [max(group, key=lambda n: n.pitch) for group in groups]
    return [
        Note(
            note.onset,
            min(note.offset, kept[i + 1].onset) if i + 1 < len(kept) else note.offset,
            note.pitch,
        )
        for i, note in enumerate(kept)
    ]


def pitch_name(pitch: int) -> str:
    return f"{ROOT_NAMES[pitch % 12]}{pitch // 12 - 1}"


@dataclass(frozen=True)
class Clash:
    time: float
    pitch: int
    chord: str  # slash form


@dataclass(frozen=True)
class Report:
    consonant_notes: int
    clashing_notes: int
    consonant_seconds: float
    clashing_seconds: float
    clashes: list[Clash]

    @property
    def note_ratio(self) -> float | None:
        """Clashing / (consonant + clashing) by note count; None when no note was counted."""
        total = self.consonant_notes + self.clashing_notes
        return self.clashing_notes / total if total else None

    @property
    def duration_ratio(self) -> float | None:
        """The same by sounding time; None when no time was counted."""
        total = self.consonant_seconds + self.clashing_seconds
        return self.clashing_seconds / total if total else None


def tones(segment: dict) -> set[int]:
    """The pitch classes of a segment's chord, plus its slash bass."""
    found = set(chord_pitch_classes(segment["chord"]))
    # The slash bass sounds too, so a note on it is not a clash.
    if segment["bass"] is not None:
        found.add(ROOT_NAMES.index(segment["bass"]))
    return found


def spans(timeline: dict) -> list[tuple[float, float, dict]]:
    """(start, end, segment) of every segment with a chord, starting no earlier than the first
    beat."""
    first_beat = beat_time(timeline, 0)
    return [
        (max(s["start_time"], first_beat), s["end_time"], s)
        for s in timeline["segments"]
        if s["chord"] != "N"
    ]


def clashes(melody: list[Note], timeline: dict) -> Report:
    """A pitch class in the chord's tones (its label plus the bass) is consonant; any other clashes.

    By count, each note is judged by the segment at its onset. By duration, each note is split
    over the segments it overlaps. Time before the first beat and under N is left out of both.
    """
    chords = [(start, end, s, tones(s)) for start, end, s in spans(timeline)]
    consonant_notes = clashing_notes = 0
    consonant_seconds = clashing_seconds = 0.0
    found = []
    for onset, offset, pitch in melody:
        for start, end, segment, chord_tones in chords:
            consonant = pitch % 12 in chord_tones
            overlap = min(offset, end) - max(onset, start)
            if overlap > 0:
                if consonant:
                    consonant_seconds += overlap
                else:
                    clashing_seconds += overlap
            if start <= onset < end:
                if consonant:
                    consonant_notes += 1
                else:
                    clashing_notes += 1
                    found.append(Clash(onset, pitch, label(segment)))
    return Report(consonant_notes, clashing_notes, consonant_seconds, clashing_seconds, found)
