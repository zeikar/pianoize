"""A finder run against a correction spec: the candidates left once the spec is applied, under the
original cover's note ids, and the status of every candidate the spec had to judge. See
docs/polishing.md."""

from dataclasses import dataclass

import mido

from . import candidates, corrections, notes
from .finding import Candidate, Thresholds, clock

FIXED, KEPT, STILL_PRESENT, UNJUDGED = "fixed", "kept", "still present", "unjudged"
STATUSES = (FIXED, KEPT, STILL_PRESENT, UNJUDGED)
OPEN = (STILL_PRESENT, UNJUDGED)  # a spec with a line of these is not finished


@dataclass(frozen=True)
class Line:
    candidate: str  # a candidate id
    time: float  # seconds: the verdict's, else the found candidate's
    status: str
    reason: str  # the verdict's; empty without one


def after(
    midi: mido.MidiFile,
    spec: corrections.Spec,
    timeline: dict,
    melody_notes: list[notes.Note],
    thresholds: Thresholds,
) -> list[Candidate]:
    """The candidates in the cover once the spec is applied, every note named by its id in the
    cover, or add-{id} for an added one. The melody notes are matched again on the corrected
    notes, so a retimed melody note still carries the melody while it matches."""
    corrected, identity = corrections.apply(midi, spec)
    guarded = notes.protected(notes.read(corrected), melody_notes)
    return candidates.find(corrected, timeline, guarded, thresholds, identity)


def lines(
    before: list[Candidate], after: list[Candidate], verdicts: list[corrections.Verdict]
) -> list[Line]:
    """One line per candidate found before the spec, found after it or given a verdict, by time
    then id."""
    found_before = {c.id: c for c in before}
    found_after = {c.id: c for c in after}
    judged = {verdict.candidate: verdict for verdict in verdicts}
    found = []
    for candidate in found_before.keys() | found_after.keys() | judged.keys():
        verdict = judged.get(candidate)
        if verdict is None:
            # A candidate another edit removed still had to be judged.
            time = (found_after.get(candidate) or found_before[candidate]).time
            found.append(Line(candidate, time, UNJUDGED, ""))
        elif verdict.action == "keep":
            found.append(Line(candidate, verdict.time, KEPT, verdict.reason))
        else:
            status = STILL_PRESENT if candidate in found_after else FIXED
            found.append(Line(candidate, verdict.time, status, verdict.reason))
    return sorted(found, key=lambda line: (line.time, line.candidate))


def kind(candidate: str) -> str:
    """`category/kind` of a candidate id."""
    return "/".join(candidate.split(":")[:2])


def _cell(text: str) -> str:
    # Reasons are free text: a line break or a pipe would split the row.
    return " ".join(text.split()).replace("|", "\\|")


def markdown(found: list[Line]) -> str:
    rows = [
        "| candidate | category/kind | time | status | reason |",
        "| --- | --- | --- | --- | --- |",
    ]
    rows += [
        f"| {_cell(line.candidate)} | {_cell(kind(line.candidate))} | {clock(line.time)} "
        f"| {line.status} | {_cell(line.reason)} |"
        for line in found
    ]
    return "\n".join(rows) + "\n"
