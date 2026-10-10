import json

import pytest
from typer.testing import CliRunner

from pianoize import corrections
from pianoize.cli import app

# A tick is a millisecond (500 ticks per beat at 120 bpm) and the timeline's beats are 1 s apart.
# Under a C major triad, a 20 ms C5 is isolated and 70 ms late, and a 20 ms E5 at 5 s isolated.
COVER = [
    (0, 4000, 48, 80),
    (0, 4000, 52, 80),
    (0, 4000, 55, 80),
    (2070, 2090, 72, 80),
    (5000, 5020, 76, 80),
]
LATE = "timing:off-grid:t2070p72"
FLICK = "glitch:short:t2070p72"
ALONE = "glitch:short:t5000p76"


@pytest.fixture
def files(tmp_path, tick_midi, write_timeline):
    cover = tmp_path / "cover.mid"
    tick_midi(COVER, ticks_per_beat=500).save(cover)
    melody = tmp_path / "melody.mid"
    tick_midi([(7000, 7500, 40, 90)], ticks_per_beat=500).save(melody)
    timeline = write_timeline([("C:maj", 8)], name="song.chords.json", bpm=60, offset=0.0)
    return cover, timeline, melody


def verdict(candidate, action, time, reason="a reason"):
    return {"candidate": candidate, "time": time, "action": action, "reason": reason}


def edit(op, candidate, **fields):
    return {"op": op, "candidate": candidate, "reason": "fixes it", **fields}


def write_spec(tmp_path, files, verdicts, edits=()):
    cover, _, melody = files
    spec = tmp_path / "spec.json"
    data = {
        "spec_version": 1,
        "inputs": {
            "cover": {"sha256": corrections.sha256(cover)},
            "melody": {"sha256": corrections.sha256(melody)},
        },
        "verdicts": verdicts,
        "edits": list(edits),
    }
    spec.write_text(json.dumps(data), encoding="utf-8")
    return spec


def find(files, spec, out, *extra):
    cover, timeline, melody = files
    return CliRunner().invoke(
        app,
        ["find-candidates", str(cover), "--timeline", str(timeline), "--melody", str(melody)]
        + ["--spec", str(spec), "-o", str(out), *extra],
    )


def test_the_original_cover_has_three_candidates(tmp_path, files):
    cover, timeline, melody = files
    out = tmp_path / "candidates.json"
    result = CliRunner().invoke(
        app,
        ["find-candidates", str(cover), "--timeline", str(timeline), "--melody", str(melody)]
        + ["-o", str(out)],
    )
    assert result.exit_code == 0, result.output
    found = json.loads(out.read_text(encoding="utf-8"))["candidates"]
    assert [c["id"] for c in found] == [FLICK, LATE, ALONE]


def test_candidates_after_the_spec_keep_the_original_ids(tmp_path, files):
    # The late flick moves onto the beat and stays a flick; the lone E5 gives way to an added
    # flick at 6 s.
    verdicts = [verdict(LATE, "fix", 2.07), verdict(ALONE, "fix", 5.0)]
    edits = [
        edit("modify", LATE, note="t2070p72", on_tick=2000, off_tick=2020),
        edit("delete", ALONE, note="t5000p76"),
        edit("add", ALONE, id="blip", pitch=84, on_tick=6000, off_tick=6010, velocity=80),
    ]
    spec = write_spec(tmp_path, files, verdicts, edits)
    out = tmp_path / "after.json"
    result = find(files, spec, out)
    assert result.exit_code == 1
    data = json.loads(out.read_text(encoding="utf-8"))
    assert list(data["inputs"]) == ["cover", "timeline", "melody", "spec"]
    moved, added = data["candidates"]
    assert moved["id"] == FLICK
    assert moved["note"] == {
        "id": "t2070p72",
        "pitch_name": "C5",
        "on_tick": 2000,
        "off_tick": 2020,
        "velocity": 80,
        "duration_ms": 20.0,
        "protected": False,
    }
    assert moved["suggested"] == {"op": "delete", "note": "t2070p72"}
    assert moved["context"] == ["t2070p72 0:02.00 C5 20ms v80"]
    assert added["id"] == "glitch:short:add-blip"
    assert added["note"]["id"] == "add-blip"
    assert added["suggested"] == {"op": "delete", "note": "add-blip"}
    assert result.stdout == (
        f"0:02.0  glitch/short  {FLICK}  unjudged\n"
        "0:06.0  glitch/short  glitch:short:add-blip  unjudged\n"
        "candidates: 2 fixed, 0 kept, 0 still present, 2 unjudged\n"
    )


