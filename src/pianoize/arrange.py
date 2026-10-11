"""A score built into a two-hand MIDI on the cover's ticks and tempo map, with the pedal."""

from dataclasses import replace
from fractions import Fraction

import mido

from . import bars
from .arrangement import ArrangementError, Bar, Score, ScoreNote, notes_of
from .bars import Meter
from .notes import tempo_map

VELOCITY = 88  # every note: no dynamics, by request; the prototype's loudness-matched value
TRACKS = {"RH": ("Right Hand", 0), "LH": ("Left Hand", 1)}  # hand -> track name, channel

# In beats, so they scale with the cover's resolution: at 960 ticks a beat the restrike gap, the
# restrike minimum and the pedal gap are the prototype's 30, 60 and 60 ticks.
TAIL = 1  # the last notes ring this much past the score's last note-off
TAIL_RELEASE = Fraction(1, 8)  # and are released this long before the build ends
RESTRIKE_GAP = Fraction(1, 32)
RESTRIKE_MIN = Fraction(1, 16)
PEDAL_GAP = Fraction(1, 16)  # from a lift to the next press

CLASHES = (1, 13)  # a semitone and a minor ninth: the rubs a held pedal makes audible

# The order of a track's messages at one tick. Note-offs come before note-ons, so a pitch
# released and struck at one tick sounds again, and before a press, which would hold them.
_META, _PROGRAM, _LIFT, _OFF, _PRESS, _ON = range(6)


def _ticks(meter: Meter, beats: Fraction | int) -> int:
    return round(beats * meter.ticks_per_beat)


def separate_restrikes(notes: list[ScoreNote], meter: Meter) -> list[ScoreNote]:
    """The notes, sorted by onset as notes_of gives them, with each pitch struck again in the same
    hand ending a restrike gap before the new attack, but no shorter than the restrike minimum,
    never later than written and never past a later attack, whose key its note-off would release.
    Without the gap, a falling-notes view draws two strikes as one."""
    gap = _ticks(meter, RESTRIKE_GAP)
    shortest = _ticks(meter, RESTRIKE_MIN)
    separated = list(notes)
    latest: dict[tuple[str, int], int] = {}  # (hand, pitch) -> index of its latest strike
    for index, note in enumerate(separated):
        key = (note.hand, note.pitch)
        if key in latest:
            before = separated[latest[key]]
            off = min(before.off_tick, max(before.on_tick + shortest, note.on_tick - gap))
            # Two strikes at one tick leave no room: ending the first there would put its
            # note-off before both note-ons. The playability check flags them instead.
            if note.on_tick > before.on_tick:
                off = min(off, note.on_tick)
            separated[latest[key]] = replace(before, off_tick=off)
        latest[key] = index
    return separated


def tail(notes: list[ScoreNote], meter: Meter) -> tuple[list[ScoreNote], int]:
    """The notes with those ending at the last note-off ringing on into the tail, and the tick
    the tail, and so the build, ends."""
    if not notes:
        raise ArrangementError("the score has no notes")
    last = max(note.off_tick for note in notes)
    end = last + _ticks(meter, TAIL)
    held = end - _ticks(meter, TAIL_RELEASE)
    return [replace(note, off_tick=held) if note.off_tick == last else note for note in notes], end


def _pedal_points(bar: Bar) -> list[tuple[float, bool]]:
    """(sixteenths into the bar, whether the pedal goes down again) of each lift in the bar."""
    if bar.pedal == "none":
        return [(0.0, False)]
    if bar.pedal == "chord":
        return [(place, True) for place, _ in bar.chords]
    # parse has checked the positions.
    return [(float(p.removeprefix("x")), not p.startswith("x")) for p in bar.pedal.split(",")]


def pedal_intervals(score: Score, meter: Meter, end_tick: int) -> list[tuple[int, int]]:
    """The (press, lift) ticks of the pedal from each bar's setting, ascending, the pedal going
    down a gap after each lift that presses again. Nothing outlasts end_tick."""
    gap = _ticks(meter, PEDAL_GAP)
    intervals = []
    down = None  # the tick the pedal went down at, while it is down
    for bar in score.bars:
        start = (bar.number - 1) * meter.bar_ticks
        for place, again in _pedal_points(bar):
            up = start + round(place * meter.sixteenth_ticks)
            if down is not None and down < up:
                intervals.append((down, up))
            down = up + gap if again else None
    if down is not None:
        intervals.append((down, end_tick))
    return [(down, min(up, end_tick)) for down, up in intervals if down < end_tick]


