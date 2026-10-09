import importlib.metadata
import json

import pytest
import soundfile
from typer.testing import CliRunner

from pianoize.cli import app


def test_version() -> None:
    result = CliRunner().invoke(app, ["--version"])

    assert result.exit_code == 0
    assert result.stdout.strip() == f"pianoize {importlib.metadata.version('pianoize')}"


def test_evaluate_writes_and_prints_the_table(tmp_path, write_timeline):
    original = write_timeline([("C:maj", 4), ("G:maj", 4)], name="original.json")
    good = write_timeline([("C:maj", 4), ("G:maj", 4)], name="good.chords.json")
    bad = write_timeline([("C:maj", 4), ("A:min", 4)], name="bad.chords.json")
    checkpoints = tmp_path / "checkpoints.json"
    checkpoints.write_text(
        json.dumps({"checkpoints": [{"name": "all", "start_beat": 0, "end_beat": 8}]})
    )
    out_dir = tmp_path / "out" / "nested"

    result = CliRunner().invoke(
        app,
        [
            "evaluate",
            "--original", str(original),
            "--checkpoints", str(checkpoints),
            "--out-dir", str(out_dir),
            f"good={good}",
            f"bad={bad}",
        ],
    )  # fmt: skip

    assert result.exit_code == 0
    table = (out_dir / "table.md").read_text(encoding="utf-8")
    assert result.stdout == table
    assert "| good | 1/1 | 2/2 | 2/2 |" in table
    assert "| bad | 0/1 | 1/2 | 1/2 |" in table


def _evaluate(tmp_path, write_timeline, *rows):
    original = write_timeline([("C:maj", 4)], name="original.json")
    checkpoints = tmp_path / "checkpoints.json"
    checkpoints.write_text(
        json.dumps({"checkpoints": [{"name": "all", "start_beat": 0, "end_beat": 4}]})
    )
    return CliRunner().invoke(
        app,
        ["evaluate", "--original", str(original), "--checkpoints", str(checkpoints),
         "--out-dir", str(tmp_path / "out"), *rows],
    )  # fmt: skip


@pytest.mark.parametrize("row", ["no-equals.chords.json", "=x.chords.json", "a=", "a=b.json"])
def test_evaluate_refuses_a_malformed_row_or_suffix(tmp_path, write_timeline, row):
    result = _evaluate(tmp_path, write_timeline, row)

    assert result.exit_code == 2
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize("name", ["../x", "a/b", ".", ".."])
def test_evaluate_refuses_a_row_name_that_is_not_a_file_name(tmp_path, write_timeline, name):
    row = f"{name}={write_timeline([('C:maj', 4)], name='r.chords.json')}"

    result = _evaluate(tmp_path, write_timeline, row)

    assert result.exit_code == 2
    assert not (tmp_path / "out").exists()


def test_evaluate_refuses_a_row_that_would_overwrite_an_input(tmp_path, write_timeline, synth):
    original = write_timeline([("C:maj", 4)], name="song.chords.json")
    checkpoints = tmp_path / "checkpoints.json"
    checkpoints.write_text(
        json.dumps({"checkpoints": [{"name": "all", "start_beat": 0, "end_beat": 4}]})
    )
    wav = _wav(tmp_path, synth)

    result = CliRunner().invoke(
        app,
        ["evaluate", "--original", str(original), "--checkpoints", str(checkpoints),
         "--out-dir", str(tmp_path), f"song={wav}"],
    )  # fmt: skip

    assert result.exit_code == 2
    assert "would overwrite an input" in " ".join(result.output.split())
    assert json.loads(original.read_text())["schema_version"] == 11


def test_evaluate_refuses_a_repeated_row_name(tmp_path, write_timeline):
    row = f"a={write_timeline([('C:maj', 4)], name='r.chords.json')}"

    assert _evaluate(tmp_path, write_timeline, row, row).exit_code == 2


def test_evaluate_reports_a_bad_timeline_without_a_traceback(tmp_path, write_timeline):
    broken = tmp_path / "broken.chords.json"
    broken.write_text("{}")

    result = _evaluate(tmp_path, write_timeline, f"a={broken}")

    assert result.exit_code == 1
    assert "schema_version" in result.output
    assert "Traceback" not in result.output


def test_evaluate_refuses_a_missing_original(tmp_path, write_timeline):
    row = f"a={write_timeline([('C:maj', 4)], name='r.chords.json')}"
    checkpoints = tmp_path / "checkpoints.json"
    checkpoints.write_text("{}")

    result = CliRunner().invoke(
        app,
        ["evaluate", "--original", str(tmp_path / "nope.json"), "--checkpoints", str(checkpoints),
         "--out-dir", str(tmp_path / "out"), row],
    )  # fmt: skip

    assert result.exit_code == 2


