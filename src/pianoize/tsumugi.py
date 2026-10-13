"""Where the tsumugi tools live, which versions pianoize pins, what is missing, and the setup
that installs them."""

import os
import shlex
import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

HOME_ENV = "PIANOIZE_HOME"

# The pins and the weights' license are the rows for tsumugi and tsumugi-piano-cover in
# docs/decisions.md; change them together.
TSUMUGI_URL = "https://github.com/anime-song/tsumugi"
TSUMUGI_COMMIT = "a700b8cde582cd95a3d20f460b3648f45734d06d"
COVER_URL = "https://github.com/anime-song/tsumugi-piano-cover"
COVER_COMMIT = "4f5c4351c8d8ec31f35279343ec8349332160787"
WEIGHTS_REPO = "anime-song/tsumugi-piano-cover"
WEIGHTS_REVISION = "12c81996ec0c7c5cb77d9d8c0a2a25234a7620fe"
WEIGHTS_FILES = (
    "piano_cover/model.safetensors",
    "piano_cover/config.json",
    "piano_ar/model.safetensors",
    "piano_ar/config.json",
    "README.md",
)

# Only what piano_cover.generate imports; the repo's requirements.txt pins a torch with no macOS
# wheel (experiments/m1/08_tsumugi.sh).
GENERATOR_PACKAGES = ("torch==2.13.0", "numpy", "symusic", "safetensors", "huggingface_hub")

TERMS = f"""tsumugi-piano-cover weights (piano_cover, piano_ar) by anime-song
License: CC BY-NC 4.0 (https://creativecommons.org/licenses/by-nc/4.0/)
Stated in: https://huggingface.co/{WEIGHTS_REPO} (model card) and https://github.com/anime-song/tsumugi-piano-cover#license
Terms: attribution, non-commercial use only.
Code: MIT, https://github.com/anime-song/tsumugi-piano-cover"""

# Run by the generator env's interpreter rather than its `hf` script: pianoize runs nothing from
# the envs but their interpreters, and this API predates the script's rename.
SNAPSHOT_CODE = """import sys
from huggingface_hub import snapshot_download
print(snapshot_download(sys.argv[1], revision=sys.argv[2], cache_dir=sys.argv[3]))"""

_INSTALL_HINTS = {
    "git": "install the system's git",
    "uv": "install it from https://docs.astral.sh/uv/",
}

Echo = Callable[[str], None]


class TsumugiError(Exception):
    pass


def _cache_root() -> Path:
    xdg = os.environ.get("XDG_CACHE_HOME")
    return Path(xdg) if xdg else Path("~/.cache")


def home() -> Path:
    """The pianoize home: $PIANOIZE_HOME, else $XDG_CACHE_HOME/pianoize, else ~/.cache/pianoize."""
    env = os.environ.get(HOME_ENV)
    path = Path(env) if env else _cache_root() / "pianoize"
    # Absolute, because the tools run as subprocesses in other directories.
    return path.expanduser().resolve()


def hub_cache() -> Path:
    """The Hugging Face hub cache: $HF_HUB_CACHE, else $HF_HOME/hub, else the default under the
    XDG cache. Setup passes it to the download as `cache_dir`, so the two always agree."""
    if os.environ.get("HF_HUB_CACHE"):
        path = Path(os.environ["HF_HUB_CACHE"])
    elif os.environ.get("HF_HOME"):
        path = Path(os.environ["HF_HOME"]) / "hub"
    else:
        path = _cache_root() / "huggingface" / "hub"
    return path.expanduser().resolve()


@dataclass
class Install:
    home: Path

    @classmethod
    def from_env(cls) -> "Install":
        return cls(home())

    @property
    def tsumugi_dir(self) -> Path:
        return self.home / "tsumugi"

    @property
    def tsumugi_commit(self) -> Path:
        return self.home / "tsumugi.commit"

    @property
    def tsumugi_python(self) -> Path:
        return self.tsumugi_dir / ".venv" / "bin" / "python"

    @property
    def cover_dir(self) -> Path:
        return self.home / "tsumugi-piano-cover"

    @property
    def cover_commit(self) -> Path:
        return self.home / "tsumugi-piano-cover.commit"

    @property
    def cover_python(self) -> Path:
        return self.home / "tsumugi-piano-cover.venv" / "bin" / "python"

    @property
    def worker(self) -> Path:
        return self.cover_dir / "cover_studio" / "tsumugi_worker.py"

    @property
    def stem_cache(self) -> Path:
        return self.home / "stem-splitter"

    @property
    def weights(self) -> Path:
        name = "models--" + WEIGHTS_REPO.replace("/", "--")
        return hub_cache() / name / "snapshots" / WEIGHTS_REVISION

    def missing(self) -> list[str]:
        """One phrase per piece that is absent or not at its pin."""
        out = []
        for name, marker, pin in (
            ("tsumugi", self.tsumugi_commit, TSUMUGI_COMMIT),
            ("tsumugi-piano-cover", self.cover_commit, COVER_COMMIT),
        ):
            if not marker.is_file() or marker.read_text().strip() != pin:
                out.append(f"{name} at {pin[:7]} ({marker})")
        for name, python in (
            ("tsumugi environment", self.tsumugi_python),
            ("generator environment", self.cover_python),
        ):
            if not python.exists():
                out.append(f"{name} ({python})")
        if not self.worker.is_file():
            out.append(f"the cover worker ({self.worker})")
        if not all((self.weights / f).is_file() for f in WEIGHTS_FILES):
            out.append(f"the tsumugi-piano-cover weights ({self.weights})")
        return out