def replan(
    notes: list[ScoreNote], intervals: list[tuple[int, int]], meter: Meter
) -> list[tuple[int, int]]:
    """The intervals with the pedal lifted at each attack that would ring a semitone or a minor
    ninth against a note it still holds, and pressed again a gap later."""
    gap = _ticks(meter, PEDAL_GAP)
    planned = list(intervals)
    attacks: dict[int, list[int]] = {}
    for note in notes:
        attacks.setdefault(note.on_tick, []).append(note.pitch)
    for tick, struck in sorted(attacks.items()):
        index = next((i for i, (down, up) in enumerate(planned) if down < tick < up), None)
        if index is None:
            continue
        down, up = planned[index]
        # Released after the pedal went down, so still ringing through it; one released at the
        # press tick is not, since note-offs come before a press.
        held = {note.pitch for note in notes if down < note.off_tick <= tick}
        if any(abs(new - old) in CLASHES for new in struck for old in held):
            again = [(tick + gap, up)] if tick + gap < up else []
            planned[index : index + 1] = [(down, tick), *again]
    return planned


def _sustain(channel: int, value: int) -> mido.Message:
    return mido.Message("control_change", channel=channel, control=64, value=value)


def _track(
    name: str,
    channel: int,
    notes: list[ScoreNote],
    pedal: list[tuple[int, int]],
    metas: list[tuple[int, mido.MetaMessage]],
    end: int,
) -> mido.MidiTrack:
    # (tick, order at the tick, pitch, message); a stable sort keeps the metas as listed.
    events = [(0, _META, 0, mido.MetaMessage("track_name", name=name))]
    events += [(tick, _META, 0, message) for tick, message in metas]
    events.append((0, _PROGRAM, 0, mido.Message("program_change", channel=channel, program=0)))
    for down, up in pedal:
        events += [(down, _PRESS, 0, _sustain(channel, 127)), (up, _LIFT, 0, _sustain(channel, 0))]
    for note in notes:
        on = mido.Message("note_on", channel=channel, note=note.pitch, velocity=VELOCITY)
        off = mido.Message("note_off", channel=channel, note=note.pitch, velocity=0)
        events += [(note.on_tick, _ON, note.pitch, on), (note.off_tick, _OFF, note.pitch, off)]
    events.sort(key=lambda event: event[:3])
    track = mido.MidiTrack()
    now = 0
    for tick, _, _, message in events:
        track.append(message.copy(time=tick - now))
        now = tick
    track.append(mido.MetaMessage("end_of_track", time=end - now))
    return track


def build(score: Score, cover: mido.MidiFile) -> mido.MidiFile:
    """The score as a type 1 MIDI at the cover's resolution: the right hand on track 0 with the
    meter and the cover's tempos, the left hand on track 1. Each track carries the pedal on its
    own channel, since sustain is per channel. Both tracks end at the tail's end."""
    meter = bars.meter(cover)
    notes, end = tail(separate_restrikes(notes_of(score, meter), meter), meter)
    pedal = replan(notes, pedal_intervals(score, meter, end), meter)
    signature = mido.MetaMessage(
        "time_signature", numerator=meter.numerator, denominator=meter.denominator
    )
    metas = [(0, signature)]
    metas += [(tick, mido.MetaMessage("set_tempo", tempo=tempo))
              for tick, _, tempo in tempo_map(cover) if tick <= end]  # fmt: skip
    midi = mido.MidiFile(type=1, ticks_per_beat=meter.ticks_per_beat)
    for hand, (name, channel) in TRACKS.items():
        played = [note for note in notes if note.hand == hand]
        # Type 1 keeps the meter and the tempos on the first track.
        midi.tracks.append(_track(name, channel, played, pedal, [] if midi.tracks else metas, end))
    return midi
