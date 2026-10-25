# The left hand, a pianist's accompaniment

The left hand written as a pianist's accompaniment, from the chords and the band's sustained parts, not a band part copied: a low bass and a short chord above it. It stays playable by one hand whatever the right hand is, written within the check's limits or for listening. `arranging-rules.md` gives what every arrangement shares; this file gives this hand.

## Bass and chord

- **Alternate bass and chord.** A low root, often an octave, on the strong beats of a 4/4 bar, `0` and `8`; a two-note chord just under the right hand, about F3 to C4, on the backbeat, `4` and `12`; a single root or fifth on the off-beat eighths, `6` and `14`. The two-note chord holds the chord's third, root and third or third and fifth, and on a `sus4` the fourth, never the third. It takes no tensions, no `9`, `11`, `b9` or `b13`, and a seventh only where the band piano holds it.
- **Don't play the bass guitar's rhythm on one low pitch under a held pad.** The bass keeps to the strong beats, not to every kick: "The kick is where the bass is struck" in `reading-the-dump.md` gives the bass guitar's rhythm, not this hand's. Only where the kick pattern is the hook, in a riff section, follow the kick, with octaves and single notes and no held chord.
- **Re-strike, don't hold.** Only the lowest root or octave rings through the bar, by the pedal, not by its written length (`span` in "Fixing the check" in `arranging-rules.md`); the chord above it is short and struck again.

## Which notes

- **Take the chord's root, not every bass note.** A bass guitar line that climbs above its home register ("The left hand against the band" in the docs), above a root the band piano holds, is a fill, not a slash bass, even where it holds a note for a beat and "Finding the chord" in `reading-the-dump.md` would put the chord over it. A step between two roots inside a section is the bass guitar's too, though "Finding the chord" marks it `~` in `L`: this hand keeps the root. Follow the bass only where it marks a real slash chord, or walks or climbs into the next section: keep that motion through a turnaround rather than restate the previous root.
- **Only what the band's sustained parts agree on.** The left hand's bass and its two-note chord take only the band piano's held notes, the bass in its home register and the chord marker; a guitar strum's third counts too. The check's harmony-backing list reads this hand against the first three (step 7 of the workflow). A note only a moving line plays, a bass fill, a backing vocal's passing tone or a guitar run, stays out of the left hand, even where the score's chord names it. On a slash chord the two-note chord's upper note is the chord's fifth or root, not the bass note's fifth.
- **Push only where the band pushes.** Push or anticipate only where the band piano or the bass pushes, written as "Keep the feel" in `arranging-rules.md` says; otherwise land on the downbeat. Don't invent walk-ups the bass doesn't play.

## Density and register

- **Density rises through the song.** A verse's first half takes about four attacks a bar, a broken chord: a root octave, a fifth, a root and a third or tenth, on `0`, `6`, `10` and `12` or so, never a whole-bar pad. Its second half and the later verses take six to eight, stride, as "Alternate bass and chord" writes it: where a later verse copies the first, override the bars of its first half (step 5 of the workflow). A pre-chorus has as many attacks as the chorus; the chorus is heavier, through low octaves ("One velocity" in `arranging-rules.md`). No bar takes more than about ten.
- **Drops, builds and hits.** A drop or breakdown holds one bass note or a fifth for the bar; a build strikes it again once, late, at `12`. On a hit, octaves or a power chord, struck together with the right hand, then silence; a walk-up on `12` to `14` only where the band plays one. A solo-piano intro or ending may hold its fifths.
- **Register.** The bass about C#1 to C#3, mostly Eb2 to C#3, its low octaves down to about Eb1 in a chorus; the two-note chords about F3 to C4; nothing above about E4, and always below the right hand's lowest note.

## One figure per section

Settle each section's figure, name it under "Left-hand figures" in `notes.md`, and write it the same in every bar, varied only where the band varies. A verse's two halves, as "Density rises through the song" splits them, each take their own.

## Playable by one hand

The check, run without `--full`, must flag nothing on `LH`. It reports `notes`, `span`, `jump` and `crossing` on this hand; their limits and fixes are in "Fixing the check" in `arranging-rules.md`.

Where your right-hand file runs the check with `--full`, run it once more without `--full` after that run prints `clean`: fix every `LH` finding and ignore the `RH` ones, whose exit 1 is expected there. Then run both again, until the first prints `clean` and the second flags nothing on `LH`.

The report says the left hand is written within the check's limits.
