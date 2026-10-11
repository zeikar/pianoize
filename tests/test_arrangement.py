import re
from dataclasses import replace

import pytest

from pianoize.arrangement import (
    QUALITIES,
    ArrangementError,
    Bar,
    ScoreNote,
    chord_at,
    chord_pitch_classes,
    notes_of,
    parse,
    pitch,
)
from pianoize.bars import Meter

FOUR_FOUR = Meter(480, 4, 4)  # 120 ticks a sixteenth, 1920 a bar
THREE_FOUR = Meter(480, 3, 4)  # 1440 a bar


@pytest.fixture
def read(write_score):
    """Parses `format 1` and the lines given, read back from a file as the commands read it."""

    def parse_lines(*lines: str, sixteenths_per_bar: int = 16):
        return parse(write_score(*lines).read_text(encoding="utf-8"), sixteenths_per_bar)

    return parse_lines


def exactly(message: str) -> str:
    return f"^{re.escape(message)}$"


TWO_BARS = (
    "# a made-up score",
    "== intro | pedal=none",
    "bar 1 | 0:C 8:G/B",
    "  M 0:E5:4 4:D5~:2 6.5:C5:1.5",
    "R 0:G4+C5:8",
    "  # an indented comment",
    "  L 0:C3:16",
    "",
    "bar 2 | F#m | pedal=0,x8,12",  # a '#' inside a line is no comment
    "  M 0:A4:20",
    "  R 0:C#4+F#4:8",
    "  L 0:F#2+C#3:16",
)


def test_a_score_parses_into_bars(read):
    score = read(*TWO_BARS)
    assert score.sixteenths_per_bar == 16
    assert score.bars == [
        Bar(
            1,
            [(0.0, "C"), (8.0, "G/B")],
            "none",
            {"M": ["0:E5:4", "4:D5~:2", "6.5:C5:1.5"], "R": ["0:G4+C5:8"], "L": ["0:C3:16"]},
            "intro",
        ),
        Bar(
            2,
            [(0.0, "F#m")],
            "0,x8,12",
            {"M": ["0:A4:20"], "R": ["0:C#4+F#4:8"], "L": ["0:F#2+C#3:16"]},
            "intro",
        ),
    ]


def test_comments_and_blank_lines_may_come_before_the_format_line():
    score = parse("# a made-up score\n\n  format 1\nbar 1 | C\n", 16)
    assert [bar.number for bar in score.bars] == [1]


def test_notes_on_a_four_four_bar(read):
    notes = notes_of(read(*TWO_BARS), FOUR_FOUR)
    assert notes == [
        ScoreNote(0, 1920, 48, "LH", "L", False, 1),
        ScoreNote(0, 960, 67, "RH", "R", False, 1),
        ScoreNote(0, 960, 72, "RH", "R", False, 1),
        ScoreNote(0, 480, 76, "RH", "M", False, 1),
        ScoreNote(480, 720, 74, "RH", "M", True, 1),  # pos 4 dur 2, a passing tone
        ScoreNote(780, 960, 72, "RH", "M", False, 1),  # pos 6.5
        ScoreNote(1920, 3840, 42, "LH", "L", False, 2),
        ScoreNote(1920, 3840, 49, "LH", "L", False, 2),
        ScoreNote(1920, 2880, 61, "RH", "R", False, 2),
        ScoreNote(1920, 2880, 66, "RH", "R", False, 2),
        ScoreNote(1920, 4320, 69, "RH", "M", False, 2),  # past the last bar line
    ]


def test_a_duration_must_round_to_a_tick(read):
    # A sixteenth is 120 ticks: 0.01 rounds to one, 0.001 to none.
    one_tick = notes_of(read("bar 1 | C", "  M 0:C4:0.01"), FOUR_FOUR)
    assert [(note.on_tick, note.off_tick) for note in one_tick] == [(0, 1)]
    message = "bar 1: token '0:C4:0.001': the duration is under a tick"
    with pytest.raises(ArrangementError, match=exactly(message)):
        notes_of(read("bar 1 | C", "  M 0:C4:0.001"), FOUR_FOUR)


