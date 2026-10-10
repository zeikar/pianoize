import json
from dataclasses import asdict

import mido
import pytest
from typer.testing import CliRunner

from pianoize import candidates, corrections, notes, review, synthetic
from pianoize.candidates import Thresholds
from pianoize.cli import app
from pianoize.timeline import beat_position

# tick_midi plays 120 bpm; at 500 ticks per beat a tick is a millisecond, so the notes below are
# (on_ms, off_ms, pitch, velocity).
MS_TICKS = 500


def run(tick_midi, played, bpm=120, offset=0.0, protected=()):
    """Candidates in a cover of `played` against a steady 16-beat timeline."""
    midi = tick_midi(played, ticks_per_beat=MS_TICKS)
    timeline = synthetic.timeline([("C:maj", 16)], bpm=bpm, offset=offset)
    return candidates.find(midi, timeline, set(protected), Thresholds())


def of_kind(found, kind):
    return [c for c in found if c.kind == kind]


def test_short_flags_an_isolated_note_not_one_inside_a_cluster(tick_midi):
    found = run(tick_midi, [(0, 400, 48, 80), (1000, 1020, 72, 80), (1500, 1900, 48, 80)])
    (short,) = of_kind(found, "short")
    assert (short.id, short.category, short.time, short.beat) == (
        "glitch:short:t1000p72",
        "glitch",
        1.0,
        2.0,
    )
    assert short.note == {
        "id": "t1000p72",
        "pitch_name": "C5",
        "on_tick": 1000,
        "off_tick": 1020,
        "velocity": 80,
        "duration_ms": 20.0,
        "protected": False,
    }
    assert short.segment is None
    assert short.measurements == {"duration_ms": 20.0, "nearest_onset_ms": 500.0}
    assert short.suggested == {"op": "delete", "note": "t1000p72"}

    in_cluster = [(1000, 1400, 60, 80), (1010, 1030, 72, 80)]
    assert of_kind(run(tick_midi, in_cluster), "short") == []


def test_stutter_flags_the_second_attack_and_deletes_the_shorter_strike(tick_midi):
    # A 10 ms sliver, then the held note: the sliver goes, though the held note is the anchor.
    (stutter,) = of_kind(run(tick_midi, [(1000, 1010, 64, 80), (1030, 1400, 64, 80)]), "stutter")
    assert stutter.id == "glitch:stutter:t1030p64"
    assert stutter.measurements == {"after_ms": 30.0, "previous": "t1000p64"}
    assert stutter.suggested == {"op": "delete", "note": "t1000p64"}

    (stutter,) = of_kind(run(tick_midi, [(1000, 1080, 64, 80), (1080, 1100, 64, 80)]), "stutter")
    assert stutter.suggested == {"op": "delete", "note": "t1080p64"}

    assert of_kind(run(tick_midi, [(1000, 1250, 64, 80), (1300, 1600, 64, 80)]), "stutter") == []


def eighths(velocities):
    """Eighth notes from 0 s on five pitches, so no pitch is struck twice in a row."""
    return [(i * 250, i * 250 + 200, 60 + i % 5, v) for i, v in enumerate(velocities)]


def test_velocity_flags_a_spike_over_the_local_median(tick_midi):
    (spike,) = of_kind(run(tick_midi, eighths([70] * 8 + [110] + [70] * 8)), "velocity")
    assert spike.id == "glitch:velocity:t2000p63"
    assert json.dumps(spike.measurements) == '{"velocity": 110, "median": 70.0, "above": 40.0}'
    assert spike.suggested == {"op": "modify", "note": "t2000p63", "velocity": 70}
    assert spike.context == [  # a beat either way
        "t1500p61 0:01.50 C#4 200ms v70",
        "t1750p62 0:01.75 D4 200ms v70",
        "t2000p63 0:02.00 D#4 200ms v110",
        "t2250p64 0:02.25 E4 200ms v70",
        "t2500p60 0:02.50 C4 200ms v70",
    ]

    even = eighths([70, 75, 80, 85] * 4)
    assert of_kind(run(tick_midi, even), "velocity") == []


