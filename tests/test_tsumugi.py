import os
import re
import shutil
import signal
import sys
from pathlib import Path

import mido
import pytest
from typer.testing import CliRunner

from pianoize import tsumugi
from pianoize.cli import app
from pianoize.tsumugi import Install


@pytest.fixture(autouse=True)
def clean_env(monkeypatch, tmp_path):
    for name in (
        "PIANOIZE_HOME", "XDG_CACHE_HOME", "HF_HUB_CACHE", "HF_HOME",
        "STEM_SPLITTER_CACHE", "DYLD_FALLBACK_LIBRARY_PATH",
    ):  # fmt: skip
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("HOME", str(tmp_path / "user"))


def test_home_prefers_pianoize_home(monkeypatch, tmp_path):
    monkeypatch.setenv("PIANOIZE_HOME", str(tmp_path / "h"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "xdg"))
    assert tsumugi.home() == (tmp_path / "h").resolve()


def test_home_under_xdg_cache(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "xdg"))
    assert tsumugi.home() == (tmp_path / "xdg" / "pianoize").resolve()


def test_home_default(tmp_path):
    assert tsumugi.home() == (tmp_path / "user" / ".cache" / "pianoize").resolve()


def test_relative_home_is_absolute(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PIANOIZE_HOME", "rel/home")
    assert tsumugi.home() == (tmp_path / "rel" / "home").resolve()
    assert tsumugi.home().is_absolute()


def test_hub_cache_resolution(monkeypatch, tmp_path):
    assert tsumugi.hub_cache() == (tmp_path / "user" / ".cache" / "huggingface" / "hub").resolve()
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "xdg"))
    assert tsumugi.hub_cache() == (tmp_path / "xdg" / "huggingface" / "hub").resolve()
    monkeypatch.setenv("HF_HOME", str(tmp_path / "hf"))
    assert tsumugi.hub_cache() == (tmp_path / "hf" / "hub").resolve()
    monkeypatch.setenv("HF_HUB_CACHE", str(tmp_path / "hub"))
    assert tsumugi.hub_cache() == (tmp_path / "hub").resolve()


def test_missing_on_empty_home(tmp_path):
    missing = Install(tmp_path / "home").missing()
    assert len(missing) == 7
    assert any("weights" in m for m in missing)
    assert any("checkpoints" in m for m in missing)


def test_missing_is_empty_on_a_complete_layout(monkeypatch, tmp_path):
    monkeypatch.setenv("HF_HUB_CACHE", str(tmp_path / "hub"))
    install = Install(tmp_path / "home")
    install.tsumugi_commit.parent.mkdir(parents=True)
    install.tsumugi_commit.write_text(tsumugi.TSUMUGI_COMMIT + "\n")
    install.cover_commit.write_text(tsumugi.COVER_COMMIT + "\n")
    files = [install.tsumugi_python, install.cover_python, install.worker, *install.checkpoints]
    files += [install.weights / f for f in tsumugi.WEIGHTS_FILES]
    for path in files:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
    assert install.missing() == []


def test_missing_names_the_checkpoints_when_one_is_absent(fake_install):
    install = fake_install.install
    (install.tsumugi_dir / "checkpoints" / "best_model_bass_v2.pth").unlink()

    [phrase] = install.missing()

    assert "tsumugi checkpoints" in phrase and str(install.tsumugi_dir) in phrase


def test_missing_names_a_commit_that_is_not_the_pin(tmp_path):
    install = Install(tmp_path)
    install.tsumugi_commit.write_text("0" * 40 + "\n")
    assert any(str(install.tsumugi_commit) in m for m in install.missing())


def test_from_env_uses_home(monkeypatch, tmp_path):
    monkeypatch.setenv("PIANOIZE_HOME", str(tmp_path))
    assert Install.from_env().home == Path(tmp_path).resolve()


def _setup():
    return CliRunner().invoke(app, ["setup"])