def test_the_meter_must_match_the_bar_the_score_was_read_with(read):
    score = read("bar 1 | C", "  M 0:C4:4")
    message = "the score was read with 16 sixteenths a bar; a 3/4 bar holds 12"
    with pytest.raises(ArrangementError, match=exactly(message)):
        notes_of(score, THREE_FOUR)
    with pytest.raises(ArrangementError, match=exactly(message)):
        chord_at(score, THREE_FOUR, 0)


def test_notes_on_a_three_four_bar(read):
    score = read("bar 1 | C", "  L 0:C3:12", "bar 2 | G", "  M 6:D5:6", sixteenths_per_bar=12)
    assert [(n.on_tick, n.off_tick, n.pitch, n.bar) for n in notes_of(score, THREE_FOUR)] == [
        (0, 1440, 48, 1),
        (2160, 2880, 74, 2),
    ]
    with pytest.raises(ArrangementError, match="position 12 is outside the bar"):
        read("bar 1 | C", "  M 12:C4:2", sixteenths_per_bar=12)


def test_pedal_defaults(read):
    score = read(
        "bar 1 | C",
        "== verse | pedal=none",
        "bar 2 | C",
        "== chorus",
        "bar 3 | C",
        "bar 4 | C | pedal=chord",
    )
    assert [(bar.section, bar.pedal) for bar in score.bars] == [
        ("", "chord"),  # chord to begin with
        ("verse", "none"),
        ("chorus", "none"),  # a section without a pedal keeps the one before
        ("chorus", "chord"),
    ]


@pytest.mark.parametrize(
    ("tick", "symbol"),
    [
        (0, "Dm"),
        (1919, "Dm"),
        (1920, "G7"),  # the first entry holds from the bar's start
        (1920 + 1499, "G7"),
        (1920 + 1500, "C/E"),  # at the chord's position, 12.5
        (3839, "C/E"),
        (3840, "C/E"),  # past the last bar: its last chord
        (100_000, "C/E"),
    ],
)
def test_chord_at(read, tick, symbol):
    score = read("bar 1 | Dm", "bar 2 | 4:G7 12.5:C/E")
    assert chord_at(score, FOUR_FOUR, tick) == symbol


QUALITY_CASES = {
    "C": {0, 4, 7},
    "Cm": {0, 3, 7},
    "C7": {0, 4, 7, 10},
    "CM7": {0, 4, 7, 11},
    "Cm7": {0, 3, 7, 10},
    "CmM7": {0, 3, 7, 11},
    "Cm6": {0, 3, 7, 9},
    "C6": {0, 4, 7, 9},
    "Cdim7": {0, 3, 6, 9},
    "Cm7b5": {0, 3, 6, 10},
    "Csus4": {0, 5, 7},
    "C7sus4": {0, 5, 7, 10},
    "Cadd9": {0, 2, 4, 7},
    "CM9": {0, 2, 4, 7, 11},
    "Caug": {0, 4, 8},
}


def test_every_quality_is_tested():
    assert {symbol.removeprefix("C") for symbol in QUALITY_CASES} == set(QUALITIES)


@pytest.mark.parametrize(
    ("symbol", "classes"),
    [
        *QUALITY_CASES.items(),
        ("C7(9,13)", {0, 4, 7, 10, 2, 9}),
        ("C7(b9,#11)", {0, 4, 7, 10, 1, 6}),
        ("Cm7(11)", {0, 3, 7, 10, 5}),
        ("C(b13)", {0, 4, 7, 8}),
        ("Bb7", {10, 2, 5, 8}),
        ("F#m", {6, 9, 1}),
        ("Cb", {11, 3, 6}),
        ("F/G", {5, 9, 0, 7}),
        ("Bbadd9/D", {10, 0, 2, 5}),
        ("Am7(9)/G", {9, 0, 4, 7, 11}),
    ],
)
def test_chord_pitch_classes(symbol, classes):
    assert chord_pitch_classes(symbol) == frozenset(classes)