def _tool(name: str) -> str:
    found = shutil.which(name)
    if found is None:
        raise TsumugiError(f"{name} not found on PATH; {_INSTALL_HINTS[name]}")
    return found


def _call(argv: list[str], cwd: Path | None = None) -> str:
    """Run a command and return its stdout. Its stderr goes straight to the terminal, so uv's
    and huggingface_hub's progress shows during the minutes a first install takes."""
    # Dropped from every call because only uv reads it: `uv run pianoize` sets it to pianoize's
    # own venv, and uv's project commands such as `uv sync` warn that it doesn't match.
    env = {key: value for key, value in os.environ.items() if key != "VIRTUAL_ENV"}
    try:
        done = subprocess.run(argv, cwd=cwd, env=env, check=True, stdout=subprocess.PIPE, text=True)
    except subprocess.CalledProcessError as exc:
        raise TsumugiError(
            f"{shlex.join(argv[:2])} failed with exit code {exc.returncode}; see the output above"
        ) from exc
    except OSError as exc:
        raise TsumugiError(f"cannot run {shlex.join(argv[:2])}: {exc}") from exc
    return done.stdout


def _clone(git: str, url: str, commit: str, directory: Path, marker: Path, echo: Echo) -> None:
    found = marker.read_text().strip() if marker.is_file() else ""
    if found == commit and directory.is_dir():
        echo(f"{directory.name}: already at {commit[:7]}")
        return
    if directory.exists():
        raise TsumugiError(
            f"{directory} is at commit {found or 'unknown'}, not the pinned {commit}; "
            "remove it and run setup again"
        )
    # Cloned aside and renamed once checked out, so an interrupted clone never passes for one.
    part = directory.with_name(directory.name + ".part")
    if part.exists():
        shutil.rmtree(part)
    echo(f"cloning {url} at {commit[:7]} into {directory}")
    _call([git, "clone", "--quiet", url, str(part)])
    _call([git, "checkout", "--quiet", "--detach", commit], cwd=part)
    # The marker first: a clone counts only once its directory is there too, so a setup stopped
    # before the rename clones again rather than finding a directory of unknown commit.
    marker.write_text(commit + "\n")
    part.rename(directory)


def _envs(uv: str, install: Install, echo: Echo) -> None:
    # The sync and the install run every time: on an installed env they finish in under a
    # second without network, and they finish an env an earlier setup left half done.
    commands = [([uv, "sync", "--locked", "--extra", "stem"], install.tsumugi_dir)]
    # The others run in the home rather than the user's directory, whose pyproject.toml or
    # uv.toml uv would read.
    if not install.cover_python.exists():
        # --allow-existing repairs a venv whose python link dangles instead of refusing it.
        venv = str(install.cover_python.parents[1])
        commands.append(([uv, "venv", "--allow-existing", "--python", "3.12", venv], install.home))
    python = str(install.cover_python)
    commands.append(([uv, "pip", "install", "--python", python, *GENERATOR_PACKAGES], install.home))
    for argv, cwd in commands:
        echo(f"{shlex.join(argv)} (in {cwd})")
        _call(argv, cwd)


def _weights(install: Install, echo: Echo) -> None:
    def absent() -> list[Path]:
        return [install.weights / f for f in WEIGHTS_FILES if not (install.weights / f).is_file()]

    if not absent():
        echo(f"weights: present at {install.weights}")
        return
    echo(TERMS)
    echo(f"downloading {WEIGHTS_REPO} revision {WEIGHTS_REVISION} into {hub_cache()}")
    # cache_dir puts the snapshot where `absent` looks, whatever HF variables are set.
    code = [SNAPSHOT_CODE, WEIGHTS_REPO, WEIGHTS_REVISION, str(hub_cache())]
    echo(_call([str(install.cover_python), "-I", "-c", *code]).rstrip("\n"))
    missing = absent()
    if missing:
        raise TsumugiError(f"the download left out {', '.join(map(str, missing))}")


def setup(install: Install, echo: Echo) -> None:
    """Clone tsumugi and tsumugi-piano-cover at their pins, build their envs and download the
    weights; what is already in place is kept."""
    echo(f"pianoize home: {install.home}")
    # Both up front, so a machine without one fails before any clone.
    git, uv = _tool("git"), _tool("uv")
    install.home.mkdir(parents=True, exist_ok=True)
    install.stem_cache.mkdir(parents=True, exist_ok=True)
    _clone(git, TSUMUGI_URL, TSUMUGI_COMMIT, install.tsumugi_dir, install.tsumugi_commit, echo)
    _clone(git, COVER_URL, COVER_COMMIT, install.cover_dir, install.cover_commit, echo)
    _envs(uv, install, echo)
    _weights(install, echo)
