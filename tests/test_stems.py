import numpy as np
import pytest

from pianoize import stems
from pianoize.bars import Meter
from pianoize.notes import Note

FS = 512 / 44100  # seconds a frame
FRAMES = 800  # about 9.3 s
FLOOR = -127.5  # dB, the table's 0
LOW = 36  # C2, the levels' first row
# At 480 ticks a beat and 120 bpm: a sixteenth 125 ms, a 4/4 bar 2 s.
METER = Meter(480, 4, 4)
TEMPO_MAP = [(0, 0.0, 500000)]


def t(frame: int) -> float:
    """The time halfway before a frame's centre: from t(a) to t(b) are frames a to b - 1."""
    return (frame - 0.5) * FS


def frame(seconds: float) -> int:
    """The first frame centred at or after a time."""
    return int(np.searchsorted(np.arange(FRAMES) * FS, seconds))


def note(first: int, last: int, pitch: int) -> Note:
    """A note over frames first to last - 1."""
    return Note(0, 0, pitch, 80, 0, t(first), t(last))


def timed(onset: float, offset: float, pitch: int) -> Note:
    return Note(0, 0, pitch, 80, 0, onset, offset)


class Voice:
    """A vocals stem, unvoiced at the floor until sung."""

    def __init__(self) -> None:
        self.pitch = np.full(FRAMES, np.nan)
        self.level = np.full(FRAMES, FLOOR)

    def sing(self, first: int, last: int, pitch: float, db=0.0) -> "Voice":
        self.pitch[first:last] = pitch
        self.level[first:last] = db
        return self


class Band:
    """A levels stem, every semitone at the floor until played."""

    def __init__(self) -> None:
        self.rows = np.full((72, FRAMES), FLOOR)

    def play(self, first: int, last: int, pitch: int, db=0.0) -> "Band":
        self.rows[pitch - LOW, first:last] = db
        return self


@pytest.fixture
def audio(stem_table):
    """The items and the count of notes read for a line against a voice, as `vocals`, or a band,
    as `other`, every level `shift` dB lower."""

    def run(line, voice=None, band=None, others=None, shift=0.0, in_range=lambda seconds: True):
        if band is None:
            voice = voice or Voice()
            path = stem_table(FRAMES, pitch=voice.pitch, level=voice.level - shift)
            stem = "vocals"
        else:
            path = stem_table(FRAMES, levels={"other": band.rows - shift})
            stem = "other"
        return stems.items(stems.load(path), stem, line, others or {}, in_range)

    return run


@pytest.fixture
def listed(audio):
    """As audio, the items as (kind, pitch, detail) and the count."""

    def run(line, **kwargs):
        found, read = audio(line, **kwargs)
        return [(item.kind, item.pitch, item.detail) for item in found], read

    return run


def rewrite(path, **changes):
    """The table at `path` with arrays replaced, or dropped for None."""
    arrays = dict(np.load(path))
    for name, value in changes.items():
        if value is None:
            del arrays[name]
        else:
            arrays[name] = value
    np.savez_compressed(path, **arrays)
    return path


# load


def test_a_table_reads_back_as_written(stem_table):
    voice = Voice().sing(10, 20, 69.25, -6)
    band = Band().play(10, 20, 69, -3.5)
    table = stems.load(stem_table(FRAMES, {"other": band.rows}, voice.pitch, voice.level))
    assert table.stems == ("guitar", "other", "piano", "vocals")
    assert table.seconds == pytest.approx(FRAMES * FS)
    assert (table.frame_seconds, table.low_pitch) == (pytest.approx(FS), LOW)
    assert (table.vocals_low, table.vocals_high) == (45, 84)
    np.testing.assert_array_equal(table.levels["other"], band.rows)
    np.testing.assert_array_equal(table.levels["piano"], Band().rows)
    np.testing.assert_array_equal(table.vocals_pitch, voice.pitch.astype(np.float32))
    np.testing.assert_array_equal(table.vocals_level, voice.level)


def test_a_file_that_is_no_npz_is_refused(tmp_path):
    text, npy = tmp_path / "text.npz", tmp_path / "array.npz"
    text.write_text("not a table")
    with npy.open("wb") as file:
        np.save(file, np.zeros(3))
    for path in (text, npy):
        with pytest.raises(stems.StemsError, match="^not an npz file$"):
            stems.load(path)
    with pytest.raises(stems.StemsError, match="No such file"):
        stems.load(tmp_path / "missing.npz")