def test_no_chord_has_no_pitch_classes():
    assert chord_pitch_classes("N.C.") is None


@pytest.mark.parametrize(
    "symbol", ["Hm7", "C(10)", "C()", "C(9,)", "C/H", "C/E/G", "c", "", "n.c."]
)
def test_bad_chord_symbols(symbol):
    with pytest.raises(ArrangementError, match=exactly(f"bad chord {symbol!r}")):
        chord_pitch_classes(symbol)


QUALITY_HINT = "(qualities: '', m, 7, M7, m7, mM7, m6, 6, dim7, m7b5, sus4, 7sus4, add9, M9, aug)"


@pytest.mark.parametrize("symbol", ["Cmaj7", "Bbmin/F", "Cm9(13)"])
def test_an_unknown_quality_lists_the_known_ones(symbol):
    with pytest.raises(ArrangementError, match=exactly(f"bad chord {symbol!r} {QUALITY_HINT}")):
        chord_pitch_classes(symbol)


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("C4", (60, False)),
        ("A0", (21, False)),
        ("F#5", (78, False)),
        ("Bb3~", (58, True)),
        ("Cb4", (59, False)),
        ("B#3", (60, False)),
        ("G9", (127, False)),
    ],
)
def test_note_names(name, expected):
    assert pitch(name) == expected


@pytest.mark.parametrize("name", ["H4", "c4", "C", "C10", "C-1", "G#9", "C4~~", "~C4", ""])
def test_bad_note_names(name):
    with pytest.raises(ArrangementError, match=exactly(f"bad note {name!r}")):
        pitch(name)


SOURCE = (
    "== verse | pedal=none",
    "bar 1 | 0:C 8:G",
    "  M 0:E5:4",
    "  L 0:C3:16",
    "bar 2 | F | pedal=0,x8",
    "  M 4:A5~:2",
    "  R 0:A4+C5:8",
    "  L 0:F2:16",
)
OVERRIDE = ("bar 4 | Dm7", "  M 0:D5:16")


def test_a_copy_repeats_bars_with_their_ticks_shifted(read):
    score = read(*SOURCE, "== chorus | pedal=chord", "bars 3-4 = 1-2")
    # Chords, pedal and lines come from the source; the section is where the copy is written.
    assert score.bars[2:] == [
        replace(bar, number=bar.number + 2, section="chorus") for bar in score.bars[:2]
    ]
    notes = notes_of(score, FOUR_FOUR)
    shift = 2 * FOUR_FOUR.bar_ticks
    assert [note for note in notes if note.bar > 2] == [
        replace(
            note, on_tick=note.on_tick + shift, off_tick=note.off_tick + shift, bar=note.bar + 2
        )
        for note in notes
        if note.bar <= 2
    ]


def test_an_override_replaces_a_copied_bar_whole(read):
    score = read(*SOURCE, "bars 3-4 = 1-2", *OVERRIDE)
    assert score.bars[2] == replace(score.bars[0], number=3)
    # Bar 4's pedal is bar 2's, as copied, not the section's none.
    assert score.bars[3] == Bar(4, [(0.0, "Dm7")], "0,x8", {"M": ["0:D5:16"]}, "verse")


def test_an_override_keeps_the_section_and_pedal_of_the_bar_it_replaces(read):
    score = read(
        *SOURCE,
        "== chorus | pedal=chord",
        "bars 3-4 = 1-2",
        "== outro | pedal=none",
        "bar 5 | C",
        *OVERRIDE,
        "bar 3 | Em | pedal=0,8",
    )
    assert [(bar.section, bar.pedal) for bar in score.bars] == [
        ("verse", "none"),
        ("verse", "0,x8"),
        ("chorus", "0,8"),  # a pedal written on the override wins
        ("chorus", "0,x8"),  # not the outro's, where the override is written
        ("outro", "none"),
    ]


