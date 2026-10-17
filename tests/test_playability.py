import mido
import pytest
from typer.testing import CliRunner

from pianoize.arrangement import ArrangementError, parse
from pianoize.bars import Meter, meter
from pianoize.cli import app
from pianoize.notes import tempo_map
from pianoize.playability import check, missing, missing_report, report

# At 480 ticks a beat: 120 a sixteenth, 1920 a 4/4 bar, 120 bpm unless a test sets the tempos.
METER = Meter(480, 4, 4)

# 150 bpm in bar 1, a sixteenth 100 ms; 30 bpm from bar 2, a sixteenth 500 ms.
JUMP_TEMPOS = [(0, 150), (1920, 30)]


@pytest.fixture
def checked(tick_midi, write_score):
    """The findings for a score of `format 1` and the lines given, on an eight-bar 4/4 cover
    with the tempos given."""

    def run(*lines, tempos=None, full=False):
        cover = tick_midi([(0, 1920 * 8, 60, 80)], tempos=tempos)
        found = meter(cover)
        assert found == METER
        text = write_score(*lines).read_text(encoding="utf-8")
        return check(parse(text, found.sixteenths_per_bar), found, tempo_map(cover), full=full)

    return run


def summary(findings):
    return sorted((f.rule, f.tick, f.hand, f.flagged) for f in findings)


def test_eight_notes_held_in_one_hand_are_flagged(checked):
    # C5, struck at 0, is still held when the seven come at 4.
    findings = checked("bar 1 | N.C.", "  M 0:C5:8", "  R 4:C4+D4+E4+F4+G4+A4+B4:4")
    assert summary(findings) == [("notes", 480, "RH", True)]
    assert findings[0].detail == "8 held: C4 D4 E4 F4 G4 A4 B4 C5"


def test_seven_notes_held_in_one_hand_are_clean(checked):
    # C5 is released at the tick the seven are struck, and the left hand counts on its own.
    assert checked("bar 1 | N.C.", "  M 0:C5:4", "  R 4:C4+D4+E4+F4+G4+A4+B4:4", "  L 4:C3:4") == []


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
        ("0:C3+G#4:4", [("span", 0, "LH", True)]),  # 20 semitones
        ("0:C3:8 4:G#4:4", [("span", 480, "LH", True)]),  # 20, with C3 still held
        ("0:C3+G#4~:4", [("span", 0, "LH", True)]),  # a passing tone is still a key
        ("0:C3+G4:4", [("span", 0, "LH", False)]),  # 19: listed, not flagged
        ("0:C3+F4:4", [("span", 0, "LH", False)]),  # 17
        ("0:C3+E4:4", []),  # 16
    ],
)
def test_a_span_over_nineteen_is_flagged_and_over_sixteen_listed(checked, left, found):
    assert summary(checked("bar 1 | N.C.", f"  L {left}")) == found


def test_a_listed_span_alone_prints_its_line_then_clean(checked):
    assert report(checked("bar 1 | N.C.", "  L 0:C3+F4:4"), METER) == (
        "span: 1 (0 flagged)\n"
        "  bar 1 pos 0  LH  span  17 semitones, C3 to F4 (listed, not flagged)\n"
        "clean"
    )


@pytest.mark.parametrize(
    ("lines", "found"),
    [
        # 19 semitones a sixteenth apart at 150 bpm: 100 ms.
        (("bar 1 | N.C.", "  L 0:C2:1 1:G3:1"), [("jump", 120, "LH", True)]),
        # The centre of a chord: C2+C3 to G3 is 13 semitones.
        (("bar 1 | N.C.", "  L 0:C2+C3:1 1:G3:1"), []),
        # 19 semitones, 60 ticks either side of the change: 50 ms and 250 ms.
        (("bar 1 | N.C.", "  L 15.5:C2:0.5", "bar 2 | N.C.", "  L 0.5:G3:1"), []),
        # 27 semitones, 120 ticks before the change and 48 after: 100 ms and 200 ms.
        (
            ("bar 1 | N.C.", "  L 15:C2:1", "bar 2 | N.C.", "  L 0.4:D#4:1"),
            [("jump", 1968, "LH", True)],
        ),
        # 37 semitones two sixteenths apart at 30 bpm: 1 s.
        (("bar 1 | N.C.", "bar 2 | N.C.", "  L 0:C2:2 2:C#5:2"), [("jump", 2160, "LH", True)]),
        # 36, the same 1 s apart.
        (("bar 1 | N.C.", "bar 2 | N.C.", "  L 0:C2:2 2:C5:2"), []),
    ],
)
def test_a_jump_is_timed_through_the_tempo_map(checked, lines, found):
    assert summary(checked(*lines, tempos=JUMP_TEMPOS)) == found