def test_a_damaged_npz_file_is_refused(stem_table):
    path = stem_table(FRAMES, pitch=np.linspace(45, 84, FRAMES), level=np.linspace(-60, 0, FRAMES))
    data = bytearray(path.read_bytes())
    # Inside the first array's compressed data, where zlib, not the zip's checksum, fails first.
    data[100:120] = bytes(byte ^ 0xFF for byte in data[100:120])
    path.write_bytes(data)
    with pytest.raises(stems.StemsError, match="^not an npz file$"):
        stems.load(path)


def test_a_table_with_no_frames_is_refused(stem_table):
    with pytest.raises(stems.StemsError, match="^no frames$"):
        stems.load(stem_table(0))


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"version": 2}, "version 2; this pianoize reads 1"),
        ({"version": None}, "missing array version"),
        ({"vocals_low": None}, "missing array vocals_low"),
        ({"vocals_high": None}, "missing array vocals_high"),
        ({"vocals_low": None, "vocals_high": None}, "missing arrays vocals_low, vocals_high"),
        ({"piano": None}, "missing array piano"),
        (
            {"vocals_level": np.zeros(FRAMES - 1, np.uint8)},
            f"arrays of unequal frame counts: guitar {FRAMES}, other {FRAMES}, piano {FRAMES}, "
            f"vocals_pitch {FRAMES}, vocals_level {FRAMES - 1}",
        ),
    ],
)
def test_a_table_off_the_format_is_refused(stem_table, changes, message):
    path = rewrite(stem_table(FRAMES), **changes)
    with pytest.raises(stems.StemsError) as error:
        stems.load(path)
    assert str(error.value) == message


# The loud level and the sounding test


@pytest.mark.parametrize("on_band", [False, True])
def test_a_tone_in_three_percent_of_the_frames_sounds_over_a_quiet_background(listed, on_band):
    # 24 frames of 800 at 0 dB; everywhere else -60 dB, which the 95th percentile of every frame
    # would make the loud level, and every frame would sound.
    line = [note(100, 124, 69), note(300, 340, 69)]
    if on_band:
        band = Band().play(0, FRAMES, 69, -60).play(100, 124, 69)
        assert listed(line, band=band) == ([("silent", 69, "audio - 0%")], 2)
    else:
        voice = Voice().sing(0, FRAMES, 69, -60).sing(100, 124, 69)
        assert listed(line, voice=voice) == ([("silent", 69, "audio - 0%")], 2)


@pytest.mark.parametrize("on_band", [False, True])
def test_a_stem_at_the_floor_never_sounds(listed, on_band):
    # Its loud level is the floor too, so only the floor itself keeps it from sounding.
    line = [note(100, 140, 69)]
    if on_band:
        found = listed(line, band=Band())
    else:
        found = listed(line, voice=Voice().sing(0, FRAMES, 72, FLOOR))
    assert found == ([("silent", 69, "audio - 0%")], 1)


# A vocals note


def test_a_note_sung_within_the_agreement_is_supported(listed):
    voice = Voice().sing(100, 140, 76.6).sing(140, 150, 75.4)
    assert listed([note(100, 150, 76)], voice=voice) == ([], 1)


@pytest.mark.parametrize(("off", "found"), [(0.6, []), (0.8, [("pitch", 76, "audio F5 100%")])])
def test_a_note_sung_more_than_0_7_semitone_off_is_listed(listed, off, found):
    voice = Voice().sing(100, 140, 76 + off)
    assert listed([note(100, 140, 76)], voice=voice) == (found, 1)


@pytest.mark.parametrize(("agree", "found"), [(20, []), (16, [("pitch", 76, "audio D5 60%")])])
def test_a_note_half_of_whose_sounding_frames_agree_is_supported(listed, agree, found):
    voice = Voice().sing(100, 140, 74).sing(100, 100 + agree, 76)
    assert listed([note(100, 140, 76)], voice=voice) == (found, 1)


@pytest.mark.parametrize(
    ("sung", "item"),
    [(74, ("pitch", 76, "audio D5 100%")), (64, ("octave", 76, "audio E4 100%"))],
)
def test_a_note_sung_at_another_pitch_is_listed_with_it(listed, sung, item):
    voice = Voice().sing(100, 140, sung)
    assert listed([note(100, 140, 76)], voice=voice) == ([item], 1)