def test_setup_installs_into_a_fresh_home(fake_installers, tmp_path):
    result = _setup()

    assert result.exit_code == 0, result.output
    install = Install.from_env()
    tsumugi_part, cover_part = f"{install.tsumugi_dir}.part", f"{install.cover_dir}.part"
    assert fake_installers.calls() == [
        ["git", "clone", "--quiet", tsumugi.TSUMUGI_URL, tsumugi_part],
        ["git", "checkout", "--quiet", "--detach", tsumugi.TSUMUGI_COMMIT],
        ["git", "clone", "--quiet", tsumugi.COVER_URL, cover_part],
        ["git", "checkout", "--quiet", "--detach", tsumugi.COVER_COMMIT],
        ["uv", "sync", "--locked", "--extra", "stem"],
        ["uv", "venv", "--allow-existing", "--python", "3.12",
         str(install.cover_python.parents[1])],
        ["uv", "pip", "install", "--python", str(install.cover_python),
         *tsumugi.GENERATOR_PACKAGES],
        ["python", "-I", "-c", tsumugi.FETCH_CODE],
        ["python", "-I", "-c", tsumugi.SNAPSHOT_CODE, tsumugi.WEIGHTS_REPO,
         tsumugi.WEIGHTS_REVISION, str(tmp_path / "hub")],
    ]  # fmt: skip
    records = fake_installers.records()
    home, here, clone = str(install.home), str(tmp_path), str(install.tsumugi_dir)
    assert [r["cwd"] for r in records] == [
        here, tsumugi_part, here, cover_part, clone, home, home, clone, here,
    ]  # fmt: skip
    fetch, download = records[-2:]
    assert fetch["argv"][0] == str(install.tsumugi_python)
    assert fetch["env"]["STEM_SPLITTER_CACHE"] == str(install.stem_cache)
    assert download["argv"][0] == str(install.cover_python)
    weights_line = f"downloading {tsumugi.WEIGHTS_REPO} "
    assert result.output.index(tsumugi.TERMS) < result.output.index(weights_line)
    # The download's stdout, the snapshot it resolved, is captured and echoed.
    assert f"\n{install.weights}\n" in result.output
    assert install.tsumugi_commit.read_text().strip() == tsumugi.TSUMUGI_COMMIT
    assert install.cover_commit.read_text().strip() == tsumugi.COVER_COMMIT
    assert install.missing() == []


def test_setup_downloads_into_hf_hub_cache(fake_installers, monkeypatch, tmp_path):
    monkeypatch.setenv("HUGGINGFACE_HUB_CACHE", str(tmp_path / "legacy-hub"))

    result = _setup()

    assert result.exit_code == 0, result.output
    assert fake_installers.calls()[-1][-1] == str(tmp_path / "hub")


def test_setup_again_only_audits_the_envs(fake_installers):
    assert _setup().exit_code == 0
    before = len(fake_installers.calls())

    result = _setup()

    assert result.exit_code == 0, result.output
    assert [call[:2] for call in fake_installers.calls()[before:]] == [
        ["uv", "sync"],
        ["uv", "pip"],
    ]
    assert tsumugi.TERMS not in result.output
    install = Install.from_env()
    for line in (
        f"tsumugi: already at {tsumugi.TSUMUGI_COMMIT[:7]}",
        f"tsumugi-piano-cover: already at {tsumugi.COVER_COMMIT[:7]}",
        "tsumugi checkpoints: present",
        f"weights: present at {install.weights}",
    ):
        assert line in result.output.splitlines()


def test_setup_refuses_a_checkpoint_whose_hash_changed(fake_installers, monkeypatch):
    name = "checkpoints/best_velocity_model.pth"
    monkeypatch.setitem(tsumugi.TSUMUGI_CHECKPOINTS, name, "0" * 64)

    result = _setup()

    assert result.exit_code == 1
    found = tsumugi._sha256(Install.from_env().tsumugi_dir / name)
    for text in ("error:", str(Install.from_env().tsumugi_dir / name), "0" * 64, found):
        assert text in result.output
    assert "docs/decisions.md" in result.output
    # Stopped before the cover's weights.
    assert fake_installers.calls()[-1] == ["python", "-I", "-c", tsumugi.FETCH_CODE]


def test_setup_names_a_checkpoint_the_fetch_left_out(fake_installers, monkeypatch):
    monkeypatch.setenv("FAKE_PYTHON_LEAVE_OUT", "stem_splitter.pt")

    result = _setup()

    assert result.exit_code == 1
    assert str(Install.from_env().stem_cache / "stem_splitter.pt") in result.output


def test_setup_refuses_a_clone_at_another_commit(fake_installers):
    install = Install.from_env()
    install.tsumugi_dir.mkdir(parents=True)
    install.tsumugi_commit.write_text("0" * 40 + "\n")

    result = _setup()

    assert result.exit_code == 1
    assert "error:" in result.output
    for text in (str(install.tsumugi_dir), "0" * 40, tsumugi.TSUMUGI_COMMIT):
        assert text in result.output
    assert fake_installers.calls() == []


@pytest.mark.parametrize("tool", ["git", "uv"])
def test_setup_names_a_missing_tool(fake_installers, monkeypatch, tool):
    which = shutil.which
    monkeypatch.setattr(shutil, "which", lambda name: None if name == tool else which(name))

    result = _setup()

    assert result.exit_code == 1
    assert f"error: {tool} not found on PATH" in result.output
    assert fake_installers.calls() == []


