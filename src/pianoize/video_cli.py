"""The video commands. They register on the same Typer app as the rest of the CLI."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Annotated

import typer

from . import files, roll, serve, video
from .cli import (
    _fail,
    _read_midi,
    _refuse_input,
    _report_peak,
    _soundfont_path,
    _stop_on_signals,
    app,
)
from .render import RenderError


def _read_cards(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise _fail(f"{path}: {exc}") from exc


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


@app.command("preview-video")
def preview_video(
    midi_path: Annotated[Path, typer.Argument(metavar="ARRANGED.mid", exists=True, dir_okay=False)],
    cards: Annotated[
        Path,
        typer.Option(
            help="The title card's lines; a '---' line and what follows are not drawn.",
            exists=True,
        ),
    ],
    soundfont: Annotated[
        Path | None,
        typer.Option(help="The SoundFont; defaults to $PIANOIZE_SOUNDFONT."),
    ] = None,
    gain: Annotated[float, typer.Option(help="FluidSynth's master gain.")] = 0.5,
) -> None:
    """Serve the falling-notes video as a page to watch in a browser."""
    _stop_on_signals()
    soundfont = _soundfont_path(soundfont)
    midi = _read_midi(midi_path)
    cards_text = _read_cards(cards)
    try:
        # Beside the MIDI, as render's scratch sits beside its WAV, so the song's files stay
        # in work/.
        with tempfile.TemporaryDirectory(dir=midi_path.parent, prefix=".preview-") as tmp:
            run_dir = Path(tmp)
            _, peak = video.prepare(midi, cards_text, soundfont, run_dir, gain)
            _report_peak(peak)
            server = serve.start(video.VIEWER, run_dir)
            typer.echo(f"preview: {serve.url(server)}")
            typer.echo("press Ctrl-C to stop")
            serve.wait(server)
    except (roll.RollError, video.VideoError, RenderError, OSError) as exc:
        raise _fail(str(exc)) from exc


@app.command("render-video")
def render_video(
    midi_path: Annotated[Path, typer.Argument(metavar="ARRANGED.mid", exists=True, dir_okay=False)],
    cards: Annotated[
        Path,
        typer.Option(
            help="The title card's lines; a '---' line and what follows are not drawn.",
            exists=True,
        ),
    ],
    out: Annotated[Path, typer.Option("-o", "--out", help="The MP4 file to write.")],
    soundfont: Annotated[
        Path | None,
        typer.Option(help="The SoundFont; defaults to $PIANOIZE_SOUNDFONT."),
    ] = None,
    gain: Annotated[float, typer.Option(help="FluidSynth's master gain.")] = 0.5,
) -> None:
    """Render the falling-notes video to an MP4, captured in Chrome and encoded with ffmpeg."""
    _stop_on_signals()
    soundfont = _soundfont_path(soundfont)
    _refuse_input(out, [midi_path, cards, soundfont], "--out")
    midi = _read_midi(midi_path)
    cards_text = _read_cards(cards)
    try:
        moments, peak = video.render_video(midi, cards_text, soundfont, out, gain)
    except (roll.RollError, video.VideoError, RenderError, OSError) as exc:
        raise _fail(str(exc)) from exc
    _report_peak(peak)
    typer.echo(f"frames: {moments.frames}")
    typer.echo(f"length: {moments.end:.1f} s")