@pytest.mark.parametrize(("voiced", "share"), [(0, "0%"), (10, "25%")])
def test_a_note_under_thirty_percent_voiced_is_silent(listed, voiced, share):
    voice = Voice().sing(100, 100 + voiced, 76)
    assert listed([note(100, 140, 76)], voice=voice) == ([("silent", 76, f"audio - {share}")], 1)


def test_a_note_thirty_percent_voiced_is_not_silent(listed):
    assert listed([note(100, 140, 76)], voice=Voice().sing(100, 112, 76)) == ([], 1)


def test_a_quiet_voiced_note_does_not_sound(listed):
    # 35 dB under the loud note: voiced, but under the sounding level.
    voice = Voice().sing(100, 140, 69).sing(200, 240, 76, -35)
    found = listed([note(100, 140, 69), note(200, 240, 76)], voice=voice)
    assert found == ([("silent", 76, "audio - 0%")], 2)


def test_a_note_under_80_ms_is_not_read(listed):
    # Six frames, 70 ms, sung a tone off.
    assert listed([note(100, 106, 76)], voice=Voice().sing(100, 106, 74)) == ([], 0)


def test_a_moving_line_read_as_a_held_note_is_listed_with_a_pitch_that_was_sung(listed):
    # Frame by frame: the median of D5 and F#5 is the transcribed E5.
    voice = Voice().sing(100, 120, 74).sing(120, 140, 78)
    assert listed([note(100, 140, 76)], voice=voice) == ([("pitch", 76, "audio D5 50%")], 1)
    voice = Voice().sing(100, 114, 74).sing(114, 128, 76).sing(128, 142, 78)
    assert listed([note(100, 142, 76)], voice=voice) == ([("pitch", 76, "audio D5 33%")], 1)


@pytest.mark.parametrize("pitch", [44, 85])
@pytest.mark.parametrize("held", ["same", "other", "none"])
def test_a_vocals_note_outside_the_trackers_range_is_not_read(listed, pitch, held):
    voice = Voice()
    if held != "none":
        voice.sing(100, 140, pitch if held == "same" else 60)
    assert listed([note(100, 140, pitch)], voice=voice) == ([], 0)


# A levels note


def test_a_leading_note_is_supported(listed):
    band = Band().play(100, 140, 72).play(100, 140, 60, -20)
    assert listed([note(100, 140, 72)], band=band) == ([], 1)


def test_a_note_an_octave_under_a_lead_over_10_db_louder_is_listed_octave(listed):
    band = Band().play(100, 140, 72).play(100, 140, 60, -15)
    assert listed([note(100, 140, 60)], band=band) == ([("octave", 60, "audio C5 100%")], 1)


@pytest.mark.parametrize(("under", "found"), [(6, []), (12, [("pitch", 76, "audio C5 100%")])])
def test_a_chord_note_within_10_db_of_the_lead_is_supported(listed, under, found):
    band = Band().play(100, 140, 72).play(100, 140, 76, -under)
    assert listed([note(100, 140, 72), note(100, 140, 76)], band=band) == (found, 2)


@pytest.mark.parametrize("away", [-13, 13])
def test_a_louder_semitone_over_an_octave_away_is_not_the_lead(listed, away):
    band = Band().play(100, 140, 72, -15).play(100, 140, 72 + away)
    assert listed([note(100, 140, 72)], band=band) == ([], 1)


def test_a_held_note_under_a_moving_line_is_listed_with_a_lead_that_was_played(listed):
    band = Band().play(100, 140, 76, -20).play(100, 120, 74).play(120, 140, 78)
    assert listed([note(100, 140, 76)], band=band) == ([("pitch", 76, "audio D5 50%")], 1)


def test_a_note_on_a_silent_stem_is_silent(listed):
    assert listed([note(100, 140, 72)], band=Band()) == ([("silent", 72, "audio - 0%")], 1)


@pytest.mark.parametrize("pitch", [35, 108])
def test_a_levels_note_outside_c2_to_b7_is_not_read(listed, pitch):
    band = Band().play(100, 140, 72)
    assert listed([note(100, 140, 72), note(100, 140, pitch)], band=band) == ([], 1)


