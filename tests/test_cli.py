import importlib.metadata
import json

import pytest
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
