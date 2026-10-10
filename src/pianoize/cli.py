"""Typer CLI for pianoize."""

from __future__ import annotations

import os
from collections import Counter
from enum import StrEnum
from pathlib import Path
from typing import Annotated

import mido
import typer

from . import __version__, checkpoints, corrections, melody, report, score, timeline
from . import chordotomy as chordotomy_module
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
_ROW_SUFFIXES = (_CHORDS_SUFFIX, ".mid", ".wav")


def _fail(message: str) -> typer.Exit:
    typer.echo(f"error: {message}", err=True)
    return typer.Exit(1)


def _parse_rows(values: list[str]) -> list[tuple[str, Path]]:
    rows = []
    for value in values:
        name, separator, path = value.partition("=")
        if not separator or not name or not path:
            raise typer.BadParameter(f"{value!r} is not name=path", param_hint="ROW")
        if not path.endswith(_ROW_SUFFIXES):
            raise typer.BadParameter(
                f"{path}: rows must be {', '.join(_ROW_SUFFIXES)} files", param_hint="ROW"
            )
        if name != Path(name).name or name in (".", ".."):
            raise typer.BadParameter(
                f"row name {name!r} is not a plain file name", param_hint="ROW"
            )
        if any(name == seen for seen, _ in rows):
            raise typer.BadParameter(f"row name {name!r} is used twice", param_hint="ROW")
        rows.append((name, Path(path)))
    return rows


class Engine(StrEnum):
    AUTO = "auto"
    DSP = "dsp"
    MODEL = "model"


def _refuse_overwriting_inputs(
    parsed: list[tuple[str, Path]], out_dir: Path, inputs: list[Path]
) -> None:
    # A row's outputs share OUT_DIR with whatever else is there: a name that lands on an input
    # would make that input pass for the row's analysis, or overwrite it under --force.
    taken = {path.resolve() for path in inputs} | {path.resolve() for _, path in parsed}
    for name, path in parsed:
        if path.name.endswith(_CHORDS_SUFFIX):
            continue
        outputs = [out_dir / f"{name}{_CHORDS_SUFFIX}"]
        if path.suffix == ".mid":
            outputs.append(out_dir / f"{name}.wav")
        for output in outputs:
            if output.resolve() in taken:
                raise typer.BadParameter(
                    f"row {name!r} would overwrite an input: {output}", param_hint="ROW"
                )


def _soundfont_path(value: Path | None) -> Path:
    if value is not None:
        return value
    env = os.environ.get("PIANOIZE_SOUNDFONT")
    if not env:
        raise typer.BadParameter(
            "give --soundfont or set PIANOIZE_SOUNDFONT", param_hint="--soundfont"
        )
    return Path(env)


def _read_midi(path: Path) -> mido.MidiFile:
    try:
        return mido.MidiFile(path)
    except (OSError, EOFError, ValueError) as exc:
        raise _fail(f"{path}: cannot read MIDI: {exc}") from exc


@app.command()
def evaluate(
    rows: Annotated[
        list[str], typer.Argument(help="name=path of a .chords.json, .wav or .mid result.")
    ],
    original: Annotated[
        Path, typer.Option(help="The original's timeline.", exists=True, dir_okay=False)
    ],
    checkpoints_path: Annotated[
        Path,
        typer.Option("--checkpoints", help="The checkpoint file.", exists=True, dir_okay=False),
    ],
    out_dir: Annotated[
        Path, typer.Option(help="Where table.md and the rendered and analyzed rows are written.")
    ],
    soundfont: Annotated[
        Path | None,
        typer.Option(help="The SoundFont for .mid rows; defaults to $PIANOIZE_SOUNDFONT."),
    ] = None,
    chordotomy: Annotated[
        Path | None,
        typer.Option(
            help="The chordotomy executable; defaults to $PIANOIZE_CHORDOTOMY, then PATH."
        ),
    ] = None,
    engine: Annotated[Engine, typer.Option(help="chordotomy's engine.")] = Engine.MODEL,
    force: Annotated[
        bool, typer.Option("--force", help="Render and analyze again over existing outputs.")
    ] = False,
) -> None:
    """Score results against the original at the checkpoints and write the table.

    A .mid row is rendered to OUT_DIR/NAME.wav, and a .wav row is analyzed to
    OUT_DIR/NAME.chords.json. Both are reused when they exist, unless --force: a model
    analysis takes minutes per song.
    """
    parsed = _parse_rows(rows)
    _refuse_overwriting_inputs(parsed, out_dir, [original, checkpoints_path])
    if any(path.suffix == ".mid" for _, path in parsed):
        soundfont = _soundfont_path(soundfont)
    try:
        original_timeline = timeline.load(original)
        spans, excluded = checkpoints.load(checkpoints_path, original_timeline)
        out_dir.mkdir(parents=True, exist_ok=True)
        exe = None
        scored = []
        for name, path in parsed:
            if path.name.endswith(_CHORDS_SUFFIX):
                result = timeline.load(path)
            else:
                out = out_dir / f"{name}{_CHORDS_SUFFIX}"
                if force or not out.exists():
                    audio = path
                    if path.suffix == ".mid":
                        audio = out_dir / f"{name}.wav"
                        if force or not audio.exists():
                            render_module.render(_read_midi(path), audio, soundfont)
                    exe = exe or chordotomy_module.executable(chordotomy)
                    typer.echo(f"analyzing {name}...", err=True)
                    result = chordotomy_module.analyze(audio, out, exe, engine.value)
                else:
                    result = timeline.load(out)
            scored.append((name, score.score(original_timeline, spans, excluded, result)))
        table = report.markdown(original_timeline, scored)
        (out_dir / "table.md").write_text(table, encoding="utf-8")
    except (
        timeline.TimelineError,
        checkpoints.CheckpointError,
        chordotomy_module.ChordotomyError,
        render_module.RenderError,
        OSError,
    ) as exc:
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
    soundfont = _soundfont_path(soundfont)
    if out.resolve() in (midi.resolve(), soundfont.resolve()):
        raise typer.BadParameter(f"would overwrite an input: {out}", param_hint="--out")
    source = _read_midi(midi)
    try:
        peak = render_module.render(source, out, soundfont, gain=gain)
    except (render_module.RenderError, OSError) as exc:
        raise _fail(str(exc)) from exc
    typer.echo(f"peak {peak:.3f}")
    if peak >= _CLIPPING:
        typer.echo(f"warning: peak {peak:.3f} may clip; lower --gain", err=True)


