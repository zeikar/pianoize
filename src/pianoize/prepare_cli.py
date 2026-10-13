"""The preparing commands: setup installs the tsumugi tools pianoize runs. They register on the
same Typer app as the rest of the CLI."""

from __future__ import annotations

import typer

from . import tsumugi
from .cli import _fail, app


@app.command()
def setup() -> None:
    """Install tsumugi and tsumugi-piano-cover into the pianoize home, pinned, once."""
    try:
        tsumugi.setup(tsumugi.Install.from_env(), typer.echo)
    except (tsumugi.TsumugiError, OSError) as exc:
        raise _fail(str(exc)) from exc
