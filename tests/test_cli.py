import importlib.metadata

from typer.testing import CliRunner

from pianoize.cli import app


def test_version() -> None:
    result = CliRunner().invoke(app, ["--version"])

    assert result.exit_code == 0
    assert result.stdout.strip() == f"pianoize {importlib.metadata.version('pianoize')}"