def test_velocity_compares_the_melody_with_the_melody(tick_midi):
    # Melody eighths at 95 over accompaniment eighths at 70: the voicing, not a spike.
    def voiced(melody_velocities):
        accompaniment = [(i * 250, i * 250 + 200, 48 + i % 5, 70) for i in range(16)]
        melody = [(i * 250, i * 250 + 200, 72 + i % 5, v) for i, v in enumerate(melody_velocities)]
        protected = {f"t{on}p{pitch}" for on, _, pitch, _ in melody}
        return accompaniment + melody, protected

    played, protected = voiced([95] * 16)
    assert of_kind(run(tick_midi, played, protected=protected), "velocity") == []

    played, protected = voiced([95] * 8 + [120] + [95] * 7)
    (spike,) = of_kind(run(tick_midi, played, protected=protected), "velocity")
    assert spike.id == "glitch:velocity:t2000p75"
    assert spike.measurements == {"velocity": 120, "median": 95.0, "above": 25.0}


def test_velocity_skips_a_note_alone_in_its_role(tick_midi):
    # The only melody note within a beat: against the accompaniment it would be its voicing.
    velocities = [70] * 8 + [110] + [70] * 8
    assert of_kind(run(tick_midi, eighths(velocities), protected={"t2000p63"}), "velocity") == []


def test_off_grid_flags_a_late_note_and_keeps_its_length(tick_midi):
    # 60 bpm: a beat is 1 s and its sixteenths are 250 ms apart.
    played = [(0, 200, 48, 80), (1070, 1300, 60, 80), (2000, 2200, 48, 80)]
    (late,) = of_kind(run(tick_midi, played, bpm=60), "off-grid")
    assert (late.id, late.category) == ("timing:off-grid:t1070p60", "timing")
    assert late.measurements == {"off_ms": 70.0, "subdivisions": 4, "grid_beat": 1.0}
    assert late.suggested == {"op": "modify", "note": "t1070p60", "on_tick": 1000, "off_tick": 1230}


def test_off_grid_suggests_nothing_that_would_overlap_a_note_of_its_pitch(tick_midi):
    # Moved back to 1 s, the late C4 would sound over the C4 still held until 1.05 s.
    played = [(500, 1050, 60, 80), (1070, 1300, 60, 80), (2000, 2200, 48, 80)]
    (late,) = of_kind(run(tick_midi, played, bpm=60), "off-grid")
    assert late.id == "timing:off-grid:t1070p60"
    assert late.suggested is None


def test_off_grid_skips_an_ordered_roll_after_its_first_note(tick_midi):
    def spread(pitches):  # 40 ms apart from beat 1
        return [(1000 + 40 * i, 1600, pitch, 80) for i, pitch in enumerate(pitches)]

    assert of_kind(run(tick_midi, spread([48, 55, 60, 64, 67, 72]), bpm=60), "off-grid") == []
    # Turning at every note, no three attacks go one way, so every note is checked.
    zigzag = of_kind(run(tick_midi, spread([48, 60, 55, 67, 64, 72]), bpm=60), "off-grid")
    assert [c.note["id"] for c in zigzag] == ["t1080p55", "t1120p67", "t1160p64", "t1200p72"]


@pytest.mark.parametrize("pitch", [72, 40])
def test_a_note_just_after_a_block_chord_is_no_roll(tick_midi, pitch):
    chord = [(1000, 1500, 48, 80), (1000, 1500, 52, 80), (1010, 1500, 55, 80)]
    found = of_kind(run(tick_midi, [*chord, (1055, 1500, pitch, 80)], bpm=60), "off-grid")
    assert [c.id for c in found] == [f"timing:off-grid:t1055p{pitch}"]


def test_a_triplet_beat_takes_the_three_grid(tick_midi):
    # 60 bpm: on sixteenths the second and third triplet notes would be 83 ms off.
    triplet = [(2000, 2200, 60, 80), (2333, 2500, 64, 80), (2667, 2900, 67, 80)]
    assert of_kind(run(tick_midi, triplet, bpm=60), "off-grid") == []

    # One triplet note among sixteenths doesn't cut the deviation, so the beat keeps 4.
    lone = [(2000, 2200, 60, 80), (2250, 2500, 64, 80), (2667, 2900, 67, 80)]
    (flagged,) = of_kind(run(tick_midi, lone, bpm=60), "off-grid")
    assert flagged.id == "timing:off-grid:t2667p67"
    assert flagged.measurements == {"off_ms": -83.0, "subdivisions": 4, "grid_beat": 2.75}

    # One attack near a triplet line is not enough to switch the beat.
    stray = [(2000, 2200, 60, 80), (2330, 2500, 64, 80)]
    (flagged,) = of_kind(run(tick_midi, stray, bpm=60), "off-grid")
    assert flagged.measurements == {"off_ms": 80.0, "subdivisions": 4, "grid_beat": 2.25}


