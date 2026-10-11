import pytest

from pianoize.arrangement import parse
from pianoize.bars import Meter, meter
from pianoize.notes import tempo_map
from pianoize.playability import check, report

# At 480 ticks a beat: 120 a sixteenth, 1920 a 4/4 bar, 120 bpm unless a test sets the tempos.
METER = Meter(480, 4, 4)

# 150 bpm in bar 1, a sixteenth 100 ms; 30 bpm from bar 2, a sixteenth 500 ms.
JUMP_TEMPOS = [(0, 150), (1920, 30)]


@pytest.fixture
def checked(tick_midi, write_score):
    """The findings for a score of `format 1` and the lines given, on an eight-bar 4/4 cover
    with the tempos given."""

    def run(*lines, tempos=None):
        cover = tick_midi([(0, 1920 * 8, 60, 80)], tempos=tempos)
        found = meter(cover)
        assert found == METER
        text = write_score(*lines).read_text(encoding="utf-8")
        return check(parse(text, found.sixteenths_per_bar), found, tempo_map(cover))

    return run


def summary(findings):
    return sorted((f.rule, f.tick, f.hand, f.flagged) for f in findings)


def test_six_notes_held_in_one_hand_are_flagged(checked):
    # A4, struck at 0, is still held when the five come at 4.
    findings = checked("bar 1 | N.C.", "  M 0:A4:8", "  R 4:C4+D4+E4+F4+G4:4")
    assert summary(findings) == [("notes", 480, "RH", True)]
    assert findings[0].detail == "6 held: C4 D4 E4 F4 G4 A4"


def test_five_notes_held_in_one_hand_are_clean(checked):
    # A4 is released at the tick the five are struck, and the left hand counts on its own.
    assert checked("bar 1 | N.C.", "  M 0:A4:4", "  R 4:C4+D4+E4+F4+G4:4", "  L 4:C3:4") == []


def test_a_pitch_struck_twice_in_one_hand_at_one_tick_is_flagged(checked):
    findings = checked("bar 1 | C", "  M 0:C5:4", "  R 0:E4+G4+C5:4")
    assert summary(findings) == [("notes", 0, "RH", True)]
    assert findings[0].detail == "C5 struck twice"


def test_a_restrike_in_one_hand_is_clean(checked):
    assert checked("bar 1 | C", "  M 0:C5:8", "  R 4:E4+C5:4") == []


def test_the_check_sees_a_restruck_note_cut_as_the_build_cuts_it(checked):
    # Written to sound until 8, the first G5 is cut at the restrike at 2, so E5 is on top at 6.
    assert checked("bar 1 | C", "  R 0:G5:8 2:G5:2", "  M 6:E5:2") == []


@pytest.mark.parametrize(
    ("left", "found"),
    [
        ("0:C3+F4:4", [("span", 0, "LH", True)]),  # 17 semitones
        ("0:C3:8 4:F4:4", [("span", 480, "LH", True)]),  # 17, with C3 still held
        ("0:C3+F4~:4", [("span", 0, "LH", True)]),  # a passing tone is still a key
        ("0:C3+E4:4", [("span", 0, "LH", False)]),  # 16: listed, not flagged
        ("0:C3+D#4:4", [("span", 0, "LH", False)]),  # 15
        ("0:C3+D4:4", []),  # 14
    ],
)
def test_a_span_over_sixteen_is_flagged_and_over_fourteen_listed(checked, left, found):
    assert summary(checked("bar 1 | N.C.", f"  L {left}")) == found


def test_a_listed_span_alone_prints_its_line_then_clean(checked):
    assert report(checked("bar 1 | N.C.", "  L 0:C3+D#4:4"), METER) == (
        "span: 1 (0 flagged)\n"
        "  bar 1 pos 0  LH  span  15 semitones, C3 to D#4 (listed, not flagged)\n"
        "clean"
    )


@pytest.mark.parametrize(
    ("lines", "found"),
    [
        # 15 semitones a sixteenth apart at 150 bpm: 100 ms.
        (("bar 1 | N.C.", "  L 0:C2:1 1:D#3:1"), [("jump", 120, "LH", True)]),
        # The centre of a chord: C2+C3 to D#3 is 9 semitones.
        (("bar 1 | N.C.", "  L 0:C2+C3:1 1:D#3:1"), []),
        # 15 semitones, 60 ticks either side of the change: 50 ms and 250 ms.
        (("bar 1 | N.C.", "  L 15.5:C2:0.5", "bar 2 | N.C.", "  L 0.5:D#3:1"), []),
        # 23 semitones, 120 ticks before the change and 48 after: 100 ms and 200 ms.
        (
            ("bar 1 | N.C.", "  L 15:C2:1", "bar 2 | N.C.", "  L 0.4:B3:1"),
            [("jump", 1968, "LH", True)],
        ),
        # 27 semitones two sixteenths apart at 30 bpm: 1 s.
        (("bar 1 | N.C.", "bar 2 | N.C.", "  L 0:C2:2 2:D#4:2"), [("jump", 2160, "LH", True)]),
        # 26, the same 1 s apart.
        (("bar 1 | N.C.", "bar 2 | N.C.", "  L 0:C2:2 2:D4:2"), []),
    ],
)
def test_a_jump_is_timed_through_the_tempo_map(checked, lines, found):
    assert summary(checked(*lines, tempos=JUMP_TEMPOS)) == found


