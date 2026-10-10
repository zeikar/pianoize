# Judging the candidates

How to judge each candidate `pianoize find-candidates` lists, write the correction spec's verdicts and edits, and answer the `--spec` run. SKILL.md gives the commands and the files; this file gives the judgment. Each kind's rule, measurements and suggestion are in pianoize's `docs/polishing.md`, under "Candidates".

A candidate is a place that may need work. Most are the cover's texture doing what it means to, and the cover is kept wherever it does not truly depart. You cannot hear it: judge from the `measurements` and the `context`, and where the notes don't settle it, `keep` and leave it to the user's listening.

## Reading a candidate

- **`id`** is `{category}:{kind}:{anchor}`. The anchor is a note id `t{on_tick}p{pitch}`, a beat `b{beat}` or a segment `s{start_beat}`.
- **`measurements`** hold what was measured, the key value first.
- **`context`** lists the notes around it, one per line: id, onset `m:ss.ss`, pitch name, length, velocity, and `*` for a note that carries the melody. Read it as a small piano roll: what comes before and after, what sounds with it, and whether its neighbours do the same.
- **`note.protected: true`** marks a melody note. Its pitch never changes: the spec refuses a `modify` of its `pitch`, and you must not get around that with a `delete` plus an `add` on another pitch. Deleting or retiming it is allowed.
- **`suggested`** is an edit with exact ticks, or `null` where the fix needs a choice. It is a starting point: copy it, change it, or write your own.

## Fix or keep, by category

### harmony (`coverage`, `missing`)

Judged against the refined timeline, the harmony decided in Phase 1.

- **Fix** only where the accompaniment plays another chord than the segment's: a wrong third, a wrong root, a foreign triad.
- **Keep** a suspension resolving into a chord tone, an anticipation of the next chord just before the change, a passing or neighbour tone, and a tension (a ninth, an eleventh, a sixth) over the right triad.
- `clashes` gives each clashing note with the nearest chord-tone pitches `below` and `above` it. Re-pitch it with a `modify` to the one that keeps its voice moving smoothly, or delete it where the chord is complete without it.
- `missing` names the triad tones and slash bass no note sounds. Fix it by re-pitching a clashing note onto the missing tone, or with an `add` where the cover never plays it. Keep an omission that is the texture: a bare fifth or octave on purpose, a sparse passage, a tone the next attack supplies.
- Where the cover plays a coherent chord and the timeline is what is wrong, fix the timeline, not the notes: see [When the harmony changes](#when-the-harmony-changes).

### glitch (`short`, `stutter`, `velocity`)

- **`short`:** an isolated flick of a few tens of milliseconds, alone between attacks, is a slip: delete it. A short note that belongs to a figure, a grace note into the next note or a fast run, stays.
- **`stutter`:** a quick re-strike under a sustained melody note, a sliver beside the held note, is a slip: delete the sliver, as suggested. A repeated-note figure in a steady rhythm, and a rolled chord, are the texture.
- **`velocity`:** a lone note far louder than its neighbours for no reason is a slip: bring it to the median, as suggested. An accent on a chord change, a downbeat or the start of a phrase stays.

### voice (`leap`, `register`, `bass-late`)

- **`leap`** compares the bass notes of consecutive chord segments, so a figure inside one chord is never a leap. A leap at the start of a section, or into a register the bass line then stays in, is intended. A single bass note an octave off between two in place is a slip: re-pitch it by the octave.
- **`register`:** a change at the start of a section, such as a chorus moving up, is intended. A single beat an octave off from the beats around it is a slip.
- **`bass-late`:** the bass reaches the new chord's bass after the change.
  - With a `suggested` move: apply it where the late bass is a stumble; keep a deliberate delay, such as a walk-up into the new bass.
  - With `suggested` `null`, first see where the first bass note, `measurements.first`, starts: its onset is in `context`, and the segment starts at beat `beat` − `late_beats`, whose time the evidence table's row with those `beats` gives.
    - **At the change,** within about 45 ms (`off_grid_ms`) of it: that note is not the new bass. Decide about it first: delete it, re-pitch it to the bass, or keep it as an intended pedal. Then move or keep the late bass note. Those are edits on two notes, both citing this candidate; a first note re-pitched to the bass must not overlap the late bass note.
    - **After the change:** the move was left out because the moved note would overlap a note of its own pitch. Shorten that note in the same spec and write the move yourself, or keep.

### timing (`off-grid`, `density`, `duration`)

- **`off-grid`:** an isolated residual, one note off while the notes around it sit on the grid, is a slip: move it as suggested, which keeps its length. A `null` suggestion means the move would overlap a note of its own pitch, or fall before the first tick: shorten that note in the same spec and write the move yourself, or keep. Keep swing, a pickup, a rolled chord, and a steady early or late feel, where the notes around it in `context` are off the same way.
- **`density`:** a fill, a break or a sparse passage is intended: keep. It has no suggestion; a slip inside it is judged by its own candidate.
- **`duration`:** a note held far past the music, ringing on into chords it clashes with, is a stuck note: shorten it as suggested. A pedal tone the harmony is built over stays.

## Writing the spec

- **A verdict for every candidate:** its `candidate` id, its `time` copied from the file that lists it (`candidates.json`, or `candidates.after.json`, the `--spec` run's output, for a candidate only that run found), `action` `fix` or `keep`, and a one-line `reason` naming what the notes show ("an isolated 20 ms flick between two chords", "an octave bass pattern"), never a bare "sounds wrong" or "intended".
- **Every edit cites one candidate with a `fix` verdict.** A note takes at most one edit, so one edit may resolve several candidates on its note: give each a `fix` verdict and cite one of them. Several edits may cite one candidate.
- **Ticks are the cover's,** never seconds. Take them from `suggested`, from the candidate's `note`, or from the ids in `context`: to put a note on another note's attack, use that note's `on_tick`.
- **An `add`** needs an `id` of your own (letters, digits, `-` and `_`), `pitch`, `on_tick`, `off_tick` and `velocity`. Take its ticks, and a velocity near theirs, from the notes of the chord it joins.
- After the edits, no two notes of one pitch may overlap or start on one tick; validation refuses that, naming the edit.

## Answering the `--spec` run

Fixed means gone. The `--spec` run applies the spec and searches again, and only that run proves a fix: its candidate is no longer found. Each status:

- **`fixed`:** a `fix` verdict whose candidate is gone. Done.
- **`kept`:** a `keep` verdict. Done.
- **`still present`:** the fix did not remove its candidate. Revise the edit, or change the verdict to `keep` with a reason.
- **`unjudged`:** no verdict. It is a new candidate an edit created, or one that another edit removed: a removed one still needs its verdict, `fix` where the edit meant to fix it, `keep` otherwise.

A candidate on a note an edit already touches carries that note's original id, and one on an added note `add-{id}`. Answer it by revising that note's edit or the `add`, or with a `keep`, never with a second edit on the same note.

## When the harmony changes

Phase 1 is final before judging starts. A harmony candidate's id names its segment by its first beat, not by its chord (`harmony:coverage:s{start_beat}`), so a segment flagged again after its chord changed keeps its id, and an old verdict would pass the `--spec` run for it. `voice:leap` and `voice:bass-late` depend on the segments too. If the harmony must change during Phase 2:

1. Revise `harmony-edits.json`, refine again, and run `pianoize find-candidates` again on the new refined timeline.
2. Delete every `harmony`, `voice:leap` and `voice:bass-late` verdict, and the edits citing them. Glitch, timing and `voice:register` verdicts stand.
3. Judge those candidates again, and iterate the `--spec` run until it exits 0.