def test_a_copy_owns_its_chords_and_lines(read):
    score = read(*SOURCE, "bars 3-4 = 1-2")
    score.bars[0].chords.append((12.0, "Am"))
    score.bars[0].lines["M"].append("12:C5:4")
    assert score.bars[2].chords == [(0.0, "C"), (8.0, "G")]
    assert score.bars[2].lines["M"] == ["0:E5:4"]


def test_a_copied_range_can_be_copied_again(read):
    score = read(*SOURCE, "bars 3-4 = 1-2", "bars 5-6 = 3-4")
    assert score.bars[4:] == [replace(bar, number=bar.number + 4) for bar in score.bars[:2]]


def test_an_override_can_be_copied(read):
    score = read(*SOURCE, "bars 3-4 = 1-2", *OVERRIDE, "bars 5-6 = 3-4")
    assert score.bars[5] == replace(score.bars[3], number=6)
    assert score.bars[5].chords == [(0.0, "Dm7")]


def test_overriding_a_source_leaves_the_copies_already_taken(read):
    score = read(*SOURCE, "bars 3-4 = 1-2", "bars 5-6 = 3-4", *OVERRIDE)
    assert score.bars[3].chords == [(0.0, "Dm7")]
    assert score.bars[5] == replace(score.bars[1], number=6)


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("bar 1 | C\n", "line 1: expected 'format 1', found 'bar 1 | C'"),
        ("# a comment\n\nbar 1 | C\n", "line 3: expected 'format 1', found 'bar 1 | C'"),
        ("format 2\nbar 1 | C\n", "line 1: expected 'format 1', found 'format 2'"),
        ("# only a comment\n", "expected 'format 1', found an empty score"),
        ("format 1\n== intro\n", "the score has no bars"),
    ],
)
def test_a_score_needs_its_format_line_and_a_bar(text, message):
    with pytest.raises(ArrangementError, match=exactly(message)):
        parse(text, 16)


