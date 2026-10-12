"""The cover and the melody bar by bar as text: an arranging agent's only view of the song. Every
tick is rounded to the nearest half-sixteenth before its bar is taken, so an onset played just
ahead of a bar line reads on the downbeat it anticipates."""

from collections import defaultdict

import mido

from . import bars, notes
from .evidence import markers
from .finding import clock
from .melody import pitch_name


def lines(
    cover: mido.MidiFile, melody: mido.MidiFile, bar_range: tuple[int, int] | None = None
) -> list[str]:
    """Per bar, `=== bar N  m:ss.ss` and the markers starting in it, a `C` line of the cover's
    attacks and a `V` line of the melody, positions and durations in sixteenths. The melody and
    the markers are placed by their seconds on the cover's tempo map. Bars run from 1 to the
    cover's last, or past it to the last any note or marker rounds into; `bar_range`, first and
    last inclusive, keeps the bars of it that exist."""
    meter = bars.meter(cover)
    per_bar = 2 * meter.sixteenths_per_bar

    def halves(tick: int) -> int:
        """Half-sixteenths from tick 0 to the nearest, a tie going later. In integers, since a
        half-sixteenth can be a fraction of a tick, and round() sends ties to the even one."""
        return (4 * tick + meter.sixteenth_ticks) // (2 * meter.sixteenth_ticks)

    def place(tick: int) -> tuple[int, str]:
        """The 1-based bar of a rounded tick and its position, `pos:`."""
        bar, half = divmod(halves(tick), per_bar)
        return bar + 1, f"{half / 2:g}:"

    heads: defaultdict[int, list[str]] = defaultdict(list)
    # bar -> half-sixteenths into it -> (pitch, duration, velocity) of each note struck there
    struck: defaultdict[int, defaultdict[int, list]] = defaultdict(lambda: defaultdict(list))
    sung: defaultdict[int, list[str]] = defaultdict(list)
    for seconds, text in markers(cover):
        bar, pos = place(notes.tick_at(cover, seconds))
        # A line break in a marker would start a line the agent cannot place, and a run of
        # spaces would read as the gap between two header fields.
        heads[bar].append(pos + " ".join(text.split()))
    for note in notes.read(cover):
        on, off = halves(note.on_tick), halves(note.off_tick)
        struck[on // per_bar + 1][on % per_bar].append((note.pitch, (off - on) / 2, note.velocity))
    for note in notes.read(melody):
        on, off = notes.tick_at(cover, note.onset), notes.tick_at(cover, note.offset)
        bar, pos = place(on)
        sung[bar].append(f"{pos}{pitch_name(note.pitch)}({(halves(off) - halves(on)) / 2:g})")

    last = max([bars.bar_count(cover, meter), *heads, *struck, *sung])
    first, final = bar_range or (1, last)
    segments = notes.tempo_map(cover)
    found: list[str] = []
    for bar in range(max(first, 1), min(final, last) + 1):
        start = notes.seconds_at(segments, meter.ticks_per_beat, (bar - 1) * meter.bar_ticks)
        found.append("  ".join([f"=== bar {bar}", clock(start), *heads[bar]]))
        played = [
            f"{half / 2:g}:" + ",".join(f"{pitch_name(p)}({d:g},{v})" for p, d, v in sorted(chord))
            for half, chord in sorted(struck[bar].items())
        ]
        found.append("C " + "  ".join(played))
        found.append("V " + "  ".join(sung[bar]))
    return found
