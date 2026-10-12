import mido
import pytest
from typer.testing import CliRunner

from pianoize.arrange import VELOCITY, build
from pianoize.arrangement import ArrangementError, parse
from pianoize.bars import meter
from pianoize.cli import app

# At 480 ticks a beat: 120 a sixteenth, 1920 a 4/4 bar, a restrike gap of 15 ticks, a restrike
# minimum and a pedal gap of 30, a tail of 480 whose notes are released 60 before its end.


@pytest.fixture
def cover(tick_midi):
    """A synthetic 480-TPB cover eight 4/4 bars long, with the tempos and metas given."""

    def make(tempos=None, meta=None):
        return tick_midi([(0, 1920 * 8, 60, 80)], tempos=tempos, meta=meta)

    return make


@pytest.fixture
def built(write_score, cover):
    """The MIDI built from a score file of `format 1` and the lines given."""

    def build_lines(*lines, cover_midi=None):
        cover_midi = cover_midi or cover()
        text = write_score(*lines).read_text(encoding="utf-8")
        return build(parse(text, meter(cover_midi).sixteenths_per_bar), cover_midi)

    return build_lines


def timed(track: mido.MidiTrack) -> list[tuple[int, mido.Message | mido.MetaMessage]]:
    events, now = [], 0
    for message in track:
        now += message.time
        events.append((now, message))
    return events


def notes(track: mido.MidiTrack) -> list[tuple[int, int, int]]:
    """(on, off, pitch) of each note, sorted; a pitch struck again while sounding pairs first in,
    first out."""
    sounding, found = {}, []
    for tick, message in timed(track):
        if message.type == "note_on":
            sounding.setdefault(message.note, []).append(tick)
        elif message.type == "note_off":
            found.append((sounding[message.note].pop(0), tick, message.note))
    return sorted(found)


def pedal(track: mido.MidiTrack) -> list[tuple[int, int]]:
    """(press, lift) of each time the sustain pedal goes down."""
    changes = [(tick, m) for tick, m in timed(track) if m.type == "control_change"]
    assert {m.control for _, m in changes} <= {64}
    presses = [tick for tick, m in changes if m.value == 127]
    lifts = [tick for tick, m in changes if m.value == 0]
    return list(zip(presses, lifts, strict=True))


def test_the_hands_go_to_two_named_tracks_on_two_channels(built):
    midi = built("bar 1 | C", "  M 0:C5:4", "  R 0:E4+G4:4", "  L 0:C3:4")
    assert (midi.type, midi.ticks_per_beat) == (1, 480)
    right, left = midi.tracks
    assert [m.name for m in right if m.type == "track_name"] == ["Right Hand"]
    assert [m.name for m in left if m.type == "track_name"] == ["Left Hand"]
    assert {m.channel for m in right if hasattr(m, "channel")} == {0}
    assert {m.channel for m in left if hasattr(m, "channel")} == {1}
    assert [pitch for _, _, pitch in notes(right)] == [64, 67, 72]
    assert [pitch for _, _, pitch in notes(left)] == [48]
    for track in midi.tracks:
        assert [m.program for m in track if m.type == "program_change"] == [0]


def test_every_note_has_one_velocity(built):
    midi = built("bar 1 | C", "  M 0:C5:4 4:D5:4", "  R 0:E4+G4:8", "  L 0:C3:16")
    sent = [m for track in midi.tracks for m in track if m.type in ("note_on", "note_off")]
    assert {m.velocity for m in sent if m.type == "note_on"} == {VELOCITY} == {88}
    assert {m.velocity for m in sent if m.type == "note_off"} == {0}


def test_a_token_lands_on_its_ticks(built):
    midi = built("bar 1 | C", "  L 0:C3:16", "bar 2 | C", "  M 4:C5:2", "  L 0:E3:16")
    assert notes(midi.tracks[0]) == [(2400, 2640, 72)]  # bar 2 pos 4, two sixteenths


def test_a_duration_past_the_bar_line_ends_in_the_next_bar(built):
    midi = built("bar 1 | C", "  L 12:G2:8", "bar 2 | C", "  L 8:C3:8")
    assert notes(midi.tracks[1])[0] == (1440, 2400, 43)  # bar 2 starts at 1920