def test_the_grid_continues_before_the_first_beat(tick_midi):
    # The first beat is at 2 s, so beat -1 is at 1 s and beat -0.5 at 1.5 s.
    played = [(1070, 1200, 60, 80), (1500, 1700, 62, 80)]
    (early,) = of_kind(run(tick_midi, played, bpm=60, offset=2.0), "off-grid")
    assert (early.id, early.beat) == ("timing:off-grid:t1070p60", -0.93)
    assert early.measurements["grid_beat"] == -1.0
    assert early.suggested["on_tick"] == 1000


def attacks(counts):
    """`counts[b]` attacks 70 ms apart from the start of each 1 s beat b."""
    return [
        (b * 1000 + 70 * k, b * 1000 + 70 * k + 50, 60 + k % 2 * 7, 80)
        for b, count in enumerate(counts)
        for k in range(count)
    ]


@pytest.mark.parametrize(
    ("counts", "flagged"),
    [
        ([3, 3, 3, 3, 12, 3, 3, 3, 3], '{"attacks": 12, "median": 3.0}'),
        ([3, 3, 3, 3, 1, 3, 3, 3, 3], '{"attacks": 1, "median": 3.0}'),
        ([3] * 9, None),
        ([1, 1, 1, 1, 0, 1, 1, 1, 1], None),  # a rest in a sparse passage is no dip
    ],
)
def test_density_flags_a_crowded_or_emptied_beat(tick_midi, counts, flagged):
    found = of_kind(run(tick_midi, attacks(counts), bpm=60), "density")
    if flagged is None:
        assert found == []
        return
    (beat,) = found
    assert (beat.id, beat.time, beat.beat, beat.note) == ("timing:density:b4", 4.0, 4.0, None)
    assert beat.segment == {"start_beat": 4, "end_beat": 5, "chord": "C:maj"}
    assert json.dumps(beat.measurements) == flagged
    assert beat.suggested is None


def test_duration_flags_a_note_held_past_eight_beats(tick_midi):
    (held,) = of_kind(run(tick_midi, [(1000, 6000, 48, 80)]), "duration")  # 10 beats at 120 bpm
    assert held.id == "timing:duration:t1000p48"
    assert held.measurements == {"beats": 10.0}
    assert held.suggested == {"op": "modify", "note": "t1000p48", "off_tick": 5000}

    assert of_kind(run(tick_midi, [(1000, 2000, 48, 80)]), "duration") == []


def test_a_note_cut_to_its_suggested_end_is_no_longer_too_long(tick_midi):
    # At 960 ticks per beat against 90 bpm beats, the nearest tick to the eighth beat lies
    # 0.0004 beats past it: the cut note must still count as 8 beats, as printed.
    midi = tick_midi([(1374, 20000, 48, 80)], ticks_per_beat=960)
    timeline = synthetic.timeline([("C:maj", 16)], bpm=90, offset=0.0)
    (held,) = of_kind(candidates.find(midi, timeline, set(), Thresholds()), "duration")
    assert held.suggested == {"op": "modify", "note": "t1374p48", "off_tick": 11614}
    cut = corrections.Edit("modify", "c", "r", note="t1374p48", off_tick=11614)
    spec = corrections.Spec([], [cut])
    (note,) = notes.read(corrections.apply(midi, spec)[0])
    assert beat_position(timeline, note.offset) - beat_position(timeline, note.onset) > 8
    assert of_kind(review.after(midi, spec, timeline, [], Thresholds()), "duration") == []


