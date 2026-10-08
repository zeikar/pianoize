"""The results table: a summary row per result, then each row's checkpoints in detail."""

from pianoize.score import Row, ScoredCheckpoint, ScoredSegment
from pianoize.timeline import beat_time

_NONE = "none"


def _counted(checkpoint: ScoredCheckpoint) -> list[ScoredSegment]:
    return [s for s in checkpoint.segments if not s.excluded]


def _mark(segment: ScoredSegment) -> str:
    if segment.excluded:
        return "–"
    return "✓" if segment.passed else "✗"


def _time(seconds: float) -> str:
    minutes, rest = divmod(int(seconds), 60)
    return f"{minutes}:{rest:02d}"


def _summary(row: Row) -> tuple[str, str, str]:
    # Overlapping checkpoints share segments, so segments are counted once by start beat.
    # A checkpoint with every segment excluded has nothing to pass and is left out.
    scored = [c for c in row.checkpoints if _counted(c)]
    segments = {s.start_beat: s for c in scored for s in _counted(c)}
    return (
        f"{sum(c.passed for c in scored)}/{len(scored)}",
        f"{sum(s.passed for s in segments.values())}/{len(segments)}",
        f"{sum(s.exact for s in segments.values())}/{len(segments)}",
    )


def markdown(original: dict, rows: list[tuple[str, Row]]) -> str:
    lines = [
        "| row | checkpoints passed | segments passed | exact labels | beat-grid distance (s) |",
        "| --- | --- | --- | --- | --- |",
    ]
    for name, row in rows:
        passed, segments, exact = _summary(row)
        lines.append(f"| {name} | {passed} | {segments} | {exact} | {row.grid_distance:.3f} |")

    for name, row in rows:
        lines += [
            "",
            f"## {name}",
            "",
            "| checkpoint | time | original | found | |",
            "| --- | --- | --- | --- | --- |",
        ]
        for scored in row.checkpoints:
            span = scored.checkpoint
            lines.append(
                "| "
                + " | ".join(
                    [
                        span.name,
                        _time(beat_time(original, span.start_beat)),
                        " ".join(s.original for s in scored.segments),
                        " ".join(s.shown or _NONE for s in scored.segments),
                        " ".join(_mark(s) for s in scored.segments),
                    ]
                )
                + " |"
            )
    return "\n".join(lines) + "\n"