def test_the_covers_tempos_go_to_track_zero_up_to_the_end(built, cover):
    tempos = [(0, 120), (1920, 90), (7680, 60)]  # the build ends at 4320
    midi = built("bar 1 | C", "  L 0:C3:16", "bar 2 | G", "  L 0:G2:16", cover_midi=cover(tempos))
    right, left = midi.tracks
    found = [(tick, m.tempo) for tick, m in timed(right) if m.type == "set_tempo"]
    assert found == [(0, mido.bpm2tempo(120)), (1920, mido.bpm2tempo(90))]
    assert not [m for m in left if m.type == "set_tempo"]


def test_messages_at_one_tick_come_in_order(built, cover):
    midi = built(
        "bar 1 | C",
        "  M 0:E5:16 8:C5:8",  # E5 struck first, both released at bar 2
        "  R 0:C4:0.25 0.25:D4:1",  # C4 released and D4 struck at the press
        "bar 2 | G",
        "  M 0:D5+B4:16",
        cover_midi=cover([(0, 120), (1920, 90)]),
    )
    at_bar_two = [m for tick, m in timed(midi.tracks[0]) if tick == 1920]
    assert [(m.type, getattr(m, "value", None), getattr(m, "note", None)) for m in at_bar_two] == [
        ("set_tempo", None, None),
        ("control_change", 0, None),  # the lift at the chord
        ("note_off", None, 72),
        ("note_off", None, 76),
        ("note_on", None, 71),
        ("note_on", None, 74),
    ]
    at_press = [m for tick, m in timed(midi.tracks[0]) if tick == 30]
    assert [(m.type, getattr(m, "value", None), getattr(m, "note", None)) for m in at_press] == [
        ("note_off", None, 60),
        ("control_change", 127, None),
        ("note_on", None, 62),
    ]
    at_start = [m.type for tick, m in timed(midi.tracks[0]) if tick == 0]
    assert at_start == [
        "track_name",
        "time_signature",
        "set_tempo",
        "program_change",
        "note_on",
        "note_on",
    ]


def test_a_three_four_cover_writes_three_four(built, cover):
    three_four = mido.MetaMessage("time_signature", numerator=3, denominator=4)
    midi = built(
        "bar 1 | C",
        "  L 0:C3:12",
        "bar 2 | G",
        "  M 6:D5:2",
        "  L 0:G2:12",
        cover_midi=cover(meta=[(0, three_four)]),
    )
    signatures = [m for m in midi.tracks[0] if m.type == "time_signature"]
    assert [(m.numerator, m.denominator) for m in signatures] == [(3, 4)]
    assert notes(midi.tracks[0]) == [(2160, 2400, 74)]  # half a 1440-tick bar past 1440


def test_the_pedal_follows_each_bars_setting(built):
    midi = built(
        "bar 1 | 0:C 8:G",  # chord, the default
        "  L 0:C3:16",
        "bar 2 | F | pedal=none",
        "  L 0:F2:16",
        "bar 3 | C | pedal=0,x8",
        "  L 0:C3:16",
        "bar 4 | G | pedal=4",
        "  L 0:G2:4",
    )
    expected = [
        (30, 960),  # down a gap after the chord at 0, up at the chord at 8
        (990, 1920),  # up at bar 2, and down nowhere in it
        (3870, 4800),  # down after bar 3's 0, up at x8 and not down again
        (6270, 6720),  # down after bar 4's 4, up at the build's end
    ]
    for track in midi.tracks:  # sustain is per channel, so each hand's channel gets it
        assert pedal(track) == expected


def test_a_semitone_against_a_held_note_lifts_the_pedal_at_the_attack(built):
    midi = built("bar 1 | C", "  M 0:C5:4 8:B4:4 12:E5:4", "  L 0:C3:16", "bar 2 | C", "  L 0:C3:4")
    # The pedal still holds C5, released at 480, when B4 comes at 960; E5 rubs against nothing.
    assert pedal(midi.tracks[0]) == [(30, 960), (990, 1920), (1950, 2880)]


