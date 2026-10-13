from pathlib import Path

import pytest

from pianoize import tsumugi
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
