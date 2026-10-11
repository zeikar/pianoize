import json
from itertools import accumulate

import mido
import pytest
from typer.testing import CliRunner

from pianoize import corrections, notes
from pianoize.cli import app
from pianoize.corrections import CorrectionError

# 480 ticks per beat at 120 bpm. The top notes, t0p72 and t480p74, carry the melody.
COVER = [(0, 480, 72, 80), (0, 480, 60, 70), (480, 960, 74, 80), (480, 960, 62, 70)]
MELODY = [(0, 480, 60, 90), (480, 960, 62, 90)]
CC64 = mido.Message("control_change", control=64, value=127)
MARKER = mido.MetaMessage("marker", text="G:maj")


@pytest.fixture
def files(tmp_path, tick_midi):
    cover = tmp_path / "cover.mid"
    tick_midi(COVER, tempos=[(0, 120), (960, 90)], meta=[(240, CC64), (480, MARKER)]).save(cover)
    melody = tmp_path / "melody.mid"
    tick_midi(MELODY).save(melody)
    return cover, melody


def fix(candidate="c1", action="fix", **fields):
    return {"candidate": candidate, "time": 0.5, "action": action, "reason": "a slip", **fields}


def edit(op, candidate="c1", **fields):
    return {"op": op, "candidate": candidate, "reason": "fixes it", **fields}


def write_spec(tmp_path, cover, melody, verdicts=None, edits=None, **fields):
    data = {
        "spec_version": 1,
        "inputs": {
            "cover": {"path": str(cover), "sha256": corrections.sha256(cover)},
            "melody": {"path": str(melody), "sha256": corrections.sha256(melody)},
        },
        **fields,
    }
    if verdicts is not None:
        data["verdicts"] = verdicts
    if edits is not None:
        data["edits"] = edits
    path = tmp_path / "spec.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def corrected(tmp_path, cover, melody, verdicts, edits, name="out.mid"):
    spec = corrections.load(write_spec(tmp_path, cover, melody, verdicts, edits), cover, melody)
    result, identity = corrections.apply(mido.MidiFile(cover), spec)
    out = tmp_path / name
    corrections.write(result, out)
    return out, identity


def played(midi):
    return [(n.on_tick, n.off_tick, n.pitch, n.velocity) for n in notes.read(midi)]


def ticks_of(midi, kind):
    track = midi.tracks[0]
    ticks = accumulate(m.time for m in track)
    return [tick for tick, m in zip(ticks, track, strict=True) if m.type == kind]


THREE_EDITS = (
    [fix("c1"), fix("c2"), fix("c3")],
    [
        edit("delete", "c1", note="t0p60"),
        edit("modify", "c2", note="t480p62", pitch=64, on_tick=600),
        edit("add", "c3", id="low", pitch=48, on_tick=0, off_tick=960, velocity=60),
    ],
)


def test_an_empty_spec_writes_the_cover_byte_for_byte(tmp_path, files):
    cover, melody = files
    spec = corrections.load(write_spec(tmp_path, cover, melody), cover, melody)
    result, identity = corrections.apply(mido.MidiFile(cover), spec)
    out = tmp_path / "out.mid"
    corrections.write(result, out)
    assert out.read_bytes() == cover.read_bytes()
    assert identity == {n.id: n.id for n in notes.read(mido.MidiFile(cover))}


def test_the_same_spec_gives_identical_bytes(tmp_path, files):
    first, _ = corrected(tmp_path, *files, *THREE_EDITS, name="first.mid")
    second, _ = corrected(tmp_path, *files, *THREE_EDITS, name="second.mid")
    assert first.read_bytes() == second.read_bytes()


def test_delete_modify_and_add(tmp_path, files):
    out, identity = corrected(tmp_path, *files, *THREE_EDITS)
    result = mido.MidiFile(out)
    assert played(result) == [
        (0, 960, 48, 60),
        (0, 480, 72, 80),
        (480, 960, 74, 80),
        (600, 960, 64, 70),
    ]
    assert identity == {
        "t0p48": "add-low",
        "t0p72": "t0p72",
        "t480p74": "t480p74",
        "t600p64": "t480p62",
    }
    assert ticks_of(result, "control_change") == [240]
    assert ticks_of(result, "marker") == [480]
    assert ticks_of(result, "set_tempo") == [0, 960]