@pytest.mark.parametrize(
    ("lines", "message"),
    [
        (["bar 2 | C"], "bar 2: expected bar 1"),
        (["bar 1 | C", "bar 3 | C"], "bar 3: expected bar 2"),
        (["bar 1 | C", "bar 1 | C"], "line 3: bar 1 is defined twice"),
        (["bar one | C"], "line 2: expected 'bar N | chords', found 'bar one | C'"),
        (["bar 1"], "bar 1: no chords"),
        (["bar 1 |"], "bar 1: no chords"),
        # copies
        (
            ["bar 1 | C", "bar 2 | C", "bars 3-4 = 2-3"],
            "bars 3-4: source 2-3 is not defined before bar 3",
        ),
        (["bar 1 | C", "bars 2-2 = 0-0"], "bars 2-2: source 0-0 is not defined before bar 2"),
        (
            ["bar 1 | C", "bar 2 | C", "bars 3-5 = 1-2"],
            "bars 3-5: source 1-2 has a different length",
        ),
        (["bar 1 | C", "bars 2-1 = 1-0"], "bars 2-1: the range runs backwards"),
        (["bar 1 | C", "bars 3-3 = 1-1"], "bars 3-3: expected bar 2"),
        (["bar 1 | C", "bars 1-1 = 1-1"], "line 3: bar 1 is defined twice"),
        (["bar 1 | C", "bars 2 = 1"], "line 3: expected 'bars A-B = C-D', found 'bars 2 = 1'"),
        # overrides
        (
            ["bar 1 | C", "bar 2 | C", "bars 3-4 = 1-2", "bar 2 | Dm"],
            "line 5: bar 2 is defined twice",
        ),
        (
            ["bar 1 | C", "bars 2-2 = 1-1", "bar 2 | D", "bar 2 | E"],
            "line 5: bar 2 is defined twice",
        ),
        # settings
        (["== verse | pedl=none"], "line 2: unknown setting 'pedl'"),
        (["bar 1 | C | pedl=none"], "bar 1: unknown setting 'pedl'"),
        (["bar 1 | C | pedal=sometimes"], "bar 1: pedal 'sometimes': bad position 'sometimes'"),
        (["bar 1 | C | pedal=0,x16"], "bar 1: pedal '0,x16': position 16 is outside the bar"),
        (
            ["bar 1 | C | pedal=0,x8,4"],
            "bar 1: pedal '0,x8,4': positions 8 and 4 are not ascending",
        ),
        (["bar 1 | C | pedal=x4,4"], "bar 1: pedal 'x4,4': positions 4 and 4 are not ascending"),
        (["bar 1 | C | pedal=none | pedal=chord"], "bar 1: setting 'pedal' given twice"),
        (["== verse | pedal=none | pedal=chord"], "line 2: setting 'pedal' given twice"),
        # role lines
        (["M 0:C4:4"], "line 2: M line outside a bar"),
        (["bar 1 | C", "bars 2-2 = 1-1", "L 0:C3:4"], "line 4: L line outside a bar"),
        (["bar 1 | C", "== verse", "R 0:C4:4"], "line 4: R line outside a bar"),
        (["bar 1 | C", "M 0:C4:4", "  M 4:D4:4"], "bar 1: a second M line"),
        (["X 0:C4:4"], "line 2: unexpected line 'X 0:C4:4'"),
        (["bar 1 | C", "X 0:C4:4"], "bar 1: unexpected line 'X 0:C4:4'"),
        # tokens
        (["bar 1 | C", "M 0:C4"], "bar 1: token '0:C4': expected pos:notes:dur"),
        (["bar 1 | C", "M 0:C4:4:1"], "bar 1: token '0:C4:4:1': expected pos:notes:dur"),
        (["bar 1 | C", "M 4:H4:2"], "bar 1: token '4:H4:2': bad note 'H4'"),
        (["bar 1 | C", "M 4:C4+:2"], "bar 1: token '4:C4+:2': bad note ''"),
        (["bar 1 | C", "M 16:C4:2"], "bar 1: token '16:C4:2': position 16 is outside the bar"),
        (["bar 1 | C", "M -1:C4:2"], "bar 1: token '-1:C4:2': bad position '-1'"),
        (["bar 1 | C", "M nan:C4:2"], "bar 1: token 'nan:C4:2': bad position 'nan'"),
        (["bar 1 | C", "M 0:C4:0"], "bar 1: token '0:C4:0': the duration is zero"),
        (["bar 1 | C", "M 0:C4:0.0"], "bar 1: token '0:C4:0.0': the duration is zero"),
        (["bar 1 | C", "M 0:C4:inf"], "bar 1: token '0:C4:inf': bad duration 'inf'"),
        # chords
        (["bar 1 | Hm7"], "bar 1: bad chord 'Hm7'"),
        (["bar 1 | 0:C 8:Cmaj7"], f"bar 1: bad chord 'Cmaj7' {QUALITY_HINT}"),
        (["bar 1 | 0:C 16:G"], "bar 1: chord '16:G': position 16 is outside the bar"),
        (["bar 1 | 0:C 8:G 4:F"], "bar 1: chord positions 8 and 4 are not ascending"),
        (["bar 1 | 0:C 0:G"], "bar 1: chord positions 0 and 0 are not ascending"),
        (["bar 1 | C 8:G"], "bar 1: chord 'C': several chords need a position each"),
    ],
)
def test_errors_name_the_bar_and_the_token(read, lines, message):
    with pytest.raises(ArrangementError, match=exactly(message)):
        read(*lines)
