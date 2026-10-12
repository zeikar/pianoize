"""The notes of a two-hand arrangement as the JSON the falling-notes viewer draws."""

import json

import mido

from . import notes
from .arrange import TRACKS

FORMAT_VERSION = 1
HANDS = {"RH": "right", "LH": "left"}
_LOWEST, _HIGHEST = 21, 108  # the 88 keys, A0 to C8


class RollError(ValueError):
    pass


def hand_tracks(midi: mido.MidiFile) -> dict[str, int]:
    """The index of the track named for each hand, as build-arrangement names them."""
    found: dict[str, int] = {}
    for hand, (name, _) in TRACKS.items():
        indexes = [
            index
            for index, track in enumerate(midi.tracks)
            if any(m.type == "track_name" and m.name == name for m in track)
        ]
        if not indexes:
            raise RollError(
                f"no {name!r} track; expected the two-hand MIDI build-arrangement writes"
            )
        if len(indexes) > 1:
            raise RollError(f"{len(indexes)} tracks are named {name!r}; expected one")
        found[hand] = indexes[0]
    return found


def length(midi: mido.MidiFile) -> float:
    """Seconds to the last tick of any track, which is where the pedal and the tail end."""
    last = max(sum(m.time for m in track) for track in midi.tracks)
    return notes.seconds_at(notes.tempo_map(midi), midi.ticks_per_beat, last)


def export(midi: mido.MidiFile) -> dict:
    """The viewer's data: every note with its hand and its seconds, by onset."""
    rolled = []
    for hand, index in hand_tracks(midi).items():
        for note in notes.read(midi, tracks=[index]):
            if not _LOWEST <= note.pitch <= _HIGHEST:
                raise RollError(
                    f"the {HANDS[hand]} hand plays pitch {note.pitch}, off the 88 keys "
                    f"({_LOWEST} to {_HIGHEST})"
                )
            rolled.append(
                {
                    "pitch": note.pitch,
                    "hand": HANDS[hand],
                    "on": round(note.onset, 6),
                    "off": round(note.offset, 6),
                }
            )
    rolled.sort(key=lambda n: (n["on"], n["pitch"], n["hand"]))
    return {"format_version": FORMAT_VERSION, "notes": rolled}


def dump(data: dict) -> str:
    """The data as JSON with one note a line, so a re-run diffs clean."""
    lines = ",\n".join(json.dumps(note) for note in data["notes"])
    header = f'{{"format_version": {data["format_version"]}, "notes": ['
    return f"{header}\n{lines}\n]}}\n" if lines else f"{header}\n]}}\n"