@pytest.mark.parametrize(("sounding", "found"), [(16, []), (8, [("silent", 72, "audio - 20%")])])
def test_a_decaying_note_is_judged_on_the_frames_that_sound(listed, sounding, found):
    # Every sounding frame carries the note; after them it has faded under the sounding level.
    band = Band().play(100, 140, 72, -45).play(100, 100 + sounding, 72)
    assert listed([note(100, 140, 72)], band=band) == (found, 1)


# Stretches

AROUND = [note(10, 50, 69), note(300, 340, 69)]  # 0 dB, around a stretch at 150


def around() -> Voice:
    return Voice().sing(10, 50, 69).sing(300, 340, 69)


@pytest.mark.parametrize(("frames", "found"), [(8, []), (9, [("untranscribed", 72, "+0 dB")])])
def test_a_run_under_100_ms_is_not_listed(listed, frames, found):
    # Eight frames are 93 ms, nine 104 ms.
    assert listed(AROUND, voice=around().sing(150, 150 + frames, 72)) == (found, 2)


def test_two_runs_40_ms_apart_are_one_stretch(audio):
    # Six frames, 70 ms, each: neither alone lasts 100 ms. The tracker drops the pitch between
    # them while the level holds, so the second has no onset of its own.
    gap = round(0.040 / FS)
    voice = around().sing(150, 156, 72).sing(156 + gap, 162 + gap, 72)
    voice.level[156 : 156 + gap] = 0
    found, _ = audio(AROUND, voice=voice)
    assert [(item.kind, item.pitch) for item in found] == [("untranscribed", 72)]
    assert (found[0].onset, found[0].offset) == pytest.approx((150 * FS, (162 + gap) * FS))


def test_two_runs_60_ms_apart_stay_two(audio):
    # Nine frames, 104 ms, each, the level holding between them: the first is listed alone, and
    # the second, which has no onset, isn't.
    gap = round(0.060 / FS)
    voice = around().sing(150, 159, 72).sing(159 + gap, 168 + gap, 72)
    voice.level[159 : 159 + gap] = 0
    found, _ = audio(AROUND, voice=voice)
    assert [(item.onset, item.offset) for item in found] == [pytest.approx((150 * FS, 159 * FS))]


def test_a_pickup_is_listed_where_its_level_rises(audio):
    # Sung at -12 dB from frame 100, out of silence, then 0.2 s on a 12 dB step to 0 dB: the
    # quiet lead-in, under the notes around, is not listed, and the pickup starts at the step.
    step = 100 + round(0.2 / FS)
    voice = around().sing(100, step, 72, -12).sing(step, 300, 72)
    found, _ = audio(AROUND, voice=voice)
    assert [(item.kind, item.pitch, item.detail) for item in found] == [
        ("untranscribed", 72, "+0 dB")
    ]
    assert found[0].onset == pytest.approx(step * FS, abs=FS)


def test_a_run_attacked_twice_is_two_stretches_at_its_two_onsets(audio):
    # One pitch, sounding throughout: 0 dB, a dip to -12 dB, then 0 dB again, over notes at -6 dB.
    voice = Voice().sing(10, 50, 69, -6).sing(300, 340, 69, -6)
    voice.sing(150, 175, 72).sing(175, 180, 72, -12).sing(180, 220, 72)
    found, _ = audio(AROUND, voice=voice)
    assert [(item.kind, item.pitch, item.detail) for item in found] == [
        ("untranscribed", 72, "+4 dB"),
        ("untranscribed", 72, "+6 dB"),
    ]
    assert [(item.onset, item.offset) for item in found] == [
        pytest.approx((150 * FS, 180 * FS)),
        pytest.approx((180 * FS, 220 * FS)),
    ]


@pytest.mark.parametrize(("step", "onsets"), [(4, [150]), (8, [150, 175])])
def test_a_rise_of_6_db_or_more_in_a_run_starts_a_stretch(audio, step, onsets):
    # Held at -8 dB, then `step` dB louder, over notes at -12 dB.
    voice = Voice().sing(10, 50, 69, -12).sing(300, 340, 69, -12)
    voice.sing(150, 175, 72, -8).sing(175, 220, 72, -8 + step)
    found, _ = audio(AROUND, voice=voice)
    assert [item.onset for item in found] == pytest.approx([frame * FS for frame in onsets])


