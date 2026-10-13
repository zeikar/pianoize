import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from pianoize import tsumugi
from pianoize.cli import app
from pianoize.tsumugi import Install


@pytest.fixture(autouse=True)
def clean_env(monkeypatch, tmp_path):
    for name in ("PIANOIZE_HOME", "XDG_CACHE_HOME", "HF_HUB_CACHE", "HF_HOME"):
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
    assert len(missing) == 6
    assert any("weights" in m for m in missing)


def test_missing_is_empty_on_a_complete_layout(monkeypatch, tmp_path):
    monkeypatch.setenv("HF_HUB_CACHE", str(tmp_path / "hub"))
    install = Install(tmp_path / "home")
    install.tsumugi_commit.parent.mkdir(parents=True)
    install.tsumugi_commit.write_text(tsumugi.TSUMUGI_COMMIT + "\n")
    install.cover_commit.write_text(tsumugi.COVER_COMMIT + "\n")
    files = [install.tsumugi_python, install.cover_python, install.worker]
    files += [install.weights / f for f in tsumugi.WEIGHTS_FILES]
    for path in files:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
    assert install.missing() == []


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
        ["python", "-I", "-c", tsumugi.SNAPSHOT_CODE, tsumugi.WEIGHTS_REPO,
         tsumugi.WEIGHTS_REVISION, str(tmp_path / "hub")],
    ]  # fmt: skip
    records = fake_installers.records()
    home, here = str(install.home), str(tmp_path)
    assert [r["cwd"] for r in records] == [
        here, tsumugi_part, here, cover_part, str(install.tsumugi_dir), home, home, here,
    ]  # fmt: skip
    assert records[-1]["argv"][0] == str(install.cover_python)
    assert result.output.index(tsumugi.TERMS) < result.output.index("downloading")
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
        f"weights: present at {install.weights}",
    ):
        assert line in result.output.splitlines()


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
