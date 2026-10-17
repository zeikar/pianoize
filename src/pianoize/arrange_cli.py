"""The arranging commands: the regridded copy of a cover, the per-bar dump an agent arranges
from, and the build and the playability check of the score it writes. They register on the same
Typer app as the rest of the CLI."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Annotated

import mido
import typer

from . import arrange, arrangement, bars, dump, evidence, files, grid, notes, playability, regrid
from .cli import _fail, _read_midi, _refuse_input, app

_RANGE = re.compile(r"(\d+)-(\d+)")


def _read_timed(path: Path) -> mido.MidiFile:
    """A melody or a source, whose notes are placed by their seconds on the cover's bars."""
    midi = _read_midi(path)
    if midi.type == 2:
        raise _fail(f"{path}: a type 2 MIDI file's tracks share no timeline to place notes on")
    return midi


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
    melody_path: Annotated[
        Path | None,
        typer.Option(
            "--melody",
            metavar="MELODY.mid",
            help="tsumugi's melody: after the report, list each vocal note the top of the right "
            "hand leaves out.",
            exists=True,
            dir_okay=False,
        ),
    ] = None,
    full: Annotated[
        bool,
        typer.Option(
            "--full",
            help="A full arrangement, for listening: no limits on the keys a hand holds, its "
            "span, its jumps or crossed hands. A key struck twice or in both hands, the melody "
            "on top of both hands and the harmony are still checked.",
        ),
    ] = False,
) -> None:
    """Check a score is playable, unless --full, and fits its own chords.

    The notes are checked as the build plays them: hand by hand for playability, unless --full,
    and the accompaniment against the score's chords. Exit 1 while any finding is flagged; a
    finding listed, not flagged, leaves it clean, as do the vocal notes --melody lists.
    """
    midi, meter, score = _load(score_path, cover)
    sung = None if melody_path is None else _read_timed(melody_path)
    tempo_map = notes.tempo_map(midi)
    try:
        findings = playability.check(score, meter, tempo_map, full=full)
    except arrangement.ArrangementError as exc:
        raise _fail(f"{score_path}: {exc}") from exc
    typer.echo(playability.report(findings, meter))
    if sung is not None:
        missing = playability.missing(score, meter, tempo_map, sung)
        typer.echo(playability.missing_report(missing, meter, tempo_map))
    if any(finding.flagged for finding in findings):
        raise typer.Exit(1)


@app.command("dump-bars")
def dump_bars(
    cover: Annotated[Path, typer.Argument(metavar="COVER.mid", exists=True, dir_okay=False)],
    melody_path: Annotated[
        Path | None,
        typer.Option(
            "--melody",
            metavar="MELODY.mid",
            help="tsumugi's melody track, placed on the cover's bars by its seconds; without it, "
            "every V line is empty, as on an instrumental.",
            exists=True,
            dir_okay=False,
        ),
    ] = None,
    source_path: Annotated[
        Path | None,
        typer.Option(
            "--source",
            metavar="SOURCE.mid",
            help="tsumugi's transcription, a track per instrument: in a bar without vocal, each "
            "track's top line, placed by its seconds.",
            exists=True,
            dir_okay=False,
        ),
    ] = None,
    every_bar: Annotated[
        bool,
        typer.Option(
            "--every-bar",
            help="With --source, print the instrument lines in every bar, sung bars included.",
        ),
    ] = False,
    every_note: Annotated[
        bool,
        typer.Option(
            "--every-note",
            help="With --source, print every note of each instrument's attacks, not only its "
            "top line.",
        ),
    ] = False,
    drums: Annotated[
        bool,
        typer.Option(
            "--drums",
            help="With --source, print the drums' hits per bar: kick, snare, hihat, cymbal and "
            "other, in sixteenths",
        ),
    ] = False,
    bar_range: Annotated[
        str | None, typer.Option("--bars", metavar="A-B", help="Print only bars A to B.")
    ] = None,
) -> None:
    """Print the cover's attacks and the melody bar by bar, for an agent to arrange from."""
    if every_bar and source_path is None:
        raise typer.BadParameter(
            "needs --source, whose instrument lines it prints", param_hint="--every-bar"
        )
    if drums and source_path is None:
        raise typer.BadParameter("needs --source, whose drums it prints", param_hint="--drums")
    if every_note and source_path is None:
        raise typer.BadParameter(
            "needs --source, whose instrument lines it prints", param_hint="--every-note"
        )
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
    melody = None if melody_path is None else _read_timed(melody_path)
    source = None if source_path is None else _read_timed(source_path)
    try:
        found = dump.lines(midi, melody, selected, source, every_bar, drums, every_note)
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


@app.command("build-grid")
def build_grid(
    source: Annotated[Path, typer.Argument(metavar="SOURCE.mid", exists=True, dir_okay=False)],
    out: Annotated[Path, typer.Option("-o", "--out", help="The grid MIDI to write.")],
    tracks: Annotated[
        list[str],
        typer.Option(
            "--track",
            metavar="NAME",
            default_factory=lambda: list(grid.DEFAULT_TRACKS),
            help="A track of the transcription to copy, by name; repeat it for several. "
            f"Default: {', '.join(grid.DEFAULT_TRACKS)}.",
        ),
    ],
) -> None:
    """Build the tempo-grid cover of a transcription: its tempo map, chord markers and band."""
    _refuse_input(out, [source], "--out")
    midi = _read_midi(source)
    try:
        built = grid.build(midi, tracks)
    except grid.GridError as exc:
        raise _fail(f"{source}: {exc}") from exc
    try:
        files.write_all({out: built.save})
    except OSError as exc:
        raise _fail(str(exc)) from exc
    conductor, *copied = built.tracks
    count = [sum(m.type == kind for m in conductor) for kind in grid.CONDUCTOR]
    typer.echo(
        f"conductor: {count[0]} tempo changes, {count[1]} time signatures, {count[2]} markers"
    )
    for track in copied:
        played = sum(m.type == "note_on" and m.velocity > 0 for m in track)
        typer.echo(f"{track.name}: {played} notes")
