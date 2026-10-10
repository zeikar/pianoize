import json

import pytest
from typer.testing import CliRunner

from pianoize import corrections, refine, timeline
from pianoize.cli import app

PROGRESSION = [("C:maj", 4), ("F:maj", 4), ("G:maj", 4)]
NUMERALS = ("I", "IV", "V")


@pytest.fixture
def original(tmp_path, make_timeline):
    """A three-segment timeline whose numerals are set, so an edit is seen to clear them."""
    data = make_timeline(PROGRESSION)
    for segment, numeral in zip(data["segments"], NUMERALS, strict=True):
        segment.update(numeral=numeral, role="diatonic", function="tonic")
    path = tmp_path / "song.chords.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def edit(start: int, end: int, chord: str = "A:min", bass: str | None = "C", **extra) -> dict:
    fields = {"start_beat": start, "end_beat": end, "chord": chord, "bass": bass}
    return {**fields, "reason": "heard", **extra}


def write_edits(original, *edits, sha256=None):
    path = original.parent / "edits.json"
    digest = sha256 or corrections.sha256(original)
    inputs = {"timeline": {"path": str(original), "sha256": digest}}
    path.write_text(json.dumps({"inputs": inputs, "edits": list(edits)}), encoding="utf-8")
    return path


def refined(original, *edits):
    data = timeline.load(original)
    loaded = refine.load_edits(write_edits(original, *edits), original, data)
    return data, *refine.apply(data, loaded)


def test_an_edit_over_half_a_segment_splits_it(original, tmp_path):
    data, result, changed = refined(original, edit(6, 8, readings={"tsumugi": "Am/C"}))

    segments = result["segments"]
    assert changed == 1
    assert [(s["start_beat"], s["end_beat"]) for s in segments] == [(0, 4), (4, 6), (6, 8), (8, 12)]
    old = data["segments"][1]
    assert segments[1] == old | {"end_beat": 6, "end_time": data["beats"][6]}
    assert segments[2] == old | {
        "start_beat": 6,
        "start_time": data["beats"][6],
        "chord": "A:min",
        "bass": "C",
        "inversion": "first",
        "numeral": None,
        "role": None,
        "function": None,
        "target": None,
        "edited": True,
    }
    assert segments[2]["candidates"] == ["F:maj", "F:min", "F:7"]
    assert timeline.problem(result) is None
    assert data == timeline.load(original)

    out = tmp_path / "song.refined.chords.json"
    refine.write(result, out)
    assert timeline.load(out) == result


def test_a_span_already_on_the_chord_is_not_split_or_marked(original):
    data, result, changed = refined(original, edit(2, 8, chord="F:maj", bass="F"))

    segments = result["segments"]
    assert changed == 1
    assert [(s["start_beat"], s["end_beat"], s["edited"]) for s in segments] == [
        (0, 2, False),
        (2, 4, True),
        (4, 8, False),
        (8, 12, False),
    ]
    assert segments[1]["numeral"] is None
    assert segments[2] == data["segments"][1]


@pytest.mark.parametrize(
    ("edits", "expected"),
    [
        (  # one edit over three segments
            [edit(2, 10, chord="D:min", bass="D")],
            [
                (0, 2, "C:maj", False),
                (2, 4, "D:min", True),
                (4, 8, "D:min", True),
                (8, 10, "D:min", True),
                (10, 12, "G:maj", False),
            ],
        ),
        (  # two edits that touch
            [edit(2, 4), edit(4, 6, chord="D:min", bass="D")],
            [
                (0, 2, "C:maj", False),
                (2, 4, "A:min", True),
                (4, 6, "D:min", True),
                (6, 8, "F:maj", False),
                (8, 12, "G:maj", False),
            ],
        ),
        (  # an edit ending on the last beat
            [edit(10, 12)],
            [(0, 4, "C:maj", False), (4, 8, "F:maj", False), (8, 10, "G:maj", False),
             (10, 12, "A:min", True)],
        ),
    ],
)  # fmt: skip
def test_edited_parts_tile_and_take_their_times_from_the_beats(original, edits, expected):
    data, result, changed = refined(original, *edits)

    segments = result["segments"]
    assert [(s["start_beat"], s["end_beat"], s["chord"], s["edited"]) for s in segments] == expected
    assert changed == sum(edited for *_, edited in expected)
    beats, duration = data["beats"], data["source"]["duration"]
    heard = {b: s for s in data["segments"] for b in range(s["start_beat"], s["end_beat"])}
    for segment in segments:
        start, end = segment["start_beat"], segment["end_beat"]
        assert segment["start_time"] == beats[start]
        assert segment["end_time"] == (beats[end] if end < len(beats) else duration)
        assert segment["candidates"] == heard[start]["candidates"]
    assert segments[-1]["end_time"] == duration
    assert timeline.problem(result) is None


