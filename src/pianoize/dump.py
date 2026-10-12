"""The cover and the melody bar by bar as text: an arranging agent's only view of the song. Every
tick is rounded to the nearest half-sixteenth before its bar is taken, so an onset played just
ahead of a bar line reads on the downbeat it anticipates."""

from collections import defaultdict

import mido

from . import bars, notes
from .bars import halves, nearest
from .evidence import markers
from .finding import clock
from .melody import pitch_name


def lines(
    cover: mido.MidiFile,
    melody: mido.MidiFile,
    bar_range: tuple[int, int] | None = None,
    source: mido.MidiFile | None = None,
    every_bar: bool = False,
) -> list[str]:
    """Per bar, `=== bar N  m:ss.ss` and the markers starting in it, a `C` line of the cover's
    attacks and a `V` line of the melody, positions and durations in sixteenths. With `source`,
    tsumugi's transcription, a bar whose `V` line is empty, or with `every_bar` any bar, gets an
    `I` line per named track of the source that strikes a note in it, drums left out, in the
    source's order: the track's name and its top line, the highest note of each attack. The
    melody, the markers and the source are placed by their seconds on the cover's tempo map. Bars
    run from 1 to the cover's last, or past it to the last any note or marker rounds into;
    `bar_range`, first and last inclusive, keeps the bars of it that exist."""
    meter = bars.meter(cover)
    per_bar = 2 * meter.sixteenths_per_bar

    def place(tick: int) -> tuple[int, str]:
        """The 1-based bar of a rounded tick and its position, `pos:`."""
        bar, sixteenths = nearest(meter, tick)
        return bar, f"{sixteenths:g}:"

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
        on, off = halves(meter, note.on_tick), halves(meter, note.off_tick)
        struck[on // per_bar + 1][on % per_bar].append((note.pitch, (off - on) / 2, note.velocity))
    for note in notes.read(melody):
        on, off = notes.tick_at(cover, note.onset), notes.tick_at(cover, note.offset)
        bar, pos = place(on)
        sung[bar].append(
            f"{pos}{pitch_name(note.pitch)}({(halves(meter, off) - halves(meter, on)) / 2:g})"
        )
    segments = notes.tempo_map(cover)
    # bar -> an `I` line, without its `I `, per track of the source striking in it, in order
    instruments: defaultdict[int, list[str]] = defaultdict(list)
    for index, track in enumerate(source.tracks if source else []):
        name = " ".join(track.name.split())  # as a marker's text, so a name reads as one field
        if not name:
            continue
        # bar -> half-sixteenths into it -> (pitch, duration) of each note struck there
        attacks: defaultdict[int, defaultdict[int, list]] = defaultdict(lambda: defaultdict(list))
        for note in notes.read(source, [index]):
            # tick_in on the one map: tick_at would rebuild it for each of a band's many notes.
            on, off = (
                halves(meter, notes.tick_in(segments, meter.ticks_per_beat, seconds))
                for seconds in (note.onset, note.offset)
            )
            attacks[on // per_bar + 1][on % per_bar].append((note.pitch, (off - on) / 2))
        for bar, chords in attacks.items():
            tops = [(half, *max(chord)) for half, chord in sorted(chords.items())]
            line = [f"{half / 2:g}:{pitch_name(p)}({d:g})" for half, p, d in tops]
            instruments[bar].append("  ".join([name, *line]))

    last = max([bars.bar_count(cover, meter), *heads, *struck, *sung, *instruments])
    first, final = bar_range or (1, last)
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
        if every_bar or not sung[bar]:
            found += ["I " + line for line in instruments[bar]]
    return found
