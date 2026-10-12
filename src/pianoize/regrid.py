"""Tempo hiccups, where a beat tracker squeezed a few of the song's bars into fewer grid bars or
stretched them over more, and a copy of the cover with each one regridded. Every command counts
bars from the cover's tempo map, so inside a hiccup the grid's bar lines fall off the song's
downbeats, and after it they fall on them again but every bar is numbered off by the bars the
hiccup lost or gained."""

from dataclasses import dataclass

import mido

from . import notes
from .bars import Meter

# A hiccup is a phrase the tracker miscounted, not a section in a new tempo.
_MAX_BARS = 4
# How far the run's tempo as a whole, its grid bars over its seconds, sits from each neighbour.
# Not each segment's: the tracker can split a hiccup into tempos one of which lands near the
# song's (one within 10% of it, say). Holding a different number of the song's bars, at
# most 4 grid bars, puts the run at least 20% off (5 in 4); the same number keeps it within 1%.
_OFF = 0.15
# The neighbours agree, so the song's tempo resumes after the run: no lasting tempo change.
_AGREE = 0.05
# How near, in seconds, a whole number of bars at the neighbours' mean tempo the run's seconds
# come. Absolute, not a share of the bars: tsumugi's hiccup fits within about 1 ms, while a window
# that grew with the run took in ritardandos and metric modulations that return to tempo.
_FIT = 0.010


@dataclass(frozen=True)
class Span:
    start: int  # tick of a bar line
    end: int  # tick of a later bar line
    tempos: tuple[int, ...]  # the run's tempos, microseconds per beat
    bars: int  # the song's bars it holds
    tempo: int  # microseconds per beat that fit `bars` bars into the run's seconds


def _apart(bpm: float, other: float) -> float:
    return abs(bpm / other - 1)


def _hiccup(
    segments: list[tuple[int, float, int]], first: int, after: int, meter: Meter
) -> Span | None:
    """The run of segments[first:after] as a hiccup, if it is one."""
    start, start_seconds, _ = segments[first]
    end, end_seconds, after_tempo = segments[after]
    if start % meter.bar_ticks or end % meter.bar_ticks:
        return None
    seconds = end_seconds - start_seconds
    beats = meter.bar_ticks / meter.ticks_per_beat  # MIDI beats, which tempos count, per bar
    run = (end - start) / meter.ticks_per_beat * 60 / seconds
    before, after_bpm = mido.tempo2bpm(segments[first - 1][2]), mido.tempo2bpm(after_tempo)
    if _apart(before, after_bpm) > _AGREE:
        return None
    if _apart(run, before) <= _OFF or _apart(run, after_bpm) <= _OFF:
        return None
    bar_seconds = beats * 60 / ((before + after_bpm) / 2)
    count = round(seconds / bar_seconds)
    if count < 1 or abs(seconds - count * bar_seconds) > _FIT:
        return None
    tempos = tuple(tempo for _, _, tempo in segments[first:after])
    return Span(start, end, tempos, count, round(seconds * 1e6 / (count * beats)))


def hiccups(midi: mido.MidiFile, meter: Meter) -> list[Span]:
    """The hiccups by tick. A hiccup is a run of whole tempo segments of the file's tempo map that
    starts and ends on bar lines and is at most _MAX_BARS long; segments shorter than a bar may
    sit inside it. Its tempo as a whole is more than _OFF from the segment just before it and the
    one just after, those two agree within _AGREE, and its seconds come within _FIT s of a whole
    number of bars at their mean tempo. Runs are tried from the left, the shortest first; the
    neighbour after a hiccup is never part of the next."""
    segments = notes.tempo_map(midi)
    longest = _MAX_BARS * meter.bar_ticks
    found: list[Span] = []
    first = 1  # a run needs a segment before it, and one after it
    while first < len(segments) - 1:
        span = None
        for after in range(first + 1, len(segments)):
            if segments[after][0] - segments[first][0] > longest:
                break
            span = _hiccup(segments, first, after, meter)
            if span is not None:
                found.append(span)
                break
        first = after + 1 if span is not None else first + 1
    return found


def repair(midi: mido.MidiFile, spans: list[Span]) -> mido.MidiFile:
    """The file with each span's tempo events replaced by one event of its new tempo at its start,
    and every event moved to the tick nearest the time it had: a span's events land where their
    seconds fall on its new bars, and the events after it move by the bars it gained or lost. Type,
    resolution, track order and every other message stay as they were. `spans` come from
    hiccups() on the same file."""
    ticks_per_beat = midi.ticks_per_beat
    old = notes.tempo_map(midi)
    new_tempos = {span.start: span.tempo for span in spans}

    def inside(tick: int) -> bool:
        return any(span.start < tick < span.end for span in spans)

    # The new map, change by change: each kept change lands where its time falls on the part of
    # the map built so far. A span's end lands on its new last bar line: its new tempo, rounded to
    # whole microseconds, is off by under 0.5 µs a beat, far less than a tick.
    new: list[tuple[int, float, int]] = []
    for tick, seconds, tempo in old:
        if inside(tick):
            continue
        tempo = new_tempos.get(tick, tempo)
        if not new:
            new.append((0, 0.0, tempo))
            continue
        at = notes.tick_in(new, ticks_per_beat, seconds)
        last_tick, last_seconds, last_tempo = new[-1]
        new.append(
            (at, last_seconds + mido.tick2second(at - last_tick, ticks_per_beat, last_tempo), tempo)
        )

    fixed = mido.MidiFile(type=midi.type, ticks_per_beat=ticks_per_beat, charset=midi.charset)
    for track in midi.tracks:
        moved = mido.MidiTrack()
        tick = now = 0
        for message in track:
            tick += message.time
            if message.type == "set_tempo":
                if inside(tick):
                    continue
                if tick in new_tempos:
                    message = message.copy(tempo=new_tempos[tick])
            at = notes.tick_in(new, ticks_per_beat, notes.seconds_at(old, ticks_per_beat, tick))
            moved.append(message.copy(time=at - now))
            now = at
        fixed.tracks.append(moved)
    return fixed
