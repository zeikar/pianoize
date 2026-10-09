"""Writes the synthetic validation song into OUT_DIR: synthetic.mid, its ground-truth timeline
synthetic.chords.json and synthetic.checkpoints.json, one checkpoint per phrase.

120 BPM in G major, 4 beats a chord after an 8-beat lead-in on D, so the first scored G is a real
transition. The lead-in is not a checkpoint. The MIDI puts beat 0 at 0 s, so the timeline's
offset is 0 too.

Run with the repo's venv: $REPO/.venv/bin/python make_synthetic.py OUT_DIR
"""

import json
import sys
from pathlib import Path

from pianoize import synthetic

BPM = 120
LEAD_IN = [("D:maj", 8)]
PHRASES = [
    ("G-D/F#-Em", [("G:maj", 4), ("D:maj", 4, "F#"), ("E:min", 4)]),
    (
        "descent",
        [
            ("C:maj", 4, "E"),
            ("C:min", 4, "D#"),
            ("G:maj", 4, "D"),
            ("A:maj", 4, "C#"),
            ("D:maj", 4),
        ],
    ),
    ("B7-Em", [("B:7", 4), ("E:min", 4)]),
    ("ascent", [("A:min7", 4), ("B:min7", 4), ("C:min7", 4), ("D:maj", 4), ("G:maj", 4)]),
]


def _slash(entry: tuple) -> str:
    return f"{entry[0]}/{entry[2]}" if len(entry) > 2 else entry[0]


def main(out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    progression = LEAD_IN + [entry for _, entries in PHRASES for entry in entries]
    checkpoints = []
    start = sum(entry[1] for entry in LEAD_IN)
    for name, entries in PHRASES:
        end = start + sum(entry[1] for entry in entries)
        note = " ".join(_slash(entry) for entry in entries)
        checkpoints.append({"name": name, "start_beat": start, "end_beat": end, "note": note})
        start = end

    synthetic.midi(progression, bpm=BPM).save(out_dir / "synthetic.mid")
    timeline = synthetic.timeline(progression, bpm=BPM, offset=0)
    for name, data in (
        ("synthetic.chords.json", timeline),
        ("synthetic.checkpoints.json", {"checkpoints": checkpoints, "excluded": []}),
    ):
        (out_dir / name).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: make_synthetic.py OUT_DIR")
    main(Path(sys.argv[1]))