def test_edited_messages_are_ordered_around_the_untouched_ones(tmp_path, tick_midi):
    cover, melody = tmp_path / "cover.mid", tmp_path / "melody.mid"
    tick_midi([(0, 480, 60, 80), (480, 960, 60, 80), (0, 480, 64, 80)]).save(cover)
    tick_midi([]).save(melody)
    out, _ = corrected(
        tmp_path,
        cover,
        melody,
        [fix("c1")],
        [
            edit("modify", note="t0p60", velocity=50),
            edit("add", id="d", pitch=60, on_tick=960, off_tick=1440, velocity=90),
        ],
    )
    result = mido.MidiFile(out)
    track = result.tracks[0]
    sequence = [
        (tick, m.type, getattr(m, "note", None))
        for tick, m in zip(accumulate(m.time for m in track), track, strict=True)
    ]
    assert sequence == [
        (0, "note_on", 64),
        (0, "note_on", 60),  # edited: after the last message at its tick
        (480, "note_off", 64),
        (480, "note_off", 60),  # edited: before the first note-on at its tick
        (480, "note_on", 60),
        (960, "note_off", 60),
        (960, "note_on", 60),  # added
        (1440, "note_off", 60),
        (1440, "end_of_track", None),  # pushed to the added note's end
    ]
    assert played(result) == [
        (0, 480, 60, 50),
        (0, 480, 64, 80),
        (480, 960, 60, 80),
        (960, 1440, 60, 90),
    ]


def test_a_fix_verdict_without_an_edit_loads(tmp_path, files):
    cover, melody = files
    path = write_spec(tmp_path, cover, melody, [fix("c1"), fix("c2", action="keep")], [])
    spec = corrections.load(path, cover, melody)
    assert [(v.candidate, v.action) for v in spec.verdicts] == [("c1", "fix"), ("c2", "keep")]


def test_a_protected_note_can_be_retimed(tmp_path, files):
    out, identity = corrected(
        tmp_path, *files, [fix()], [edit("modify", note="t0p72", on_tick=120, velocity=90)]
    )
    assert (120, 480, 72, 90) in played(mido.MidiFile(out))
    assert identity["t120p72"] == "t0p72"