def test_a_jump_exactly_at_its_time_limit_is_clean(checked):
    # 26 semitones three sixteenths apart at 125 bpm: 360 ms exactly.
    assert checked("bar 1 | N.C.", "  L 0:C2:3 3:D4:3", tempos=[(0, 125)]) == []


def test_a_jump_names_its_shift_and_gap(checked):
    [finding] = checked("bar 1 | N.C.", "  L 0:C2:1 1:G3:1", tempos=JUMP_TEMPOS)
    assert finding.detail == "19 semitones in 100 ms"


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


def test_a_right_hand_note_struck_above_a_held_melody_note_is_flagged(checked):
    findings = checked("bar 1 | C", "  M 0:C5:16", "  R 4:G5:4")
    assert summary(findings) == [("melody", 480, "RH", True)]
    assert findings[0].detail == "C5 under G5"


@pytest.mark.parametrize(
    ("melody", "found"),
    [
        ("M 0:C5:16 4:E5:8", [("melody", 480, "RH", True)]),  # overlap
        ("M 0:C5:4 4:E5:8", []),  # released where the next begins
    ],
)
def test_melody_notes_do_not_overlap(checked, melody, found):
    assert summary(checked("bar 1 | C", f"  {melody}")) == found


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
        "  L 0:C3+G4:16",
        "bar 2 | C",
        "  M 4.5:E5:2",
        "  R 4.5:G5:2",
        "  L 0:F3:16",
    )
    assert report(findings, METER) == "\n".join(
        [
            "span: 1 (0 flagged)",
            "  bar 1 pos 0  LH  span  19 semitones, C3 to G4 (listed, not flagged)",
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


def test_a_score_without_notes_raises(checked):
    with pytest.raises(ArrangementError, match="the score has no notes"):
        checked("bar 1 | C")


# Eight keys in the right hand over two octaves, and a left hand leaping three octaves in a
# sixteenth to cross it: every limit on the hands, and no chord to check.
UNPLAYABLE = ("bar 1 | N.C.", "  M 0:C6:4", "  R 0:C4+D4+E4+F4+G4+A4+B4:4", "  L 0:C2:1 1:C5:1")


def test_a_full_arrangement_drops_the_limits_on_the_hands(checked):
    rules = {finding.rule for finding in checked(*UNPLAYABLE) if finding.flagged}
    assert rules == {"notes", "span", "jump", "crossing"}
    assert checked(*UNPLAYABLE, full=True) == []


@pytest.mark.parametrize(
    ("lines", "found", "detail"),
    [
        # With no crossing rule, the left hand is held under the tune by the melody rule.
        (("bar 1 | C", "  M 0:E4:4", "  L 0:C4+G4:4"), ("melody", 0, "RH", True), "E4 under G4"),
        (("bar 1 | C", "  R 0:C4:4", "  L 0:C4:4"), ("notes", 0, "LH", True), "C4 in both hands"),
        # The right hand still holds C4 when the left strikes it.
        (("bar 1 | C", "  R 0:C4:8", "  L 4:C4:4"), ("notes", 480, "LH", True), "C4 in both hands"),
    ],
)
def test_a_full_arrangement_keeps_the_tune_on_top_and_a_key_in_one_hand(
    checked, lines, found, detail
):
    findings = checked(*lines, full=True)
    assert summary(findings) == [found]
    assert findings[0].detail == detail


@pytest.mark.parametrize(
    "lines",
    [
        ("bar 1 | C", "  M 0:C5:4", "  R 0:E4+G4+C5:4"),  # C5 struck twice
        ("bar 1 | C", "  M 0:E5:4", "  R 0:G5:4"),  # the melody under G5
        ("bar 1 | C", "  L 0:F3:4"),  # F3 off the chord
    ],
)
def test_a_full_arrangement_still_checks_a_double_strike_the_melody_and_the_harmony(checked, lines):
    findings = checked(*lines, full=True)
    assert findings
    assert summary(findings) == summary(checked(*lines))


@pytest.fixture
def missed(tick_midi, write_score):
    """The report of the vocal notes, (on_tick, off_tick, pitch) at 480 ticks a beat and 120 bpm,
    that a score of `format 1` and the lines given leaves out, on an eight-bar 4/4 cover with the
    tempos given."""

    def run(sung, *lines, tempos=None):
        cover = tick_midi([(0, 1920 * 8, 60, 80)], tempos=tempos)
        score = parse(write_score(*lines).read_text(encoding="utf-8"), METER.sixteenths_per_bar)
        melody = tick_midi([(on, off, pitch, 100) for on, off, pitch in sung])
        segments = tempo_map(cover)
        return missing_report(missing(score, METER, segments, melody), METER, segments)

    return run


def test_a_score_playing_every_vocal_note_lists_none(missed):
    sung = [(0, 480, 76), (480, 960, 79), (960, 1440, 72)]
    # An R note on top of the right hand plays a vocal note as well as an M note does.
    report = missed(sung, "bar 1 | C", "  M 0:E5:4 4:G5:4", "  R 8:C5:4")
    assert report == "melody missing: 0"


def test_a_vocal_note_left_out_is_listed_with_its_bar_and_position(missed):
    # The left hand's E3 at the vocal note's onset doesn't play it: only the right hand does.
    lines = ("bar 1 | C", "  M 0:E5:4", "  L 0:C3:16", "bar 2 | C", "  L 4.5:E3:2")
    assert missed([(0, 480, 76), (2460, 2700, 76)], *lines) == (
        "bar 2 pos 4.5  melody missing  E5 (2)\nmelody missing: 1"
    )


def test_vocal_notes_under_80_ms_are_not_listed(missed):
    sung = [
        (0, 72, 76),  # 75 ms
        (480, 600, 79),  # 125 ms
        (960, 1440, 72),  # cut to 50 ms by the next onset, as melody.monophonic cuts it
        (1008, 1440, 74),
        (1440, 1522, 77),  # 85 ms
    ]
    assert missed(sung, "bar 1 | C", "  L 0:C3:16") == (
        "bar 1 pos 4  melody missing  G5 (1)\n"
        "bar 1 pos 8.5  melody missing  D5 (3.5)\n"
        "bar 1 pos 12  melody missing  F5 (0.5)\n"
        "melody missing: 3"
    )


@pytest.mark.parametrize(
    ("right", "count"),
    [
        ("4:E5:2", 0),  # an octave up, as the cover plays the melody
        ("4:E6:2", 0),
        ("4.5:E5:2", 0),  # 62.5 ms late
        ("3.5:E5:2", 0),  # 62.5 ms early
        ("4.6:E5:2", 1),  # 75 ms late
        ("3.4:E5:2", 1),  # 75 ms early
        ("4:F5:2", 1),
    ],
)
def test_a_right_hand_note_of_its_pitch_class_within_70_ms_plays_a_vocal_note(missed, right, count):
    report = missed([(480, 720, 64)], "bar 1 | C", f"  M {right}")
    assert report.splitlines()[-1] == f"melody missing: {count}"


@pytest.mark.parametrize(
    "right",
    [
        ("  M 4:G5:2", "  R 4:E5:2"),  # an inner voice, struck under the top
        ("  M 0:G5:8", "  R 4:E5:2"),  # an inner voice, under a top held from an earlier attack
        ("  M 0:E5:8", "  R 4:C5:2"),  # a top of its pitch class, struck 500 ms before it
    ],
)
def test_only_a_top_right_hand_note_struck_near_a_vocal_note_plays_it(missed, right):
    assert missed([(480, 720, 64)], "bar 1 | C", *right) == (
        "bar 1 pos 4  melody missing  E4 (2)\nmelody missing: 1"
    )


def test_the_vocal_lands_by_seconds_on_the_covers_tempo_map(missed):
    # The cover takes 2 s for bar 1 at 120 bpm, then 4 s a bar at 60 bpm. The vocal note sounds
    # from 3 s to 3.5 s: bar 2 pos 4, two of the cover's sixteenths, where its own ticks would
    # say bar 2 pos 8.
    sung = [(2880, 3360, 76)]
    tempos = [(1920, 60)]
    assert missed(sung, "bar 1 | C", "  L 0:C3:16", tempos=tempos) == (
        "bar 2 pos 4  melody missing  E5 (2)\nmelody missing: 1"
    )
    played = ("bar 1 | C", "  L 0:C3:16", "bar 2 | C", "  M 4:E5:4")
    assert missed(sung, *played, tempos=tempos) == "melody missing: 0"


def _cover_file(tmp_path, tick_midi, meta=None, ticks_per_beat=480):
    path = tmp_path / "cover.mid"
    notes = [(0, ticks_per_beat * 32, 60, 80)]  # eight 4/4 bars
    tick_midi(notes, meta=meta, ticks_per_beat=ticks_per_beat).save(path)
    return path


def _check_cli(score, cover, *options):
    arguments = ["check-arrangement", str(score), "--cover", str(cover), *options]
    return CliRunner().invoke(app, arguments)


@pytest.mark.parametrize(
    ("lines", "code", "printed"),
    [
        (
            ("bar 1 | 0:C 8:F", "  L 0:F3:8 8:E3:8"),
            1,
            "harmony: 2 (2 flagged)\n"
            "  bar 1 pos 0  LH  harmony  L F3 over C\n"
            "  bar 1 pos 8  LH  harmony  L E3 over F\n"
            "problems: 2\n",
        ),
        (
            ("bar 1 | N.C.", "  L 0:C3+F4:4"),
            0,
            "span: 1 (0 flagged)\n"
            "  bar 1 pos 0  LH  span  17 semitones, C3 to F4 (listed, not flagged)\n"
            "clean\n",
        ),
        (("bar 1 | C", "  M 0:E5:4 4:G5:4", "  R 0:G4+C5:8", "  L 0:C3:8 8:G2:8"), 0, "clean\n"),
    ],
)
def test_cli_prints_the_report_and_exits_1_on_a_flagged_finding(
    tmp_path, tick_midi, write_score, lines, code, printed
):
    result = _check_cli(write_score(*lines), _cover_file(tmp_path, tick_midi))
    assert result.exit_code == code, result.output
    assert result.stdout == printed


def test_cli_checks_a_full_arrangement_with_full(tmp_path, tick_midi, write_score):
    score, cover = write_score(*UNPLAYABLE), _cover_file(tmp_path, tick_midi)
    assert _check_cli(score, cover).exit_code == 1
    result = _check_cli(score, cover, "--full")
    assert result.exit_code == 0, result.output
    assert result.stdout == "clean\n"


@pytest.mark.parametrize(
    ("lines", "ticks_per_beat", "message"),
    [
        (("bar 1 | C",), 480, "the score has no notes"),
        # A sixteenth is one tick at 4 ticks a beat: a quarter of one rounds to none.
        (
            ("bar 1 | C", "  L 0:C3:0.25"),
            4,
            "bar 1: token '0:C3:0.25': the duration is under a tick",
        ),
    ],
)
def test_cli_reports_a_score_the_check_cannot_read(
    tmp_path, tick_midi, write_score, lines, ticks_per_beat, message
):
    score = write_score(*lines)
    result = _check_cli(score, _cover_file(tmp_path, tick_midi, ticks_per_beat=ticks_per_beat))
    assert result.exit_code == 1
    assert f"error: {score}: {message}" in result.output
    assert "Traceback" not in result.output


def test_cli_refuses_a_cover_that_changes_meter(tmp_path, tick_midi, write_score):
    three_four = mido.MetaMessage("time_signature", numerator=3, denominator=4)
    cover = _cover_file(tmp_path, tick_midi, meta=[(1920, three_four)])
    result = _check_cli(write_score("bar 1 | C", "  L 0:C3:4"), cover)
    assert result.exit_code == 1
    assert f"error: {cover}: the cover changes meter at tick 1920, 4/4 to 3/4" in result.output
    assert "Traceback" not in result.output


@pytest.mark.parametrize(
    ("lines", "code", "printed"),
    [
        (
            ("bar 1 | C", "  M 0:E5:4", "bar 2 | C", "  L 0:C3:16"),
            0,
            "clean\nbar 2 pos 4.5  melody missing  E5 (2)\nmelody missing: 1\n",
        ),
        (
            ("bar 1 | C", "  M 0:E5:4", "  L 0:F3:4"),
            1,
            "harmony: 1 (1 flagged)\n"
            "  bar 1 pos 0  LH  harmony  L F3 over C\n"
            "problems: 1\n"
            "bar 2 pos 4.5  melody missing  E5 (2)\n"
            "melody missing: 1\n",
        ),
        (("bar 1 | C", "  M 0:E5:4", "bar 2 | C", "  M 4.5:E5:2"), 0, "clean\nmelody missing: 0\n"),
    ],
)
def test_cli_lists_the_vocal_notes_left_out_after_the_report_and_keeps_its_exit_code(
    tmp_path, tick_midi, write_score, lines, code, printed
):
    melody = tmp_path / "melody.mid"
    tick_midi([(0, 480, 76, 100), (2460, 2700, 76, 100)]).save(melody)
    cover = _cover_file(tmp_path, tick_midi)
    result = _check_cli(write_score(*lines), cover, "--melody", str(melody))
    assert result.exit_code == code, result.output
    assert result.stdout == printed


def test_cli_refuses_a_type_2_melody(tmp_path, tick_midi, write_score):
    melody = tmp_path / "melody.mid"
    midi = tick_midi([(0, 480, 76, 100)])
    midi.type = 2
    midi.save(melody)
    cover = _cover_file(tmp_path, tick_midi)
    result = _check_cli(write_score("bar 1 | C", "  M 0:E5:4"), cover, "--melody", str(melody))
    assert result.exit_code == 1
    assert f"error: {melody}: a type 2 MIDI file's tracks share no timeline" in result.output
    assert "Traceback" not in result.output
