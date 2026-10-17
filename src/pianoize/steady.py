"""One steady tempo for a transcription whose tempo map bends. tsumugi tracks long stretches at
half speed and squeezes bars elsewhere, so its bar lines fall off the song's downbeats there. The
fit finds the sixteenth grid nearest the transcription's attacks, near tsumugi's dominant tempo,
and puts the downbeats where tsumugi's own bar lines say, counting only bars it tracked at that
tempo. The copy gets the steady tempo, after a pickup bar when the song starts off a downbeat, and
every event the tick its seconds fall on."""

import bisect
import itertools
from dataclasses import dataclass

import mido
import numpy as np

from . import bars, notes
from .bars import Meter
from .grid import _final_tick, _retimed, _ticks

# An attack is on the grid within this share of a sixteenth. A share, not seconds, so attacks
# placed at random land on it half the time at every tempo, and one coverage gate holds for all.
ON_GRID = 0.25
# The best grid the search finds for randomly timed attacks covers 62% of 300 of them, and up to
# 73% of 100; the two test songs give 89% and 77%.
MIN_ATTACKS = 300
GOOD = 0.7
# An attack off the grid by more than this, in sixteenths, costs no more: a slip, an ornament or a
# triplet must not pull the grid.
_CLIP = 0.375
# The bpm searched, as a share either side of tsumugi's dominant tempo. A nearest-sixteenth cost
# always prefers the double tempo, so tsumugi chooses the octave.
_BAND = 0.15
# Over a 5-minute song a 0.01 bpm error drifts 18 ms, so no coarser pass finds the basin.
_STEP = 0.01
# Grid offsets tried within a sixteenth. The search lands within half a step of the best offset,
# about 1.4 ms at 170 bpm, near the millisecond the attacks are rounded to, so a finer one has
# little left to find.
_PHASES = 32
# The attacks cannot tell the octave for eighth-note music (a nearest-sixteenth grid fits double at
# least as well, and eighths fit half as well as sixteenths), so the grid takes the octave tsumugi
# held longer, and any seconds the map spent at the other octave are reported.
# The grid is checked over spans of this many seconds. A span with at least _SPAN_ATTACKS attacks
# misses when under _SPAN_GOOD of them are on the grid: attacks placed at random are on it half the
# time, and 100 of them stay under 0.6 about 3% of the time. It has changed tempo when another
# tempo holds the beats better: a tempo's beat occupancy is the share of the span's quarter-note
# beats, at the span's best phase, that carry an attack. Uniform subdivisions, eighths or
# sixteenths, fill every beat of the fit's tempo (and of half and double it, which are never
# tried), so no other tempo can beat the fit, while a section at another tempo fills its own
# beats and, under the fit's, only the few that line up (a quarter-note section at 120 bpm fills
# 1.0 of its beats and about 0.2 at 150). An alternative has to reach _OCCUPIED and beat the
# fit's by _GAIN; tempos within _SIMILAR of the fit, half and double share beats with it and
# are not tried. _SPAN_RUN spans in a row that miss or changed are a stretch the steady tempo
# does not fit; a short intro or coda is not. At four alignments of the spans, neither test
# song has a changed span, and the longest run of misses is 2.
_SPAN = 10.0
_SPAN_ATTACKS = 20
_SPAN_GOOD = 0.6
_OCCUPIED = 0.8
_GAIN = 0.3
_SIMILAR = 0.05
_RATIOS = (1 / 2, 1, 2)
_ALTERNATIVES = 0.5 * 1.003 ** np.arange(round(np.log(4) / np.log(1.003)) + 1)  # 0.5x to 2x
_BEAT_PHASES = 16
_SPAN_RUN = 3
# A tsumugi bar line votes for the downbeat where its tempo is this near the fit, as in regrid.
_AGREE = 0.05


class SteadyError(ValueError):
    pass


@dataclass(frozen=True)
class Fit:
    bpm: float
    downbeat: float  # seconds of the first downbeat, in [-window, bar - window)
    coverage: float  # the share of the attacks on the grid
    attacks: int  # distinct attacks
    other_octave: float = 0.0  # bpm of the other octave tsumugi's map ran at, half or double
    other_octave_share: float = (
        0.0  # its share of the map's seconds; 0 when the map spent none there
    )
    # bars.meter_change of the transcription: the grid keeps the first meter through the song
    meter_change: tuple[int, str, str] | None = None

    @property
    def window(self) -> float:
        """Seconds either side of a sixteenth within which an attack is on it."""
        return ON_GRID * _sixteenth(self.bpm)


def _sixteenth(bpm: float) -> float:
    return 15 / bpm  # a tempo counts quarter notes


