"""The score an agent writes for two hands, bar by bar: parsed with its bar-range copies resolved,
then read as notes and chords on the cover's meter."""

import re
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, replace
from itertools import pairwise

from .bars import Meter

FORMAT_VERSION = 1

# The role each hand line plays and the hand that plays it: the melody and the right hand's
# voicing are both right hand, so the playability check counts them together.
HANDS = {"M": "RH", "R": "RH", "L": "LH"}

QUALITIES = {
    "": (0, 4, 7),
    "m": (0, 3, 7),
    "7": (0, 4, 7, 10),
    "M7": (0, 4, 7, 11),
    "m7": (0, 3, 7, 10),
    "mM7": (0, 3, 7, 11),
    "m6": (0, 3, 7, 9),
    "6": (0, 4, 7, 9),
    "dim7": (0, 3, 6, 9),
    "m7b5": (0, 3, 6, 10),
    "sus4": (0, 5, 7),
    "7sus4": (0, 5, 7, 10),
    "add9": (0, 2, 4, 7),
    "M9": (0, 2, 4, 7, 11),
    "aug": (0, 4, 8),
}
TENSIONS = {"9": 2, "b9": 1, "11": 5, "#11": 6, "13": 9, "b13": 8}

_LETTERS = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
_ACCIDENTALS = {"": 0, "#": 1, "b": -1}
_NOTE = re.compile(r"([A-G])([#b]?)(\d)(~?)")
_CHORD = re.compile(r"([A-G])([#b]?)([^/(]*)(?:\(([^)]*)\))?(?:/([A-G])([#b]?))?")
# Digits only: float() would also take nan, inf and signs.
_DECIMAL = re.compile(r"\d*\.?\d+")
_BAR = re.compile(r"bar\s+(\d+)")
_COPY = re.compile(r"bars\s+(\d+)-(\d+)\s*=\s*(\d+)-(\d+)")


class ArrangementError(ValueError):
    pass


@dataclass(frozen=True)
class ScoreNote:
    on_tick: int
    off_tick: int
    pitch: int
    hand: str  # RH | LH
    role: str  # M | R | L
    passing: bool  # written with ~: off the chord on purpose
    bar: int


@dataclass
class Bar:
    number: int
    chords: list[tuple[float, str]]  # (sixteenths into the bar, symbol), ascending
    pedal: str  # chord | none | positions, x for a lift only: "0,x8,12"
    lines: dict[str, list[str]]  # role -> its pos:notes:dur tokens as written
    section: str


@dataclass
class Score:
    bars: list[Bar]  # bar n at index n - 1
    sixteenths_per_bar: int


def pitch_class(letter: str, accidental: str) -> int:
    return _LETTERS[letter] + _ACCIDENTALS[accidental]


def chord_pitch_classes(symbol: str) -> frozenset[int] | None:
    """The pitch classes of a chord symbol, its tensions and its slash bass; None for N.C."""
    if symbol == "N.C.":
        return None
    match = _CHORD.fullmatch(symbol)
    if match and match[3] not in QUALITIES:
        known = ", ".join(quality or "''" for quality in QUALITIES)
        raise ArrangementError(f"bad chord {symbol!r} (qualities: {known})")
    tensions = match[4].split(",") if match and match[4] is not None else []
    if match and all(tension in TENSIONS for tension in tensions):
        root = pitch_class(match[1], match[2])
        intervals = [*QUALITIES[match[3]], *(TENSIONS[tension] for tension in tensions)]
        classes = {(root + interval) % 12 for interval in intervals}
        if match[5]:
            classes.add(pitch_class(match[5], match[6]) % 12)
        return frozenset(classes)
    raise ArrangementError(f"bad chord {symbol!r}")


def pitch(name: str) -> tuple[int, bool]:
    """A note name's MIDI pitch, C4 being 60, and whether a trailing ~ marks it a passing tone."""
    match = _NOTE.fullmatch(name)
    if match:
        value = 12 * (int(match[3]) + 1) + pitch_class(match[1], match[2])
        if value <= 127:  # MIDI's top note is G9
            return value, match[4] == "~"
    raise ArrangementError(f"bad note {name!r}")


@contextmanager
def _within(what: str) -> Iterator[None]:
    """Prefixes an error raised inside with what it was raised on."""
    try:
        yield
    except ArrangementError as exc:
        raise ArrangementError(f"{what}: {exc}") from None


