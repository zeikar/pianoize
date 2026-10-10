"""A MIDI file's notes at tick level, so an edit lands on an exact tick and a note keeps an id."""

import bisect
from dataclasses import dataclass

import mido

from .melody import _DRUM_CHANNEL, _SAME_ONSET

_DEFAULT_TEMPO = 500000  # microseconds per beat until the first set_tempo
_MATCH_WINDOW = 0.060


class NoteError(ValueError):
    pass


@dataclass(frozen=True)
class Note:
    on_tick: int
    off_tick: int
    pitch: int
    velocity: int
    channel: int
    onset: float  # seconds
    offset: float

    @property
    def id(self) -> str:
        return f"t{self.on_tick}p{self.pitch}"


def _tempo_map(midi: mido.MidiFile) -> list[tuple[int, float, int]]:
    """(tick, seconds at that tick, tempo from there on), from tick 0; tempo events may sit on any
    track."""
    changes: dict[int, int] = {}
    for track in midi.tracks:
        tick = 0
        for message in track:
            tick += message.time
            if message.type == "set_tempo":
                changes[tick] = message.tempo
    changes.setdefault(0, _DEFAULT_TEMPO)
    segments: list[tuple[int, float, int]] = []
    for tick in sorted(changes):
        if segments:
            last_tick, last_seconds, last_tempo = segments[-1]
            seconds = last_seconds + mido.tick2second(
                tick - last_tick, midi.ticks_per_beat, last_tempo
            )
        else:
            seconds = 0.0
        segments.append((tick, seconds, changes[tick]))
    return segments


def _seconds(segments: list[tuple[int, float, int]], ticks_per_beat: int, tick: int) -> float:
    index = bisect.bisect_right([s[0] for s in segments], tick) - 1
    start, seconds, tempo = segments[index]
    return seconds + mido.tick2second(tick - start, ticks_per_beat, tempo)


def _close(
    open_notes: dict[tuple[int, int], tuple[int, int]],
    key: tuple[int, int],
    off_tick: int,
    segments: list[tuple[int, float, int]],
    ticks_per_beat: int,
) -> Note:
    on_tick, velocity = open_notes.pop(key)
    channel, pitch = key
    return Note(
        on_tick,
        off_tick,
        pitch,
        velocity,
        channel,
        _seconds(segments, ticks_per_beat, on_tick),
        _seconds(segments, ticks_per_beat, off_tick),
    )


def read(midi: mido.MidiFile) -> list[Note]:
    """Every note by onset, without drums, paired per track. That equals melody.notes for the
    single-track covers check_editable accepts; see docs/evaluation.md for the pairing."""
    segments = _tempo_map(midi)
    found: list[Note] = []
    for track in midi.tracks:
        open_notes: dict[tuple[int, int], tuple[int, int]] = {}  # -> (on_tick, velocity)
        now = 0
        for message in track:
            now += message.time
            if message.is_meta or message.type not in ("note_on", "note_off"):
                continue
            if message.channel == _DRUM_CHANNEL:
                continue
            key = (message.channel, message.note)
            if key in open_notes:
                found.append(_close(open_notes, key, now, segments, midi.ticks_per_beat))
            if message.type == "note_on" and message.velocity > 0:
                open_notes[key] = (now, message.velocity)
        for key in list(open_notes):
            found.append(_close(open_notes, key, now, segments, midi.ticks_per_beat))
    return sorted(found, key=lambda n: (n.onset, n.pitch, n.on_tick))


def tick_at(midi: mido.MidiFile, seconds: float) -> int:
    """The tick nearest a time in seconds: the inverse of the file's tempo map."""
    segments = _tempo_map(midi)
    index = max(bisect.bisect_right([s[1] for s in segments], seconds) - 1, 0)
    start, start_seconds, tempo = segments[index]
    return start + round(mido.second2tick(seconds - start_seconds, midi.ticks_per_beat, tempo))


def check_editable(midi: mido.MidiFile) -> None:
    """Raise NoteError unless the notes sit on one track and channel and every id is unique."""
    with_notes = [
        i
        for i, track in enumerate(midi.tracks)
        if any(m.type == "note_on" and m.channel != _DRUM_CHANNEL for m in track)
    ]
    if len(with_notes) > 1:
        raise NoteError(f"notes sit on {len(with_notes)} tracks ({with_notes}); expected one")
    found = read(midi)
    channels = sorted({n.channel for n in found})
    if len(channels) > 1:
        raise NoteError(f"notes sit on {len(channels)} channels ({channels}); expected one")
    seen: set[str] = set()
    for note in found:
        if note.id in seen:
            raise NoteError(f"two notes share the id {note.id}")
        seen.add(note.id)


def clusters(notes: list[Note], window: float = _SAME_ONSET) -> list[list[Note]]:
    """Notes by onset, grouped while each starts within `window` of the group's first."""
    groups: list[list[Note]] = []
    for note in sorted(notes, key=lambda n: (n.onset, n.pitch)):
        if groups and note.onset - groups[-1][0].onset <= window:
            groups[-1].append(note)
        else:
            groups.append([note])
    return groups


def protected(cover_notes: list[Note], melody_notes: list[Note]) -> set[str]:
    """Ids of the cover notes that carry the melody: same pitch class as a melody note within 60 ms,
    at or above its pitch (the cover plays it mostly an octave up), and top of its onset cluster."""
    tops = {max(group, key=lambda n: n.pitch).id for group in clusters(cover_notes)}
    return {
        note.id
        for note in cover_notes
        if note.id in tops
        and any(
            note.pitch % 12 == m.pitch % 12
            and note.pitch >= m.pitch
            and abs(note.onset - m.onset) <= _MATCH_WINDOW
            for m in melody_notes
        )
    }