def _attacks(midi: mido.MidiFile, segments: list[tuple[int, float, int]]) -> np.ndarray:
    """The seconds of every struck note on every track and channel, to the millisecond, on
    `segments`, the file's tempo map; distinct and sorted, so a chord counts once. Drums included:
    they mark the beat best."""
    ticks = {
        tick
        for track in midi.tracks
        for tick, message in _ticks(track)
        if message.type == "note_on" and message.velocity > 0
    }
    found = {round(notes.seconds_at(segments, midi.ticks_per_beat, tick), 3) for tick in ticks}
    return np.array(sorted(found))


def _weighted(
    segments: list[tuple[int, float, int]], end_seconds: float
) -> list[tuple[float, float]]:
    """(bpm, seconds) of each of tsumugi's tempo segments, up to the next one or to the end."""
    ends = [seconds for _, seconds, _ in segments[1:]] + [end_seconds]
    return [
        (mido.tempo2bpm(tempo), end - start)
        for (_, start, tempo), end in zip(segments, ends, strict=True)
    ]


def _dominant(segments: list[tuple[int, float, int]], end_seconds: float) -> float:
    """tsumugi's tempo over most of the song: the median bpm of its tempo segments, each weighted
    by its seconds up to the next one or to the end."""
    weighted = sorted(_weighted(segments, end_seconds))
    half = sum(seconds for _, seconds in weighted) / 2
    reached = itertools.accumulate(seconds for _, seconds in weighted)
    return next(bpm for (bpm, _), total in zip(weighted, reached, strict=True) if total >= half)


def _other_octave(
    segments: list[tuple[int, float, int]], end_seconds: float, bpm: float
) -> tuple[float, float]:
    """The bpm, half or double `bpm`, that holds the larger share of tsumugi's map seconds within
    _BAND, and that share; (0, 0) when the map spent none there."""
    weighted = _weighted(segments, end_seconds)
    total = sum(seconds for _, seconds in weighted)
    share, other = max(
        (sum(s for tempo, s in weighted if abs(tempo / o - 1) <= _BAND) / total, o)
        for o in (bpm / 2, bpm * 2)
    )
    return (other, share) if share > 0 else (0.0, 0.0)


def _distances(onsets: np.ndarray, bpm: float, phases: np.ndarray) -> np.ndarray:
    """Each attack's distance to its nearest sixteenth, in sixteenths, on the grid at `bpm`
    shifted by each of `phases` sixteenths: a row a phase."""
    # Each attack in sixteenths of the shifted grid; rint, since % 1 is about ten times slower.
    v = onsets * (bpm / 15) - phases[:, np.newaxis]
    return np.abs(v - np.rint(v))


def _search(onsets: np.ndarray, dominant: float) -> tuple[float, float, int]:
    """The bpm and the phase, in seconds, of the sixteenth grid the attacks sit nearest, and how
    many of them are on it. Every bpm on the _STEP grid within _BAND of `dominant` and _PHASES
    phases a sixteenth are tried; the cost is the attacks' mean distance to the grid, each
    clipped at _CLIP, and the first minimum wins."""
    steps = round(1 / _STEP)  # candidates a bpm, so each is exactly k / steps
    phases = np.arange(_PHASES) / _PHASES
    best_cost, best_bpm, best_phase = np.inf, 0.0, 0.0
    for k in range(
        round((1 - _BAND) * dominant * steps), round((1 + _BAND) * dominant * steps) + 1
    ):
        bpm = k / steps
        costs = np.minimum(_distances(onsets, bpm, phases), _CLIP).mean(axis=1)
        j = int(np.argmin(costs))
        if costs[j] < best_cost:
            best_cost, best_bpm, best_phase = costs[j], bpm, float(phases[j])
    on_grid = _distances(onsets, best_bpm, np.array([best_phase]))[0] <= ON_GRID
    return best_bpm, best_phase * _sixteenth(best_bpm), int(on_grid.sum())


def _occupancy(attacks: np.ndarray, start: float, length: float, bpms: np.ndarray) -> np.ndarray:
    """Each of `bpms`' beat occupancy over the span of `length` seconds from `start`: the share of
    its quarter-note beats with an attack within ON_GRID of a sixteenth, at the best of
    _BEAT_PHASES phases of the beat."""
    beats = bpms / 60  # a second
    width = ON_GRID / 4  # of a beat
    u = (attacks - start) * beats[:, np.newaxis]  # a row a tempo, in beats
    best = np.zeros(len(bpms))
    rows = np.arange(len(bpms))[:, np.newaxis]
    # Beat n of row r is cell r * size + n; the attacks of a beat share a cell.
    size = int(length * beats.max()) + 2
    for phase in np.arange(_BEAT_PHASES) / _BEAT_PHASES:
        v = u - phase
        n = np.rint(v)
        cell = (rows * size + n).astype(int)
        keep = (np.abs(v - n) <= width) & (n >= 0) & (n < size)
        filled = np.bincount(cell[keep], minlength=len(bpms) * size).reshape(len(bpms), size) > 0
        best = np.maximum(best, filled.sum(axis=1) / (length * beats))
    return np.minimum(best, 1.0)


