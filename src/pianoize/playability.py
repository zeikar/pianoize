"""Whether a score is playable by an intermediate-to-advanced pianist, hand by hand, and whether
its accompaniment fits the score's own chords. It checks the notes the build plays."""

from collections.abc import Iterator
from dataclasses import dataclass
from itertools import groupby

from .arrange import separate_restrikes
from .arrangement import Score, ScoreNote, chord_at, chord_pitch_classes, notes_of
from .bars import Meter, where
from .melody import pitch_name
from .notes import seconds_at

NOTES_PER_HAND = 5
SPAN_MAX = 16  # semitones, a tenth: a wider span is flagged
SPAN_WIDE = 14  # a ninth: a wider span is listed, not flagged
JUMPS = ((15, 0.2), (22, 0.36))  # (semitones, seconds): a shift this wide in less time is flagged
JUMP_MAX = 26  # a wider shift is flagged at any speed

RULES = ("notes", "span", "jump", "crossing", "melody", "harmony")


@dataclass(frozen=True)
class Finding:
    rule: str  # one of RULES
    tick: int
    hand: str  # RH | LH
    detail: str
    flagged: bool  # False for a span listed only: over SPAN_WIDE but not over SPAN_MAX


def _attacks(notes: list[ScoreNote]) -> Iterator[tuple[int, list[ScoreNote], list[ScoreNote]]]:
    """Each attack's tick, the notes struck at it and the notes held there (on <= tick < off),
    from notes sorted by onset."""
    held: list[ScoreNote] = []
    for tick, group in groupby(notes, key=lambda note: note.on_tick):
        struck = list(group)
        held = [note for note in held if note.off_tick > tick] + struck
        yield tick, struck, held


def _hand(
    played: list[ScoreNote], hand: str, tempos: list[tuple[int, float, int]], ticks_per_beat: int
) -> list[Finding]:
    """The notes, span and jump findings at each of one hand's attacks."""
    findings = []
    previous = None  # (seconds, centre) of the hand's previous attack
    for tick, struck, held in _attacks(played):
        pitches = sorted(note.pitch for note in struck)
        # Keys, not notes: a pitch struck twice is flagged on its own below.
        keys = sorted({note.pitch for note in held})
        if len(keys) > NOTES_PER_HAND:
            names = " ".join(pitch_name(key) for key in keys)
            findings.append(Finding("notes", tick, hand, f"{len(keys)} held: {names}", True))
        for doubled in sorted({pitch for pitch in pitches if pitches.count(pitch) > 1}):
            detail = f"{pitch_name(doubled)} struck twice"
            findings.append(Finding("notes", tick, hand, detail, True))
        span = keys[-1] - keys[0]
        if span > SPAN_WIDE:
            detail = f"{span} semitones, {pitch_name(keys[0])} to {pitch_name(keys[-1])}"
            findings.append(Finding("span", tick, hand, detail, span > SPAN_MAX))
        seconds = seconds_at(tempos, ticks_per_beat, tick)
        centre = (pitches[0] + pitches[-1]) / 2
        if previous is not None:
            gap, shift = seconds - previous[0], abs(centre - previous[1])
            if shift > JUMP_MAX or any(shift >= wide and gap < fast for wide, fast in JUMPS):
                detail = f"{shift:g} semitones in {gap * 1000:.0f} ms"
                findings.append(Finding("jump", tick, hand, detail, True))
        previous = seconds, centre
    return findings


def check(score: Score, meter: Meter, tempo_map: list[tuple[int, float, int]]) -> list[Finding]:
    """The findings on the notes the build plays, timed by the cover's tempo map
    (notes.tempo_map). A pitch struck twice in one hand at one tick is flagged: the build would
    cut the first strike to a sliver whose note-off releases the key."""
    built = separate_restrikes(notes_of(score, meter), meter)
    findings = []
    for hand in ("RH", "LH"):
        played = [note for note in built if note.hand == hand]
        findings += _hand(played, hand, tempo_map, meter.ticks_per_beat)
    for tick, struck, held in _attacks(built):
        right = [note.pitch for note in held if note.hand == "RH"]
        left = [note.pitch for note in held if note.hand == "LH"]
        if right and left and max(left) >= min(right):
            detail = f"top {pitch_name(max(left))} at or above RH bottom {pitch_name(min(right))}"
            findings.append(Finding("crossing", tick, "LH", detail, True))
        for note in struck:
            if note.role == "M":
                if note.pitch < max(right):
                    detail = f"{pitch_name(note.pitch)} under {pitch_name(max(right))}"
                    findings.append(Finding("melody", tick, note.hand, detail, True))
            elif not note.passing:
                symbol = chord_at(score, meter, tick)
                classes = chord_pitch_classes(symbol)
                if classes is not None and note.pitch % 12 not in classes:
                    detail = f"{note.role} {pitch_name(note.pitch)} over {symbol}"
                    findings.append(Finding("harmony", tick, note.hand, detail, True))
    return findings


def report(findings: list[Finding], meter: Meter) -> str:
    """One line per finding, grouped by rule with each rule's count and flagged count, then
    `problems: K` counting the flagged findings, or `clean` when none is flagged."""
    lines = []
    for rule in RULES:
        found = sorted((f for f in findings if f.rule == rule), key=lambda f: (f.tick, f.hand))
        if found:
            flagged = sum(finding.flagged for finding in found)
            lines.append(f"{rule}: {len(found)} ({flagged} flagged)")
        for finding in found:
            listed = "" if finding.flagged else " (listed, not flagged)"
            place = where(meter, finding.tick)
            lines.append(f"  {place}  {finding.hand}  {rule}  {finding.detail}{listed}")
    problems = sum(finding.flagged for finding in findings)
    lines.append(f"problems: {problems}" if problems else "clean")
    return "\n".join(lines)
