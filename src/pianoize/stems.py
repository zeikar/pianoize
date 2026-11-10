"""Where a transcribed line and the recording disagree, listed for the arranger to weigh and never
flagged: the stem table is evidence like the transcription, with errors of its own (the tracker's
octave slips, a backing voice, reverb). The table, `stems.npz`, is what `prepare` measures from
the separated stems: on `vocals`, a pitch and a level per frame; on `guitar`, `other` and `piano`,
a level per semitone per frame. No threshold is an absolute level: a level is read against the
stem's loud level or against the line's own notes. On a line's notes, in seconds:

- a frame's reading is, on the vocals, its pitch and its level; on a levels stem, for a note at
  pitch p, the lead, the loudest semitone from p - LEAD_SEMITONES to p + LEAD_SEMITONES, a tie
  going lower, and its level;
- the stem's loud level is the LOUD_PERCENTILE percentile of its frame levels, a levels stem's
  being its loudest semitone, among the frames within LOUD_WITHIN_DB of its loudest. A frame
  sounds when its reading's level is within SOUNDING_DB of it and above the scale's floor; a
  vocals frame also needs a pitch;
- the notes read last playability.SUNG_MIN or more and sit inside the table's time and the
  pitches the stem was measured over: vocals_low to vocals_high on the vocals, low_pitch and the
  rows above it on a levels stem. Another note is not read and not counted. A note's frames are
  those centred in it, and its level the mean, over them, of the vocals level or of its own
  semitone;
- a note is `silent` when under SILENT_SHARE of its frames sound. Else it is judged frame by
  frame, never by a median, which can land on a pitch no frame sounds: a sounding vocals frame
  agrees within AGREE_SEMITONES of the note, a sounding levels frame carries the note when its
  semitone is within CARRY_DB of the lead, and the note is supported when SUPPORTED_SHARE of its
  sounding frames agree or carry it. Else the audio's reading is the commonest rounded pitch, or
  lead, among the sounding frames that don't, a tie going lower: `octave` when it is the note an
  octave either side, else `pitch`;
- a stretch, `untranscribed`, is a run of one pitch over the sounding frames no note of the line
  covers: the rounded pitch on the vocals, on a levels stem the lead between the lowest and the
  highest note read. Two runs of a pitch under JOIN_SECONDS apart are one. An onset is the first
  of consecutive frames of a run each RISE_DB or more over its level RISE_SECONDS earlier, so a
  fading tail never has one. Each onset starts a stretch, to the next onset or the run's end, and
  the frames ahead of the first start none: a quiet lead-in and the pickup after it are two
  stretches, the pickup printed at its rise. A stretch is listed only when it lasts STRETCH_MIN;
  when it is no slide, ending within SLIDE_SECONDS of the start of a note of the line within
  SLIDE_SEMITONES of it, its loudest frame in its last SLIDE_SECONDS; and when its mean level is
  not under every one of the notes read around it, NEIGHBOURS before it and NEIGHBOURS after. A
  stretch's level is that of the vocals or of its own semitone."""

import zipfile
import zlib
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .bars import Meter, halves, nearest
from .finding import clock
from .melody import pitch_name
from .notes import Note, tick_in
from .playability import SUNG_MIN

VERSION = 1
LEVEL_STEMS = ("guitar", "other", "piano")
PITCH_STEM = "vocals"

LOUD_PERCENTILE = 95  # the stem's loud level is not its single loudest frame, a peak
LOUD_WITHIN_DB = 40  # its quiet frames left out, a stem silent most of the song still has one
SOUNDING_DB = 30  # a reading this near the loud level is the stem playing, not bleed or reverb
SILENT_SHARE = 0.3  # the experiment's voiced share: a note fewer of whose frames sound is silent
AGREE_SEMITONES = 0.7  # the experiment's: within it a sung pitch is the note, vibrato and all
CARRY_DB = 10  # the experiment saw an instrument line stand 10 dB over the rest of its register
LEAD_SEMITONES = 12  # an octave either side: the register a note's lead is sought in
SUPPORTED_SHARE = 0.5  # half the sounding frames, so a held note under a moving line is not passed
RISE_DB = 6  # a doubling: a note starting; a held note's tail only fades
RISE_SECONDS = 0.050  # the rise is measured across the experiment's joining gap
JOIN_SECONDS = 0.050  # the experiment's joining gap: a shorter break is one stretch
STRETCH_MIN = 0.100  # the experiment listed stretches this long; a shorter one is a sliver
SLIDE_SEMITONES = 2  # a tone: a scoop into a note starts this near it
SLIDE_SECONDS = 0.050  # a scoop ends at its note and is loudest just before it
NEIGHBOURS = 4  # the notes either side a stretch's level is read against, a bar or so of a line