def test_a_fix_still_found_and_a_candidate_without_a_verdict_fail(tmp_path, files):
    spec = write_spec(tmp_path, files, [verdict(ALONE, "fix", 5.0), verdict(LATE, "keep", 2.07)])
    result = find(files, spec, tmp_path / "after.json")
    assert result.exit_code == 1
    assert result.stdout == (
        f"0:02.1  glitch/short  {FLICK}  unjudged\n"
        f"0:05.0  glitch/short  {ALONE}  still present\n"
        "candidates: 0 fixed, 1 kept, 1 still present, 1 unjudged\n"
    )


def test_every_candidate_fixed_or_kept_passes(tmp_path, files):
    verdicts = [
        verdict(LATE, "fix", 2.07),
        verdict(FLICK, "keep", 2.07),
        verdict(ALONE, "fix", 5.0),
    ]
    edits = [
        edit("modify", LATE, note="t2070p72", on_tick=2000, off_tick=2020),
        edit("delete", ALONE, note="t5000p76"),
    ]
    spec = write_spec(tmp_path, files, verdicts, edits)
    result = find(files, spec, tmp_path / "after.json")
    assert result.exit_code == 0, result.output
    assert result.stdout == (
        "candidates: 2 fixed, 1 kept, 0 still present, 0 unjudged\nall candidates judged\n"
    )


def test_the_report_has_a_line_per_candidate(tmp_path, files):
    # Deleting the late flick also removes its short candidate, which has no verdict; the stutter
    # was fixed in an earlier iteration and is found in neither search.
    verdicts = [
        verdict(LATE, "fix", 2.07, "a late flick | gone"),
        verdict("glitch:stutter:t3000p60", "fix", 3.0, "gone in an earlier iteration"),
        verdict(ALONE, "keep", 5.0, "a grace note"),
    ]
    spec = write_spec(tmp_path, files, verdicts, [edit("delete", LATE, note="t2070p72")])
    report = tmp_path / "report.md"
    result = find(files, spec, tmp_path / "after.json", "--report", str(report))
    assert result.exit_code == 1
    assert f"{FLICK}  unjudged" in result.stdout
    assert report.read_text(encoding="utf-8") == (
        "| candidate | category/kind | time | status | reason |\n"
        "| --- | --- | --- | --- | --- |\n"
        f"| {FLICK} | glitch/short | 0:02.07 | unjudged |  |\n"
        f"| {LATE} | timing/off-grid | 0:02.07 | fixed | a late flick \\| gone |\n"
        "| glitch:stutter:t3000p60 | glitch/stutter | 0:03.00 | fixed | gone in an earlier "
        "iteration |\n"
        f"| {ALONE} | glitch/short | 0:05.00 | kept | a grace note |\n"
    )


@pytest.mark.parametrize("flag", ["-o", "--report"])
@pytest.mark.parametrize("target", [0, 1, 2, 3])
def test_outputs_never_overwrite_an_input(tmp_path, files, flag, target):
    spec = write_spec(tmp_path, files, [])
    inputs = [*files, spec]
    before = [path.read_bytes() for path in inputs]
    out = tmp_path / "after.json"
    extra = ["--report", str(inputs[target])] if flag == "--report" else []
    result = find(files, spec, inputs[target] if flag == "-o" else out, *extra)
    assert result.exit_code == 2
    assert "would overwrite an input" in " ".join(result.output.split())
    assert [path.read_bytes() for path in inputs] == before
    assert not out.exists()


def test_a_report_needs_a_spec(tmp_path, files):
    cover, timeline, melody = files
    result = CliRunner().invoke(
        app,
        ["find-candidates", str(cover), "--timeline", str(timeline), "--melody", str(melody)]
        + ["-o", str(tmp_path / "c.json"), "--report", str(tmp_path / "r.md")],
    )
    assert result.exit_code == 2
    assert "needs --spec" in " ".join(result.output.split())