def test_a_candidate_keeps_its_id_when_an_unrelated_note_moves(tick_midi):
    played = [(0, 400, 48, 80), (1000, 1020, 72, 80), (3000, 3400, 52, 80)]
    moved = [(0, 400, 48, 80), (600, 900, 52, 80), (1000, 1020, 72, 80)]  # now before it
    before = {c.id for c in run(tick_midi, played)}
    after = {c.id for c in run(tick_midi, moved)}
    assert "glitch:short:t1000p72" in before & after


def test_a_protected_note_is_flagged_and_marked(tick_midi):
    found = run(tick_midi, [(1000, 1020, 72, 80)], protected={"t1000p72"})
    (short,) = of_kind(found, "short")
    assert short.note["protected"] is True
    assert short.context == ["t1000p72 0:01.00 C5 20ms v80 *"]


def test_candidates_are_sorted_by_time_then_id(tick_midi):
    # A 9-beat bass under a segment it leaves without a third and fifth, then a 20 ms note that
    # is both isolated and 70 ms late.
    found = run(tick_midi, [(0, 9000, 48, 80), (1070, 1090, 72, 80)], bpm=60)
    assert [c.id for c in found] == [
        "harmony:missing:s0",
        "timing:duration:t0p48",
        "glitch:short:t1070p72",
        "timing:off-grid:t1070p72",
    ]


def test_grid_time_inverts_beat_position_past_both_ends():
    timeline = {"beats": [1.0, 1.5, 2.0, 3.0]}
    for seconds in (0.25, 1.25, 2.5, 4.0):
        position = beat_position(timeline, seconds)
        assert candidates.grid_time(timeline, position) == pytest.approx(seconds)


# The cover's 20 ms C5 at 1 s is isolated, and the melody's C4 then makes it the melody. The C
# major triad keeps the harmony kinds quiet.
COVER = [
    (0, 400, 48, 80),
    (0, 400, 52, 80),
    (0, 400, 55, 80),
    (1000, 1020, 72, 80),
    (1500, 1900, 48, 80),
]
MELODY = [(1000, 1300, 60, 90)]


@pytest.fixture
def files(tmp_path, tick_midi, write_timeline):
    cover = tmp_path / "cover.mid"
    tick_midi(COVER, ticks_per_beat=MS_TICKS).save(cover)
    melody = tmp_path / "melody.mid"
    tick_midi(MELODY, ticks_per_beat=MS_TICKS).save(melody)
    timeline = write_timeline([("C:maj", 16)], name="song.chords.json", offset=0.0)
    return cover, timeline, melody


def _find_cli(cover, timeline, melody, out):
    return CliRunner().invoke(
        app,
        ["find-candidates", str(cover), "--timeline", str(timeline), "--melody", str(melody)]
        + ["-o", str(out)],
    )


def test_cli_writes_the_candidates_and_lists_them(tmp_path, files):
    cover, timeline, melody = files
    out = tmp_path / "candidates.json"
    result = _find_cli(cover, timeline, melody, out)
    assert result.exit_code == 0, result.output
    assert result.stdout == (
        "0:01.0  glitch/short  t1000p72 C5  duration_ms=20.0\n"
        "candidates: 1 glitch, 0 timing, 0 voice, 0 harmony\n"
    )
    data = json.loads(out.read_text(encoding="utf-8"))
    assert list(data) == ["inputs", "thresholds", "candidates"]
    assert data["inputs"] == {
        name: {"path": str(path), "sha256": corrections.sha256(path)}
        for name, path in (("cover", cover), ("timeline", timeline), ("melody", melody))
    }
    assert data["thresholds"] == asdict(Thresholds())
    (short,) = data["candidates"]
    assert list(short) == [
        "id",
        "category",
        "kind",
        "time",
        "beat",
        "note",
        "segment",
        "measurements",
        "context",
        "suggested",
    ]
    assert short["note"]["protected"] is True
    assert short["suggested"] == {"op": "delete", "note": "t1000p72"}

    first = out.read_bytes()
    assert _find_cli(cover, timeline, melody, out).exit_code == 0
    assert out.read_bytes() == first


@pytest.mark.parametrize("target", [0, 1, 2])
def test_cli_refuses_to_overwrite_an_input(files, target):
    before = [path.read_bytes() for path in files]
    result = _find_cli(*files, files[target])
    assert result.exit_code == 2
    assert "would overwrite an input" in " ".join(result.output.split())
    assert [path.read_bytes() for path in files] == before


