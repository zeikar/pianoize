# A section the piano leads

Where a song's band has a piano and, in a section, that piano carries the music, its part is already a pianist's part and the best material there is. This file replaces your two hand files for those sections, except as it says. Everything in `arranging-rules.md` holds too, except that its left hand under "Where no one sings", "One pattern per section" and the rule against one key struck again on every eighth give way to the piano's part here. It is the first thing to try; the user's ear decides.

## Finding them

Your hand files may not dump every note. Where they don't, run `dump-bars` again with `--every-note` before you read on: without it an instrument's line shows only its top notes. The track doesn't say which hand played what, only the pitches.

Read each section's band from the dump. A section is piano-led where:

- the `piano` line, or the keyboard track recorded under "Grid tracks" as the chords, plays through it, a figure of its own, above and below about middle C, not only the odd stab or a held chord;
- the `D` line has fewer drums and hits than in the song's choruses, or none, and the other instruments hold behind it or stay out. A section as full as the chorus is not piano-led.

An intro, a verse, a pre-chorus or an interlude is often piano-led, and a chorus rarely is. There the band carries the song, and the piano alone is thin: such a section keeps your hand files. A run or a fill the piano is known by stays in the piano's register there, on `R` under the tune: it doesn't take `M` from the line that carries the tune. Name each piano-led section under "Sections" in `notes.md`, and decide section by section, since one song usually has both kinds.

## Write the piano's part

- **Both hands take its notes and its rhythm,** split where a pianist's hands would part, about middle C, and by the phrase rather than note by note. The left hand here is the piano's left hand, not "Bass and chord" or the density and register that a left-hand file sets, and its figures are the piano's, varied as the piano varies them.
- **The tune stays on `M`, on top.** Where someone sings, `V` is `M`, in the octave your front end chooses, so it is above the piano's notes: where it sits inside the piano's register, an octave up, with the piano's notes under it. Where a piano note would sit on `M`'s key or above it, drop it or take it down an octave; where a run would climb onto `M`'s key or above it, take the whole run down an octave, never single notes of it, which would break its shape. Where `V` is empty and an `I` line carries the tune ("Without a melody" in your front end), that line is `M`. Where no one sings and nothing else carries the tune, the piano's top line is the tune.
- **Clean the transcription, nothing else:** a stray, a split note, a wrong octave, a note a voice-leading ear wouldn't believe, read against the section's repeats ("Infer and fill" in `arranging-rules.md`). A repeat the piano plays differently stays different, unless the difference is the transcription's.
- **Put the piano and the voice on the same grid.** Where a vocal note and a piano note are struck together but transcribed a fraction apart, write them at one position: on one piano they would flam.
- **Pedal as the piano plays.** Its detached chords stay dry, `pedal=none`; notes it lets ring across bars on one harmony are held by the pedal, `pedal=hold`, not by written lengths the check would flag (`span` in "Fixing the check" in `arranging-rules.md`; see "Pedal" there).
- **Add little from the others.** A line the song is known by still goes in ("Take from the band"). A bass guitar doubling the piano's left hand, and a pad holding its chords, stay out.

## The limits still hold

- A left-hand file with limits keeps them. Where the check flags `notes`, `span`, `jump` or `crossing` on `LH`, first shorten the held notes, which the pedal holds anyway; then move one note an octave, or give it to the other hand.
- A right hand written to be played is cut down until the check passes. The tune goes last.

## Where the band comes back

A piano-led section next to one the band carries shouldn't change texture in a bar. Let the section before the change take on your hand files' figure in its last bar, or the next one start lighter, as the band itself does there.

## Recording it

Under "The band" in `notes.md`, record for each piano-led section that its hands are the piano's. Under "Inferred, filled and copied", record, one line per passage, what was changed or left out of the piano's part and why. The report names these sections, for the user to judge by ear.
