"""Checkpoints: the beat ranges of a song a trial is scored on, and the ranges left out.

File format (see docs/evaluation.md):
{"checkpoints": [{"name", "start_beat", "end_beat", "note"?}],
 "excluded": [{"start_beat", "end_beat", "reason"}]}
"""

import json
from dataclasses import dataclass
from pathlib import Path


class CheckpointError(ValueError):
    pass


@dataclass(frozen=True)
class Checkpoint:
    name: str
    start_beat: int
    end_beat: int
    note: str | None = None


@dataclass(frozen=True)
class Excluded:
    start_beat: int
    end_beat: int
    reason: str


def _check_range(who: str, start: int, end: int, timeline: dict, boundaries: set[int]) -> None:
    n_beats = len(timeline["beats"])
    if not 0 <= start < end <= n_beats:
        raise CheckpointError(
            f"{who}: beats {start}-{end} are not inside the timeline (0-{n_beats})"
        )
    for edge in (start, end):
        if edge not in boundaries:
            raise CheckpointError(f"{who}: beat {edge} is not on a segment boundary")


def load(path: str | Path, timeline: dict) -> tuple[list[Checkpoint], list[Excluded]]:
    path = Path(path)
    boundaries = {s["start_beat"] for s in timeline["segments"]}
    boundaries |= {s["end_beat"] for s in timeline["segments"]}

    where = "file"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        checkpoints = []
        for index, item in enumerate(data["checkpoints"]):
            where = f"checkpoint {index}"
            checkpoints.append(
                Checkpoint(item["name"], item["start_beat"], item["end_beat"], item.get("note"))
            )
        excluded = []
        for index, item in enumerate(data.get("excluded", [])):
            where = f"excluded range {index}"
            excluded.append(Excluded(item["start_beat"], item["end_beat"], item["reason"]))
    except json.JSONDecodeError as exc:
        raise CheckpointError(f"{path}: not valid JSON ({exc})") from exc
    except KeyError as exc:
        raise CheckpointError(f"{path}: {where} is missing {exc.args[0]!r}") from exc

    for checkpoint in checkpoints:
        _check_range(
            f"{path}: checkpoint {checkpoint.name!r}",
            checkpoint.start_beat,
            checkpoint.end_beat,
            timeline,
            boundaries,
        )
    for span in excluded:
        _check_range(
            f"{path}: excluded range {span.reason!r}",
            span.start_beat,
            span.end_beat,
            timeline,
            boundaries,
        )
    return checkpoints, excluded