def test_a_bad_spec_is_named_without_writing(tmp_path, files):
    spec = write_spec(tmp_path, files, [], [edit("delete", LATE, note="t2070p72")])
    out = tmp_path / "after.json"
    result = find(files, spec, out)
    assert result.exit_code == 1
    assert f"edits[0]: candidate {LATE} has no fix verdict" in result.output
    assert not out.exists()


def test_a_report_may_not_be_the_candidates_file(tmp_path, files):
    spec = write_spec(tmp_path, files, [])
    out = tmp_path / "after.json"
    result = find(files, spec, out, "--report", str(out))
    assert result.exit_code == 2
    assert "is also --out" in " ".join(result.output.split())
    assert not out.exists()


def test_an_input_spelt_in_other_case_is_refused(tmp_path, files):
    spec = write_spec(tmp_path, files, [])
    other = tmp_path / "SPEC.JSON"
    if not other.exists():
        pytest.skip("the filesystem tells case apart")
    before = spec.read_bytes()
    out = tmp_path / "after.json"
    result = find(files, spec, out, "--report", str(other))
    assert result.exit_code == 2
    assert "would overwrite an input" in " ".join(result.output.split())
    assert spec.read_bytes() == before
    assert not out.exists()


def test_a_report_that_cannot_be_written_leaves_the_candidates_file(tmp_path, files):
    spec = write_spec(tmp_path, files, [verdict(ALONE, "keep", 5.0)])
    out = tmp_path / "after.json"
    out.write_text("earlier run", encoding="utf-8")
    result = find(files, spec, out, "--report", str(tmp_path / "missing" / "report.md"))
    assert result.exit_code == 1
    assert "error:" in result.output
    assert out.read_text(encoding="utf-8") == "earlier run"
    assert sorted(path.name for path in tmp_path.iterdir() if path.name.startswith(".")) == []


# One fixable candidate of each kind with a suggestion, at 60 bpm in C major and then C/E from
# 6 s: a C3 held 9.5 beats, an isolated G5 flick, an E5 sliver before the held E5, a G4 struck
# 40 over its neighbours, a C4 70 ms late, and an E2 half a beat after the change to C/E, after
# a C2 that comes a quarter of a beat after it.
EACH_KIND = [
    (0, 9500, 48, 80),
    (0, 900, 52, 80),
    (0, 900, 55, 80),
    (2000, 2020, 79, 80),
    (3000, 3010, 76, 80),
    (3025, 3500, 76, 80),
    (4000, 4200, 60, 70),
    (4500, 4700, 67, 110),
    (5070, 5300, 60, 80),
    (6250, 6400, 36, 80),
    (6250, 6400, 55, 80),
    (6500, 7000, 40, 80),
]


def test_every_suggested_edit_fixes_its_candidate(tmp_path, tick_midi, write_timeline):
    cover = tmp_path / "cover.mid"
    tick_midi(EACH_KIND, ticks_per_beat=500).save(cover)
    melody = tmp_path / "melody.mid"
    tick_midi([(11000, 11500, 40, 90)], ticks_per_beat=500).save(melody)
    timeline = write_timeline(
        [("C:maj", 6), ("C:maj", 6, "E")], name="song.chords.json", bpm=60, offset=0.0
    )
    inputs = (cover, timeline, melody)
    out = tmp_path / "candidates.json"
    result = CliRunner().invoke(
        app,
        ["find-candidates", str(cover), "--timeline", str(timeline), "--melody", str(melody)]
        + ["-o", str(out)],
    )
    assert result.exit_code == 0, result.output
    found = json.loads(out.read_text(encoding="utf-8"))["candidates"]
    assert sorted(c["kind"] for c in found) == sorted(
        ["duration", "short", "stutter", "velocity", "off-grid", "bass-late"]
    )

    verdicts = [verdict(c["id"], "fix", c["time"]) for c in found]
    edits = [{**c["suggested"], "candidate": c["id"], "reason": "as suggested"} for c in found]
    spec = write_spec(tmp_path, inputs, verdicts, edits)
    result = find(inputs, spec, tmp_path / "after.json")
    assert result.exit_code == 0, result.output
    assert result.stdout == (
        "candidates: 6 fixed, 0 kept, 0 still present, 0 unjudged\nall candidates judged\n"
    )