_FLOOR = -127.5  # dB, the byte scale's 0: this or less is nothing measured

# tsumugi's STEM_INSTRUMENT_CLASSES (instrument_agnostic_amt/amt/inference/instruments.py) at
# tsumugi.TSUMUGI_COMMIT, by stem; it changes with the pin. A track of tsumugi's transcription
# is named by its class.
_STEM_CLASSES = {
    "drums": ("drums", "wind_chimes", "timpani"),
    "bass": ("acoustic_bass", "electric_bass", "slap_bass", "synth_bass"),
    "vocals": ("melody", "vocal_harmony", "choir"),
    "guitar": (
        "acoustic_guitar",
        "electric_guitar_clean",
        "electric_guitar_muted",
        "distorted_guitar",
        "guitar_harmonics",
        "ethnic",
    ),
    "piano": ("piano", "electric_piano", "plucked_keyboard"),
    "other": (
        "accordion_family",
        "brass",
        "chromatic_percussion",
        "ethnic",
        "flute_pipe",
        "harmonica",
        "orchestra_hit",
        "orchestral_harp",
        "orchestral_woodwind",
        "organ",
        "percussive_fx",
        "pizzicato_strings",
        "plucked_keyboard",
        "sax",
        "sound_fx",
        "strings",
        "synth_fx",
        "synth_lead",
        "synth_pad",
        "timpani",
        "wind_chimes",
    ),
}
# A track's class -> the stem it reads against. A class listed under `other` and under a named
# stem reads against the named one, `other` being the splitter's catch-all: written after it.
# A class under `drums` and `other` reads `drums`, which the table doesn't measure, so its track
# is refused unless `--stem` names a stem.
STEM_OF = {
    name: stem
    for stem in ("other", "drums", "bass", "vocals", "guitar", "piano")
    for name in _STEM_CLASSES[stem]
}

KINDS = ("pitch", "octave", "silent", "untranscribed")

_ARRAYS = (
    "frame_seconds",
    "low_pitch",
    *LEVEL_STEMS,
    "vocals_pitch",
    "vocals_low",
    "vocals_high",
    "vocals_level",
)
_PER_FRAME = (*LEVEL_STEMS, "vocals_pitch", "vocals_level")


class StemsError(ValueError):
    pass


@dataclass(frozen=True)
class Table:
    """A stem table, its levels in dB under each stem's loudest: frame i is centred on
    i × frame_seconds."""

    frame_seconds: float
    low_pitch: int  # the levels' first row
    levels: dict[str, np.ndarray]  # stem -> a row per semitone from low_pitch, by frames
    vocals_pitch: np.ndarray  # a fractional MIDI pitch per frame, NaN where unvoiced
    vocals_low: int  # the pitch tracker's range, as MIDI pitches
    vocals_high: int
    vocals_level: np.ndarray

    @property
    def stems(self) -> tuple[str, ...]:
        return tuple(sorted([PITCH_STEM, *self.levels]))

    @property
    def seconds(self) -> float:
        return len(self.vocals_level) * self.frame_seconds


def _decibels(scaled: np.ndarray) -> np.ndarray:
    """The byte scale in dB: 255 is 0 dB, a step half a dB."""
    return (scaled.astype(np.float32) - 255) / 2


def load(path: Path) -> Table:
    """The table at `path`. A file that is no npz or a damaged one, another version, a missing
    array, arrays of unequal frame counts and no frames raise StemsError, its message the
    reason."""
    try:
        data = np.load(path, allow_pickle=False)
        if not isinstance(data, np.lib.npyio.NpzFile):  # a .npy file's one array
            raise StemsError("not an npz file")
        with data:
            arrays = {name: data[name] for name in data.files}
    except OSError as error:
        raise StemsError(error.strerror or str(error)) from error
    # np.load takes a file that is no zip and no .npy for pickled data, its ValueError.
    except (ValueError, EOFError, zipfile.BadZipFile, zlib.error) as error:
        raise StemsError("not an npz file") from error
    if "version" not in arrays:
        raise StemsError("missing array version")
    if int(arrays["version"]) != VERSION:
        raise StemsError(f"version {int(arrays['version'])}; this pianoize reads {VERSION}")
    missing = [name for name in _ARRAYS if name not in arrays]
    if missing:
        raise StemsError(f"missing array{'s' * (len(missing) > 1)} {', '.join(missing)}")
    counts = {name: arrays[name].shape[-1] for name in _PER_FRAME}
    if len(set(counts.values())) > 1:
        listed = ", ".join(f"{name} {count}" for name, count in counts.items())
        raise StemsError(f"arrays of unequal frame counts: {listed}")
    if not counts["vocals_level"]:
        raise StemsError("no frames")
    return Table(
        frame_seconds=float(arrays["frame_seconds"]),
        low_pitch=int(arrays["low_pitch"]),
        levels={stem: _decibels(arrays[stem]) for stem in LEVEL_STEMS},
        vocals_pitch=arrays["vocals_pitch"].astype(np.float32),
        vocals_low=int(arrays["vocals_low"]),
        vocals_high=int(arrays["vocals_high"]),
        vocals_level=_decibels(arrays["vocals_level"]),
    )