@pytest.mark.parametrize("under", [10, 15, 20])
@pytest.mark.parametrize("on_band", [False, True])
def test_a_held_notes_fading_tail_is_never_listed(listed, under, on_band):
    # Fading 10 dB more after the note; a quieter note later keeps the tail from being under
    # every note around it, so only the missing onset leaves it out.
    tail = np.linspace(-under, -under - 10, 40)
    line = [note(10, 50, 69), note(150, 190, 69)]
    if on_band:
        band = Band().play(10, 50, 69).play(50, 90, 69, tail).play(150, 190, 69, -28)
        assert listed(line, band=band) == ([], 2)
    else:
        voice = Voice().sing(10, 50, 69).sing(50, 90, 69, tail).sing(150, 190, 69, -28)
        assert listed(line, voice=voice) == ([], 2)


@pytest.mark.parametrize(("below", "found"), [(1, 0), (2, 0), (3, 1)])
def test_a_scoop_a_tone_or_less_under_the_next_note_is_not_listed(listed, below, found):
    # Rising from -12 dB to 0 dB into the note at frame 150; a quiet note later keeps it from
    # being under every note around it.
    line = [note(10, 50, 69), note(150, 190, 72), note(250, 290, 72)]
    voice = Voice().sing(10, 50, 69).sing(150, 190, 72).sing(250, 290, 72, -20)
    voice.sing(120, 150, 72 - below, np.linspace(-12, 0, 30))
    items, _ = listed(line, voice=voice)
    assert [(kind, pitch) for kind, pitch, _ in items] == [("untranscribed", 72 - below)] * found


@pytest.mark.parametrize(
    ("end", "ramp"),
    [(150 - round(0.1 / FS), (-12, 0)), (150, (0, -12))],
    ids=["ending 0.1 s early", "falling"],
)
def test_a_run_a_semitone_under_the_next_note_that_is_no_scoop_is_listed(listed, end, ramp):
    # As the scoop above, but ending 0.1 s before the note, or loudest at its start.
    line = [note(10, 50, 69), note(150, 190, 72), note(250, 290, 72)]
    voice = Voice().sing(10, 50, 69).sing(150, 190, 72).sing(250, 290, 72, -20)
    voice.sing(end - 30, end, 71, np.linspace(*ramp, 30))
    items, _ = listed(line, voice=voice)
    assert [(kind, pitch) for kind, pitch, _ in items] == [("untranscribed", 71)]


# Four notes either side of the stretch at 300, from -2 to -9 dB, and one more each side at
# -20 dB, which would let a stretch under the eight through were it counted.
LEVELS = (-20, -2, -4, -6, -8, -3, -5, -7, -9, -20)


def neighbours() -> tuple[list[Note], Voice]:
    starts = [0, 50, 100, 150, 200, 400, 450, 500, 550, 600]
    voice = Voice()
    for start, db in zip(starts, LEVELS, strict=True):
        voice.sing(start + 5, start + 45, 69, db)
    return [note(start + 5, start + 45, 69) for start in starts], voice


def test_a_stretch_under_all_eight_notes_around_it_is_not_listed(listed):
    line, voice = neighbours()
    assert listed(line, voice=voice.sing(300, 340, 72, -10)) == ([], 10)


def test_a_stretch_at_the_median_of_the_notes_around_it_is_listed(listed):
    line, voice = neighbours()
    found, _ = listed(line, voice=voice.sing(300, 340, 72, np.median(LEVELS[1:-1])))
    assert found == [("untranscribed", 72, "+0 dB")]


def test_a_stretch_by_a_line_of_one_note_is_read_against_it(listed):
    voice = Voice().sing(10, 50, 69, -6).sing(150, 190, 72)
    assert listed([note(10, 50, 69)], voice=voice) == ([("untranscribed", 72, "+6 dB")], 1)
    voice = Voice().sing(10, 50, 69).sing(150, 190, 72, -6)
    assert listed([note(10, 50, 69)], voice=voice) == ([], 1)


def test_a_levels_stretch_is_the_lead_inside_the_register_of_the_notes_read(listed):
    # C3 is the loudest in the gap, but under the line; E5 is the lead between C5 and G5.
    band = Band().play(10, 50, 72, -6).play(250, 290, 79, -6)
    band.play(100, 150, 48).play(100, 150, 76, -6)
    line = [note(10, 50, 72), note(250, 290, 79)]
    assert listed(line, band=band) == ([("untranscribed", 76, "+0 dB")], 2)


