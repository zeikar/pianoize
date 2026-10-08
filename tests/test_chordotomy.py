import json
import sys

import pytest

from pianoize import chordotomy


def test_executable_resolution_order(monkeypatch, tmp_path):
    monkeypatch.setattr(chordotomy.shutil, "which", lambda name: f"/on/path/{name}")
    monkeypatch.setenv(chordotomy.ENV_VAR, "/from/env")

    assert chordotomy.executable("/explicit") == "/explicit"
    assert chordotomy.executable() == "/from/env"
    monkeypatch.delenv(chordotomy.ENV_VAR)
    assert chordotomy.executable() == "/on/path/chordotomy"


def test_executable_error_lists_where_it_looked(monkeypatch):
    monkeypatch.delenv(chordotomy.ENV_VAR, raising=False)
    monkeypatch.setattr(chordotomy.shutil, "which", lambda name: None)

    with pytest.raises(chordotomy.ChordotomyError, match="--chordotomy.*PIANOIZE_CHORDOTOMY.*PATH"):
        chordotomy.executable()


def test_analyze_runs_the_cli_and_returns_the_timeline(tmp_path, fake_chordotomy):
    out = tmp_path / "song.chords.json"

    result = chordotomy.analyze(tmp_path / "song.wav", out, str(fake_chordotomy.path))

    assert result == json.loads(out.read_text())
    assert fake_chordotomy.calls() == [(str(tmp_path / "song.wav"), "model")]


def test_analyze_passes_the_environment_through_untouched(tmp_path, monkeypatch):
    seen = tmp_path / "env.txt"
    script = tmp_path / "chordotomy"
    script.write_text(
        f"#!{sys.executable}\nimport json, os\n"
        f"open({str(seen)!r}, 'w').write(json.dumps(sorted(os.environ)))\nraise SystemExit(1)\n"
    )
    script.chmod(0o755)
    monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
    monkeypatch.setenv("HF_HOME", "/somewhere")

    with pytest.raises(chordotomy.ChordotomyError):
        chordotomy.analyze(tmp_path / "a.wav", tmp_path / "o.json", str(script))

    names = json.loads(seen.read_text())
    assert "HF_HOME" in names and "XDG_CACHE_HOME" not in names


def test_analyze_includes_stderr_when_it_fails(tmp_path):
    script = tmp_path / "chordotomy"
    script.write_text(
        f"#!{sys.executable}\nimport sys\nprint('no beats', file=sys.stderr)\nsys.exit(3)\n"
    )
    script.chmod(0o755)

    with pytest.raises(chordotomy.ChordotomyError, match=r"\(3\).*no beats"):
        chordotomy.analyze(tmp_path / "a.wav", tmp_path / "o.json", str(script))


def test_analyze_reports_an_unrunnable_executable(tmp_path):
    with pytest.raises(chordotomy.ChordotomyError, match="cannot run"):
        chordotomy.analyze(tmp_path / "a.wav", tmp_path / "o.json", str(tmp_path / "missing"))