def _sixteenths(text: str, what: str) -> float:
    if not _DECIMAL.fullmatch(text):
        raise ArrangementError(f"bad {what} {text!r}")
    return float(text)


def _position(text: str, sixteenths_per_bar: int) -> float:
    position = _sixteenths(text, "position")
    if position >= sixteenths_per_bar:
        raise ArrangementError(f"position {text} is outside the bar")
    return position


def _token(token: str, sixteenths_per_bar: int) -> tuple[float, list[tuple[int, bool]], float]:
    """A pos:notes:dur token's position, its (pitch, passing) notes and its duration."""
    with _within(f"token {token!r}"):
        fields = token.split(":")
        if len(fields) != 3:
            raise ArrangementError("expected pos:notes:dur")
        place, names, length = fields
        position = _position(place, sixteenths_per_bar)
        notes = [pitch(name) for name in names.split("+")]
        duration = _sixteenths(length, "duration")
        if duration == 0:
            raise ArrangementError("the duration is zero")
        return position, notes, duration


def _chords(field: str, sixteenths_per_bar: int) -> list[tuple[float, str]]:
    entries = field.split()
    if not entries:
        raise ArrangementError("no chords")
    if len(entries) == 1 and ":" not in entries[0]:
        entries = [f"0:{entries[0]}"]
    chords = []
    for entry in entries:
        place, colon, symbol = entry.partition(":")
        if not colon:
            raise ArrangementError(f"chord {entry!r}: several chords need a position each")
        with _within(f"chord {entry!r}"):
            chords.append((_position(place, sixteenths_per_bar), symbol))
    _ascending([position for position, _ in chords], "chord positions")
    for _, symbol in chords:
        chord_pitch_classes(symbol)
    return chords


def _ascending(positions: list[float], what: str) -> None:
    for before, after in pairwise(positions):
        if after <= before:
            raise ArrangementError(f"{what} {before:g} and {after:g} are not ascending")


def _pedal(settings: list[str], default: str, sixteenths_per_bar: int) -> str:
    pedal = None
    for setting in settings:
        key, _, value = (part.strip() for part in setting.partition("="))
        if key != "pedal":
            raise ArrangementError(f"unknown setting {key!r}")
        if pedal is not None:
            raise ArrangementError("setting 'pedal' given twice")
        if value not in ("chord", "none"):
            with _within(f"pedal {value!r}"):
                places = value.split(",")
                positions = [_position(p.removeprefix("x"), sixteenths_per_bar) for p in places]
                # The builder lifts and presses in the order written.
                _ascending(positions, "positions")
        pedal = value
    return default if pedal is None else pedal