def _on_two_channels(track):
    for message in track:
        if message.type in ("note_on", "note_off") and message.note == 72:
            message.channel = 1


def _never_ended(track):
    track.append(mido.Message("note_on", note=84, velocity=80, time=0))


@pytest.mark.parametrize(
    ("spoil", "message"),
    [
        (_on_two_channels, "notes sit on 2 channels"),
        (_never_ended, "note t1900p84 has no note-off of its own"),
    ],
)
def test_cli_refuses_a_cover_the_applier_refuses(tmp_path, files, tick_midi, spoil, message):
    cover, timeline, melody = files
    midi = tick_midi(COVER, ticks_per_beat=MS_TICKS)
    spoil(midi.tracks[0])
    midi.save(cover)
    out = tmp_path / "candidates.json"
    result = _find_cli(cover, timeline, melody, out)
    assert result.exit_code == 1
    assert f"error: {cover}: {message}" in " ".join(result.output.split())
    assert not out.exists()


def test_cli_reports_a_bad_timeline_without_a_traceback(tmp_path, files):
    cover, timeline, melody = files
    timeline.write_text('{"schema_version": 10}', encoding="utf-8")
    result = _find_cli(cover, timeline, melody, tmp_path / "candidates.json")
    assert result.exit_code == 1
    assert "schema_version is 10" in result.output
    assert "Traceback" not in result.output


def test_three_quick_strikes_never_suggest_deleting_one_note_twice(tick_midi):
    # The 5 ms middle strike is the shorter of both pairs.
    played = [(1000, 1030, 64, 80), (1040, 1045, 64, 80), (1060, 1400, 64, 80)]
    found = of_kind(run(tick_midi, played), "stutter")
    assert [(c.id, c.suggested) for c in found] == [
        ("glitch:stutter:t1040p64", {"op": "delete", "note": "t1040p64"}),
        ("glitch:stutter:t1060p64", None),
    ]


def test_names_reach_every_note_a_candidate_mentions(tick_midi):
    # A sliver, then the held note: the stutter names both, in its id, note, measurements,
    # suggestion and context.
    midi = tick_midi([(1000, 1010, 64, 80), (1030, 1400, 64, 80)], ticks_per_beat=MS_TICKS)
    timeline = synthetic.timeline([("C:maj", 16)], offset=0.0)
    names = {"t1000p64": "t900p64", "t1030p64": "add-held"}
    (stutter,) = of_kind(candidates.find(midi, timeline, set(), Thresholds(), names), "stutter")
    assert stutter.id == "glitch:stutter:add-held"
    assert stutter.note["id"] == "add-held"
    assert stutter.measurements["previous"] == "t900p64"
    assert stutter.suggested == {"op": "delete", "note": "t900p64"}
    assert stutter.context == ["t900p64 0:01.00 E4 10ms v80", "add-held 0:01.03 E4 370ms v80"]


def chords(tick_midi, played, progression, protected=()):
    """Candidates in a cover of `played` against `progression` at 120 bpm from 0 s: a beat is
    500 ms."""
    midi = tick_midi(played, ticks_per_beat=MS_TICKS)
    timeline = synthetic.timeline(progression, offset=0.0)
    return candidates.find(midi, timeline, set(protected), Thresholds())


def held(pitches, on=0, off=2000):
    return [(on, off, pitch, 80) for pitch in pitches]


def twice(pitches):
    """The pitches struck together on beat 0 and again on beat 2."""
    return held(pitches, 0, 1000) + held(pitches, 1000, 2000)


