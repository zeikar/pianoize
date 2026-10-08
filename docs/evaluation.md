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

## The pass rule

`score.score` compares a result's timeline with the original's at every segment a checkpoint covers.

- **Triad class.** A chord is reduced to its root and the class of its first three tones: `maj`, `min`, `dim`, `aug`, `sus2`, `sus4`. Sevenths and tensions fall away. A suspension keeps its own class, so it matches only the same suspension, not the major or minor chord it resolves to. `N` matches only `N`.
- **Bass.** Where the original is inverted, the result's bass must equal the original's. Where it is in root position, any bass passes.
- **Transition window.** A result chord can be chosen for a segment if it starts within one beat either side of the segment's start (a millisecond of slack covers the timelines' rounding).
- **Held chord.** A result chord sounding at the segment's start also counts, when it passes this segment and the one before it. That lets one sustained chord pass a boundary the rule doesn't see, such as a seventh coming or going or a bass move under a root-position chord. A chord that does not pass the previous original chord does not qualify, so a chord held over from a different chord still fails. The song's first segment has no previous one.
- **Chronological order.** Scoring is one pass over the original's segments in time order, and each segment takes the earliest candidate that passes and does not precede the chord chosen last. A result chord is therefore not used twice (except when held) or out of order. Overlapping or split checkpoints do not change a segment's result. A segment outside every checkpoint starts the order again; failed and excluded segments leave it where it was.
- **Excluded ranges** are scored and shown but not counted.

A checkpoint passes when every counted segment passes. One whose segments are all excluded has nothing to pass: it is shown with `–` and left out of the checkpoint count.

## The results table

`pianoize evaluate --original TIMELINE --checkpoints FILE --out-dir DIR NAME=RESULT ...` writes `DIR/table.md` (overwriting it) and prints it. A result is one of:

- `RESULT.chords.json`: a chordotomy timeline, used as it is.
- `RESULT.wav`: analyzed by chordotomy into `DIR/NAME.chords.json`.
- `RESULT.mid`: rendered with FluidSynth into `DIR/NAME.wav`, then analyzed as above.

Existing `DIR/NAME.wav` and `DIR/NAME.chords.json` are reused, matched by name only, so pass `--force` after changing a source file. They are reused because a model-engine analysis takes minutes per song and rows get added one at a time. `--force` renders and analyzes again. A reused timeline is still checked against the schema.

| option | meaning |
| --- | --- |
| `--soundfont` | the SoundFont for `.mid` rows; defaults to `$PIANOIZE_SOUNDFONT`. A `.mid` row without one is a usage error. |
| `--chordotomy` | the chordotomy executable; defaults to `$PIANOIZE_CHORDOTOMY`, then `chordotomy` on `PATH`. Only looked for when a row needs analysis. |
| `--engine` | chordotomy's `--engine`: `auto`, `dsp` or `model` (default `model`) |
| `--force` | ignore existing outputs |

chordotomy runs with pianoize's environment unchanged, so its Beat This! weights come from the cache it normally uses.

| column | meaning |
| --- | --- |
| row | the name given on the command line |
| checkpoints passed | `k/n` checkpoints passed, not counting the all-excluded ones |
| segments passed | `k/n` counted segments passed, each segment once even where checkpoints overlap |
| exact labels | `k/n` counted segments whose chosen chord has the same label and bass as the original; for reference only |
| beat-grid distance | median seconds from each of the result's beats to the nearest original beat |

Below the summary each row has a detail table with one line per checkpoint: its name, its start time (`m:ss`, in the original), the original's labels (slash form, `C:maj/E`), the chords found for them, and a mark per segment: `✓` passed, `✗` failed, `–` excluded. For a failed segment the chord found is the one sounding at its start.

The beat-grid distance says how far the two analyses' beat grids sit from each other, so a large value warns that the result's timing was analyzed against a different grid. It does not say whether the chords line up; that is what the pass counts are for.

## Rendering a MIDI file

`pianoize render MIDI -o OUT.wav [--soundfont SF2] [--gain G]` renders one MIDI file with FluidSynth, as `evaluate` does for `.mid` rows, and prints the peak amplitude. It warns when the peak could clip; lower `--gain` then.