def parse(text: str, sixteenths_per_bar: int) -> Score:
    """A score from its text. An error names the bar it is in, or the line outside any bar."""
    bars: list[Bar] = []
    # Copied bars not yet overridden: a `bar N` block may replace each of them once.
    copied: set[int] = set()
    section, section_pedal = "", "chord"
    current: Bar | None = None  # the bar the role lines that follow belong to
    versioned = False
    for line_number, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):  # only at the start: F#4 has one too
            continue
        where = f"line {line_number}"
        word = line.split()[0]
        try:
            if not versioned:
                if line.split() != ["format", str(FORMAT_VERSION)]:
                    raise ArrangementError(f"expected 'format {FORMAT_VERSION}', found {line!r}")
                versioned = True
            elif line.startswith("=="):
                current = None
                section, *settings = (part.strip() for part in line[2:].split("|"))
                section_pedal = _pedal(settings, section_pedal, sixteenths_per_bar)
            elif word == "bars":
                current = None
                match = _COPY.fullmatch(line)
                if not match:
                    raise ArrangementError(f"expected 'bars A-B = C-D', found {line!r}")
                first, last, source_first, source_last = map(int, match.groups())
                if 1 <= first <= len(bars):
                    raise ArrangementError(f"bar {first} is defined twice")
                where = f"bars {first}-{last}"
                if first != len(bars) + 1:
                    raise ArrangementError(f"expected bar {len(bars) + 1}")
                if last < first:
                    raise ArrangementError("the range runs backwards")
                source = f"source {source_first}-{source_last}"
                if last - first != source_last - source_first:
                    raise ArrangementError(f"{source} has a different length")
                # Every bar before the next one is defined, so this is all a source needs.
                if source_first < 1 or source_last >= first:
                    raise ArrangementError(f"{source} is not defined before bar {first}")
                # Own containers, so editing one bar of a parsed score never edits its copies.
                for bar in bars[source_first - 1 : source_last]:
                    copy = replace(
                        bar,
                        number=bar.number - source_first + first,
                        chords=list(bar.chords),
                        lines={role: list(tokens) for role, tokens in bar.lines.items()},
                        section=section,
                    )
                    bars.append(copy)
                copied.update(range(first, last + 1))
            elif word == "bar":
                head, *fields = (part.strip() for part in line.split("|"))
                match = _BAR.fullmatch(head)
                if not match:
                    raise ArrangementError(f"expected 'bar N | chords', found {line!r}")
                number = int(match[1])
                override = number in copied
                if not override and 1 <= number <= len(bars):
                    raise ArrangementError(f"bar {number} is defined twice")
                where = f"bar {number}"
                if not override and number != len(bars) + 1:
                    raise ArrangementError(f"expected bar {len(bars) + 1}")
                # An override starts from the bar it replaces, so it means the same wherever
                # in the file it is written.
                replaced = bars[number - 1] if override else None
                bar_section = replaced.section if replaced else section
                default_pedal = replaced.pedal if replaced else section_pedal
                chords = _chords(fields[0] if fields else "", sixteenths_per_bar)
                pedal = _pedal(fields[1:], default_pedal, sixteenths_per_bar)
                current = Bar(number, chords, pedal, {}, bar_section)
                if override:  # whole: the copies already taken from this bar keep theirs
                    copied.remove(number)
                    bars[number - 1] = current
                else:
                    bars.append(current)
            else:
                if current is not None:
                    where = f"bar {current.number}"
                role, *tokens = line.split()
                if role not in HANDS:
                    raise ArrangementError(f"unexpected line {line!r}")
                if current is None:
                    raise ArrangementError(f"{role} line outside a bar")
                if role in current.lines:
                    raise ArrangementError(f"a second {role} line")
                for token in tokens:
                    _token(token, sixteenths_per_bar)
                current.lines[role] = tokens
        except ArrangementError as exc:
            raise ArrangementError(f"{where}: {exc}") from None
    if not versioned:
        raise ArrangementError(f"expected 'format {FORMAT_VERSION}', found an empty score")
    if not bars:
        raise ArrangementError("the score has no bars")
    return Score(bars, sixteenths_per_bar)


def _same_bar(score: Score, meter: Meter) -> None:
    """The score's positions were checked against its own bar length; another meter would
    misplace them."""
    if score.sixteenths_per_bar != meter.sixteenths_per_bar:
        raise ArrangementError(
            f"the score was read with {score.sixteenths_per_bar} sixteenths a bar; a "
            f"{meter.numerator}/{meter.denominator} bar holds {meter.sixteenths_per_bar}"
        )


def notes_of(score: Score, meter: Meter) -> list[ScoreNote]:
    """Every note of the score in ticks, sorted by onset, then pitch."""
    _same_bar(score, meter)
    notes = []
    for bar in score.bars:
        start = (bar.number - 1) * meter.bar_ticks
        for role, tokens in bar.lines.items():
            for token in tokens:
                position, pitches, duration = _token(token, score.sixteenths_per_bar)
                on = start + round(position * meter.sixteenth_ticks)
                off = on + round(duration * meter.sixteenth_ticks)
                if off == on:  # parse cannot see this: it depends on the cover's resolution
                    raise ArrangementError(
                        f"bar {bar.number}: token {token!r}: the duration is under a tick"
                    )
                notes += [
                    ScoreNote(on, off, value, HANDS[role], role, passing, bar.number)
                    for value, passing in pitches
                ]
    return sorted(notes, key=lambda note: (note.on_tick, note.pitch))


def chord_at(score: Score, meter: Meter, tick: int) -> str:
    """The chord symbol at a tick: its bar's last entry at or before it, the first entry holding
    from the bar's start; past the last bar, the last bar's last chord."""
    _same_bar(score, meter)
    index = min(tick // meter.bar_ticks, len(score.bars) - 1)
    offset = tick - index * meter.bar_ticks  # past the last bar, beyond every entry
    chords = score.bars[index].chords
    # Compared in ticks, as notes_of places them, so a note on a chord's position gets that chord.
    entered = [symbol for place, symbol in chords if round(place * meter.sixteenth_ticks) <= offset]
    return entered[-1] if entered else chords[0][1]
