# Arranging rules

How to write the score: what to keep of the song, what to copy from the cover, what to take from the band, how to voice the hands, and how to answer each finding of `pianoize check-arrangement`. The workflow gives the commands and the files; this file gives the judgment. The score format and the check's limits are in pianoize's `docs/arranging.md`, under "The score format" and "Checking".

The goal is a piano arrangement for a falling-notes video, written for two hands at an advanced level from the cover, the melody and, where there is one, the band's transcription; or in full mode, for listening, with no limits on the hands ("A full arrangement"). A listener should know the song at once and feel its groove, and a viewer should be able to read every note as it falls.

## Keep the feel

- **The groove is the original's.** Keep the rhythm the cover's accompaniment plays where it carries the song's feel: the bass's rhythm, off-beat chords, a push into the next bar. Take the positions from the `C` lines rather than a straight pattern of your own.
- **Keep the signature rhythmic moments**: band hits, stop-time and syncopations. They are what a listener recognises, more than any voicing. Write each on the grid where the dump shows it: a hit at `7` stays at `7`, not on the beat at `8`.
- **A hit** is short notes in both hands at once, low and high. Give it the pedal of its own, lifted at the hit and pressed again, or let it sound dry.
- **A stop** is silence in the accompaniment: end every note before it, and lift the pedal there without pressing again, with an `x` position or `pedal=none`. The melody may go on alone.
- **A push** across a bar line is a chord struck late in the bar before, at `14` say, and held over the bar line. Give the bar a chord at that position (`bar 8 | 0:F 14:G`), so the check reads the pushed notes against the chord they belong to.

Made up, from the bars of the example in `reading-the-dump.md`: the hit at 7, then a stop under the melody's pickup:

```
format 1
# Made-up: the two bars of the dump in reading-the-dump.md, the hit at 7, then the stop.
== verse | pedal=chord
bar 1 | F
  M 0:A5:4 4:C6:4 8:A5:4 12:G5:4
  R 0:C5+F5:8 8:C5+F5:4
  L 0:F2:8 8:C3:8
bar 2 | 0:Dm7 7:Bb | pedal=0,7,x8
  M 0:F5:6 12:D5:2 14:F5:2
  R 0:A4+C5:6 7:F4+Bb4+D5:1
  L 0:D2+A2:6 7:Bb1+Bb2:1
```

## Copy the cover where it renders a moment best

The cover's own notes are often the best rendering of a hit, a fill or an accompaniment figure. Copy them there, position by position, then clean the strays:

- **slivers**, `(0)` and other very short quiet notes beside a real one;
- **doubled strikes**, one pitch struck twice in one attack (`G5(0,38),G5(4,86)`): keep one;
- **notes outside the chord** that no line explains: drop them, or mark a real passing tone `~`;
- **too many notes for a hand**, more than seven or wider than a tenth: thin the inner voices.

Then split the copied notes between the hands: the low notes to `L`, the rest to `R`, and the tune on top to `M`. Record each copied place in `notes.md`.

## Where no one sings

In a section without vocal, an intro, an interlude, a bridge or an ending, an instrument carries the tune. The cover blends the band into one piano part there, so its top note is often an accompaniment voice, and such a section sounds weaker than the sung ones.

- **The right hand takes the instrument line that carries the tune**, from its `I` line ("The instrument lines" in `reading-the-dump.md`): a brass or synth riff, a guitar or flute lead. Keep its rhythm and its notes, and write it as `M`, in the octave where it sits above the accompaniment, rather than the cover's top note.
- **The left hand still comes from the cover:** its groove and the chords, as in the sung sections.
- **Without a source**, or where no instrument line carries a tune, take the hook from the cover's top line.

## Take from the band

With a source, the dump shows the band under the cover in every bar. The cover renders the band as one pianist might and leaves parts out; take back the ones the song is known by, as long as every hand stays readable ("Readable when falling"). Record what each section takes under "The band" in `notes.md`.