def test_a_foreign_triad_over_the_chord_is_flagged_with_its_notes(tick_midi):
    # Over C2, a C# major triad for the whole C major segment.
    found = chords(tick_midi, held([36, 49, 53, 56]), [("C:maj", 4)])
    (flagged,) = of_kind(found, "coverage")
    assert (flagged.id, flagged.category, flagged.time, flagged.beat) == (
        "harmony:coverage:s0",
        "harmony",
        0.0,
        0.0,
    )
    assert flagged.segment == {"start_beat": 0, "end_beat": 4, "chord": "C:maj"}
    assert flagged.note is None
    assert flagged.suggested is None

    def clash(pitch, name, below, above):
        return {"note": f"t0p{pitch}", "pitch_name": name, "on_tick": 0, "off_tick": 2000,
                "below": below, "above": above}  # fmt: skip

    assert flagged.measurements == {
        "coverage": 0.25,
        "missing": ["E", "G"],
        "clashes": [clash(49, "C#3", 48, 52), clash(53, "F3", 52, 55), clash(56, "G#3", 55, 60)],
    }
    assert flagged.context == [
        "t0p36 0:00.00 C2 2000ms v80",
        "t0p49 0:00.00 C#3 2000ms v80",
        "t0p53 0:00.00 F3 2000ms v80",
        "t0p56 0:00.00 G#3 2000ms v80",
    ]
    # Struck once, the segment is no missing candidate; the coverage one names what it lacks.
    assert of_kind(found, "missing") == []


@pytest.mark.parametrize(
    "pitches",
    [[36, 52, 55, 58], [36, 52, 55, 62], [36, 52, 55, 61]],
    ids=["seventh", "ninth", "c-sharp"],
)
def test_one_foreign_voice_of_four_keeps_coverage_above_the_cutoff(tick_midi, pitches):
    # Coverage weighs time, not names: a seventh, an added ninth or any other foreign voice
    # sounding as long as each of three chord tones leaves coverage at 0.75.
    found = chords(tick_midi, held(pitches), [("C:maj", 4)])
    assert [c for c in found if c.category == "harmony"] == []


@pytest.mark.parametrize(
    ("line", "listed"),
    [
        ([(0, 250, 64, 80), (250, 500, 65, 80), (500, 750, 67, 80)], False),
        ([(250, 500, 64, 80), (500, 750, 65, 80), (750, 1000, 67, 80)], True),  # on the beat
        ([(250, 500, 65, 80)], True),  # no note a step away before or after it
    ],
    ids=["passing", "on-the-beat", "no-neighbours"],
)
def test_a_short_stepwise_note_off_the_beat_passes(tick_midi, line, listed):
    # A foreign chord flags the segment; over it an F4, in an E4-F4-G4 line or alone. A short
    # F4 between the beats, approached and left by step, is a passing tone.
    found = chords(tick_midi, held([49, 53, 56]) + line, [("C:maj", 4)])
    (flagged,) = of_kind(found, "coverage")
    clashing = [c["note"] for c in flagged.measurements["clashes"]]
    (passing,) = (f"t{on}p65" for on, _, pitch, _ in line if pitch == 65)
    assert (passing in clashing) is listed
    assert {"t0p49", "t0p53", "t0p56"} <= set(clashing)


@pytest.mark.parametrize(
    ("played", "progression", "missing"),
    [
        (twice([36]), [("C:maj", 4)], ["E", "G"]),
        (twice([36, 48]), [("C:maj", 4)], ["E", "G"]),
        (twice([36, 52, 55]), [("C:maj", 4)], None),
        (held([36]), [("C:maj", 4)], None),
        (held([36, 48]), [("C:maj", 4)], None),  # two notes, one attack
        (twice([34, 48, 52, 55]), [("C:maj", 4, "A#")], None),
        (twice([36, 52, 55]), [("C:maj", 4, "A#")], ["A#"]),
    ],
    ids=["root", "octave", "triad", "one-attack", "one-octave", "slash-bass", "no-slash-bass"],
)
def test_missing_names_the_tones_never_sounded(tick_midi, played, progression, missing):
    found = chords(tick_midi, played, progression)
    flagged = of_kind(found, "missing")
    if missing is None:
        assert flagged == []
        return
    (flagged,) = flagged
    assert flagged.id == "harmony:missing:s0"
    assert flagged.measurements == {"missing": missing}
    assert of_kind(found, "coverage") == []  # the tones it plays are all chord tones


