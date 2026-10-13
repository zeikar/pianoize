"""Where the tsumugi tools live, which versions pianoize pins, and what is missing."""

import os
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
