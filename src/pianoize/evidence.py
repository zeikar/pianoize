"""The harmony evidence table: per segment of a chord timeline, what the timeline, tsumugi's
transcription and the cover's notes each say, for an agent to weigh; none is the answer key. Run
on a refined timeline and a polished cover, it is the direct check of the notes against the
harmony. The columns are in docs/polishing.md; pedal is ignored, a note sounds from its note-on to
its note-off."""

import mido

from . import notes
from .chords import ROOT_NAMES
from .finding import clock
from .harmony import coverage, held, missing
from .melody import tones
from .review import cell
from .score import label

COLUMNS = (
    "#",
    "time",
    "beats",
    "chord",
    "candidates",
    "edited",
    "marker",
    "transcribed bass",
    "cover tones",
    "coverage",
    "missing",
    "melody",
)
_COVER_TONES = 4


class EvidenceError(ValueError):
    pass


def markers(midi: mido.MidiFile) -> list[tuple[float, str]]:
    """(seconds, text) of every marker, by time, the text as written. Nothing else is read: a
    tsumugi file can carry lyrics in its text and lyrics messages."""
    if midi.type == 2:
        raise EvidenceError("a type 2 MIDI file's tracks share no timeline to place markers on")
    found = []
    now = 0.0
    for message in midi:  # iterating a MidiFile merges the tracks and applies the tempo map
        now += message.time
        if message.type == "marker":
            found.append((now, message.text))
    return found


def track_notes(midi: mido.MidiFile, name: str) -> list[notes.Note]:
    """The notes of the tracks named `name`, timed by the whole file's tempo map, which tsumugi
    writes on a track of its own."""
    chosen = [i for i, track in enumerate(midi.tracks) if track.name == name]
    if not chosen:
        names = ", ".join(repr(track.name) for track in midi.tracks if track.name)
        raise EvidenceError(f"no track named {name!r}; tracks named: {names or 'none'}")
    return notes.read(midi, chosen)


def _shares(played: list[notes.Note], start: float, end: float, limit: int | None = None) -> str:
    """The pitch classes sounding between start and end, most sounding time first, each with its
    share of that time: `C 50%, G 30%`. Of two as long, the one with the lower note goes first,
    so the bass of a power chord leads."""
    sounding: dict[int, float] = {}
    lowest: dict[int, int] = {}
    for note in played:
        seconds = held(note, start, end)
        if seconds > 0:
            pc = note.pitch % 12
            sounding[pc] = sounding.get(pc, 0.0) + seconds
            lowest[pc] = min(lowest.get(pc, note.pitch), note.pitch)
    total = sum(sounding.values())
    ranked = sorted(sounding, key=lambda pc: (-sounding[pc], lowest[pc]))[:limit]
    return ", ".join(f"{ROOT_NAMES[pc]} {sounding[pc] / total:.0%}" for pc in ranked)


def _markers_in(found: list[tuple[float, str]], start: float, end: float) -> str:
    """The marker active at start, then every one starting before end."""
    active = [text for time, text in found if time <= start][-1:]
    return ", ".join(active + [text for time, text in found if start < time < end])


def rows(
    timeline: dict,
    cover_notes: list[notes.Note],
    protected: set[str],
    markers: list[tuple[float, str]],
    bass_notes: list[notes.Note],
    melody_notes: list[notes.Note],
) -> list[dict[str, str]]:
    """One row per segment, `N` included, each cell as text. The notes carrying the melody are
    left out of the cover's tones and its coverage, as the harmony candidates leave them out, but
    sound their tones for `missing`."""
    accompaniment = [n for n in cover_notes if n.id not in protected]
    found = []
    for index, segment in enumerate(timeline["segments"]):
        start, end = segment["start_time"], segment["end_time"]
        share = None
        if segment["chord"] != "N":  # no chord has no tones to cover
            share = coverage(accompaniment, start, end, tones(segment))
        cells = [
            str(index),
            clock(start),
            f"{segment['start_beat']}-{segment['end_beat']}",
            label(segment),
            " ".join(segment["candidates"]),
            "yes" if segment["edited"] else "",
            _markers_in(markers, start, end),
            _shares(bass_notes, start, end, 1),
            _shares(accompaniment, start, end, _COVER_TONES),
            "" if share is None else f"{share:.3f}",
            " ".join(ROOT_NAMES[pc] for pc in missing(cover_notes, start, end, segment)),
            _shares(melody_notes, start, end),
        ]
        found.append(dict(zip(COLUMNS, cells, strict=True)))
    return found


def markdown(found: list[dict[str, str]]) -> str:
    lines = ["| " + " | ".join(COLUMNS) + " |", "|" + " --- |" * len(COLUMNS)]
    lines += ["| " + " | ".join(cell(row[c]) for c in COLUMNS) + " |" for row in found]
    return "\n".join(lines) + "\n"
