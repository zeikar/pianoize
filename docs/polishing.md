# Polishing

How pianoize refines a song's harmony timeline and polishes a tsumugi-piano-cover MIDI against it. An agent session writes two small JSON files into `work/`, the chord edits and the correction spec; pianoize validates them and writes the refined timeline and the polished cover. The CLI never calls an LLM. The reasons are in [docs/decisions.md](decisions.md#an-agent-writes-the-correction-spec-code-applies-it).

## Workflow

The [`polish-cover` skill](#running-the-skill) runs the four commands in two phases. In each, a command lays out the evidence, the agent decides and writes a JSON file, and a command validates that file and writes the result.

1. **The refined harmony timeline.** [`harmony-evidence`](#harmony-evidence) tabulates what chordotomy's timeline, tsumugi's transcription and the cover's notes say in each segment. The agent decides each disagreement and writes the chord edits; [`refine-timeline`](#refined-harmony-timeline) writes the refined timeline from them, and `harmony-evidence` run on it confirms the edits.
2. **The polished cover.** [`find-candidates`](#candidates) lists the candidates against the refined timeline. The agent gives each a verdict and writes the [correction spec](#correction-spec); `find-candidates` with `--spec` [checks it](#checking-a-spec), run after run, until every candidate is judged and every fix is gone. [`apply-corrections`](#applying) writes the polished cover, and `harmony-evidence` run on it checks its notes against the refined harmony.
3. **Listening.** The agent cannot hear the result, so the user is the last gate. Both covers are rendered with `pianoize render` ([docs/evaluation.md](evaluation.md#rendering-a-midi-file)); the user listens A/B and approves, or names places to revert. A revert drops the edits there and turns the verdicts they answered into `keep`, and the second phase runs again from the `--spec` check.

Since M3 (2026-10-11) this path is kept but is no longer the main one: at its listening gate an arrangement an agent wrote from the cover and the melody sounded better than the polished cover ([decision](decisions.md#m3-an-agent-writes-the-arrangement-2026-10-11)). The refined timeline and the evidence table stay as evidence for that arrangement.

## Candidates

`pianoize find-candidates COVER.mid --timeline TIMELINE.chords.json --melody MELODY.mid -o candidates.json` finds the places that may need work and writes them, each with the notes around it, for the agent to judge. It prints one line per candidate (time, category/kind, the note or beats, the key measurement) and ends with a count per category. It refuses an `-o` that is one of its inputs, under any spelling the disk takes for it, and any cover the applier refuses: notes on several tracks or channels, two notes sharing an id, or a note not ended by its own note-off (see [Validation](#validation)). The same inputs write the same bytes. With `--spec`, it checks a correction spec instead (see [Checking a spec](#checking-a-spec)).

```json
{
  "inputs": {
    "cover": {"path": "work/song/cover.mid", "sha256": "9f2c…"},
    "timeline": {"path": "work/song/song.refined.chords.json", "sha256": "c7e1…"},
    "melody": {"path": "work/song/melody.mid", "sha256": "41d0…"}
  },
  "thresholds": {"short_ms": 50, "alone_ms": 30, "stutter_ms": 120, "velocity_above": 20,
                 "off_grid_ms": 50, "roll_ms": 60, "density_factor": 3, "density_beats": 4,
                 "duration_beats": 8, "coverage_below": 0.6, "leap_above": 12,
                 "register_above": 12, "late_beats": 0.25},
  "candidates": [
    {
      "id": "timing:off-grid:t20160p62",
      "category": "timing",
      "kind": "off-grid",
      "time": 21.252,
      "beat": 30.425,
      "note": {"id": "t20160p62", "pitch_name": "D4", "on_tick": 20160, "off_tick": 20400,
               "velocity": 84, "duration_ms": 104.2, "protected": false},
      "segment": null,
      "measurements": {"off_ms": -52.2, "subdivisions": 4, "grid_beat": 30.5},
      "context": [
        "t19920p50 0:21.15 D3 600ms v72",
        "t20160p62 0:21.25 D4 104ms v84",
        "t20280p74 0:21.30 D5 300ms v96 *"
      ],
      "suggested": {"op": "modify", "note": "t20160p62", "on_tick": 20280, "off_tick": 20520}
    }
  ]
}
```

| field | meaning |
| --- | --- |
| `inputs.cover`, `inputs.timeline`, `inputs.melody` | the path as given and the SHA-256 of each input; a correction spec copies the cover's and the melody's. A `--spec` run adds `inputs.spec` |
| `thresholds` | the values this run used (below) |
| `candidates` | sorted by `time`, then `id` |
| `id` | `{category}:{kind}:{anchor}` |
| `category`, `kind` | `glitch`, `timing`, `voice` or `harmony`, and a kind below |
| `time` | seconds, to the millisecond: the note's onset, or the start of the beat or segment. A verdict copies it |
| `beat` | `time` as a fractional chordotomy beat |
| `note` | a note candidate's note: `id`, `pitch_name` (the MIDI pitch is in the id), `on_tick`, `off_tick`, `velocity`, `duration_ms`, and `protected`, true when it carries the melody (see [Melody protection](#melody-protection)) and so keeps its pitch. `null` for a beat or segment candidate |
| `segment` | a beat or segment candidate's `start_beat`, `end_beat` and `chord` in slash form (`C:maj/E`); `chord` is `null` for a beat before the timeline's first segment or after its last. The whole field is `null` for a note candidate |
| `measurements` | what was measured, the key measurement first; per kind below. Counts, subdivisions, velocities, ticks, MIDI pitches and the semitones between two notes are integers and every other number a float: milliseconds to one decimal, beats and coverage to three, medians to one |
| `context` | every note starting within one beat of the candidate (of the beat's middle for a beat candidate), or for a segment candidate every note sounding in the segment, held ones included, by onset, one string each: `t1234p60 1:02.35 C4 120ms v90` is the id, the onset as `m:ss.ss`, the pitch name, the duration in whole milliseconds and the velocity, followed by ` *` when the note carries the melody |
| `suggested` | an edit in the correction spec's format with exact ticks, or `null`: the agent copies it, changes it or writes its own |

**Ids come from content.** The anchor is the note's id, `b{beat}` for a beat (`timing:density:b42`) or `s{start_beat}` for a segment, never a position in the list. A note no edit touches keeps its id whatever moves around it, so a later run lists an untouched candidate under the same id, and a fixed candidate simply disappears instead of renumbering the rest. A spec's verdicts stay attached to their candidates as the spec is revised, and a run with the spec names even the notes it edits as the original cover does (see [Checking a spec](#checking-a-spec)).

**Melody notes are flagged too.** A slip in the melody is still a slip, so the glitch and timing kinds check the notes that carry the melody like the others and mark them `protected`. None of their suggestions changes a pitch. The harmony and voice kinds look at the accompaniment, the cover's notes that don't carry the melody: they never flag a melody note.

**Pedal is ignored.** A note lasts from its note-on to its note-off, though the pedal may let it ring: to the harmony kinds, a chord tone only the pedal holds is missing.

### The grid

Timing is measured against chordotomy's beats, not the cover's ticks: tsumugi's tempo map changes tempo and counts twice as fast as the song's beats. An attack is an onset cluster, the notes starting within 30 ms of the cluster's first, placed at its first note, so a chord is one attack. Each beat is divided into 4, or into 3 when at least two of its attacks lie nearer a triplet line inside the beat (a third or two thirds in) than its start or end, and the 3-grid cuts the total distance from its attacks to their nearest lines by at least a third. So a triplet beat is not flagged, one stray attack can't switch a beat, and the rest stays on sixteenths. A beat without attacks takes 4. Before the first beat and after the last, the beats continue at the neighbouring beat interval.

An ordered roll counts as one attack: its notes after the first attack are left out of the grid, `off-grid` and `density`. A roll is a run of at least three attacks, each starting within `roll_ms` of the previous and lying wholly above it throughout or wholly below it throughout. An attack that turns back starts a new run with the one before it. Two attacks make no roll, so a note played just after a chord is checked whether it is higher or lower.

`density` counts attacks, each in the beat of its nearest grid line, so one played a little early still counts on its beat. Beats from the first attack's to the last attack's count, empty ones included.

### Kinds

| kind | flagged | `measurements` | `suggested` |
| --- | --- | --- | --- |
| `glitch:short` | a note shorter than `short_ms` with no other onset within `alone_ms` | `duration_ms`, `nearest_onset_ms` (`null` for the only note) | `delete` |
| `glitch:stutter` | a note whose pitch was struck within `stutter_ms` before it; the anchor is the second attack | `after_ms`, `previous` (the first attack's id) | `delete` the shorter of the two strikes, the second when they are as long: mostly one is a sliver and the other the held note. `null` when an earlier stutter already suggests deleting that strike: of three quick strikes the middle one can be the shorter of both pairs |
| `glitch:velocity` | a velocity at least `velocity_above` over the median velocity of the other notes of its role starting within a beat of it: a melody note against the melody, an accompaniment note against the accompaniment, since the melody is voiced louder. A note with no other note of its role within a beat is not checked | `velocity`, `median`, `above` | `modify` the velocity to the median, rounded |
| `timing:off-grid` | an onset more than `off_grid_ms` from its nearest grid line, roll notes after the first attack skipped | `off_ms` (signed, positive is late), `subdivisions` (4 or 3), `grid_beat` (the line) | `modify` `on_tick` to the line and `off_tick` by as many ticks, so the length stays; `null` when the line falls before tick 0 or the moved note would overlap a note of its pitch, which the applier refuses |
| `timing:density` | a beat with at least `density_factor` times the median attacks of the `density_beats` beats on each side, when that median is at least 1; or with at most the median divided by `density_factor`, when the median is at least `density_factor`, so at least one attack was expected | `attacks`, `median` | `null` |
| `timing:duration` | a note longer than `duration_beats`, its length rounded to three decimals as printed: a note cut to the nearest tick may end a hair past the limit | `beats` | `modify` `off_tick` to `duration_beats` after the onset; `null` if that rounds onto the note's own end |
| `harmony:coverage` | a segment whose accompaniment spends less than `coverage_below` of its sounding time on the chord's tones (see [Harmony](#harmony)) | `coverage`, `missing` (as `harmony:missing`), `clashes`: per clashing accompaniment note, its `note` id, `pitch_name`, `on_tick`, `off_tick`, and the nearest MIDI pitches on a chord tone `below` and `above` it, the options for a `modify` | `null`: the agent picks |
| `harmony:missing` | a segment at least a beat long, with at least two accompaniment attacks starting in it, or a clash (a foreign tone that is not a passing tone, as in `harmony:coverage`) sounding in it, in which no note of the cover strikes or holds the chord's root, third or fifth, or its slash bass | `missing`: the absent pitch classes, root, third, fifth, then the bass, spelled with sharps | `null` |
| `voice:leap` | the bass of a segment more than `leap_above` semitones from the bass of the segment before it (see [The bass line](#the-bass-line)); an octave passes. The anchor is the later segment's bass note | `semitones` (signed, positive is up), `previous` (the earlier segment's bass note's id) | `null` |
| `voice:register` | a beat whose bass notes' median pitch is more than `register_above` semitones from the median of the beat before's; a beat without bass notes, or right after one, is not compared | `semitones` (signed), `median`, `previous_median` (MIDI pitches) | `null` |
| `voice:bass-late` | at a segment whose bass differs from the previous segment's, the first bass note at the segment start or after it is not on the bass pitch class, and either the first one after it on the bass pitch class starts at least `late_beats` after the segment start and at most one beat after it, or, failing that, the first bass note is at the change and its attack holds the bass pitch class above it (`late_beats` 0: a bass struck over the old one is still not the bass). An onset up to `off_grid_ms` from the segment start counts as at the change, and one up to `off_grid_ms` after the next beat as within the beat. The anchor is the arriving note, or the lowest note on the bass pitch class in that attack, so a late bass moved onto the change over the old one keeps its id | `late_beats`, `bass` (the segment's), `first` (the first bass note's id) | `modify` `on_tick` to the segment start and `off_tick` by as many ticks, so the length stays. `null` when the first bass note is at the change, since the moved note would only sound over it and the agent decides about that note first (delete it, re-pitch it, or keep it as a pedal), or when the moved note would overlap a note of its pitch |

### Harmony

The harmony kinds weigh each segment of the timeline with a chord (not `N`), from its first beat on, against its tones: the chord's pitch classes, sevenths and added tones included, plus the slash bass.

- **Coverage** is the share of the accompaniment's sounding time inside the segment, each note clipped to it, that falls on the tones. A segment with no accompaniment sounding has no coverage and is not flagged. The melody notes are left out: the melody may pass through any note over the chord.
- **Clashes** are listed only for a flagged segment: every accompaniment note sounding in it on a pitch class outside the tones, except a passing tone. A passing tone lasts at most half a beat, starts more than `off_grid_ms` from the nearest beat, and has a note one or two semitones away in the accompaniment's attack before and after its own (an attack is the notes starting within 30 ms of its first).
- **Missing tones** count every note of the cover, the melody's included: a tone the melody sounds is not missing. Only the triad (root, third and fifth, the first three tones of the chord's quality) and the slash bass are asked for, so a seventh left out is no candidate. A bare root has coverage 1.0 and still lacks its harmony, so `missing` is its own kind.

### The bass line

The voice kinds read the bass line: the lowest note of each accompaniment attack (notes starting within 30 ms of its first), when it is below MIDI 60, middle C. A beat's bass notes are those starting in it. A segment's bass note is the lowest bass note starting from `off_grid_ms` before the segment start to one beat after it; a segment under `N`, or without a bass note there, has none. `leap` compares the bass notes of segments next to each other in the timeline, both with one: voice leading is the step from chord to chord, while a figure inside one chord, an octave pattern or an arpeggio, is the texture.

### Thresholds

| threshold | default | rule | first real cover |
| --- | --- | --- | --- |
| `short_ms` | 50 | `short`: duration below this | `short` 21 |
| `alone_ms` | 30 | `short`: no other onset within this | `short` 21 |
| `stutter_ms` | 120 | `stutter`: the pitch struck again within this | `stutter` 8 |
| `velocity_above` | 20 | `velocity`: at least this over the median of its role | `velocity` 45 |
| `off_grid_ms` | 50 | `off-grid`: more than this from the nearest line | `off-grid` 45 (73 at 45) |
| `roll_ms` | 60 | rolls: each attack within this of the previous | |
| `density_factor` | 3 | `density`: a spike at this times the median, a dip at the median divided by this | `density` 10 |
| `density_beats` | 4 | `density`: the beats on each side the median is taken over | `density` 10 |
| `duration_beats` | 8 | `duration`: longer than this | `duration` 3 |
| `coverage_below` | 0.6 | `coverage`: a share of the accompaniment's sounding time on the chord's tones below this | `coverage` 13 |
| `leap_above` | 12 | `leap`: more semitones than this between the basses of two segments | `leap` 6 |
| `register_above` | 12 | `register`: the median bass pitch moves more semitones than this | `register` 16 |
| `late_beats` | 0.25 | `bass-late`: the bass pitch class arrives at least this late | `bass-late` 6 |

The defaults were tuned once on the first real cover, a full-length tsumugi-piano-cover MIDI with its refined timeline: a kind giving more than about 60 candidates floods the judging. Only `off-grid` did, with 73 at 45 ms, 28 of them between 45 and 50 ms; at 50 ms it gives 45, and no other kind's count changes, though `off_grid_ms` also sets the passing-tone, segment-bass and `bass-late` tolerances. The last column is the kind's count on that cover at these defaults, 181 candidates in all; `harmony:missing` gave 8.

### Checking a spec

`pianoize find-candidates COVER.mid --timeline TIMELINE.chords.json --melody MELODY.mid --spec SPEC.json -o candidates.json --report REPORT.md` checks a correction spec against the original cover. It validates the spec as `apply-corrections` does, applies it in memory, and finds the candidates in the corrected cover. Each note keeps the id it has in the original cover, or `add-{id}` for an added note, in every place a candidate names a note: its `id`, its `note`, its measurements, its `suggested` edit and its `context`. Beat and segment anchors stay as they are. Which notes carry the melody is matched again on the corrected notes, by the same rule. `-o` gets these candidates, with `inputs.spec` added.

So one spec is revised from run to run and never piles up: a candidate on a note the spec already edits, or on an added note, names that note as the spec does, and is answered by changing its edit or by a `keep`, never by a second edit on the note. The run proves what the spec claims: each `fix` removed its candidate, and every candidate left has a verdict.

Every candidate found in the original cover, found after the spec, or given a verdict gets one status:

| status | when |
| --- | --- |
| `fixed` | a `fix` verdict, and the candidate is not found after the spec. A verdict from an earlier iteration whose candidate is found in neither cover stays a line |
| `kept` | a `keep` verdict |
| `still present` | a `fix` verdict, and the candidate is still found |
| `unjudged` | no verdict, whether the candidate is found after the spec or only before it: a candidate another edit removed still had to be judged |

`--report` (only with `--spec`) writes a markdown table with a line per candidate, by time then id: the candidate id, its category/kind (from the id), the time as `m:ss.ss`, the status and the verdict's reason. The time is the verdict's `time`, or the found candidate's when there is no verdict, after the spec if it is still found. The command prints every `still present` and `unjudged` line and a count per status, and exits 1 while there is any; otherwise it prints `all candidates judged` and exits 0. `-o` and `--report` each refuse a path that is the cover, the timeline, the melody, the spec or the other, under any spelling the disk takes for it. Both files are written only once everything is computed, each through a temporary file beside it that replaces it atomically. A failed save, or a directory named as either path, leaves both files as they were; a failure while replacing, after the first file is replaced, can leave only that one new.

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
- The cover's notes sit on one track and one channel, and no two share an id. Every cover note ends with its own note-off (a note-on with velocity 0 counts as one), not with a strike of its pitch or the end of the track: an edit that moved that strike or the track's end would change the note's length unasked. No note-off may end nothing: an edit across it would cut the retimed note short. tsumugi-piano-cover's covers end every note with a note-off.

### Melody protection

A cover note that carries the melody never changes pitch: a `modify` that gives it another `pitch` is refused. Delete and retime stay allowed, so the guard does not stop a delete plus an `add` on another pitch; the judge must not re-pitch the melody that way. A note carries the melody when it is the top of its onset cluster (notes starting within 30 ms of the cluster's first) and a note of `--melody`, tsumugi's melody track, starts within 60 ms of it with the same pitch class at or below its pitch. The cover mostly plays the melody an octave up.

### Applying

`pianoize apply-corrections COVER.mid SPEC.json --melody MELODY.mid -o OUT.mid` validates the spec, applies it to a copy of the cover and writes `OUT.mid`, then prints how many notes were deleted, modified and added. It refuses an `-o` that is one of its inputs, under any spelling the disk takes for it. The file is written through a temporary file beside it, so a failed run leaves any existing `OUT.mid` as it was.

- `delete` removes the note's note-on and note-off. `modify` rewrites them in place of the old pair. `add` writes a new pair on the cover's notes' channel, its note-off with velocity 0.
- **Order at one tick.** Untouched messages keep their order. An edited or added note-off goes before the first note-on at its tick, and an edited or added note-on after the last message at its tick, so a note ending where another of its pitch starts stays apart from it. Edited messages at one tick go by pitch.
- `end_of_track` stays last, moved later if an edited or added note now ends after it. Markers, tempo changes, pedal (CC64), the program change and every other message are untouched.

**Determinism.** The same cover and spec give byte-identical output. A spec with no edits writes the cover's own bytes back, for any cover mido writes the way it was read; tsumugi-piano-cover's covers are such files.

## Harmony evidence

`pianoize harmony-evidence COVER.mid TIMELINE.chords.json --source SOURCE.mid --melody MELODY.mid -o evidence.md` prints a markdown table, one row per segment of the timeline, `N` included, of what each source says there: chordotomy's timeline, tsumugi's transcription (its `source.mid`) and the cover's notes. None of them is the answer key; the agent weighs them. `-o` also writes the table, and is refused when it is one of the inputs, under any spelling the disk takes for it. `--bass-track` names the transcription's bass track, `electric_bass` by default; a name no track has is an error. tsumugi writes a track only for an instrument it hears, so for a song without bass `--bass-track ""` reads none: the transcribed bass column stays empty and the markers are kept. Without `--source` the marker and transcribed bass columns are empty; without `--melody` the melody column is empty and every cover note counts as accompaniment.

| column | meaning |
| --- | --- |
| `#` | the segment's index in the timeline's `segments` |
| `time` | the segment's start, `m:ss.ss` |
| `beats` | `start_beat-end_beat`, the end exclusive: the range an edit of the [refined timeline](#refined-harmony-timeline) names |
| `chord` | the timeline's chord, in slash form (`C:maj/E`) when inverted |
| `candidates` | chordotomy's candidate labels for the segment |
| `edited` | `yes` where the timeline marks the segment `edited` |
| `marker` | the transcription's marker sounding at the segment's start, then every one starting inside it, as written: tsumugi's chord names are not Harte labels |
| `transcribed bass` | the pitch class the transcription's bass track sounds longest in the segment, with its share of the track's sounding time there |
| `cover tones` | the four pitch classes the accompaniment sounds longest in the segment, each with its share of the accompaniment's sounding time there |
| `coverage` | the accompaniment's share of sounding time on the chord's tones, as `harmony:coverage` measures it (see [Harmony](#harmony)), to three decimals, as in the candidate; empty under `N` or when no accompaniment sounds |
| `missing` | the triad tones and slash bass that no cover note strikes or holds in the segment, the melody's included, as `harmony:missing` names them, but for every segment, whatever its length and attacks |
| `melody` | the pitch classes of `--melody`'s notes in the segment, most sounding time first, each with its share: the transcription's own reading of the melody, notes the cover never plays included |

Pitch classes are spelled with sharps: B♭ reads `A#`. Of two pitch classes sounding as long, the one with the lower note comes first, so a power chord's bass leads. A note counts for the time it sounds inside the segment, from its note-on to its note-off: pedal is ignored, as by the harmony candidates. The accompaniment is the cover's notes that don't carry the melody, matched against `--melody` (see [Melody protection](#melody-protection)). The transcription's times come from its own tempo map; a type 2 file, whose tracks share no timeline, is refused. Of its meta messages only the markers are read, never the text and lyrics messages, which can carry the song's lyrics.

**The direct note-vs-harmony check.** Run with the refined timeline and the polished cover, the same command shows whether the notes now sound the harmony decided: `missing` empty and `coverage` high where a chord was fixed. No render and no chordotomy reanalysis stand between the notes and the check.

## Refined harmony timeline

`pianoize refine-timeline ORIGINAL.chords.json EDITS.json -o REFINED.chords.json` writes a copy of chordotomy's timeline (schema 11, see chordotomy's [timeline-json.md](https://github.com/zeikar/chordotomy/blob/main/docs/timeline-json.md)) with the chords an agent decided over beat ranges, and prints how many segments the edits changed. Name the output `<stem>.refined.chords.json`: chordotomy's viewer saves its own corrections as `<stem>.edited.chords.json`, so a save there never overwrites it. The command refuses an `-o` that is one of its inputs, under any spelling the disk takes for it, and writes through a temporary file beside it. The same timeline and edits write the same bytes, formatted as chordotomy writes a timeline: a two-space indent, UTF-8 characters as themselves, a trailing newline.

```json
{
  "inputs": {"timeline": {"path": "work/song/song.chords.json", "sha256": "c7e1…"}},
  "edits": [
    {"start_beat": 24, "end_beat": 28, "chord": "A:min", "bass": "C",
     "reason": "the cover and the transcribed bass agree on Am over C",
     "readings": {"chordotomy": "C:maj", "marker": "Am/C", "bass": "C"}}
  ]
}
```

| field | meaning |
| --- | --- |
| `inputs.timeline.sha256` | the SHA-256 of the timeline the edits were written for, given as `ORIGINAL`; `path` is informational |
| `edits[].start_beat`, `end_beat` | int, the beats the edit covers, `end_beat` exclusive: `0 <= start_beat < end_beat <= len(beats)` |
| `edits[].chord` | a label chordotomy writes: `N`, or `<root>:<quality>` with a sharp root and one of the schema's fifteen qualities |
| `edits[].bass` | the bass note, a sharp root: the chord's root for a root-position chord. `null` only with `N` |
| `edits[].reason` | str |
| `edits[].readings` | optional object, informational: each source's reading of the span |

`edits` may be left out; the copy then changes nothing. Loading fails on the first broken rule, naming the item: `edits[1]: beats 2-6 overlap edits[0] (0-4)`.

- `ORIGINAL` is plain JSON, without the `NaN` or `Infinity` that Python reads and the browser's `JSON.parse` refuses, passes the viewer's rules (below), and its hash is `inputs.timeline.sha256`.
- The file has no keys but `inputs` and `edits`, an edit none but the fields above, and every field its type. A reason is a non-empty string.
- An edit's beats lie inside the timeline, and no two edits overlap; edits may touch.
- A chord names its bass, and `N` none. In schema 11 a `null` bass means none was heard, which would drop the segment from the bass checks, so an edit to a chord with `bass` `null` is refused.
- An edit changes something: a segment it covers has another chord or bass.

**What changes.** A segment is cut where an edit that changes it starts or ends, as the viewer's split cuts one: each part keeps the segment's fields and takes its `start_time` and `end_time` from `beats` (`source.duration` at the end), copied, since the viewer compares them exactly. A part inside an edit takes the edit's `chord` and `bass`, the `inversion` they make, `edited: true`, and `null` for `numeral`, `role`, `function` and `target`. A part already on the edit's chord and bass is neither cut nor marked, as the viewer takes a chord picked again for no edit.

**What is kept.** `candidates` stays the analyzer's, which is what the schema keeps on an edited segment, and `generator`, `source`, `beats`, `global_key` and `key_regions` are copied as they are, so the key is still the one chordotomy estimated from its own chords.

**Numerals are `null` on changed segments.** pianoize does not port chordotomy's harmonic analysis. The viewer accepts `null`, and its reanalysis recomputes the numerals, the key and the key regions from the chords at the first edit made there.

**Beats only.** An edit is a beat range, so a chord change between two beats, or a chord shorter than a beat, cannot be written: it goes to a beat.

**The viewer opens it.** The original and the result are checked with a port of the viewer's `timelineProblem` (chordotomy's `viewer/core.js`) for schema 11, and the command fails, writing nothing, on the viewer's message: `beats` finite and ascending; `source.duration` finite and `source.url` a string or `null`; `generator.engine.name` and `version` strings; `global_key` `null`, or a key label with `source` `estimated` or `given` and key labels as `candidates`; every segment's `chord` a label, `bass` `null` or a sharp root, `inversion` `root`, `first`, `second`, `third`, `non_chord` or `null`, `numeral`, `role`, `function` and `target` strings or `null`, `edited` a boolean; the segments tiling the beats from 0 to `len(beats)`, each `start_time` equal to `beats[start_beat]` and each `end_time` to `beats[end_beat]`, or `source.duration` for the last; the key regions tiling the beats, each after the first starting where a segment starts, a given key one region, and a lone region labelled with the key.

## Running the skill

The repository is a Claude Code plugin: `.claude-plugin/plugin.json` and `marketplace.json` at its root, and the `polish-cover` skill in `skills/polish-cover/`, its `SKILL.md` and the judgment it draws on in `references/`. The skill runs the [workflow](#workflow) above. In Claude Code, install it with `/plugin marketplace add zeikar/pianoize` and `/plugin install pianoize@pianoize`; the plugin then runs its own copy of pianoize through `uv run --project`. In a checkout, `.claude/settings.json` registers the checkout as a plugin marketplace and enables the plugin, so the skill runs from the working tree once the first session's trust prompt is accepted; `claude plugin marketplace add .` does the same by hand.
