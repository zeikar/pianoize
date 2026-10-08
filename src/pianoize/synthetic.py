"""Synthetic timelines and MIDI from a chord progression, for tests and for trial runs.

A progression is a list of (chord, n_beats) or (chord, n_beats, bass) with Harte labels,
sharps only; the bass defaults to the chord's root.
"""

import mido

from pianoize.chords import INTERVALS, ROOT_NAMES, inversion, parse_chord
from pianoize.timeline import SCHEMA_VERSION

Progression = list[tuple[str, int] | tuple[str, int, str]]

# The schema lists three candidates per segment, the written chord first. Nothing here scores
# alternatives, so any distinct labels do; N gets real chords so the list is never all N.
_FILLERS = ("maj", "min", "7")


def _candidates(chord: str) -> list[str]:
    parsed = parse_chord(chord)
    if parsed is None:
        return ["N", "C:maj", "C:min"]
    root = ROOT_NAMES[parsed[0]]
    others = [f"{root}:{q}" for q in _FILLERS if f"{root}:{q}" != chord]
    return [chord, *others[:2]]


def _bass(entry: tuple) -> str | None:
    chord = entry[0]
    if chord == "N":
        return None
    return entry[2] if len(entry) > 2 else chord.split(":")[0]


def timeline(progression: Progression, bpm: float = 120, offset: float = 0.05) -> dict:
    total = sum(entry[1] for entry in progression)
    step = 60 / bpm
    beats = [round(offset + i * step, 3) for i in range(total)]
    duration = round(offset + total * step, 3)
    segments = []
    start = 0
    for entry in progression:
        chord, length = entry[0], entry[1]
        end = start + length
        bass = _bass(entry)
        segments.append(
            {
                "start_beat": start,
                "end_beat": end,
                "start_time": beats[start],
                "end_time": beats[end] if end < total else duration,
                "chord": chord,
                "candidates": _candidates(chord),
                "bass": bass,
                "inversion": inversion(chord, bass),
                "numeral": None,
                "role": None,
                "function": None,
                "target": None,
                "edited": False,
            }
        )
        start = end
    return {
        "schema_version": SCHEMA_VERSION,
        "generator": {"name": "pianoize-synthetic", "version": "0"},
        "source": {"path": "synthetic.wav", "duration": duration, "url": None},
        "beats": beats,
        "global_key": None,
        "key_regions": [],
        "segments": segments,
    }


def midi(progression: Progression, bpm: float = 120) -> mido.MidiFile:
    """Strike every chord tone from MIDI 60 and the bass in 36-47 on each beat, so a beat tracker
    has an onset per beat."""
    ticks = 480
    gate = ticks * 3 // 4
    mid = mido.MidiFile(ticks_per_beat=ticks)
    track = mido.MidiTrack()
    mid.tracks.append(track)
    track.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(bpm), time=0))
    rest = 0  # ticks since the last message
    for entry in progression:
        parsed = parse_chord(entry[0])
        notes: list[int] = []
        if parsed is not None:
            root = parsed[0]
            notes = [60 + root + i for i in INTERVALS[parsed[1]]]
            notes.append(36 + ROOT_NAMES.index(_bass(entry)))
        for _ in range(entry[1]):
            for n, note in enumerate(notes):
                track.append(
                    mido.Message("note_on", note=note, velocity=80, time=rest if n == 0 else 0)
                )
            for n, note in enumerate(notes):
                track.append(
                    mido.Message("note_off", note=note, velocity=0, time=gate if n == 0 else 0)
                )
            rest = ticks - gate if notes else rest + ticks
    return mid
