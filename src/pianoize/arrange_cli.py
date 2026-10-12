"""The arranging commands: the regridded copy of a cover, the per-bar dump an agent arranges
from, and the build and the playability check of the score it writes. They register on the same
Typer app as the rest of the CLI."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Annotated

import mido
import typer

from . import arrange, arrangement, bars, dump, evidence, files, notes, playability, regrid
from .cli import _fail, _read_midi, _refuse_input, app

_RANGE = re.compile(r"(\d+)-(\d+)")


def _load(
    score_path: Path, cover_path: Path
) -> tuple[mido.MidiFile, bars.Meter, arrangement.Score]:
    """The cover, its meter and the score read on that meter."""
    cover = _read_midi(cover_path)
    if cover.type == 2:
        raise _fail(f"{cover_path}: a type 2 MIDI file's tracks share no timeline to build on")
    try:
        meter = bars.meter(cover)
    except bars.MeterError as exc:
        raise _fail(f"{cover_path}: {exc}") from exc
    try:
        # utf-8-sig: an editor that saves with a byte order mark would hide the `format` line.
        text = score_path.read_text(encoding="utf-8-sig")
        score = arrangement.parse(text, meter.sixteenths_per_bar)
    except (arrangement.ArrangementError, UnicodeDecodeError, OSError) as exc:
        raise _fail(f"{score_path}: {exc}") from exc
    return cover, meter, score


_SCORE = typer.Argument(metavar="SCORE.txt", exists=True, dir_okay=False)
_COVER = typer.Option(
    "--cover",
    metavar="COVER.mid",
    help="The cover whose meter, tempo map and resolution the score is placed on.",
    exists=True,
    dir_okay=False,
)


@app.command("build-arrangement")
def build_arrangement(
    score_path: Annotated[Path, _SCORE],
    cover: Annotated[Path, _COVER],
    out: Annotated[Path, typer.Option("-o", "--out", help="The MIDI file to write.")],
) -> None:
    """Build a score into a two-hand MIDI on the cover's tempo map."""
    _refuse_input(out, [score_path, cover], "--out")
    midi, _, score = _load(score_path, cover)
    try:
        built = arrange.build(score, midi)
    except arrangement.ArrangementError as exc:
        raise _fail(f"{score_path}: {exc}") from exc
    try:
        files.write_all({out: built.save})
    except OSError as exc:
        raise _fail(str(exc)) from exc
    right, left = (sum(m.type == "note_on" for m in track) for track in built.tracks)
    # Both tracks carry the same pedal, each on its own channel: one track's presses count it.
    presses = sum(m.type == "control_change" and m.value == 127 for m in built.tracks[0])
    typer.echo(f"notes: {right} right hand, {left} left hand")
    typer.echo(f"pedal presses: {presses}")
    typer.echo(f"length: {built.length:.1f} s")


@app.command("check-arrangement")
def check_arrangement(
    score_path: Annotated[Path, _SCORE],
    cover: Annotated[Path, _COVER],
) -> None:
    """Check a score is playable and fits its own chords.

    The notes are checked as the build plays them: hand by hand for playability, and the
    accompaniment against the score's chords. Exit 1 while any finding is flagged; a finding
    listed, not flagged, leaves it clean.
    """
    midi, meter, score = _load(score_path, cover)
    try:
        findings = playability.check(score, meter, notes.tempo_map(midi))
    except arrangement.ArrangementError as exc:
        raise _fail(f"{score_path}: {exc}") from exc
    typer.echo(playability.report(findings, meter))
    if any(finding.flagged for finding in findings):
        raise typer.Exit(1)


@app.command("dump-bars")
def dump_bars(
    cover: Annotated[Path, typer.Argument(metavar="COVER.mid", exists=True, dir_okay=False)],
    melody_path: Annotated[
        Path,
        typer.Option(
            "--melody",
            metavar="MELODY.mid",
            help="tsumugi's melody track, placed on the cover's bars by its seconds.",
            exists=True,
            dir_okay=False,
        ),
    ],
    bar_range: Annotated[
        str | None, typer.Option("--bars", metavar="A-B", help="Print only bars A to B.")
    ] = None,
) -> None:
    """Print the cover's attacks and the melody bar by bar, for an agent to arrange from."""
    selected = None
    if bar_range is not None:
        match = _RANGE.fullmatch(bar_range)
        if not match:
            raise typer.BadParameter(f"{bar_range!r} is not A-B", param_hint="--bars")
        selected = int(match[1]), int(match[2])
        if not 1 <= selected[0] <= selected[1]:
            raise typer.BadParameter(
                f"{bar_range!r}: bars count from 1 and A is at most B", param_hint="--bars"
            )
    midi = _read_midi(cover)
    melody = _read_midi(melody_path)
    try:
        found = dump.lines(midi, melody, selected)
    except (bars.MeterError, evidence.EvidenceError) as exc:
        raise _fail(f"{cover}: {exc}") from exc
    for line in found:
        typer.echo(line)


@app.command("regrid")
def regrid_cover(
    cover: Annotated[Path, typer.Argument(metavar="COVER.mid", exists=True, dir_okay=False)],
    out: Annotated[Path, typer.Option("-o", "--out", help="The regridded copy to write.")],
) -> None:
    """Find the cover's tempo hiccups and write a copy with the song's bars on the grid.

    Only the tempo map and the ticks change; every note keeps its time in seconds.
    """
    _refuse_input(out, [cover], "--out")
    midi = _read_midi(cover)
    if midi.type == 2:
        raise _fail(f"{cover}: a type 2 MIDI file's tracks share no timeline to regrid")
    try:
        meter = bars.meter(midi)
    except bars.MeterError as exc:
        raise _fail(f"{cover}: {exc}") from exc
    spans = regrid.hiccups(midi, meter)
    try:
        files.write_all({out: regrid.repair(midi, spans).save})
    except OSError as exc:
        raise _fail(str(exc)) from exc
    for span in spans:
        old = ", ".join(f"{mido.tempo2bpm(tempo):.2f}" for tempo in span.tempos)
        typer.echo(
            f"bars {span.start // meter.bar_ticks + 1}-{span.end // meter.bar_ticks}: {old} BPM "
            f"-> {span.bars} bars at {mido.tempo2bpm(span.tempo):.2f}"
        )
    if not spans:
        typer.echo("no tempo hiccups")