def test_setup_stops_at_a_failed_clone_and_clones_again(fake_installers, monkeypatch, capfd):
    monkeypatch.setenv("FAKE_GIT_CLONE_FAILS", "1")
    install = Install.from_env()
    part = install.home / "tsumugi.part"

    result = _setup()

    assert result.exit_code == 1
    assert "git clone failed with exit code 1; see the output above" in result.output
    # Streamed, not captured: git's own message reached the terminal.
    assert "fatal: fake git: clone failed" in capfd.readouterr().err
    assert not install.tsumugi_dir.exists()
    assert not install.tsumugi_commit.exists()
    assert part.is_dir()

    monkeypatch.delenv("FAKE_GIT_CLONE_FAILS")
    result = _setup()

    assert result.exit_code == 0, result.output
    assert install.tsumugi_dir.is_dir()
    assert not part.exists()


def test_setup_names_a_file_the_download_left_out(fake_installers, monkeypatch):
    monkeypatch.setenv("FAKE_PYTHON_LEAVE_OUT", "piano_ar/config.json")

    result = _setup()

    assert result.exit_code == 1
    assert "error:" in result.output
    assert str(Install.from_env().weights / "piano_ar" / "config.json") in result.output


def _wav(tmp_path: Path) -> Path:
    wav = tmp_path / "song.wav"
    wav.touch()  # the fake worker only checks it is there
    return wav


def test_transcribe_writes_the_midi_and_logs_without_streamed_lines(fake_install, tmp_path):
    install = fake_install.install
    wav, out, log = _wav(tmp_path), tmp_path / "scratch" / "source.mid", tmp_path / "t.log"
    out.parent.mkdir()

    tsumugi.transcribe(install, wav, out, log)

    assert [t.name for t in mido.MidiFile(out).tracks] == [
        "Predicted Tempo Map", "Predicted Chords", "", "piano", "melody", "drums",
    ]  # fmt: skip
    lines = log.read_text(encoding="utf-8").splitlines()
    assert "Loading AMT model on cpu" in lines
    assert not any(line.startswith("@@") for line in lines)
    [record] = fake_install.records()
    assert record["argv"] == [
        str(install.tsumugi_python), "-X", "utf8", str(install.worker),
        "--tsumugi-dir", str(install.tsumugi_dir),
        "--audio", str(wav), "--out", str(out), "--work", str(tmp_path / "scratch" / "work"),
    ]  # fmt: skip
    assert record["cwd"] == str(install.tsumugi_dir)
    assert record["env"]["STEM_SPLITTER_CACHE"] == str(install.home / "stem-splitter")
    # Else the log would take a Python child's output in blocks.
    assert record["env"]["PYTHONUNBUFFERED"] == "1"


