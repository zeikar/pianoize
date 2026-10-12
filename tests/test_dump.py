import mido
import pytest
from typer.testing import CliRunner

from pianoize.bars import MeterError
from pianoize.cli import app
from pianoize.dump import lines

# At 480 ticks a beat: 120 a sixteenth, 60 a half-sixteenth, 1920 a 4/4 bar; 120 bpm, so a bar
# lasts 2 s, unless a test sets the tempos.


def meta(kind: str, **fields) -> mido.MetaMessage:
    return mido.MetaMessage(kind, **fields)


def bar(found: list[str], number: int) -> list[str]:
    """The header, C and V lines of bar `number`."""
    start = next(i for i, line in enumerate(found) if line.startswith(f"=== bar {number} "))
    return found[start : start + 3]


@pytest.fixture
def silent(tick_midi):
    return tick_midi([])


def test_onsets_print_at_their_sixteenth_with_duration_and_velocity(tick_midi, silent):
    # G4, struck 10 ticks before E4, rounds into the same attack and still prints above it.
    cover = tick_midi([(0, 480, 60, 80), (480, 720, 64, 90), (470, 960, 67, 70)])
    assert lines(cover, silent) == [
        "=== bar 1  0:00.00",
        "C 0:C4(4,80)  4:E4(2,90),G4(4,70)",
        "V ",
    ]


@pytest.mark.parametrize(
    ("on", "expected"),
    [
        (460, "C 4:C4(2,80)"),  # 20 ticks early: under the 30 that would round it back
        (440, "C 3.5:C4(2,80)"),  # 40 ticks early: nearer the half-sixteenth before
        (390, "C 3.5:C4(2,80)"),  # a tie, exactly between 3 and 3.5, goes later
    ],
)
def test_an_onset_rounds_to_the_nearest_half_sixteenth(tick_midi, silent, on, expected):
    cover = tick_midi([(on, on + 240, 60, 80)])
    assert lines(cover, silent)[1] == expected


def test_an_onset_just_before_a_bar_line_opens_the_next_bar(tick_midi, silent):
    cover = tick_midi([(0, 240, 48, 60), (3820, 4060, 60, 80)])
    found = lines(cover, silent)
    assert bar(found, 2) == ["=== bar 2  0:02.00", "C ", "V "]  # silence still prints
    assert bar(found, 3) == ["=== bar 3  0:04.00", "C 0:C4(2,80)", "V "]


def test_a_note_rounding_past_the_last_bar_line_adds_its_bar(tick_midi, silent):
    cover = tick_midi([(0, 240, 48, 60), (3820, 3840, 60, 80)])  # the file ends at tick 3840
    found = lines(cover, silent)
    assert len(found) == 9
    assert bar(found, 3) == ["=== bar 3  0:04.00", "C 0:C4(0,80)", "V "]


def test_a_melody_at_another_resolution_lands_on_the_covers_grid(tick_midi):
    cover = tick_midi([(0, 1920, 48, 60)])
    melody = tick_midi([(0, 120, 72, 100), (240, 480, 74, 100)], ticks_per_beat=240)
    assert lines(cover, melody)[2] == "V 0:C5(2)  4:D5(4)"


def test_a_melody_lands_by_seconds_across_tempo_changes(tick_midi):
    # The cover takes 2 s for bar 1 at 120 bpm, then 4 s a bar at 60 bpm. The melody plays its
    # first beat at 120 bpm and the rest at 240, so its ticks 2400 and 5280 sound at 1.5 s and
    # 3 s: bar 1 pos 12 and bar 2 pos 4 of the cover, where its own ticks would say pos 4 of bar 2
    # and pos 12 of bar 3.
    cover = tick_midi([(0, 1920 * 3, 48, 60)], tempos=[(1920, 60)])
    melody = tick_midi([(2400, 2640, 72, 100), (5280, 5520, 74, 100)], tempos=[(480, 240)])
    found = lines(cover, melody)
    assert bar(found, 1)[2] == "V 12:C5(1)"
    assert bar(found, 2) == ["=== bar 2  0:02.00", "C ", "V 4:D5(0.5)"]
    assert bar(found, 3)[0] == "=== bar 3  0:06.00"


def test_markers_print_on_their_bars_header(tick_midi, silent):
    cover = tick_midi(
        [(0, 1920 * 2, 48, 60)],
        meta=[
            (0, meta("marker", text="Intro")),
            (1910, meta("marker", text="A")),  # 10 ticks early: the downbeat of bar 2
            (2880, meta("marker", text=" Pre  \nChorus")),
        ],
    )
    found = lines(cover, silent)
    assert bar(found, 1)[0] == "=== bar 1  0:00.00  0:Intro"
    # The newline breaks no line, and the run of spaces reads as no gap between two fields.
    assert bar(found, 2)[0] == "=== bar 2  0:02.00  0:A  8:Pre Chorus"
    assert len(found) == 6


@pytest.mark.parametrize(
    ("bar_range", "numbers"), [((2, 3), [2, 3]), ((3, 99), [3, 4]), ((0, 1), [1]), ((5, 9), [])]
)
def test_a_bar_range_prints_only_its_bars(tick_midi, silent, bar_range, numbers):
    cover = tick_midi([(0, 1920 * 4, 48, 60)])
    found = lines(cover, silent, bar_range)
    assert [line.split("  ")[0] for line in found[::3]] == [f"=== bar {n}" for n in numbers]
    assert len(found) == 3 * len(numbers)