def _check_spans(onsets: np.ndarray, bpm: float, phase: float) -> None:
    """Raise SteadyError when the grid at `bpm` and `phase` seconds misses a sustained stretch:
    _SPAN_RUN spans of _SPAN seconds in a row that miss it or have changed tempo."""
    v = onsets * (bpm / 15) - phase / _sixteenth(bpm)
    on_grid = np.abs(v - np.rint(v)) <= ON_GRID
    span = (onsets // _SPAN).astype(int)
    counts = np.bincount(span)
    hits = np.bincount(span, weights=on_grid)
    near = [bpm * ratio for ratio in _RATIOS]
    tried = _ALTERNATIVES * bpm
    tried = tried[[all(abs(t / n - 1) > _SIMILAR for n in near) for t in tried]]
    run = []  # per span of the run, the tempo that holds its beats, or None for a miss
    longest: list[float | None] = []
    for index, (count, hit) in enumerate(zip(counts, hits, strict=True)):
        if count < _SPAN_ATTACKS:
            run = []
            continue
        start = index * _SPAN
        found = onsets[span == index]
        length = min(_SPAN, found[-1] - start)
        changed = None
        if hit >= _SPAN_GOOD * count:
            own = _occupancy(found, start, length, np.array([bpm]))[0]
            # The fit needs no alternative where nothing could beat it by _GAIN.
            if own <= 1 - _GAIN:
                other = _occupancy(found, start, length, tried)
                best = int(np.argmax(other))
                if other[best] >= max(_OCCUPIED, own + _GAIN):
                    changed = float(tried[best])
            if changed is None:
                run = []
                continue
        run.append(changed)
        if len(run) > len(longest):
            longest = list(run)
    if len(longest) >= _SPAN_RUN:
        named = next((t for t in longest if t is not None), None)
        why = (
            f"; their beats sit nearer {named:.0f} bpm"
            if named is not None
            else f", under {_SPAN_GOOD:.0%} of their attacks on the grid"
        )
        raise SteadyError(
            f"{bpm:.2f} bpm does not hold through the song: {len(longest)} spans of {_SPAN:g} s "
            f"in a row miss it{why}"
        )


def _downbeat(
    meter: Meter,
    segments: list[tuple[int, float, int]],
    last: int,
    bpm: float,
    phase: float,
) -> float:
    """Seconds of the first downbeat on the grid at `bpm` and `phase`: the sixteenth of the bar
    most of tsumugi's bar lines fall on, counting only those whose tempo is within _AGREE of the
    fit. Where tsumugi's tempo is right its bars are right; a tempo a little off passes that test
    but drifts through every sixteenth of the bar, so the winner must hold more than half the
    votes. A downbeat within the window of the next bar line is the one a bar earlier, so the
    result is in [-window, bar - window). Bar lines run up to tick `last`."""
    sixteenth = _sixteenth(bpm)
    starts = [tick for tick, _, _ in segments]
    votes = [0] * meter.sixteenths_per_bar
    for tick in range(0, last + 1, meter.bar_ticks):
        _, _, tempo = segments[bisect.bisect_right(starts, tick) - 1]
        if abs(mido.tempo2bpm(tempo) / bpm - 1) > _AGREE:
            continue
        seconds = notes.seconds_at(segments, meter.ticks_per_beat, tick)
        # The grid's sixteenths sit at phase + n * sixteenth, not at multiples of it from zero.
        votes[round((seconds - phase) / sixteenth) % meter.sixteenths_per_bar] += 1
    agreeing = sum(votes)
    if not agreeing:
        raise SteadyError(
            f"none of tsumugi's bars run within {_AGREE:.0%} of {bpm:.2f} bpm, so the downbeats "
            "are unknown"
        )
    index = votes.index(max(votes))  # the lowest on a tie
    if 2 * votes[index] <= agreeing:
        raise SteadyError(
            f"tsumugi's bars agree on no downbeat: the most-voted sixteenth holds {votes[index]} "
            f"of {agreeing} bar lines"
        )
    downbeat = phase + index * sixteenth
    bar = meter.sixteenths_per_bar * sixteenth
    return downbeat - bar if bar - downbeat <= ON_GRID * sixteenth else downbeat


def fit(midi: mido.MidiFile) -> Fit:
    """The steady tempo and the first downbeat of a transcription, on its first meter, and the
    change of meter that the grid flattens, if any. Raises SteadyError when it has fewer than
    MIN_ATTACKS distinct attacks, or bars.first_meter refuses its meter, or
    it puts under GOOD of its attacks on the best grid, or the grid misses a sustained stretch, or
    its bars don't say where the downbeats are. The octave is the dominant tempo's."""
    segments = notes.tempo_map(midi)
    onsets = _attacks(midi, segments)
    if len(onsets) < MIN_ATTACKS:
        raise SteadyError(f"{len(onsets)} distinct attacks, fewer than {MIN_ATTACKS}")
    try:
        meter = bars.first_meter(midi)
    except bars.MeterError as exc:
        raise SteadyError(str(exc)) from exc
    last = max(_final_tick(track) for track in midi.tracks)
    end = notes.seconds_at(segments, midi.ticks_per_beat, last)
    bpm, phase, on_grid = _search(onsets, _dominant(segments, end))
    coverage = on_grid / len(onsets)
    if coverage < GOOD:
        # Floored, so a share just under the gate never reads as the gate, and in integers:
        # 0.57 * 100 is 56.99999999999999.
        raise SteadyError(
            f"best fit {bpm:.2f} bpm puts {100 * on_grid // len(onsets)}% of {len(onsets)} attacks "
            f"within a quarter sixteenth, under {GOOD:.0%}"
        )
    _check_spans(onsets, bpm, phase)
    downbeat = _downbeat(meter, segments, last, bpm, phase)
    other, share = _other_octave(segments, end, bpm)
    return Fit(bpm, downbeat, coverage, len(onsets), other, share, bars.meter_change(midi))


def apply(midi: mido.MidiFile, fit: Fit) -> mido.MidiFile:
    """A copy of the file on the fitted grid. Its tempo is the steady one from tick 0 when the
    first downbeat is within the window of the start; otherwise bar 1 is a pickup at the tempo
    that fits it into the seconds before that downbeat, and the steady tempo starts at bar 2. That
    keeps tick 0 at 0 s, one meter, and the bar lines on the downbeats. Every event but the old
    tempos, each track's end included, moves to the tick nearest the seconds it had, so it keeps
    them within half a tick. A time signature whose bar is not the first one's length is dropped:
    the steady map replaces the one tsumugi's beat tracking wrote it with, as when it flips to the
    other octave, and the score format needs one meter. Type, resolution, charset, track order
    and every other message stay as they were; the new tempos go on the track that carried the
    first old one."""
    ticks_per_beat = midi.ticks_per_beat
    first = bars.first_meter(midi)
    bar_ticks = first.bar_ticks

    def kept(message: mido.Message) -> bool:
        if message.type in ("set_tempo", "end_of_track"):
            return False
        if message.type != "time_signature":
            return True
        return message.numerator * first.denominator == first.numerator * message.denominator

    steady = round(60e6 / fit.bpm)
    new = [(0, 0.0, steady)]
    if fit.downbeat > fit.window:
        pickup = round(fit.downbeat * 1e6 * ticks_per_beat / bar_ticks)
        # Bar 2's seconds as notes.tempo_map reads them back, so every event lands where it reads.
        bar_2 = mido.tick2second(bar_ticks, ticks_per_beat, pickup)
        new = [(0, 0.0, pickup), (bar_ticks, bar_2, steady)]
    old = notes.tempo_map(midi)

    def moved(tick: int) -> int:
        return notes.tick_in(new, ticks_per_beat, notes.seconds_at(old, ticks_per_beat, tick))

    _, carrier = min(
        (
            (tick, index)
            for index, track in enumerate(midi.tracks)
            for tick, message in _ticks(track)
            if message.type == "set_tempo"
        ),
        default=(0, 0),
    )
    fixed = mido.MidiFile(type=midi.type, ticks_per_beat=ticks_per_beat, charset=midi.charset)
    for index, track in enumerate(midi.tracks):
        events = [(moved(tick), message) for tick, message in _ticks(track) if kept(message)]
        end = moved(_final_tick(track))
        if index == carrier:
            tempos = [(tick, mido.MetaMessage("set_tempo", tempo=t)) for tick, _, t in new]
            # Stable: a tempo goes after the messages on its tick. tsumugi's tempo track ends at
            # its last tempo, which on a flat map is tick 0, before bar 2's.
            events = sorted(events + tempos, key=lambda event: event[0])
            end = max(end, events[-1][0])
        fixed.tracks.append(_retimed(events, end))
    return fixed