def test_a_jump_exactly_at_its_time_limit_is_clean(checked):
    # 22 semitones three sixteenths apart at 125 bpm: 360 ms exactly.
    assert checked("bar 1 | N.C.", "  L 0:C2:3 3:A#3:3", tempos=[(0, 125)]) == []


def test_a_jump_names_its_shift_and_gap(checked):
    [finding] = checked("bar 1 | N.C.", "  L 0:C2:1 1:D#3:1", tempos=JUMP_TEMPOS)
    assert finding.detail == "15 semitones in 100 ms"


@pytest.mark.parametrize(
    ("lines", "found"),
    [
        (("  R 0:C4+G4:8", "  L 4:C4:4"), [("crossing", 480, "LH", True)]),  # at a LH attack
        (("  R 0:C4+G4:8", "  L 4:G3:4"), []),
        (("  L 0:C4:8", "  R 4:C4+G4:4"), [("crossing", 480, "LH", True)]),  # at a RH attack
    ],
)
def test_the_left_hand_at_the_right_hands_bottom_is_crossed(checked, lines, found):
    # The other hand's note is held from an earlier attack.
    findings = checked("bar 1 | C", *lines)
    assert summary(findings) == found
    if found:
        assert findings[0].detail == "top C4 at or above RH bottom C4"


@pytest.mark.parametrize(
    ("right", "found"),
    [
        ("4:G4:4", [("melody", 480, "RH", True)]),  # struck with it
        ("0:G4:8", [("melody", 480, "RH", True)]),  # held from an earlier attack
        ("0:G4:4", []),  # released at the melody's onset
        ("4:C4:4", []),
    ],
)
def test_the_melody_is_the_top_right_hand_note(checked, right, found):
    findings = checked("bar 1 | C", "  M 4:E4:4", f"  R {right}")
    assert summary(findings) == found
    if found:
        assert findings[0].detail == "E4 under G4"


def test_an_accompaniment_note_outside_the_chord_is_flagged(checked):
    # The melody's F5 is free to leave the chord.
    findings = checked("bar 1 | C", "  M 0:F5:4", "  R 0:F4:4", "  L 0:F3:4")
    assert summary(findings) == [("harmony", 0, "LH", True), ("harmony", 0, "RH", True)]
    assert sorted(f.detail for f in findings) == ["L F3 over C", "R F4 over C"]


@pytest.mark.parametrize(
    "lines",
    [
        ("bar 1 | C", "  L 0:F3~:4"),  # marked passing
        ("bar 1 | N.C.", "  L 0:F3:4"),
        ("bar 1 | C(11)", "  L 0:F3:4"),  # a tension
        ("bar 1 | C/F", "  L 0:F3:4"),  # the slash bass
    ],
)
def test_an_accompaniment_note_off_the_triad_can_pass(checked, lines):
    assert checked(*lines) == []


def test_each_note_is_checked_against_its_own_chord(checked):
    assert checked("bar 1 | 0:C 8:F", "  L 0:E3:8 8:F3:8") == []
    findings = checked("bar 1 | 0:C 8:F", "  L 0:F3:8 8:E3:8")
    assert summary(findings) == [("harmony", 0, "LH", True), ("harmony", 960, "LH", True)]


def test_the_report_groups_by_rule_and_names_bar_position_and_hand(checked):
    findings = checked(
        "bar 1 | Cm",
        "  L 0:C3+D#4:16",
        "bar 2 | C",
        "  M 4.5:E5:2",
        "  R 4.5:G5:2",
        "  L 0:F3:16",
    )
    assert report(findings, METER) == "\n".join(
        [
            "span: 1 (0 flagged)",
            "  bar 1 pos 0  LH  span  15 semitones, C3 to D#4 (listed, not flagged)",
            "melody: 1 (1 flagged)",
            "  bar 2 pos 4.5  RH  melody  E5 under G5",
            "harmony: 1 (1 flagged)",
            "  bar 2 pos 0  LH  harmony  L F3 over C",
            "problems: 2",
        ]
    )


def test_the_report_counts_each_rules_lines(checked):
    findings = checked("bar 1 | 0:C 8:F", "  L 0:F3:8 8:E3:8")
    assert report(findings, METER).splitlines() == [
        "harmony: 2 (2 flagged)",
        "  bar 1 pos 0  LH  harmony  L F3 over C",
        "  bar 1 pos 8  LH  harmony  L E3 over F",
        "problems: 2",
    ]


def test_a_passing_score_reports_clean(checked):
    findings = checked("bar 1 | C", "  M 0:E5:4 4:G5:4", "  R 0:G4+C5:8", "  L 0:C3:8 8:G2:8")
    assert findings == []
    assert report(findings, METER) == "clean"