@dataclass(frozen=True)
class Item:
    kind: str  # one of KINDS
    onset: float  # seconds: a note's onset, or where a stretch rises
    offset: float
    pitch: int
    detail: str  # what its line prints after the pitch and the length


def _loud(frame_levels: np.ndarray) -> float:
    near = frame_levels[frame_levels >= frame_levels.max() - LOUD_WITHIN_DB]
    return float(np.percentile(near, LOUD_PERCENTILE))


def _sounds(levels: np.ndarray, loud: float) -> np.ndarray:
    return (levels >= loud - SOUNDING_DB) & (levels > _FLOOR)


def _share(count: int, total: int) -> str:
    return f"{round(100 * count / total)}%"


def _judged(
    note: Note, sounding: np.ndarray, kept: np.ndarray, readings: np.ndarray
) -> Item | None:
    """The item of a note from its frames: which sound, which of those agree with it or carry it,
    and each frame's reading; None when it is supported."""
    frames, sounded = len(sounding), int(sounding.sum())
    if sounded < SILENT_SHARE * frames:
        detail = f"audio - {_share(sounded, frames)}"
        return Item("silent", note.onset, note.offset, note.pitch, detail)
    if kept.sum() >= SUPPORTED_SHARE * sounded:
        return None
    counts = Counter(readings[sounding & ~kept].tolist())
    reading = min(counts, key=lambda pitch: (-counts[pitch], pitch))
    kind = "octave" if abs(reading - note.pitch) == 12 else "pitch"
    detail = f"audio {pitch_name(reading)} {_share(counts[reading], frames)}"
    return Item(kind, note.onset, note.offset, note.pitch, detail)