def _percent(ratio: float | None) -> str:
    return "n/a" if ratio is None else f"{ratio:.1%}"


def _clock(seconds: float) -> str:
    minutes, rest = divmod(round(seconds, 1), 60)
    return f"{int(minutes)}:{rest:04.1f}"


@app.command("melody-clashes")
def melody_clashes(
    melody_path: Annotated[Path, typer.Argument(metavar="MELODY.mid", exists=True, dir_okay=False)],
    timeline_path: Annotated[
        Path, typer.Argument(metavar="TIMELINE.chords.json", exists=True, dir_okay=False)
    ],
    mono: Annotated[
        bool, typer.Option("--mono", help="Reduce the melody to one voice first.")
    ] = False,
) -> None:
    """List the melody notes that clash with the chord under them."""
    midi = _read_midi(melody_path)
    try:
        chords = timeline.load(timeline_path)
    except timeline.TimelineError as exc:
        raise _fail(str(exc)) from exc
    found = melody.notes(midi)
    if mono:
        found = melody.monophonic(found)
    result = melody.clashes(found, chords)
    typer.echo(f"notes: {result.consonant_notes} consonant, {result.clashing_notes} clashing")
    typer.echo(f"clash ratio by notes: {_percent(result.note_ratio)}")
    consonant, clashing = result.consonant_seconds, result.clashing_seconds
    typer.echo(f"time: {consonant:.1f} s consonant, {clashing:.1f} s clashing")
    typer.echo(f"clash ratio by duration: {_percent(result.duration_ratio)}")
    for clash in result.clashes:
        typer.echo(f"{_clock(clash.time)}  {melody.pitch_name(clash.pitch)}  over {clash.chord}")


@app.command("apply-corrections")
def apply_corrections(
    cover: Annotated[Path, typer.Argument(metavar="COVER.mid", exists=True, dir_okay=False)],
    spec_path: Annotated[Path, typer.Argument(metavar="SPEC.json", exists=True, dir_okay=False)],
    melody_path: Annotated[
        Path,
        typer.Option(
            "--melody",
            metavar="MELODY.mid",
            help="tsumugi's melody track, whose notes keep the cover's melody at its pitch.",
            exists=True,
            dir_okay=False,
        ),
    ],
    out: Annotated[Path, typer.Option("-o", "--out", help="The corrected MIDI file to write.")],
) -> None:
    """Apply a correction spec to a copy of the cover."""
    if out.resolve() in (cover.resolve(), spec_path.resolve(), melody_path.resolve()):
        raise typer.BadParameter(f"would overwrite an input: {out}", param_hint="--out")
    try:
        spec = corrections.load(spec_path, cover, melody_path)
        result, _ = corrections.apply(_read_midi(cover), spec)
        corrections.write(result, out)
    except (corrections.CorrectionError, OSError) as exc:
        raise _fail(str(exc)) from exc
    counts = Counter(edit.op for edit in spec.edits)
    typer.echo(
        f"notes: {counts['delete']} deleted, {counts['modify']} modified, {counts['add']} added"
    )
