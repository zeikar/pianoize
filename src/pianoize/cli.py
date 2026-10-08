"""Typer CLI for pianoize."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Annotated

import mido
import typer

from . import __version__, checkpoints, report, score, timeline
from . import render as render_module

app = typer.Typer(no_args_is_help=True, add_completion=False)


def _print_version(value: bool) -> None:
    if value:
        typer.echo(f"pianoize {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        bool,
        typer.Option("--version", callback=_print_version, is_eager=True, help="Show the version."),
    ] = False,
) -> None:
    """Turn a song recording into a piano arrangement."""


_CHORDS_SUFFIX = ".chords.json"


def _fail(message: str) -> typer.Exit:
    typer.echo(f"error: {message}", err=True)
    return typer.Exit(1)


def _parse_rows(values: list[str]) -> list[tuple[str, Path]]:
    rows = []
    for value in values:
        name, separator, path = value.partition("=")
        if not separator or not name or not path:
            raise typer.BadParameter(f"{value!r} is not name=path", param_hint="ROW")
        if not path.endswith(_CHORDS_SUFFIX):
            raise typer.BadParameter(
                f"{path}: rows must be {_CHORDS_SUFFIX} files", param_hint="ROW"
            )
        if any(name == seen for seen, _ in rows):
            raise typer.BadParameter(f"row name {name!r} is used twice", param_hint="ROW")
        rows.append((name, Path(path)))
    return rows


@app.command()
def evaluate(
    rows: Annotated[list[str], typer.Argument(help="name=path of a .chords.json result.")],
    original: Annotated[
        Path, typer.Option(help="The original's timeline.", exists=True, dir_okay=False)
    ],
    checkpoints_path: Annotated[
        Path,
        typer.Option("--checkpoints", help="The checkpoint file.", exists=True, dir_okay=False),
    ],
    out_dir: Annotated[Path, typer.Option(help="Where table.md is written.")],
) -> None:
    """Score results against the original at the checkpoints and write the table."""
    parsed = _parse_rows(rows)
    try:
        original_timeline = timeline.load(original)
        spans, excluded = checkpoints.load(checkpoints_path, original_timeline)
        scored = [
            (name, score.score(original_timeline, spans, excluded, timeline.load(path)))
            for name, path in parsed
        ]
        table = report.markdown(original_timeline, scored)
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "table.md").write_text(table, encoding="utf-8")
    except (timeline.TimelineError, checkpoints.CheckpointError, OSError) as exc:
        raise _fail(str(exc)) from exc
    typer.echo(table, nl=False)


_CLIPPING = 0.99


@app.command()
def render(
    midi: Annotated[Path, typer.Argument(help="The MIDI file.", exists=True, dir_okay=False)],
    out: Annotated[Path, typer.Option("-o", "--out", help="The WAV file to write.")],
    soundfont: Annotated[
        Path | None,
        typer.Option(help="The SoundFont; defaults to $PIANOIZE_SOUNDFONT."),
    ] = None,
    gain: Annotated[float, typer.Option(help="FluidSynth's master gain.")] = 0.5,
) -> None:
    """Render a MIDI file to a WAV with FluidSynth."""
    if soundfont is None:
        env = os.environ.get("PIANOIZE_SOUNDFONT")
        if not env:
            raise typer.BadParameter(
                "give --soundfont or set PIANOIZE_SOUNDFONT", param_hint="--soundfont"
            )
        soundfont = Path(env)
    try:
        source = mido.MidiFile(midi)
    except (OSError, EOFError, ValueError) as exc:
        raise _fail(f"{midi}: cannot read MIDI: {exc}") from exc
    try:
        peak = render_module.render(source, out, soundfont, gain=gain)
    except render_module.RenderError as exc:
        raise _fail(str(exc)) from exc
    typer.echo(f"peak {peak:.3f}")
    if peak >= _CLIPPING:
        typer.echo(f"warning: peak {peak:.3f} may clip; lower --gain", err=True)
