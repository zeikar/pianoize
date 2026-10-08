# Evaluation

Model-free tooling for comparing melody extractors and scoring arrangements against a chordotomy timeline.

## Checkpoint file

A checkpoint file picks the stretches of one song a trial is scored on, in beats of that song's timeline.

```json
{
  "checkpoints": [
    {"name": "verse-1", "start_beat": 16, "end_beat": 32, "note": "melody over a held chord"}
  ],
  "excluded": [
    {"start_beat": 0, "end_beat": 8, "reason": "spoken intro"}
  ]
}
```

| field | meaning |
| --- | --- |
| `checkpoints[].name` | str, shown in the results table and in errors |
| `checkpoints[].start_beat`, `end_beat` | int, `end_beat` exclusive |
| `checkpoints[].note` | optional str |
| `excluded[].start_beat`, `end_beat` | int, a range left out of scoring |
| `excluded[].reason` | str |

Every range must lie inside the timeline (`0 <= start_beat < end_beat <= len(beats)`), and both its beats must fall on segment boundaries of the timeline, so a range never cuts a chord. Loading fails naming the checkpoint (or the excluded range's reason) that breaks this.

A song's checkpoint file is made from the recording, so it stays in the gitignored `work/` next to the song and is never committed.