- **The backing vocal under the melody.** Where `vocal_harmony` sings with the lead, `R` takes its line under `M`, a third or a sixth below, in place of the melody's octave: in the lead's octave where it sits under the lead, an octave down where it sits above it. Its notes are chord tones, or passing tones marked `~`.
- **The bass line's motion.** `L`'s lowest note follows `electric_bass` where it walks, steps to a slash bass or pushes ahead of the bar line with the kick. A walk in quarter-note triplets is written at `8`, `10.667` and `13.333`, each `2.667` long.
- **A pulse where the cover only holds.** Where a synth or the strings pulse in eighths and the cover holds whole-bar chords, give `L` the pulse's rate as a broken chord: the bass, then the chord's tones rising above it, such as root, fifth, octave and tenth on four eighths, struck again from the bass on the next four, one figure through the section. Never one key struck again on every eighth, even where the band's synth does that: on a piano it sounds like a stuck note, and as it falls it reads as one.
- **Riffs and fills in the voice's gaps** go on top of the right hand where `V` rests, as "Where no one sings" says of a section.
- **Stops and breakdowns follow the band, not the cover.** Where the drums and the band stop after a hit, end every accompaniment note there, even where the cover lets a chord ring. Where the drums thin to a kick on the downbeat and the band holds its chords, drop the section's running figure: hold the chords, or keep only a pulse the band plays there, as the bullet above writes it.
- **A repeat copies only what repeats.** A copied section takes its source's texture with it: check each copied bar's `D` and `I` lines against its source bar's, and override where the band drops out, holds or changes figure.
- **One part at a time.** The backing vocal replaces the octave doubling rather than joining it, and a pulse replaces the left hand's figure rather than adding to it.

## Infer and fill

The transcriptions differ from the song in places: a chord dropped or wrong, a phrase of the melody missing or an octave off, a hit smeared over two attacks. Where the dump is wrong or silent, infer what the song plays from the same passage elsewhere in the song, the bass line, the melody's long notes and the key, and write that. Record each place in `notes.md` with what you inferred and why: the user listens there first.

## One velocity

pianoize plays every note at one velocity, with no dynamics, so weight comes from register, doubling and note count. A chorus can take octaves in the left hand, a fuller right hand and, under the melody on `R`, the backing vocal's line or the melody's octave; a verse is thinner, a single bass line and two-note chords. A hit is loud by being many notes at once, low and high. A quiet passage is few notes in the middle register.

## Readable when falling

- **Fewer, better notes.** Every note falls as its own bar, and clutter reads as noise. Three-note voicings beat five, a doubled inner note adds nothing, and a fast repeated figure the eye can't follow is better as one held note.
- **No slivers.** Write nothing much shorter than a sixteenth unless it is a deliberate grace note.
- **One pattern per section.** A left-hand figure kept through a section reads better than a new one every bar.

## The hands

- **The melody is the top right-hand note.** One `M` note at a time, and nothing on `R` above it while it sounds. Write it an octave up where the cover plays it there.
- **Doubling the melody:** its octave goes under it on `R` (`M 0:E5:4` with `R 0:E4:4`). Never the melody's own pitch on `R` at its tick: that strikes one key twice.
- **The right hand's inner voices** sit under the melody, chord tones within about an octave below it.
- **The left hand stays close**: a bass with its fifth, octave or tenth above, in the register below middle C. The check flags a span wider than a twelfth and lists one wider than a tenth.
- **The hands stay apart:** the left hand's top below the right hand's bottom at every moment.
- **Jumps take time.** A hand moving 19 semitones or more in under 0.2 s, 26 or more in under 0.36 s, or more than 36 at any speed is flagged; keep a figure compact, or give the hand a rest to move in.

## Pedal

- `chord`, the default, changes the pedal at each chord: right for most bars.
- A list where the hits need it: `0,7,x8` changes at the downbeat and at a hit at 7, then lifts at 8 for a dry stop.
- `none` for stop-time and for passages that must sound dry.
- pianoize itself lifts the pedal where a note would ring a semitone or a minor ninth against one the pedal is holding; leave that to it.

## Chords and passing tones

- **Write the chord the notes say, not the marker's guess.** Decide it from the bass and the long notes ("Finding the chord" in `reading-the-dump.md`), and keep `notes.md`'s chord per bar in step with the score.
- **Position a change where the bass moves** (`0:Am 8:G/B`), and use a slash chord for an inversion or a moving bass.
- **Use the qualities the docs' table lists**, and tensions in parentheses where the accompaniment plays them (`Am7(9)`).
- **A quality the table lacks**, such as a plain diminished triad, `sus2` or `7#9`, doesn't stop the run. Write the nearest quality whose tones you play (a diminished triad as `dim7` or `m7b5`, `sus2` as `add9`), mark any chord tone outside it `~` (the `#9` over a `7`), and record the place under "Gaps" in `notes.md`, naming the quality the song needs. The table can gain it later.
- **Mark a passing tone `~`** on `R` or `L`: a note off the chord on purpose, such as a step in a walking bass or a neighbour note. A note that clashes for a whole beat is no passing tone: it is a wrong chord or a wrong note.

## A full arrangement