@pytest.mark.parametrize(
    "verdicts, edits, message",
    [
        ([fix()], [edit("delete", note="t1920p62")], r"edits\[0\]: unknown note t1920p62"),
        (
            [fix()],
            [edit("delete", note="t0p60"), edit("modify", note="t0p60", velocity=50)],
            r"edits\[1\]: note t0p60 already has an edit \(edits\[0\]\)",
        ),
        (
            [fix()],
            [
                edit("add", id="x", pitch=50, on_tick=0, off_tick=100, velocity=60),
                edit("add", id="x", pitch=52, on_tick=0, off_tick=100, velocity=60),
            ],
            r"edits\[1\]: id x is taken by edits\[0\]",
        ),
        (
            [fix()],
            [edit("modify", note="t0p60", pitch=60, velocity=70)],
            r"edits\[0\]: modify changes nothing",
        ),
        ([fix()], [edit("modify", note="t0p60")], r"edits\[0\]: modify changes nothing"),
        (
            [fix()],
            [edit("add", id="x", pitch=128, on_tick=0, off_tick=100, velocity=60)],
            r"edits\[0\]: pitch must be an integer 0-127, not 128",
        ),
        (
            [fix()],
            [edit("modify", note="t0p60", velocity=0)],
            r"edits\[0\]: velocity must be an integer 1-127, not 0",
        ),
        (
            [fix()],
            [edit("modify", note="t0p60", pitch=61.5)],
            r"edits\[0\]: pitch must be an integer",
        ),
        (
            [fix()],
            [edit("add", id="x", pitch=50, on_tick=-1, off_tick=100, velocity=60)],
            r"edits\[0\]: on_tick must be an integer 0 or more",
        ),
        (
            [fix()],
            [edit("modify", note="t0p60", on_tick=480)],
            r"edits\[0\]: off_tick 480 must be after on_tick 480",
        ),
        (
            [fix(action="keep")],
            [edit("delete", note="t0p60")],
            r"edits\[0\]: candidate c1 has no fix verdict",
        ),
        ([fix()], [edit("delete", "c2", note="t0p60")], r"edits\[0\]: candidate c2 has no"),
        ([fix(), fix(action="keep")], [], r"verdicts\[1\]: candidate c1 already has a verdict"),
        ([fix(action="maybe")], [], r"verdicts\[0\]: action must be fix or keep"),
        ([fix(time="0:01.2")], [], r"verdicts\[0\]: time must be a finite number"),
        ([fix(time=float("nan"))], [], r"verdicts\[0\]: time must be a finite number"),
        ([fix(reason="")], [], r"verdicts\[0\]: reason must be a non-empty string"),
        ([{"candidate": "c1", "action": "fix"}], [], r"verdicts\[0\] is missing 'time'"),
        ([fix()], [edit("move", note="t0p60")], r"edits\[0\]: op must be delete, modify or add"),
        (
            [fix()],
            [edit("add", id="x", pitch=50, on_tick=0, off_tick=100)],
            r"edits\[0\] is missing 'velocity'",
        ),
        (
            [fix()],
            [edit("add", id="a b", pitch=50, on_tick=0, off_tick=100, velocity=60)],
            r"edits\[0\]: id must match \[A-Za-z0-9_-\]\+",
        ),
        (
            [fix()],
            [edit("delete", note="t0p60", pitch=61)],
            r"edits\[0\]: delete does not take pitch",
        ),
        ([fix()], ["delete t0p60"], r"edits\[0\] must be an object"),
        (
            [fix()],
            [edit("add", id="x", pitch=62, on_tick=240, off_tick=720, velocity=60)],
            r"edits\[0\]: add-x and t480p62 would both sound pitch 62 at tick 480",
        ),
        (
            [fix()],
            [edit("delete", note="t0p60"), edit("modify", note="t480p62", pitch=72, on_tick=240)],
            r"edits\[1\]: t0p72 and t480p62 would both sound pitch 72 at tick 240",
        ),
        (
            [fix()],
            [edit("modify", note="t0p72", pitch=71)],
            r"edits\[0\]: note t0p72 carries the melody, so its pitch stays 72",
        ),
    ],
)
def test_validation_names_the_item(tmp_path, files, verdicts, edits, message):
    cover, melody = files
    path = write_spec(tmp_path, cover, melody, verdicts, edits)
    with pytest.raises(CorrectionError, match=message):
        corrections.load(path, cover, melody)


@pytest.mark.parametrize("name", ["cover", "melody"])
def test_a_hash_mismatch_names_the_input(tmp_path, files, name):
    cover, melody = files
    path = write_spec(tmp_path, cover, melody)
    data = json.loads(path.read_text())
    data["inputs"][name]["sha256"] = "0" * 64
    path.write_text(json.dumps(data))
    with pytest.raises(CorrectionError, match=rf"inputs\.{name}: sha256 does not match"):
        corrections.load(path, cover, melody)


def test_an_unknown_spec_version_is_refused(tmp_path, files):
    path = write_spec(tmp_path, *files, spec_version=2)
    with pytest.raises(CorrectionError, match="spec_version must be 1, not 2"):
        corrections.load(path, *files)


def test_an_unknown_top_level_key_is_refused(tmp_path, files):
    path = write_spec(tmp_path, *files, edit=[edit("delete", note="t0p60")])
    with pytest.raises(CorrectionError, match="the spec does not take edit"):
        corrections.load(path, *files)


STRIKE_60 = mido.Message("note_on", note=60, velocity=80)


