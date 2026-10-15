"""The cover's meter and bars, so a tick reads as a bar and the sixteenths into it."""

from dataclasses import dataclass

import mido


class MeterError(ValueError):
    pass


@dataclass(frozen=True)
class Meter:
    ticks_per_beat: int
    numerator: int
    denominator: int

    @property
    def bar_ticks(self) -> int:
        return self.numerator * 4 * self.ticks_per_beat // self.denominator

    @property
    def sixteenth_ticks(self) -> int:
        return self.ticks_per_beat // 4

    @property
    def sixteenths_per_bar(self) -> int:
        return self.bar_ticks // self.sixteenth_ticks


def meter(midi: mido.MidiFile) -> Meter:
    """The one meter of the file, from the time signatures on every track. With none it is 4/4,
    the MIDI default, which also holds before a first signature after tick 0. A signature with the
    first one's bar length, 8/8 after 4/4, is no change and the first stands; any other change of
    meter raises MeterError."""
    found: list[tuple[int, int, int]] = []
    for track in midi.tracks:
        tick = 0
        for message in track:
            tick += message.time
            if message.type == "time_signature":
                found.append((tick, message.numerator, message.denominator))
    found.sort(key=lambda f: f[0])  # stable: same-tick signatures keep track order
    if not found or found[0][0] > 0:
        found.insert(0, (0, 4, 4))
    _, numerator, denominator = found[0]
    for tick, other_numerator, other_denominator in found[1:]:
        # The score counts sixteenths per bar, so only the bar's length matters: tsumugi writes
        # 8/8 for stretches of a 4/4 song.
        if other_numerator * denominator != numerator * other_denominator:
            raise MeterError(
                f"the cover changes meter at tick {tick}, {numerator}/{denominator} to "
                f"{other_numerator}/{other_denominator}; the score format needs one meter"
            )
    # Notes land at a rounded sixteenth count times sixteenth_ticks, so a fractional sixteenth
    # would misplace every note.
    if midi.ticks_per_beat % 4:
        raise MeterError(
            f"the score format counts whole sixteenths; {midi.ticks_per_beat} ticks per beat "
            "do not divide by 4"
        )
    if numerator * 16 % denominator:
        raise MeterError(
            f"the score format counts whole sixteenths; a {numerator}/{denominator} bar does not "
            "hold a whole number of them"
        )
    return Meter(midi.ticks_per_beat, numerator, denominator)


def bar_count(midi: mido.MidiFile, meter: Meter) -> int:
    """Bars up to the last tick of any track, a partial last bar counted whole."""
    last = max((sum(message.time for message in track) for track in midi.tracks), default=0)
    return -(-last // meter.bar_ticks)


def position(meter: Meter, tick: int) -> tuple[int, float]:
    """The 1-based bar a tick falls in and the sixteenths from that bar's start."""
    bar, offset = divmod(tick, meter.bar_ticks)
    return bar + 1, offset / meter.sixteenth_ticks


def where(meter: Meter, tick: int) -> str:
    bar, sixteenths = position(meter, tick)
    return f"bar {bar} pos {sixteenths:g}"


def halves(meter: Meter, tick: int) -> int:
    """Half-sixteenths from tick 0 to the nearest, a tie going later. In integers, since a
    half-sixteenth can be a fraction of a tick, and round() sends ties to the even one."""
    return (4 * tick + meter.sixteenth_ticks) // (2 * meter.sixteenth_ticks)


def nearest(meter: Meter, tick: int) -> tuple[int, float]:
    """As position, for a tick rounded to the nearest half-sixteenth first, as the dump places a
    note: an onset just ahead of a bar line reads on the downbeat it anticipates."""
    bar, half = divmod(halves(meter, tick), 2 * meter.sixteenths_per_bar)
    return bar + 1, half / 2
