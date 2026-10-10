# Reconciling the harmony

How to decide each segment's chord from the evidence table `pianoize harmony-evidence` writes. SKILL.md gives the commands and the files; this file gives the judgment. The columns are defined in pianoize's `docs/polishing.md`, under "Harmony evidence".

None of the sources is the answer key. Each reads the song its own way and gets its own things wrong. A chord is decided where readings agree and the notes back them.

## What each column says

- **`chord`, `candidates`:** chordotomy's reading of the recording and its ranking, best first. Its beats are the grid every edit is written on. When the other columns point away from `chord`, a reading already in `candidates` is the likeliest answer.
- **`edited`:** `yes` is a chord the user corrected in chordotomy's viewer. That is the user's decision: keep it, and where the evidence disagrees, say so in the report instead of overruling it.
- **`marker`:** tsumugi's predicted chord. tsumugi-piano-cover built the cover from these predictions, so the cover follows them, wrong ones included: a marker and the cover's tones agreeing is one reading, not two.
- **`transcribed bass`:** the pitch class tsumugi's bass track holds longest in the segment, with its share. A high share is strong evidence for the segment's bass, and often its root. A low share means a moving bass line: look at the segments around it before relying on it.
- **`cover tones`, `coverage`, `missing`:** what the cover's accompaniment sounds, the melody left out, and how well that fits the timeline's chord. Low coverage or a missing tone means the cover and the timeline disagree, and the other columns decide which is wrong. Fixing the cover is Phase 2's job: never change the timeline to match a cover that is itself wrong.
- **`melody`:** tsumugi's melody. A melody passes through notes outside the chord, so a pitch class only the melody sounds is no evidence for the chord.

## The analyzer's known misreadings

chordotomy reads some chords as a neighbour. Check these first where it disagrees with the rest:

- **A minor chord over its third read as the major chord on that bass:** `A:min` over `C` (A, C, E) read as `C:maj` (C, E, G). The signs: the accompaniment and the transcription sound A and not G. Write `A:min` with bass `C`.
- **An augmented chord read as major:** `C:aug` (C, E, G♯) read as `C:maj`. The signs: the raised fifth sounds in the accompaniment or the transcription and the plain fifth does not. Write `C:aug`.
- **A melody note on top read as the chord:** a long melody note pulls the reading toward a chord built on it, as an `E:min` under a held melody C read as `C:maj`. The signs: that pitch class is strong in `melody` and weak or absent in `cover tones` and the transcribed bass. Decide from the accompaniment and the bass.

## Deciding

- **The triad and the bass decide.** Compare root, third, fifth and bass. A seventh, sixth, added ninth or other tension the sources disagree on never justifies an edit by itself: `G:7` against a marker reading G gets none. When an edit changes the triad, write the quality the accompaniment sounds, with a seventh only when the accompaniment plays one.
- **No edit when every source agrees with chordotomy.** None either when the sources split and the notes back no reading: keep chordotomy's chord and give the reason in the report.
- **A short chord between two others is harmony, not noise.** A passing chord whose bass moves by step (`C:maj` → `G:maj/B` → `A:min`) stays.
- **Beats only.** An edit covers whole beats, taken from the `beats` column (`start-end`, the end exclusive). A change between two beats goes to the nearer beat. Edit only the beats where the chord differs; `pianoize refine-timeline` cuts the segment there.
- **`N` only for silence,** or a passage with no harmony at all, such as a drum break. Never write `N` for a segment you are unsure of: keep chordotomy's chord.

## Writing a label

- A chord is `<root>:<quality>` with a sharp root: `C`, `C#`, `D`, `D#`, `E`, `F`, `F#`, `G`, `G#`, `A`, `A#`, `B`. B♭ is `A#`, never `Bb`.
- The quality is one of the fifteen chordotomy writes: `maj`, `min`, `7`, `maj7`, `min7`, `min6`, `hdim7`, `dim7`, `sus4`, `aug`, `dim`, `sus2`, `sus4(b7)`, `maj(9)`, `min(9)`.
- `bass` is the bass note, a sharp root: the chord's root for a root-position chord (`C:maj` over C has `bass` `C`), another note for an inversion or a slash chord (`A:min` over C has `bass` `C`). It is `null` only with `N`: in the timeline a `null` bass means none was heard, and `refine-timeline` refuses a chord without one.
- **tsumugi's markers are not labels.** They are chord symbols in a mixed syntax, with flats as well as sharps, slash basses, and a wider vocabulary of qualities than these fifteen. Never copy one into an edit verbatim: translate it, `Bbm7` reading `A#:min7`, into one of the fifteen.
- Record each source's reading, as the table shows it, in the edit's `readings`.