def items(
    table: Table,
    stem: str,
    line: list[Note],
    others: dict[str, list[Note]],
    in_range: Callable[[float], bool],
) -> tuple[list[Item], int]:
    """The items of a line read against a stem of the table, by time, and the count of its notes
    read that `in_range` keeps. `others` are the other tracks reading against the stem, their
    notes by track name, each named on a stretch it has a note over; `in_range` keeps the notes
    and the stretches starting at the seconds it accepts."""
    seconds = table.frame_seconds
    centres = np.arange(len(table.vocals_level)) * seconds

    def frames(start: float, end: float) -> slice:
        return slice(*np.searchsorted(centres, [start, end]))

    if stem == PITCH_STEM:
        loud = _loud(table.vocals_level)
        pitched = ~np.isnan(table.vocals_pitch) & _sounds(table.vocals_level, loud)
        rounded = np.rint(np.nan_to_num(table.vocals_pitch)).astype(int)
        low, high = table.vocals_low, table.vocals_high

        def level(pitch: int) -> np.ndarray:
            return table.vocals_level

        def judge(note: Note) -> Item | None:
            span = frames(note.onset, note.offset)
            sounding = pitched[span]
            agree = sounding & (np.abs(table.vocals_pitch[span] - note.pitch) <= AGREE_SEMITONES)
            return _judged(note, sounding, agree, rounded[span])

    else:
        rows = table.levels[stem]
        loud = _loud(rows.max(axis=0))
        low, high = table.low_pitch, table.low_pitch + len(rows) - 1

        def level(pitch: int) -> np.ndarray:
            return rows[pitch - table.low_pitch]

        def lead(first: int, last: int, span: slice) -> tuple[np.ndarray, np.ndarray]:
            """Each frame's loudest semitone from `first` to `last`, clipped to the rows, a tie
            going lower, and its level."""
            first, last = max(first, low), min(last, high)
            window = rows[first - low : last - low + 1, span]
            return window.argmax(axis=0) + first, window.max(axis=0)

        def judge(note: Note) -> Item | None:
            span = frames(note.onset, note.offset)
            leads, loudest = lead(note.pitch - LEAD_SEMITONES, note.pitch + LEAD_SEMITONES, span)
            sounding = _sounds(loudest, loud)
            carried = sounding & (level(note.pitch)[span] >= loudest - CARRY_DB)
            return _judged(note, sounding, carried, leads)

    read = sorted(
        (
            note
            for note in line
            if note.offset - note.onset >= SUNG_MIN
            and note.offset <= table.seconds
            and low <= note.pitch <= high
        ),
        key=lambda note: (note.onset, note.pitch),
    )
    if not read:  # no note to read a stretch's level against
        return [], 0
    found = [item for note in read if in_range(note.onset) and (item := judge(note)) is not None]

    covered = np.zeros(len(centres), dtype=bool)
    for note in line:
        covered[frames(note.onset, note.offset)] = True
    # Each frame's pitch for a stretch, -1 where none can be.
    if stem == PITCH_STEM:
        pitch_at = np.where(pitched & ~covered, rounded, -1)
    else:
        pitches = [note.pitch for note in read]
        leads, loudest = lead(min(pitches), max(pitches), slice(None))
        pitch_at = np.where(_sounds(loudest, loud) & ~covered, leads, -1)

    def note_level(note: Note) -> float:
        return float(level(note.pitch)[frames(note.onset, note.offset)].mean())

    def stretch(piece: np.ndarray, pitch: int, run_level: np.ndarray) -> Item | None:
        """The item of a piece of a run, its frames from its onset on, or None when it is not
        listed."""
        start, end = piece[0] * seconds, (piece[-1] + 1) * seconds
        if end - start < STRETCH_MIN or not in_range(start):
            return None
        ends_rising = piece[run_level[piece].argmax()] * seconds >= end - SLIDE_SECONDS
        if ends_rising and any(
            abs(note.onset - end) <= SLIDE_SECONDS and abs(note.pitch - pitch) <= SLIDE_SEMITONES
            for note in line
        ):
            return None
        mean = float(run_level[piece].mean())
        around = [note for note in read if note.onset < start][-NEIGHBOURS:]
        around += [note for note in read if note.onset >= start][:NEIGHBOURS]
        around_levels = [note_level(note) for note in around]
        if all(mean < other for other in around_levels):
            return None
        detail = f"{round(mean - float(np.median(around_levels))):+d} dB"
        also = [
            f"{name} {' '.join(pitch_name(p) for p in sorted(over))}"
            for name, notes in others.items()
            if (over := {n.pitch for n in notes if n.onset < end and n.offset > start})
        ]
        if also:
            detail += "  also " + ", ".join(also)
        return Item("untranscribed", start, end, pitch, detail)

    back = round(RISE_SECONDS / seconds)
    for pitch in np.unique(pitch_at[pitch_at >= 0]).tolist():
        at = np.flatnonzero(pitch_at == pitch)
        run_level = level(pitch)
        for run in np.split(at, np.flatnonzero((np.diff(at) - 1) * seconds >= JOIN_SECONDS) + 1):
            earlier = np.where(run >= back, run_level[np.maximum(run - back, 0)], _FLOOR)
            rising = run_level[run] - earlier >= RISE_DB
            # An attack rises over several frames: only the first of consecutive rising frames
            # is an onset.
            follows = np.concatenate([[False], rising[:-1] & (np.diff(run) == 1)])
            # Each onset starts a piece; the frames ahead of the first belong to none.
            for piece in np.split(run, np.flatnonzero(rising & ~follows))[1:]:
                item = stretch(piece, pitch, run_level)
                if item is not None:
                    found.append(item)

    found.sort(key=lambda item: (item.onset, KINDS.index(item.kind), item.pitch))
    return found, sum(in_range(note.onset) for note in read)


def report(
    found: list[Item], read: int, stem: str, meter: Meter, tempo_map: list[tuple[int, float, int]]
) -> str:
    """A line per item, `bar N pos P  m:ss.ss  KIND  PITCH (LENGTH)  DETAIL`, placed by its
    seconds on the cover's tempo map as the dump places a note, the length in sixteenths; then
    `audio check: STEM, K of N notes unsupported, J untranscribed`. A note's detail is `audio
    READING SHARE`, the share of its frames that give the reading, or that sound for `silent`,
    whose reading is `-`; a stretch's is its mean level against the median of the notes around
    it, `+N dB`, and `also TRACK PITCH, …` for the other tracks with a note over it."""
    lines = []
    for item in found:
        on, off = (tick_in(tempo_map, meter.ticks_per_beat, s) for s in (item.onset, item.offset))
        bar, position = nearest(meter, on)
        length = (halves(meter, off) - halves(meter, on)) / 2
        lines.append(
            f"bar {bar} pos {position:g}  {clock(item.onset)}  {item.kind}  "
            f"{pitch_name(item.pitch)} ({length:g})  {item.detail}"
        )
    stretches = sum(item.kind == "untranscribed" for item in found)
    lines.append(
        f"audio check: {stem}, {len(found) - stretches} of {read} notes unsupported, "
        f"{stretches} untranscribed"
    )
    return "\n".join(lines)
