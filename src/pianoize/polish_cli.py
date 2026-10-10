"""The polishing commands: candidates, corrections, the refined timeline and the harmony
evidence. They register on the same Typer app as the rest of the CLI."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from pathlib import Path
from typing import Annotated

import typer

from . import candidates, corrections, evidence, files, notes, refine, review, timeline
from .cli import _clock, _fail, _is_one_of, _read_midi, _refuse_input, app


def _candidate_line(found: candidates.Candidate) -> str:
    if found.note is not None:
        where = f"{found.note['id']} {found.note['pitch_name']}"
    else:
        segment = found.segment
        where = f"b{segment['start_beat']}-{segment['end_beat']} {segment['chord'] or ''}".rstrip()
    key, value = next(iter(found.measurements.items()))
    return f"{_clock(found.time)}  {found.category}/{found.kind}  {where}  {key}={value}"


def _saving(text: str) -> Callable[[Path], None]:
    return lambda path: path.write_text(text, encoding="utf-8")


def _write(outputs: dict[Path, str]) -> None:
    """Write the text files, every one saved before any replaces an existing file."""
    try:
        files.write_all({path: _saving(text) for path, text in outputs.items()})
    except OSError as exc:
        raise _fail(str(exc)) from exc


def _print_statuses(lines: list[review.Line]) -> None:
    """Print the lines a spec leaves open and a count per status; exit 1 when any is open."""
    for line in lines:
        if line.status in review.OPEN:
            typer.echo(
                f"{_clock(line.time)}  {review.kind(line.candidate)}  {line.candidate}  "
                f"{line.status}"
            )
    counts = Counter(line.status for line in lines)
    typer.echo("candidates: " + ", ".join(f"{counts[s]} {s}" for s in review.STATUSES))
    if any(counts[s] for s in review.OPEN):
        raise typer.Exit(1)
    typer.echo("all candidates judged")


@app.command("find-candidates")
def find_candidates(
    cover: Annotated[Path, typer.Argument(metavar="COVER.mid", exists=True, dir_okay=False)],
    timeline_path: Annotated[
        Path,
        typer.Option(
            "--timeline",
            metavar="TIMELINE.chords.json",
            help="The harmony timeline: the beats the timing grid divides and the chords.",
            exists=True,
            dir_okay=False,
        ),
    ],
    melody_path: Annotated[
        Path,
        typer.Option(
            "--melody",
            metavar="MELODY.mid",
            help="tsumugi's melody track, which marks the cover's melody notes.",
            exists=True,
            dir_okay=False,
        ),
    ],
    out: Annotated[Path, typer.Option("-o", "--out", help="The candidates JSON to write.")],
    spec_path: Annotated[
        Path | None,
        typer.Option(
            "--spec",
            metavar="SPEC.json",
            help="A correction spec for the cover: find the candidates left once it is applied, "
            "under the cover's note ids, and check every candidate has a verdict.",
            exists=True,
            dir_okay=False,
        ),
    ] = None,
    report_path: Annotated[
        Path | None,
        typer.Option(
            "--report",
            metavar="REPORT.md",
            help="With --spec, the markdown table of every candidate's status to write.",
        ),
    ] = None,
) -> None:
    """List the places in a cover that may need polishing, for an agent to judge.

    With --spec, exit 1 while a candidate has no verdict or a fixed one is still found.
    """
    inputs = {"cover": cover, "timeline": timeline_path, "melody": melody_path}
    if spec_path is not None:
        inputs["spec"] = spec_path
    elif report_path is not None:
        raise typer.BadParameter("needs --spec", param_hint="--report")
    _refuse_input(out, list(inputs.values()), "--out")
    _refuse_input(report_path, list(inputs.values()), "--report")
    if report_path is not None and _is_one_of(report_path, [out]):
        raise typer.BadParameter(f"{report_path} is also --out", param_hint="--report")
    midi = _read_midi(cover)
    try:
        corrections.check_cover(midi)
    except corrections.CorrectionError as exc:
        raise _fail(f"{cover}: {exc}") from exc
    try:
        chords = timeline.load(timeline_path)
        spec = None if spec_path is None else corrections.load(spec_path, cover, melody_path)
    except (timeline.TimelineError, corrections.CorrectionError) as exc:
        raise _fail(str(exc)) from exc
    melody_notes = notes.read(_read_midi(melody_path))
    guarded = notes.protected(notes.read(midi), melody_notes)
    thresholds = candidates.Thresholds()
    found = candidates.find(midi, chords, guarded, thresholds)
    if spec is None:
        _write({out: candidates.to_json(found, inputs, thresholds)})
        for candidate in found:
            typer.echo(_candidate_line(candidate))
        counts = Counter(candidate.category for candidate in found)
        typer.echo("candidates: " + ", ".join(f"{counts[c]} {c}" for c in candidates.CATEGORIES))
        return
    remaining = review.after(midi, spec, chords, melody_notes, thresholds)
    lines = review.lines(found, remaining, spec.verdicts)
    outputs = {out: candidates.to_json(remaining, inputs, thresholds)}
    if report_path is not None:
        outputs[report_path] = review.markdown(lines)
    _write(outputs)
    _print_statuses(lines)


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
    _refuse_input(out, [cover, spec_path, melody_path], "--out")
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


@app.command("refine-timeline")
def refine_timeline(
    original_path: Annotated[
        Path, typer.Argument(metavar="ORIGINAL.chords.json", exists=True, dir_okay=False)
    ],
    edits_path: Annotated[Path, typer.Argument(metavar="EDITS.json", exists=True, dir_okay=False)],
    out: Annotated[
        Path,
        typer.Option(
            "-o", "--out", help="The refined timeline to write, named <stem>.refined.chords.json."
        ),
    ],
) -> None:
    """Write chordotomy's timeline with the edits' chords over their beats, checked by the
    viewer's rules."""
    _refuse_input(out, [original_path, edits_path], "--out")
    try:
        original = timeline.load(original_path)
        edits = refine.load_edits(edits_path, original_path, original)
        result, changed = refine.apply(original, edits)
        refine.write(result, out)
    except (timeline.TimelineError, refine.RefineError, OSError) as exc:
        raise _fail(str(exc)) from exc
    typer.echo(f"segments changed: {changed}")