def test_a_segment_under_a_beat_is_not_missing_its_tones(tick_midi):
    # C major for two beats, then G major ending a quarter of a second, half a beat, after its
    # start: the audio ends there.
    def found(end):
        timeline = synthetic.timeline([("C:maj", 2), ("G:maj", 1)], offset=0.0)
        timeline["segments"][-1]["end_time"] = timeline["source"]["duration"] = end
        played = twice([36, 52, 55]) + [(1000, 1100, 43, 80), (1100, 1200, 43, 80)]
        midi = tick_midi(played, ticks_per_beat=MS_TICKS)
        return of_kind(candidates.find(midi, timeline, set(), Thresholds()), "missing")

    assert found(1.25) == []
    assert [(c.id, c.measurements) for c in found(1.5)] == [
        ("harmony:missing:s2", {"missing": ["B", "D"]})
    ]


def test_melody_notes_are_left_out_of_coverage_but_sound_their_tones(tick_midi):
    # C2 and G2 twice under a melody F5 held for three beats, then E5.
    accompaniment = held([36, 43], 0, 250) + held([36, 43], 250, 500)
    melody = [(0, 1500, 77, 90), (1500, 2000, 76, 90)]
    protected = {"t0p77", "t1500p76"}
    found = chords(tick_midi, accompaniment + melody, [("C:maj", 4)], protected)
    assert [c for c in found if c.category == "harmony"] == []

    # Counted as accompaniment, the F5 would pull coverage to a half.
    (flagged,) = of_kind(chords(tick_midi, accompaniment + melody, [("C:maj", 4)]), "coverage")
    assert flagged.measurements["coverage"] == 0.5
    assert [c["note"] for c in flagged.measurements["clashes"]] == ["t0p77"]

    # Without the melody's E5 the segment leaves out its third.
    found = chords(tick_midi, accompaniment + [(0, 2000, 77, 90)], [("C:maj", 4)], {"t0p77"})
    (flagged,) = of_kind(found, "missing")
    assert flagged.measurements == {"missing": ["E"]}


def basses(pitches, step=250):
    return [(i * step, i * step + step - 10, pitch, 80) for i, pitch in enumerate(pitches)]


def test_leap_compares_the_basses_of_consecutive_chords(tick_midi):
    # Octave figures in eighths: C2-C3 under C, then F2-F3 under F, a fourth up.
    octaves = basses([36, 48, 36, 48, 41, 53, 41, 53])
    assert of_kind(chords(tick_midi, octaves, [("C:maj", 2), ("F:maj", 2)]), "leap") == []

    # Under D# major the bass starts on D#3, 15 semitones over the C2 that began C major.
    jumped = basses([36, 43, 36, 43, 51, 58, 51, 58])
    (leap,) = of_kind(chords(tick_midi, jumped, [("C:maj", 2), ("D#:maj", 2)]), "leap")
    assert leap.id == "voice:leap:t1000p51"
    assert leap.measurements == {"semitones": 15, "previous": "t0p36"}
    assert leap.suggested is None

    # A 15-semitone figure inside one chord is its texture.
    figure = basses([36, 51, 36, 51, 36, 51, 36, 51])
    assert of_kind(chords(tick_midi, figure, [("C:maj", 4)]), "leap") == []


def test_register_flags_a_beat_whose_bass_moves_past_an_octave(tick_midi):
    # Two bass notes a beat: C2 C2, then D3 E3.
    (jump,) = of_kind(chords(tick_midi, basses([36, 36, 50, 52]), [("C:maj", 4)]), "register")
    assert (jump.id, jump.time, jump.note) == ("voice:register:b1", 0.5, None)
    assert jump.segment == {"start_beat": 1, "end_beat": 2, "chord": "C:maj"}
    assert jump.measurements == {"semitones": 15.0, "median": 51.0, "previous_median": 36.0}

    assert of_kind(chords(tick_midi, basses([36, 36, 43, 48]), [("C:maj", 4)]), "register") == []


# C major for two beats, then C/E from 1 s: the bass should move to E there.
TO_E = [("C:maj", 2), ("C:maj", 2, "E")]