def test_a_stretch_names_the_other_tracks_with_a_note_over_it(listed):
    others = {
        "vocal_harmony": [note(160, 170, 69), note(170, 180, 72), note(400, 440, 60)],
        "choir": [note(400, 440, 64)],
        "lead_vocal_double": [note(140, 151, 65)],
    }
    found, _ = listed(AROUND, voice=around().sing(150, 190, 76), others=others)
    assert found == [("untranscribed", 76, "+0 dB  also vocal_harmony A4 C5, lead_vocal_double F4")]


def test_in_range_keeps_the_notes_and_stretches_starting_in_it_and_counts_their_notes(audio):
    voice = Voice().sing(10, 50, 74).sing(150, 190, 72).sing(300, 340, 74)
    line = [note(10, 50, 76), note(300, 340, 76)]
    found, read = audio(line, voice=voice, in_range=lambda seconds: seconds < 200 * FS)
    assert [(item.kind, item.pitch) for item in found] == [("pitch", 76), ("untranscribed", 72)]
    assert read == 1


# The report


@pytest.fixture
def reported(audio):
    def run(line, **kwargs):
        stem = "other" if "band" in kwargs else "vocals"
        found, read = audio(line, **kwargs)
        return stems.report(found, read, stem, METER, TEMPO_MAP)

    return run


def sung(*notes: tuple[float, float, int, int | None]) -> tuple[list[Note], Voice]:
    """A line of (onset, offset, pitch, pitch sung or None) notes in seconds, and its voice."""
    voice = Voice()
    for onset, offset, _, pitch in notes:
        if pitch is not None:
            voice.sing(frame(onset), frame(offset), pitch)
    return [timed(onset, offset, pitch) for onset, offset, pitch, _ in notes], voice


def report_song() -> tuple[list[Note], Voice]:
    line, voice = sung(
        (1.0, 1.5, 72, 72),
        (2.25, 2.5, 76, 74),
        (2.5, 2.75, 76, 64),
        (3.0, 3.5, 79, None),
        (3.99, 4.24, 79, 77),  # just ahead of bar 3's downbeat
    )
    return line, voice.sing(frame(5.0), frame(5.5), 69)


def test_the_report_prints_each_line_shape_by_bar_position_and_time(reported):
    line, voice = report_song()
    others = {"vocal_harmony": [timed(5.1, 5.4, 69)], "choir": [timed(1.0, 1.5, 60)]}
    assert reported(line, voice=voice, others=others) == (
        "bar 2 pos 2  0:02.25  pitch  E5 (2)  audio D5 100%\n"
        "bar 2 pos 4  0:02.50  octave  E5 (2)  audio E4 100%\n"
        "bar 2 pos 8  0:03.00  silent  G5 (4)  audio - 0%\n"
        "bar 3 pos 0  0:03.99  pitch  G5 (2)  audio F5 100%\n"
        "bar 3 pos 8  0:05.00  untranscribed  A4 (4)  +0 dB  also vocal_harmony A4\n"
        "audio check: vocals, 4 of 5 notes unsupported, 1 untranscribed"
    )


def test_the_report_with_nothing_listed_is_its_count_line(reported):
    band = Band().play(frame(1.0), frame(1.5), 72).play(frame(2.0), frame(2.5), 74)
    line = [timed(1.0, 1.5, 72), timed(2.0, 2.5, 74)]
    assert (
        reported(line, band=band) == "audio check: other, 0 of 2 notes unsupported, 0 untranscribed"
    )


def levels_song() -> tuple[list[Note], Band]:
    band = Band().play(10, 50, 72).play(60, 100, 60, -15).play(60, 100, 72)
    band.play(150, 200, 76, -3).play(250, 290, 79)
    return [note(10, 50, 72), note(60, 100, 60), note(250, 290, 79)], band


def test_a_table_12_db_quieter_gives_the_same_report(reported):
    line, voice = report_song()
    report = reported(line, voice=voice)
    assert report.count("\n") == 5
    assert reported(line, voice=voice, shift=12) == report
    line, band = levels_song()
    report = reported(line, band=band)
    assert report.count("\n") == 2
    assert reported(line, band=band, shift=12) == report