@app.command("harmony-evidence")
def harmony_evidence(
    cover: Annotated[Path, typer.Argument(metavar="COVER.mid", exists=True, dir_okay=False)],
    timeline_path: Annotated[
        Path, typer.Argument(metavar="TIMELINE.chords.json", exists=True, dir_okay=False)
    ],
    source: Annotated[
        Path | None,
        typer.Option(
            metavar="SOURCE.mid",
            help="tsumugi's transcription: its markers and its bass track.",
            exists=True,
            dir_okay=False,
        ),
    ] = None,
    bass_track: Annotated[
        str, typer.Option(help="The source's bass track; an empty name reads none.")
    ] = "electric_bass",
    melody_path: Annotated[
        Path | None,
        typer.Option(
            "--melody",
            metavar="MELODY.mid",
            help="tsumugi's melody track: the melody column, and the cover notes that carry it, "
            "which the cover's tones and coverage leave out.",
            exists=True,
            dir_okay=False,
        ),
    ] = None,
    out: Annotated[Path | None, typer.Option("-o", "--out", help="Also write the table.")] = None,
) -> None:
    """Print per chord segment what the timeline, the transcription and the cover's notes say.

    On a refined timeline and a polished cover, the direct check of the notes against the harmony.
    """
    _refuse_input(out, [p for p in (cover, timeline_path, source, melody_path) if p], "--out")
    played = notes.read(_read_midi(cover))
    melody_notes = [] if melody_path is None else notes.read(_read_midi(melody_path))
    marked, bass = [], []
    try:
        chords = timeline.load(timeline_path)
        if source is not None:
            transcription = _read_midi(source)
            marked = evidence.markers(transcription)
            if bass_track:  # tsumugi writes no bass track for a song it hears no bass in
                bass = evidence.track_notes(transcription, bass_track)
    except (timeline.TimelineError, evidence.EvidenceError) as exc:
        raise _fail(str(exc)) from exc
    guarded = notes.protected(played, melody_notes)
    table = evidence.markdown(evidence.rows(chords, played, guarded, marked, bass, melody_notes))
    if out is not None:
        _write({out: table})
    typer.echo(table, nl=False)