def test_a_semitone_against_a_note_released_before_the_press_keeps_the_pedal(built):
    midi = built("bar 1 | 0:C 8:C", "  M 0:C5:8 12:B4:4", "  L 0:E3:16", "bar 2 | C", "  L 0:E3:4")
    # C5 is released at the lift at 960, before the pedal goes down again at 990.
    assert pedal(midi.tracks[0]) == [(30, 960), (990, 1920), (1950, 2880)]


def test_a_semitone_against_a_note_released_at_the_press_keeps_the_pedal(built):
    midi = built(
        "bar 1 | 0:C 8:C", "  M 7.75:C5:0.5 12:B4:2", "  L 0:E3:16", "bar 2 | C", "  L 0:E3:4"
    )
    # C5 is released at 990, the press, and its note-off comes first.
    assert pedal(midi.tracks[0]) == [(30, 960), (990, 1920), (1950, 2880)]


def test_a_minor_ninth_against_a_held_note_lifts_it_too(built):
    midi = built("bar 1 | C", "  M 0:C5:4 8:B3:4", "  L 0:C3:16", "bar 2 | C", "  L 0:C3:4")
    assert pedal(midi.tracks[0]) == [(30, 960), (990, 1920), (1950, 2880)]


def test_a_restrike_is_separated(built):
    midi = built(
        "bar 1 | C",
        "  M 0:C5:4 4:C5:4 8:C5:0.5 8.25:C5:2 12:C5:0.1 12.5:C5:1",
        "  L 0:C5:16",
        "bar 2 | C",
        "  L 0:C3:4",
    )
    assert notes(midi.tracks[0]) == [
        (0, 465, 72),  # a gap before the next strike
        (480, 945, 72),  # written to end where the next starts
        (960, 990, 72),  # the minimum, though a gap before the next strike is sooner
        (990, 1230, 72),
        (1440, 1452, 72),  # already shorter than the minimum, so not lengthened
        (1500, 1620, 72),
    ]
    assert notes(midi.tracks[1])[0] == (0, 1920, 72)  # the other hand's C5 is not cut


def test_an_earlier_note_never_ends_past_a_later_strike(built):
    midi = built(
        "bar 1 | C",
        "  M 0:C5:1 0.125:C5:2 4:E5:2",
        "  R 4:G4+E5:2",
        "  L 0:C3:16",
        "bar 2 | C",
        "  L 0:C3:4",
    )
    assert notes(midi.tracks[0]) == [
        (0, 15, 72),  # at the next strike, under the minimum
        (15, 255, 72),
        (480, 510, 76),  # struck twice at one tick: the minimum, not a note of no length
        (480, 720, 67),
        (480, 720, 76),
    ]


def test_the_tail_holds_the_last_notes_a_beat(built):
    midi = built("bar 1 | C | pedal=none", "  M 0:C5:8", "  R 0:E4+G4:16", "  L 0:C3:16 8:G2:8")
    right, left = midi.tracks
    assert notes(right) == [(0, 960, 72), (0, 2340, 64), (0, 2340, 67)]
    assert notes(left) == [(0, 2340, 48), (960, 2340, 43)]
    for track in midi.tracks:
        assert (timed(track)[-1][0], track[-1].type) == (2400, "end_of_track")


def test_the_pedal_stops_at_the_end(built):
    midi = built("bar 1 | C", "  L 0:C3:4", "bar 2 | C", "bar 3 | C")
    assert pedal(midi.tracks[1]) == [(30, 960)]  # a beat past the last note-off, at 480


def test_a_score_without_notes_raises(built):
    with pytest.raises(ArrangementError, match="the score has no notes"):
        built("bar 1 | C")


def test_the_same_inputs_give_the_same_bytes(built, tmp_path):
    lines = ("bar 1 | 0:C 8:G/B", "  M 0:E5:4 4:D5~:2 6.5:C5:1.5", "  R 0:G4+C5:8", "  L 0:C3:16")
    first, second = tmp_path / "first.mid", tmp_path / "second.mid"
    built(*lines).save(first)
    built(*lines).save(second)
    assert first.read_bytes() == second.read_bytes()


SCORE = ("bar 1 | C", "  M 0:E5:4 4:G5:4", "  R 0:G4+C5:8", "  L 0:C3:8 8:G2:8")


@pytest.fixture
def cover_file(tmp_path, cover):
    path = tmp_path / "cover.mid"
    cover().save(path)
    return path