def test_evaluate_reports_a_missing_row_file_without_a_traceback(tmp_path, write_timeline):
    result = _evaluate(tmp_path, write_timeline, f"a={tmp_path / 'gone.chords.json'}")

    assert result.exit_code == 1
    assert "error:" in result.output
    assert "Traceback" not in result.output


def _wav(tmp_path, synth):
    wav = tmp_path / "song.wav"
    soundfile.write(wav, synth, 44100)
    return wav


def _mid_row(tmp_path, make_midi, name="mine"):
    path = tmp_path / f"{name}.mid"
    make_midi([("C:maj", 4)]).save(path)
    return f"{name}={path}"


def test_evaluate_renders_and_analyzes_a_mid_row(
    tmp_path, write_timeline, make_midi, fake_fluidsynth, fake_chordotomy, monkeypatch
):
    monkeypatch.setenv("PIANOIZE_CHORDOTOMY", str(fake_chordotomy.path))
    soundfont = tmp_path / "piano.sf2"

    result = _evaluate(
        tmp_path, write_timeline, "--soundfont", str(soundfont), _mid_row(tmp_path, make_midi)
    )

    assert result.exit_code == 0, result.output
    out = tmp_path / "out"
    assert (out / "mine.wav").exists() and (out / "mine.chords.json").exists()
    assert fake_fluidsynth.calls[0]["soundfont"] == soundfont
    assert "| mine | 1/1 |" in (out / "table.md").read_text(encoding="utf-8")
    assert sorted(p.name for p in out.iterdir()) == [
        "mine.chords.json", "mine.wav", "table.md",
    ]  # fmt: skip


def test_evaluate_reuses_outputs_unless_forced(
    tmp_path, write_timeline, make_midi, fake_fluidsynth, fake_chordotomy
):
    args = ["--soundfont", "sf.sf2", "--chordotomy", str(fake_chordotomy.path),
            _mid_row(tmp_path, make_midi)]  # fmt: skip

    assert _evaluate(tmp_path, write_timeline, *args).exit_code == 0
    assert _evaluate(tmp_path, write_timeline, *args).exit_code == 0
    assert len(fake_fluidsynth.calls) == 1 and len(fake_chordotomy.calls()) == 1

    assert _evaluate(tmp_path, write_timeline, "--force", *args).exit_code == 0
    assert len(fake_fluidsynth.calls) == 2 and len(fake_chordotomy.calls()) == 2

    # A wav that survives without its analysis is analyzed, not rendered again.
    (tmp_path / "out" / "mine.chords.json").unlink()
    assert _evaluate(tmp_path, write_timeline, *args).exit_code == 0
    assert len(fake_fluidsynth.calls) == 2 and len(fake_chordotomy.calls()) == 3


def test_evaluate_analyzes_a_wav_row_and_passes_the_engine(
    tmp_path, write_timeline, fake_chordotomy, synth
):
    wav = _wav(tmp_path, synth)

    result = _evaluate(
        tmp_path, write_timeline, "--engine", "dsp", "--chordotomy", str(fake_chordotomy.path),
        f"song={wav}",
    )  # fmt: skip

    assert result.exit_code == 0, result.output
    assert fake_chordotomy.calls() == [(str(wav), "dsp")]
    assert (tmp_path / "out" / "song.chords.json").exists()


def test_evaluate_needs_a_soundfont_for_a_mid_row_before_any_work(
    tmp_path, write_timeline, make_midi, monkeypatch
):
    monkeypatch.delenv("PIANOIZE_SOUNDFONT", raising=False)

    result = _evaluate(tmp_path, write_timeline, _mid_row(tmp_path, make_midi))

    assert result.exit_code == 2
    assert not (tmp_path / "out").exists()


def test_evaluate_does_not_look_for_chordotomy_when_nothing_needs_analysis(
    tmp_path, write_timeline, monkeypatch
):
    monkeypatch.delenv("PIANOIZE_CHORDOTOMY", raising=False)
    monkeypatch.setattr("shutil.which", lambda name: None)
    row = f"a={write_timeline([('C:maj', 4)], name='r.chords.json')}"

    assert _evaluate(tmp_path, write_timeline, row).exit_code == 0


def test_evaluate_reports_a_missing_chordotomy(tmp_path, write_timeline, synth, monkeypatch):
    monkeypatch.delenv("PIANOIZE_CHORDOTOMY", raising=False)
    monkeypatch.setattr("shutil.which", lambda name: None)
    wav = _wav(tmp_path, synth)

    result = _evaluate(tmp_path, write_timeline, f"song={wav}")

    assert result.exit_code == 1
    assert "error: chordotomy not found" in result.output
