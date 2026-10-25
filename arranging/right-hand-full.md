# The right hand, full

The right hand written for listening, not for playing. It may hold any number of keys, stretch and leap, and `check-arrangement --full` doesn't flag any of it. It takes every band part in its register that the score can hold clearly. What decides is how it sounds, not what a hand reaches. `arranging-rules.md` gives what every arrangement shares; this file gives this hand, and the layering rules below.

It is dumped with `--every-note` and checked with `--full`. It needs a source: dispatched with this file and no source, stop and report it.

## Taking the band's parts

- **Take every band part, in its own register:** each instrument's line, its inner voices and held chords, the counterlines and the fills, with their rhythm and notes. The dump's `--every-note` shows what each part plays under its top line.
- **Leave out what muddies the parts together.** On a piano every part sounds in one timbre, and what the band's instruments kept apart blurs:
  - **One key once.** Where two parts double each other in the same register, keep one.
  - **No seconds.** Leave out a note a second from another part's note in the same octave while both sound, such as a held chord tone beside an arpeggio's step.
  - **Nothing above the tune.** Every other part sits under `M`: one above it goes down an octave, or stays out.
  - **A held pad that doubles another part's chords stays out,** in any register: brass or strings holding the chord tones the guitar or the piano already plays. Its top voice is no line on its own, and held on `R` it sounds like a stray long note. Keep a pad where it moves as a line of its own, or where no other part plays the chord.
  - **Any other part that fills another's register** goes up an octave, or stays out.
- **One figure per layer, per section.** The transcription's note lengths and voicings vary from bar to bar where the band's don't. So for each section, settle each layer's figure:
  - the top voice, one note held or two struck;
  - each inner part's rhythm.

  Write each figure the same in every bar of the section and its repeats. Vary it only where the band clearly changes: a new chord rhythm, a stop, a fill, the section's last bar. Record each section's figures under "Figures" in `notes.md`.

## The right hand

- **The right hand takes the tune on `M` and, on `R`, the parts above about middle C:** the backing vocal among them, in the lead's octave where it sits under the lead, an octave down where it sits above it ("The backing vocal under the melody" in `arranging-rules.md`), and the band piano's mid-register line, the counterlines and the fills.
- **The melody is on `M`, on top of everything:** one note at a time, above every note of either hand, in the octave your front end gives. Its octave doubling goes under it on `R` (`M 0:E5:4` with `R 0:E4:4`); never the melody's own pitch on `R` at its tick, which strikes one key twice.
- **The right hand's inner voices** sit under the melody, chord tones within about an octave below it.

## What still holds

No key is struck twice at once, in one hand or in both: under `--full` the check's `notes` rule flags a key struck while both hands hold it. Everything in `arranging-rules.md` holds as written.

The report says the right hand is written for listening, not for playing.
