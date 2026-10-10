# Polishing

How pianoize polishes a tsumugi-piano-cover MIDI. An agent session judges the candidate problems and writes a correction spec into `work/`; `pianoize apply-corrections` validates the spec and applies it to a copy of the cover. The CLI never calls an LLM. The reasons are in [docs/decisions.md](decisions.md#an-agent-writes-the-correction-spec-code-applies-it).

## Correction spec

A correction spec is a JSON file, `spec_version 1`. It names the files it was written for, gives a verdict on candidates, and lists the edits that fix them.

```json
{
  "spec_version": 1,
  "inputs": {
    "cover": {"path": "work/song/cover.mid", "sha256": "9f2c…"},
    "melody": {"path": "work/song/melody.mid", "sha256": "41d0…"}
  },
  "verdicts": [
    {"candidate": "CANDIDATE-A", "time": 12.48, "action": "fix", "reason": "the chord is G, not Gm"},
    {"candidate": "CANDIDATE-B", "time": 30.1, "action": "keep", "reason": "a passing tone"}
  ],
  "edits": [
    {"op": "modify", "candidate": "CANDIDATE-A", "note": "t11520p70", "pitch": 71,
     "reason": "B natural, the third of G"},
    {"op": "delete", "candidate": "CANDIDATE-A", "note": "t11520p58", "reason": "doubles the wrong third"},
    {"op": "add", "candidate": "CANDIDATE-A", "id": "g-bass", "pitch": 43, "on_tick": 11520,
     "off_tick": 12480, "velocity": 70, "reason": "the bass the chord was missing"}
  ]
}
```

A note is named by its id, `t{on_tick}p{pitch}`, in the cover's ticks: `t11520p70` starts at tick 11520 on pitch 70. Candidate ids and times come from the finder's output.

| field | meaning |
| --- | --- |
| `spec_version` | int, `1` |
| `inputs.cover.sha256`, `inputs.melody.sha256` | the SHA-256 of the cover MIDI and of tsumugi's melody MIDI the spec was written for |
| `inputs.cover.path`, `inputs.melody.path` | optional, informational: the files used are the ones on the command line |
| `verdicts[].candidate` | str, a candidate id |
| `verdicts[].time` | number, the candidate's `time` in seconds, copied from the finder's output, so a report line survives when the edit or note it concerned is gone |
| `verdicts[].action` | `fix` or `keep` |
| `verdicts[].reason` | str |
| `edits[].op` | `delete`, `modify` or `add` |
| `edits[].candidate` | str, the candidate the edit fixes |
| `edits[].reason` | str |
| `edits[].note` | `delete` and `modify`: the id of a note of the cover |
| `edits[].pitch`, `on_tick`, `off_tick`, `velocity` | int, absolute values. `modify` gives any of them and keeps the note's own value for the rest; `add` gives all four |
| `edits[].id` | `add` only: `[A-Za-z0-9_-]+`. Later finder runs name the added note `add-{id}` |

`verdicts` and `edits` may be left out; a spec with only `spec_version` and `inputs` changes nothing.

### Validation

Loading fails on the first broken rule, naming the item: `edits[3]: unknown note t1920p62`, `verdicts[7]: action must be fix or keep`, `inputs.cover: sha256 does not match cover.mid`.

- `spec_version` is 1, and both input hashes equal the hashes of the files given on the command line.
- The spec has no keys but `spec_version`, `inputs`, `verdicts` and `edits`, so a misspelt `edits` is refused rather than read as no edits. Every field has its type, and an edit carries only the fields its `op` takes. Strings are non-empty and a verdict's `time` is a finite number.
- `pitch` is 0–127, `velocity` 1–127, ticks are 0 or more, and an edited or added note ends after it starts (`off_tick > on_tick`).
- A candidate has at most one verdict. An edit's candidate has a `fix` verdict. A `fix` verdict needs no edit citing it: one edit can remove several candidates on its note, and a later finder run proves each fix by the candidate being gone.
- `note` names a note of the cover, and a note has at most one edit. Two `add` edits never share an `id`.
- A `modify` changes something: at least one of its fields differs from the note's.
- After the edits, no two notes of one pitch overlap (`[on_tick, off_tick)`) or start on the same tick, so each note-off pairs with its own note-on and no two notes share an id.
- The cover's notes sit on one track and one channel, and no two share an id. Every cover note ends with its own note-off (a note-on with velocity 0 counts as one), not with a strike of its pitch or the end of the track: an edit that moved that strike or the track's end would change the note's length unasked. tsumugi-piano-cover's covers end every note with a note-off.

### Melody protection

A cover note that carries the melody never changes pitch: a `modify` that gives it another `pitch` is refused. Delete and retime stay allowed, so the guard does not stop a delete plus an `add` on another pitch; the judge must not re-pitch the melody that way. A note carries the melody when it is the top of its onset cluster (notes starting within 30 ms of the cluster's first) and a note of `--melody`, tsumugi's melody track, starts within 60 ms of it with the same pitch class at or below its pitch. The cover mostly plays the melody an octave up.

### Applying

`pianoize apply-corrections COVER.mid SPEC.json --melody MELODY.mid -o OUT.mid` validates the spec, applies it to a copy of the cover and writes `OUT.mid`, then prints how many notes were deleted, modified and added. It refuses an `-o` that is one of its inputs. The file is written through a temporary file beside it, so a failed run leaves any existing `OUT.mid` as it was.

- `delete` removes the note's note-on and note-off. `modify` rewrites them in place of the old pair. `add` writes a new pair on the cover's notes' channel, its note-off with velocity 0.
- **Order at one tick.** Untouched messages keep their order. An edited or added note-off goes before the first note-on at its tick, and an edited or added note-on after the last message at its tick, so a note ending where another of its pitch starts stays apart from it. Edited messages at one tick go by pitch.
- `end_of_track` stays last, moved later if an edited or added note now ends after it. Markers, tempo changes, pedal (CC64), the program change and every other message are untouched.

**Determinism.** The same cover and spec give byte-identical output. A spec with no edits writes the cover's own bytes back, for any cover mido writes the way it was read; tsumugi-piano-cover's covers are such files.
