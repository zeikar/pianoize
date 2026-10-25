# Front end: the cover

What you arrange from when this is your front end, in `arrange-cover`: the piano cover tsumugi-piano-cover made of the song and tsumugi's transcription of its sung melody, where the song has one. tsumugi's transcription of the whole band, `source.mid`, a track per instrument, is read under the cover in every bar where you have it: its bass, its drums, its backing vocal and the parts the cover leaves out.

## Inputs

`<cover>`, `<melody>` and `<source>` are the paths your prompt gives:

- `<cover>`: the cover MIDI tsumugi-piano-cover made;
- `<melody>`, optional: tsumugi's melody MIDI;
- `<source>`, optional but asked for: tsumugi's transcription of the whole band. Without one, the arrangement is written from the cover and the melody alone.

## Regrid

Step 1 of the workflow: `pianoize regrid '<cover>' -o '<out>/cover.regrid.mid'`. It writes a copy of the cover with the tempo hiccups of its beat tracking regridded, so the song's bars fall on the grid's ("Regridding" in the docs). From here on, every `'<cover>'` in a command stands for that copy, `'<out>/cover.regrid.mid'`. `no tempo hiccups` is the usual answer, since `prepare` puts the transcription on a steady grid where its fit was applied. If it prints spans (`bars 40-43: … BPM -> 5 bars at 120.00`) instead, record each under "Regridded spans" in `notes.md`: the user checks each by ear.

## The dump

- **`C` is the cover's attacks.** The cover renders the band as one pianist might and leaves parts out. It mashes the whole band into one piano part, so where no one sings its top note is often an accompaniment voice or two lines blended.
- **The markers and the cover are one reading.** The cover was generated from the markers' predictions, so its notes often follow a wrong marker too. A marker and the cover agreeing is one reading, not two ("Markers are a model's guesses" in `reading-the-dump.md`).

## The melody off the cover

- **Note the octave.** Compare `V` with the cover's top notes at the same positions. The cover often plays the melody an octave up, as in bars 1 to 3 of the example in `reading-the-dump.md` (`V 0:A4(4)` against `A5(4,90)` in `C`). Write it where the cover plays it, which keeps the right hand above the accompaniment.
- **Where `V` and the cover disagree on a pitch,** prefer the one that fits the chord and the phrase's repeats, and record the choice.
- **The cover's top line.** Where `V` is silent and there is no source, or where no `I` line carries a tune, take the hook from the cover's top line.

## The cover's notes

- **The groove is the original's.** Keep the rhythm the cover's accompaniment plays where it carries the song's feel: the bass's rhythm, off-beat chords, a push into the next bar. Take the positions from the `C` lines rather than a straight pattern of your own.
- **Copy the cover where it renders a moment best.** The cover's own notes are often the best rendering of a hit, a fill or an accompaniment figure. Copy them there, position by position, then clean the strays:
  - **slivers**, `(0)` and other very short quiet notes beside a real one;
  - **doubled strikes**, one pitch struck twice in one attack (`G5(0,38),G5(4,86)`): keep one;
  - **notes outside the chord** that no line explains: drop them, or mark a real passing tone `~`;
  - **too many notes for a hand**, more than seven or wider than a tenth: thin the inner voices.

  Then split the copied notes between the hands: the low notes to `L`, the rest to `R`, and the tune on top to `M`. Record each copied place under "Inferred, filled and copied" in `notes.md`.
- **A pulse where the cover only holds.** Where a synth or the strings pulse in eighths and the cover holds whole-bar chords, give `L` the pulse's rate as a broken chord: the bass, then the chord's tones rising above it, such as root, fifth, octave and tenth on four eighths, struck again from the bass on the next four, one figure through the section.

How far the groove and the copied notes hold depends on your left-hand file:

- **With `left-hand-cover.md`** they hold as written: the cover's accompaniment is the texture.
- **With `left-hand-band-layers.md`** the cover is evidence, not the texture. The band's parts take the place of its accompaniment wherever the band plays. Its notes still help decide the chords and a hit's timing, and are copied only where the band's transcription is silent or wrong. Where the groove and the copy say otherwise, they give way to the band, and a copied moment is not thinned for a hand, since neither hand has limits.

## Compare with the band

Step 8 of the workflow, with a source, once the whole score checks clean. Read the dump again a section at a time beside the score, bar by bar, copies and overrides included, and fix what disagrees:

- each chord's bass against `electric_bass`'s line, where the band holds another bass for a beat or more;
- each bar where the drums or the band hit, stop, hold their chords or drop out, against what the score plays there;
- the backing vocal, pulses, riffs and fills `notes.md` records, against what the score took of them.

Record each change under "Compared with the band" in `notes.md`, then run steps 6 and 7 again until clean.