@pytest.mark.parametrize(
    "cover_notes, meta",
    [
        ([(0, 480, 60, 80)], [(240, STRIKE_60)]),  # struck again at 240 while sounding
        ([(0, 480, 64, 80)], [(0, STRIKE_60)]),  # never ended: open until the track's end
    ],
)
def test_a_note_without_its_own_note_off_is_refused(tmp_path, files, tick_midi, cover_notes, meta):
    cover, melody = files
    tick_midi(cover_notes, meta=meta).save(cover)
    with pytest.raises(CorrectionError, match=r"cover\.mid: note t0p60 has no note-off of its own"):
        corrections.load(write_spec(tmp_path, cover, melody), cover, melody)


def test_a_note_off_that_ends_no_note_is_refused(tmp_path, files, tick_midi):
    # Retiming the note to 150-250 would leave the stray off at 200 cutting it short.
    cover, melody = files
    stray = [(200, mido.Message("note_off", note=60))]
    tick_midi([(0, 100, 60, 80)], meta=stray).save(cover)
    with pytest.raises(
        CorrectionError, match=r"cover\.mid: track 0 has a note-off for pitch 60 at tick 200"
    ):
        corrections.load(write_spec(tmp_path, cover, melody), cover, melody)


def test_an_added_note_may_not_share_an_id(tmp_path, files, tick_midi):
    cover, melody = files
    zero_length = [
        (480, mido.Message("note_on", note=66, velocity=80)),
        (480, mido.Message("note_off", note=66)),
    ]
    tick_midi(COVER, meta=zero_length).save(cover)
    assert (480, 480, 66, 80) in played(mido.MidiFile(cover))
    path = write_spec(
        tmp_path,
        cover,
        melody,
        [fix()],
        [edit("add", id="x", pitch=66, on_tick=480, off_tick=960, velocity=60)],
    )
    with pytest.raises(
        CorrectionError,
        match=r"edits\[0\]: t480p66 and add-x would both start pitch 66 at tick 480",
    ):
        corrections.load(path, cover, melody)


def test_a_cover_on_two_channels_is_refused(tmp_path, files, tick_midi):
    cover, melody = files
    midi = tick_midi([(0, 100, 60, 80), (0, 100, 64, 80)])
    midi.tracks[0][-1].channel = 1  # the 64's note-on and note-off
    midi.tracks[0][1].channel = 1
    midi.save(cover)
    with pytest.raises(CorrectionError, match="2 channels"):
        corrections.load(write_spec(tmp_path, cover, melody), cover, melody)


def _apply_cli(cover, spec, melody, out):
    return CliRunner().invoke(
        app, ["apply-corrections", str(cover), str(spec), "--melody", str(melody), "-o", str(out)]
    )


def test_cli_writes_the_corrected_cover(tmp_path, files):
    cover, melody = files
    spec = write_spec(tmp_path, cover, melody, *THREE_EDITS)
    out = tmp_path / "out.mid"
    result = _apply_cli(cover, spec, melody, out)
    assert result.exit_code == 0, result.output
    assert result.stdout == "notes: 1 deleted, 1 modified, 1 added\n"
    assert played(mido.MidiFile(out))[0] == (0, 960, 48, 60)


@pytest.mark.parametrize("target", ["cover", "spec", "melody"])
def test_cli_refuses_to_overwrite_an_input(tmp_path, files, target):
    cover, melody = files
    spec = write_spec(tmp_path, cover, melody, *THREE_EDITS)
    inputs = {"cover": cover, "spec": spec, "melody": melody}
    before = {name: path.read_bytes() for name, path in inputs.items()}
    result = _apply_cli(cover, spec, melody, inputs[target])
    assert result.exit_code == 2
    assert "would overwrite an input" in " ".join(result.output.split())
    assert {name: path.read_bytes() for name, path in inputs.items()} == before


def test_cli_reports_a_bad_spec_without_a_traceback(tmp_path, files):
    cover, melody = files
    spec = write_spec(tmp_path, cover, melody, [fix()], [edit("delete", note="t1920p62")])
    out = tmp_path / "out.mid"
    result = _apply_cli(cover, spec, melody, out)
    assert result.exit_code == 1
    assert "error: edits[0]: unknown note t1920p62" in result.output
    assert "Traceback" not in result.output
    assert not out.exists()
