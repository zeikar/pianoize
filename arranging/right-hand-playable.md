# The right hand, playable

The right hand within the check's limits, for an arrangement someone could play at an advanced level: the melody on top, its doubling and its inner voices, readable as they fall. `arranging-rules.md` gives what every arrangement shares; this file gives this hand.

The dump runs without `--every-note`. The check runs without `--full`, and the arrangement is clean when it flags nothing.

## The melody and its voices

- **The melody is the top right-hand note.** One `M` note at a time, and nothing on `R` above it while it sounds. Write it in the octave your front end gives.
- **Doubling the melody:** its octave goes under it on `R` (`M 0:E5:4` with `R 0:E4:4`). Never the melody's own pitch on `R` at its tick: that strikes one key twice.
- **The right hand's inner voices** sit under the melody, chord tones within about an octave below it.
- **One part at a time.** Where `R` takes the backing vocal's line ("The backing vocal under the melody" in `arranging-rules.md`), it replaces the octave doubling rather than joining it, in the lead's octave where it sits under the lead, an octave down where it sits above it.

## How much it takes

- **The band's parts, as long as the hand stays readable.** Take back on `R` the parts the song is known by ("Take from the band" in `arranging-rules.md`).
- **Fewer, better notes.** Every note falls as its own bar, and clutter reads as noise. In the right hand, three-note voicings beat five, a doubled inner note adds nothing, and a fast repeated figure the eye can't follow is better as one held note.
- **A chorus is fuller than a verse** ("One velocity" in `arranging-rules.md`): a chorus can take a fuller right hand and, under the melody on `R`, the backing vocal's line or the melody's octave; a verse is thinner.

## The limits

The check reports `notes`, `span` and `jump` on this hand, and `crossing`, on `LH`, where the left hand reaches it; their limits and fixes are in "Fixing the check" in `arranging-rules.md`.

- **The hands stay apart:** the right hand's bottom above the left hand's top at every moment.
- **Jumps take time:** keep a figure compact, or give the hand a rest to move in.

The report says the right hand is written within the check's limits.
