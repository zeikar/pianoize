"""Harmony candidates: segments whose accompaniment strays from the chord, and segments that never
sound one of the chord's tones. The rules are in docs/polishing.md; pedal is ignored, a note
sounds from its note-on to its note-off."""

from collections.abc import Iterator

from . import notes
from .chords import ROOT_NAMES, chord_pitch_classes
from .finding import Candidate, Cover, Thresholds, context_note, grid_time, name
from .melody import pitch_name, spans, tones
from .score import label
from .timeline import beat_position

_PASSING_BEATS = 0.5  # a passing tone lasts at most this long
_STEP = 2  # semitones: a passing tone is approached and left by a step of at most this
# A segment struck once, or shorter than a beat, says little about what it leaves out.
_MISSING_ATTACKS = 2
_MISSING_BEATS = 1


def _held(note: notes.Note, start: float, end: float) -> float:
    """Seconds the note sounds between start and end."""
    return max(0.0, min(note.offset, end) - max(note.onset, start))


def coverage(
    played: list[notes.Note], start: float, end: float, chord_tones: set[int]
) -> float | None:
    """The share of the notes' sounding time between start and end that is on the pitch classes
    `chord_tones`; None when no note sounds there."""
    total = on_tones = 0.0
    for note in played:
        held = _held(note, start, end)
        total += held
        if note.pitch % 12 in chord_tones:
            on_tones += held
    return on_tones / total if total else None


def missing(played: list[notes.Note], start: float, end: float, segment: dict) -> list[int]:
    """The pitch classes of the chord's root, third and fifth, then its slash bass, that no note
    strikes or holds between start and end."""
    wanted = list(chord_pitch_classes(segment["chord"])[:3])
    if segment["bass"] is not None and ROOT_NAMES.index(segment["bass"]) not in wanted:
        wanted.append(ROOT_NAMES.index(segment["bass"]))
    heard = {note.pitch % 12 for note in played if _held(note, start, end) > 0}
    return [pc for pc in wanted if pc not in heard]


def _around(
    attacks: list[list[notes.Note]],
) -> dict[str, tuple[list[notes.Note] | None, list[notes.Note] | None]]:
    """Each note's id -> the attacks just before and after its own."""
    padded = [None, *attacks, None]
    return {n.id: (padded[i], padded[i + 2]) for i, attack in enumerate(attacks) for n in attack}


def _steps_to(note: notes.Note, attack: list[notes.Note] | None) -> bool:
    return attack is not None and any(0 < abs(n.pitch - note.pitch) <= _STEP for n in attack)


def _passing(
    cover: Cover,
    limits: Thresholds,
    note: notes.Note,
    before: list[notes.Note] | None,
    after: list[notes.Note] | None,
) -> bool:
    """Whether a note is a passing tone: at most half a beat long, starting more than
    `off_grid_ms` from the nearest beat, with a note a step away in the attacks just before and
    after its own."""
    position = beat_position(cover.timeline, note.onset)
    if beat_position(cover.timeline, note.offset) - position > _PASSING_BEATS:
        return False
    beat = grid_time(cover.timeline, round(position))
    if abs(note.onset - beat) <= limits.off_grid_ms / 1000:
        return False
    return _steps_to(note, before) and _steps_to(note, after)


def _nearest(pitch: int, chord_tones: set[int], step: int) -> int:
    """The nearest pitch past `pitch` in the direction of `step` (1 or -1) on a chord tone."""
    found = pitch + step
    while found % 12 not in chord_tones:
        found += step
    return found


def _clash(cover: Cover, note: notes.Note, chord_tones: set[int]) -> dict:
    return {
        "note": name(cover, note),
        "pitch_name": pitch_name(note.pitch),
        "on_tick": note.on_tick,
        "off_tick": note.off_tick,
        "below": _nearest(note.pitch, chord_tones, -1),
        "above": _nearest(note.pitch, chord_tones, 1),
    }


def _on_segment(
    cover: Cover, kind: str, start: float, end: float, segment: dict, measurements: dict
) -> Candidate:
    return Candidate(
        id=f"harmony:{kind}:s{segment['start_beat']}",
        category="harmony",
        kind=kind,
        time=round(start, 3),
        beat=float(segment["start_beat"]),
        note=None,
        segment={
            "start_beat": segment["start_beat"],
            "end_beat": segment["end_beat"],
            "chord": label(segment),
        },
        measurements=measurements,
        # A segment's context is every note sounding in it, held ones included.
        context=[context_note(cover, n) for n in cover.played if _held(n, start, end) > 0],
        suggested=None,
    )


def find(cover: Cover, limits: Thresholds) -> Iterator[Candidate]:
    """`coverage` and `missing` candidates, at most one of each per segment with a chord. Only
    the accompaniment is weighed against the chord and listed as clashing, never a note that
    carries the melody, but any note sounding one of its tones counts toward it."""
    accompaniment = [n for n in cover.played if n.id not in cover.protected]
    attacks = notes.clusters(accompaniment)
    around = _around(attacks)
    for start, end, segment in spans(cover.timeline):
        chord_tones = tones(segment)
        absent = [ROOT_NAMES[pc] for pc in missing(cover.played, start, end, segment)]
        share = coverage(accompaniment, start, end, chord_tones)
        if share is not None and share < limits.coverage_below:
            clashes = [
                _clash(cover, n, chord_tones)
                for n in accompaniment
                if _held(n, start, end) > 0
                and n.pitch % 12 not in chord_tones
                and not _passing(cover, limits, n, *around[n.id])
            ]
            measured = {"coverage": round(share, 3), "missing": absent, "clashes": clashes}
            yield _on_segment(cover, "coverage", start, end, segment, measured)
        struck = sum(1 for attack in attacks if start <= attack[0].onset < end)
        beats = beat_position(cover.timeline, end) - beat_position(cover.timeline, start)
        if absent and struck >= _MISSING_ATTACKS and beats >= _MISSING_BEATS:
            yield _on_segment(cover, "missing", start, end, segment, {"missing": absent})