def test_bass_late_flags_a_bass_that_reaches_the_change_half_a_beat_late(tick_midi):
    # C2 struck again at the change, E2 half a beat later: moved onto the change the E2 would
    # only stack over the C2, so nothing is suggested.
    played = [(0, 1000, 36, 80), (1000, 1240, 36, 80), (1250, 2000, 40, 80)]
    (late,) = of_kind(chords(tick_midi, played, TO_E), "bass-late")
    assert late.id == "voice:bass-late:t1250p40"
    assert late.measurements == {"late_beats": 0.5, "bass": "E", "first": "t1000p36"}
    assert late.suggested is None

    # Nothing at the change and a C2 a quarter of a beat after it: the E2 can move there.
    played = [(0, 1000, 36, 80), (1125, 1240, 36, 80), (1250, 2000, 40, 80)]
    (late,) = of_kind(chords(tick_midi, played, TO_E), "bass-late")
    assert late.measurements == {"late_beats": 0.5, "bass": "E", "first": "t1125p36"}
    assert late.suggested == {"op": "modify", "note": "t1250p40", "on_tick": 1000, "off_tick": 1750}

    on_time = [(0, 1000, 36, 80), (1000, 2000, 40, 80)]
    assert of_kind(chords(tick_midi, on_time, TO_E), "bass-late") == []


def test_bass_late_flags_the_bass_struck_over_a_lower_note_at_the_change(tick_midi):
    played = [(0, 1000, 36, 80), (1000, 2000, 36, 80), (1000, 2000, 52, 80)]
    (late,) = of_kind(chords(tick_midi, played, TO_E), "bass-late")
    assert late.id == "voice:bass-late:t1000p52"
    assert late.measurements == {"late_beats": 0.0, "bass": "E", "first": "t1000p36"}
    assert late.suggested is None

    # A bass that arrives late is the candidate, though an E3 sounds over the C2 at the change.
    played = [(0, 1000, 36, 80), (1000, 1240, 36, 80), (1000, 2000, 52, 80), (1250, 2000, 40, 80)]
    (late,) = of_kind(chords(tick_midi, played, TO_E), "bass-late")
    assert (late.id, late.measurements["late_beats"]) == ("voice:bass-late:t1250p40", 0.5)


def test_a_bass_moved_onto_the_change_is_fixed_only_as_the_lowest_note(tick_midi):
    timeline = synthetic.timeline(TO_E, offset=0.0)
    move = ("modify", {"note": "t1250p40", "on_tick": 1000, "off_tick": 1750})

    def late_after(played, *edits):
        midi = tick_midi(played, ticks_per_beat=MS_TICKS)
        spec = corrections.Spec([], [corrections.Edit(op, "c", "r", **f) for op, f in edits])
        found = review.after(midi, spec, timeline, [], Thresholds())
        return [c.id for c in of_kind(found, "bass-late")]

    # The suggested move, with nothing at the change, leaves the E2 lowest there.
    assert late_after([(0, 1000, 36, 80), (1125, 1240, 36, 80), (1250, 2000, 40, 80)], move) == []
    # Moved over the C2 still struck at the change, it is still no bass, under its own id, though
    # the chord there has an E3 over it too.
    stacked = [(0, 1000, 36, 80), (1000, 1240, 36, 80), (1000, 2000, 52, 80), (1250, 2000, 40, 80)]
    assert late_after(stacked, move) == ["voice:bass-late:t1250p40"]
    assert late_after(stacked, move, ("delete", {"note": "t1000p36"})) == []


@pytest.mark.parametrize(
    ("first", "arrives", "late"),
    [
        (980, 1250, 0.5),  # a first bass note 20 ms early is still played at the change
        (1000, 1510, 1.02),  # 10 ms past the next beat is still on it
        (1000, 1100, None),  # under a quarter of a beat
        (1000, 1625, None),  # past the next beat
    ],
)
def test_bass_late_window(tick_midi, first, arrives, late):
    played = [(0, first - 20, 36, 80), (first, arrives - 10, 36, 80), (arrives, 2000, 40, 80)]
    found = of_kind(chords(tick_midi, played, TO_E), "bass-late")
    assert [c.measurements["late_beats"] for c in found] == ([] if late is None else [late])


def test_bass_late_suggests_nothing_that_would_overlap_a_note_of_its_pitch(tick_midi):
    # Moved to 1 s, the late E2 would sound over the E2 held until 1.1 s.
    played = [(0, 500, 36, 80), (500, 1100, 40, 80), (1125, 1240, 36, 80), (1250, 2000, 40, 80)]
    (late,) = of_kind(chords(tick_midi, played, TO_E), "bass-late")
    assert late.id == "voice:bass-late:t1250p40"
    assert late.suggested is None