def _build_cli(score, cover, out):
    return CliRunner().invoke(
        app, ["build-arrangement", str(score), "--cover", str(cover), "-o", str(out)]
    )


def test_cli_writes_the_build_and_prints_its_counts(tmp_path, write_score, cover_file, built):
    out, expected = tmp_path / "out.mid", tmp_path / "expected.mid"
    result = _build_cli(write_score(*SCORE), cover_file, out)
    assert result.exit_code == 0, result.output
    # The pedal goes down once, after bar 1's chord; the tail ends a beat past bar 1, at 120 bpm.
    assert result.stdout == "notes: 4 right hand, 2 left hand\npedal presses: 1\nlength: 2.5 s\n"
    built(*SCORE).save(expected)
    assert out.read_bytes() == expected.read_bytes()


def test_cli_reads_a_score_with_a_byte_order_mark(tmp_path, write_score, cover_file):
    score = write_score(*SCORE)
    score.write_text(score.read_text(encoding="utf-8"), encoding="utf-8-sig")
    result = _build_cli(score, cover_file, tmp_path / "out.mid")
    assert result.exit_code == 0, result.output


@pytest.mark.parametrize("target", ["score", "cover", "score respelled"])
def test_cli_refuses_to_overwrite_an_input(tmp_path, write_score, cover_file, target):
    inputs = {"score": write_score(*SCORE), "cover": cover_file}
    (tmp_path / "sub").mkdir()
    targets = {**inputs, "score respelled": tmp_path / "sub" / ".." / "score.txt"}
    before = {name: path.read_bytes() for name, path in inputs.items()}
    result = _build_cli(inputs["score"], cover_file, targets[target])
    assert result.exit_code == 2
    assert "would overwrite an input" in " ".join(result.output.split())
    assert {name: path.read_bytes() for name, path in inputs.items()} == before


@pytest.mark.parametrize(
    ("lines", "message"),
    [
        (("bar 1 | C", "  L 0:C3:4", "bar 2 | G", "  L 0:H3:4"), "bar 2: token '0:H3:4': bad note"),
        (("bar 1 | C",), "the score has no notes"),
    ],
)
def test_cli_reports_a_bad_score_without_a_traceback(
    tmp_path, write_score, cover_file, lines, message
):
    score, out = write_score(*lines), tmp_path / "out.mid"
    result = _build_cli(score, cover_file, out)
    assert result.exit_code == 1
    assert f"error: {score}: {message}" in result.output
    assert "Traceback" not in result.output
    assert not out.exists()


def test_cli_refuses_a_cover_that_changes_meter(tmp_path, write_score, cover):
    path, out = tmp_path / "cover.mid", tmp_path / "out.mid"
    three_four = mido.MetaMessage("time_signature", numerator=3, denominator=4)
    cover(meta=[(1920, three_four)]).save(path)
    result = _build_cli(write_score(*SCORE), path, out)
    assert result.exit_code == 1
    assert f"error: {path}: the cover changes meter at tick 1920, 4/4 to 3/4" in result.output
    assert "Traceback" not in result.output
    assert not out.exists()


def test_cli_reports_a_score_not_in_utf_8(tmp_path, write_score, cover_file):
    score, out = write_score(*SCORE), tmp_path / "out.mid"
    score.write_bytes(score.read_bytes() + b"# \xff\n")
    result = _build_cli(score, cover_file, out)
    assert result.exit_code == 1
    assert f"error: {score}: " in result.output
    assert "can't decode byte 0xff" in result.output
    assert "Traceback" not in result.output
    assert not out.exists()


def test_cli_refuses_a_type_2_cover(tmp_path, write_score, cover):
    path, out = tmp_path / "cover.mid", tmp_path / "out.mid"
    midi = cover()
    midi.type = 2
    midi.save(path)
    result = _build_cli(write_score(*SCORE), path, out)
    assert result.exit_code == 1
    assert f"error: {path}: a type 2 MIDI file's tracks share no timeline" in result.output
    assert "Traceback" not in result.output
    assert not out.exists()


def test_help_lists_the_arranging_commands():
    result = CliRunner().invoke(app, ["--help"])
    assert result.exit_code == 0
    for name in ("build-arrangement", "check-arrangement", "dump-bars"):
        assert name in result.output