When your prompt's mode is `full`, the arrangement is for listening, not for playing. The hands may hold any number of keys, stretch, leap and cross, and `check-arrangement --full` doesn't flag any of it. It takes every band part the score can hold clearly, so the arrangement sounds as full as the band. What decides is how it sounds, not what two hands reach.

- **Take every band part, in its own register:** the bass, each instrument's line, its inner voices and held chords, the counterlines and the fills, with their rhythm and notes. The dump's `--every-note` shows what each part plays under its top line.
- **Leave out the transcription's errors:**
  - slivers and one-sixteenth blips no other part confirms;
  - a very fast run rounded onto the grid into a false line;
  - a note off the chord against the other parts;
  - a note held on past the band's next chord.
- **Leave out what muddies the parts together.** On a piano every part sounds in one timbre, and what the band's instruments kept apart blurs:
  - **One key once.** Where two parts double each other in the same register, keep one.
  - **No seconds.** Leave out a note a second from another part's note in the same octave while both sound, such as a held chord tone beside an arpeggio's step.
  - **An open low register.** Below C3, no two notes closer than a fifth.
  - **Nothing above the tune.** Every other part sits under `M`: one above it goes down an octave, or stays out.
  - **A held pad that doubles another part's chords stays out,** in any register: brass or strings holding the chord tones the guitar or the piano already plays. Its top voice is no line on its own, and held on `R` it sounds like a stray long note. Keep a pad where it moves as a line of its own, or where no other part plays the chord.
  - **Any other part that fills another's register** goes up an octave, or stays out.
- **One figure per layer, per section.** The transcription's note lengths and voicings vary from bar to bar where the band's don't. So for each section, settle each layer's figure:
  - the bass, held through the bar or struck short;
  - the top voice, one note held or two struck;
  - each inner part's rhythm.

  Write each figure the same in every bar of the section and its repeats. Vary it only where the band clearly changes: a new chord rhythm, a stop, a fill, the section's last bar. Record each section's figures under "Figures" in `notes.md`.
- **The hands:** `R` takes the tune and the parts above about middle C, `L` the bass and the parts below it.
- **The cover, in `arrange-cover`,** is evidence, not the texture. The band's parts take the place of its accompaniment wherever the band plays. Its notes still help decide the chords and a hit's timing, and are copied only where the band's transcription is silent or wrong. Where they say otherwise, "Take the positions from the `C` lines", "Copy the cover where it renders a moment best" and "The left hand still comes from the cover" give way to the band.
- **What no longer applies,** since it thins the band for two hands:
  - the limits under "The hands": a close left hand, hands apart, jumps that take time;
  - the `N held`, `span`, `jump` and `crossing` fixes under "Fixing the check";
  - "too many notes for a hand" among the cover's strays;
  - "as long as every hand stays readable" and "One part at a time" under "Take from the band";
  - "One velocity"'s thinner verse;
  - "Fewer, better notes".
- **What still holds:**
  - the melody on top, on `M`, above every note of either hand;
  - no key struck twice at once, in one hand or in both;
  - the chords and passing tones;
  - every note at pianoize's one velocity;
  - the pedal;
  - no slivers;
  - no low key struck on every eighth.

## Fixing the check

Each finding names its bar, position, hand and rule. Fix every flagged one; never quiet the check by marking notes `~` that aren't passing tones or by moving the melody off `M`.

- **`notes`, `N held`:** more than seven keys in one hand at an attack, notes still held from earlier attacks included. End the held notes before the attack, or drop doubled and inner notes.
- **`notes`, `struck twice`:** one pitch struck twice in one hand at one tick, mostly `M` doubled on `R`. Drop the `R` note, or move it an octave down.
- **`span`:** a hand's held keys wider than a twelfth (flagged) or a tenth (listed). Move the outer note an octave in, drop it, or end a held note sooner. A listed span may stay where the music needs it, now and then.
- **`jump`:** a hand's attack moving too far too fast from its previous one, measured between the middles of the two attacks. Voice the chord near the one before, keep the figure compact, or drop the note that stretches the leap.
- **`crossing`:** the left hand's top at or above the right hand's bottom. Move the left-hand note an octave down or the `R` note up, or end the earlier note before the other hand's attack.
- **`melody`:** an `M` note under another right-hand note: an `R` note above the melody, struck with it or while it is held, an `R` note still held above a new `M` note, or two `M` notes at once. Voice `R` under the melody, end the held note before the `M` attack, or keep one `M` note and move the other to `R` under it.
- **`harmony`:** an `R` or `L` note outside its chord at its onset. Decide what is wrong: the note (move it to a chord tone), the chord (the notes say another: fix the chord, and `notes.md`), the chord's position (the change comes earlier or later), or nothing, because it is a real passing tone: mark it `~`.