@pytest.mark.parametrize(
    ("edits", "message"),
    [
        ([edit(0, 4), edit(2, 6)], "edits[1]: beats 2-6 overlap edits[0] (0-4)"),
        ([edit(2, 6), edit(0, 4)], "edits[1]: beats 0-4 overlap edits[0] (2-6)"),
        ([edit(0, 2), edit(10, 13)], "edits[1]: beats 10-13 are not inside the timeline"),
        ([edit(4, 6, chord="F:maj", bass="F")], "edits[0]: changes nothing"),
        ([edit(0, 2, chord="Bb:maj", bass="A#")], "edits[0]: chord 'Bb:maj'"),
        ([edit(0, 2, bass="Db")], "edits[0]: bass 'Db'"),
        ([edit(0, 2, chord="N", bass="C")], "edits[0]: N takes no bass"),
        ([edit(0, 2, root="A")], "edits[0] does not take root"),
    ],
)
def test_bad_edits_are_refused_naming_the_edit(original, edits, message):
    with pytest.raises(refine.RefineError) as err:
        refined(original, *edits)

    assert message in str(err.value)


def test_edits_for_another_timeline_are_refused(original):
    path = write_edits(original, edit(0, 2), sha256="0" * 64)

    with pytest.raises(refine.RefineError, match="inputs.timeline: sha256 does not match"):
        refine.load_edits(path, original, timeline.load(original))


def test_write_refuses_a_number_json_parse_cannot_read(tmp_path, make_timeline):
    data = make_timeline(PROGRESSION)
    data["source"]["confidence"] = float("nan")
    out = tmp_path / "song.refined.chords.json"

    with pytest.raises(refine.RefineError, match="a number JSON can't write"):
        refine.write(data, out)
    assert not out.exists()


def _cli(original, edits, out):
    return CliRunner().invoke(app, ["refine-timeline", str(original), str(edits), "-o", str(out)])


def test_cli_writes_a_timeline_the_viewer_opens(original, tmp_path):
    edits = write_edits(original, edit(6, 8))
    out = tmp_path / "song.refined.chords.json"

    result = _cli(original, edits, out)

    assert result.exit_code == 0
    assert result.output == "segments changed: 1\n"
    text = out.read_text(encoding="utf-8")
    assert text.endswith("}\n")
    assert timeline.problem(json.loads(text)) is None
    again = tmp_path / "again.refined.chords.json"
    assert _cli(original, edits, again).exit_code == 0
    assert again.read_bytes() == out.read_bytes()


def test_cli_refuses_to_overwrite_an_input(original):
    edits = write_edits(original, edit(6, 8))
    before = {path: path.read_bytes() for path in (original, edits)}

    for target in before:
        result = _cli(original, edits, target)
        assert result.exit_code == 2
        assert "would overwrite an input" in " ".join(result.output.split())
    assert {path: path.read_bytes() for path in before} == before


def test_cli_reports_bad_edits_without_a_traceback(original, tmp_path):
    edits = write_edits(original, edit(0, 4), edit(2, 6))
    out = tmp_path / "song.refined.chords.json"

    result = _cli(original, edits, out)

    assert result.exit_code == 1
    assert "error: edits[1]: beats 2-6 overlap edits[0]" in result.output
    assert "Traceback" not in result.output
    assert not out.exists()
