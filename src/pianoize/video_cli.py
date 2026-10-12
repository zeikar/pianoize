"""The video commands. They register on the same Typer app as the rest of the CLI."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from . import files, roll
from .cli import _fail, _read_midi, _refuse_input, app


@app.command("export-arrangement")
def export_arrangement(
    midi_path: Annotated[Path, typer.Argument(metavar="ARRANGED.mid", exists=True, dir_okay=False)],
    out: Annotated[Path, typer.Option("-o", "--out", help="The JSON file to write.")],
) -> None:
    """Export a two-hand arrangement's notes as the JSON the falling-notes viewer draws."""
    _refuse_input(out, [midi_path], "--out")
    midi = _read_midi(midi_path)
    try:
        data = roll.export(midi)
        files.write_all({out: lambda path: path.write_text(roll.dump(data), encoding="utf-8")})
    except roll.RollError as exc:
        raise _fail(f"{midi_path}: {exc}") from exc
    except OSError as exc:
        raise _fail(str(exc)) from exc
    hands = [n["hand"] for n in data["notes"]]
    typer.echo(f"notes: {hands.count('right')} right hand, {hands.count('left')} left hand")
    typer.echo(f"length: {roll.length(midi):.1f} s")