@pytest.mark.parametrize("tempo_track", [False, True])
def test_text_and_lyrics_never_print(tick_midi, tempo_track):
    words = [(0, meta("text", text="sung text")), (0, meta("lyrics", text="sung line"))]
    cover = tick_midi(
        [(0, 480, 60, 80)],
        meta=[(0, meta("text", text="secret words")), (0, meta("lyrics", text="la la"))],
    )
    # At 60 bpm the melody's beat lasts 1 s, 8 sixteenths of the cover's 120 bpm.
    if tempo_track:  # as tsumugi writes it: the tempo on a track of its own, words on the vocal's
        melody = mido.MidiFile(type=1, ticks_per_beat=480)
        melody.tracks += [tick_midi([], tempos=[(0, 60)]).tracks[0]]
        melody.tracks += [tick_midi([(0, 480, 72, 100)], meta=words).tracks[0]]
    else:
        melody = tick_midi([(0, 480, 72, 100)], tempos=[(0, 60)], meta=words)
    dumped = "\n".join(lines(cover, melody))
    assert "C4(4,80)" in dumped
    assert "V 0:C5(8)" in dumped
    for text in ("secret", "la la", "sung"):
        assert text not in dumped


def test_an_empty_cover_prints_silent_bars(tick_midi, silent):
    cover = tick_midi([], meta=[(3840, meta("end_of_track"))])
    assert lines(cover, silent) == [
        "=== bar 1  0:00.00",
        "C ",
        "V ",
        "=== bar 2  0:02.00",
        "C ",
        "V ",
    ]


def test_a_three_four_bar_holds_twelve_sixteenths(tick_midi, silent):
    three_four = meta("time_signature", numerator=3, denominator=4)
    cover = tick_midi([(1320, 1440, 60, 80), (1440, 1560, 62, 80)], meta=[(0, three_four)])
    found = lines(cover, silent)
    assert bar(found, 1)[1] == "C 11:C4(1,80)"
    assert bar(found, 2) == ["=== bar 2  0:01.50", "C 0:D4(1,80)", "V "]


def test_a_change_of_meter_raises(tick_midi, silent):
    cover = tick_midi(
        [(0, 1920 * 2, 48, 60)],
        meta=[
            (0, meta("time_signature", numerator=4, denominator=4)),
            (1920, meta("time_signature", numerator=3, denominator=4)),
        ],
    )
    with pytest.raises(MeterError, match="at tick 1920, 4/4 to 3/4"):
        lines(cover, silent)


@pytest.fixture
def dumped(tmp_path, tick_midi):
    """A four-bar cover and a melody note in bar 2, on disk."""
    cover, melody = tmp_path / "cover.mid", tmp_path / "melody.mid"
    tick_midi([(0, 1920 * 4, 48, 60)]).save(cover)
    tick_midi([(1920, 2160, 72, 100)]).save(melody)
    return cover, melody


def _dump_cli(cover, melody, *options):
    return CliRunner().invoke(app, ["dump-bars", str(cover), "--melody", str(melody), *options])


def test_cli_prints_the_bars(dumped):
    cover, melody = dumped
    result = _dump_cli(cover, melody)
    assert result.exit_code == 0, result.output
    found = lines(mido.MidiFile(cover), mido.MidiFile(melody))
    assert len(found) == 12
    assert result.stdout == "\n".join(found) + "\n"


def test_cli_prints_only_the_bars_asked_for(dumped):
    result = _dump_cli(*dumped, "--bars", "2-3")
    assert result.exit_code == 0, result.output
    assert result.stdout.splitlines() == [
        "=== bar 2  0:02.00",
        "C ",
        "V 0:C5(2)",
        "=== bar 3  0:04.00",
        "C ",
        "V ",
    ]


@pytest.mark.parametrize("value", ["x", "2", "2-", "-3", "2-3-4", "2 - 3", "0-2", "3-2"])
def test_cli_refuses_a_range_not_written_a_dash_b_from_bar_1_up(dumped, value):
    result = _dump_cli(*dumped, "--bars", value)
    assert result.exit_code == 2
    assert "--bars" in result.output


def test_cli_refuses_a_cover_that_changes_meter(dumped, tick_midi):
    cover, melody = dumped
    three_four = meta("time_signature", numerator=3, denominator=4)
    tick_midi([(0, 1920 * 2, 48, 60)], meta=[(1920, three_four)]).save(cover)
    result = _dump_cli(cover, melody)
    assert result.exit_code == 1
    assert f"error: {cover}: the cover changes meter at tick 1920, 4/4 to 3/4" in result.output
    assert "Traceback" not in result.output


def test_cli_refuses_a_type_2_cover(dumped, tick_midi):
    cover, melody = dumped
    midi = tick_midi([(0, 1920, 48, 60)])
    midi.type = 2
    midi.save(cover)
    result = _dump_cli(cover, melody)
    assert result.exit_code == 1
    assert f"error: {cover}: a type 2 MIDI file's tracks share no timeline" in result.output
    assert "Traceback" not in result.output