def test_transcribe_passes_absolute_paths(fake_install, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    _wav(tmp_path)

    tsumugi.transcribe(fake_install.install, Path("song.wav"), Path("source.mid"), Path("t.log"))

    argv = fake_install.records()[-1]["argv"]
    for flag, path in (
        ("--audio", tmp_path / "song.wav"),
        ("--out", tmp_path / "source.mid"),
        ("--work", tmp_path / "work"),
    ):
        assert argv[argv.index(flag) + 1] == str(path)
    assert (tmp_path / "source.mid").is_file()


def test_transcribe_points_torchcodec_at_homebrew_on_macos(fake_install, monkeypatch, tmp_path):
    monkeypatch.delenv("DYLD_FALLBACK_LIBRARY_PATH", raising=False)
    wav = _wav(tmp_path)

    def seen() -> str | None:
        tsumugi.transcribe(fake_install.install, wav, tmp_path / "source.mid", tmp_path / "t.log")
        return fake_install.records()[-1]["env"]["DYLD_FALLBACK_LIBRARY_PATH"]

    monkeypatch.setattr(sys, "platform", "darwin")
    assert seen() == "/opt/homebrew/lib"
    monkeypatch.setenv("DYLD_FALLBACK_LIBRARY_PATH", "/elsewhere/lib")
    assert seen() == "/elsewhere/lib"
    monkeypatch.delenv("DYLD_FALLBACK_LIBRARY_PATH")
    monkeypatch.setattr(sys, "platform", "linux")
    assert seen() is None


def test_a_failing_worker_names_its_error_and_its_log(fake_install, tmp_path):
    fake_install.log.with_name("fail").touch()
    out, log = tmp_path / "source.mid", tmp_path / "t.log"

    with pytest.raises(
        tsumugi.TsumugiError, match=r"tsumugi transcribe failed \(1\): RuntimeError: boom; log: "
    ) as info:
        tsumugi.transcribe(fake_install.install, _wav(tmp_path), out, log)

    assert str(info.value).endswith(f"; log: {log}")
    assert not out.exists()


def test_transcribe_names_the_midi_it_did_not_write(fake_install, tmp_path):
    fake_install.log.with_name("no-output").touch()
    out, log = tmp_path / "source.mid", tmp_path / "t.log"

    with pytest.raises(tsumugi.TsumugiError) as info:
        tsumugi.transcribe(fake_install.install, _wav(tmp_path), out, log)

    assert str(info.value) == f"tsumugi transcribe wrote no {out}; log: {log}"


def test_transcribe_fails_on_the_workers_stage_warning(fake_install, tmp_path):
    fake_install.log.with_name("warns").touch()
    out, log = tmp_path / "source.mid", tmp_path / "t.log"

    with pytest.raises(tsumugi.TsumugiError) as info:
        tsumugi.transcribe(fake_install.install, _wav(tmp_path), out, log)

    assert str(info.value) == (
        "tsumugi transcribe: a stage failed: "
        f"Warning: Velocity prediction skipped due to error: boom; log: {log}"
    )


@pytest.mark.parametrize(
    ("output", "reason"),
    [
        # The last of a chained traceback's error lines, not the first.
        ("KeyError: 'a'\nloading\nValueError: bad input\nexiting\n\n", "ValueError: bad input"),
        ("loading\n" + "x" * 300 + "\n\n", "x" * 200),
    ],
)
def test_a_failed_run_quotes_the_error_else_the_last_line(tmp_path, output, reason):
    # On stderr, which the log takes too, as a traceback goes.
    code = f"import sys; sys.stderr.write({output!r}); sys.exit(3)"
    log = tmp_path / "step.log"

    with pytest.raises(tsumugi.TsumugiError) as info:
        tsumugi._run("tool", "step", [sys.executable, "-c", code], log, tmp_path, os.environ)

    assert str(info.value) == f"tool step failed (3): {reason}; log: {log}"
    assert log.read_text(encoding="utf-8") == output


def test_generate_returns_the_cover(fake_install, monkeypatch, tmp_path):
    install = fake_install.install
    monkeypatch.chdir(tmp_path)

    cover = tsumugi.generate(install, Path("source.mid"), Path("cover"), Path("g.log"))

    assert cover == tmp_path / "cover" / "source_ch0_0.mid"
    assert [t.name for t in mido.MidiFile(cover).tracks] == ["Piano"]
    assert (tmp_path / "g.log").read_text(encoding="utf-8") == f"{cover}: 1 note\n"
    [record] = fake_install.records()
    assert record["argv"] == [
        str(install.cover_python), "-m", "piano_cover.generate",
        "--checkpoint", str(install.weights),
        "--source", str(tmp_path / "source.mid"), "--seed", "0",
        "--out-dir", str(tmp_path / "cover"),
    ]  # fmt: skip
    assert record["cwd"] == str(install.cover_dir)
    assert record["env"]["STEM_SPLITTER_CACHE"] is None


def test_generate_names_the_cover_it_did_not_write(fake_install, tmp_path):
    fake_install.install.cover_python.write_text("#!/bin/sh\necho 'no cover'\n")
    expected = tmp_path / "cover" / "source_ch0_0.mid"

    with pytest.raises(tsumugi.TsumugiError, match=re.escape(f"wrote no {expected}")):
        tsumugi.generate(
            fake_install.install, tmp_path / "source.mid", tmp_path / "cover", tmp_path / "g.log"
        )


def test_generate_names_an_interpreter_it_cannot_run(fake_install, tmp_path):
    python = fake_install.install.cover_python
    python.unlink()

    with pytest.raises(tsumugi.TsumugiError, match=re.escape(f"cannot run {python}: ")):
        tsumugi.generate(
            fake_install.install, tmp_path / "source.mid", tmp_path / "cover", tmp_path / "g.log"
        )


def test_an_interrupted_transcribe_stops_the_worker(
    fake_install, interrupt_after_started, tmp_path
):
    fake_install.log.with_name("hang").touch()
    log = tmp_path / "t.log"

    with pytest.raises(KeyboardInterrupt):
        tsumugi.transcribe(fake_install.install, _wav(tmp_path), tmp_path / "source.mid", log)

    [proc] = interrupt_after_started
    assert proc.returncode == -signal.SIGTERM
    assert log.read_text(encoding="utf-8").splitlines() == ["started"]
