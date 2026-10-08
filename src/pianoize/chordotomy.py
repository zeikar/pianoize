"""Run the chordotomy CLI, which pianoize uses as a separately installed tool."""

import os
import shutil
import subprocess
from pathlib import Path

from . import timeline

ENV_VAR = "PIANOIZE_CHORDOTOMY"


class ChordotomyError(Exception):
    pass


def executable(explicit: str | Path | None = None) -> str:
    """The chordotomy to run: `explicit`, else $PIANOIZE_CHORDOTOMY, else the one on PATH."""
    if explicit:
        return str(explicit)
    env = os.environ.get(ENV_VAR)
    if env:
        return env
    found = shutil.which("chordotomy")
    if found is None:
        raise ChordotomyError(
            f"chordotomy not found; looked at the --chordotomy option, ${ENV_VAR} and PATH"
        )
    return found


def analyze(audio: Path, out: Path, exe: str, engine: str = "model") -> dict:
    """Analyze `audio` into the timeline `out` (overwriting it) and return the loaded timeline."""
    # The environment is inherited untouched: the Beat This! weights live in the user's cache.
    command = [exe, "analyze", str(audio), "-o", str(out), "--force", "--engine", engine]
    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        raise ChordotomyError(
            f"{exe} analyze failed ({exc.returncode}) on {audio}: {(exc.stderr or '').strip()}"
        ) from exc
    except OSError as exc:
        raise ChordotomyError(f"cannot run {exe}: {exc}") from exc
    return timeline.load(out)
