# Arranging rules

How to write the score: what to keep of the song, what to copy from the cover, how to voice the hands, and how to answer each finding of `pianoize check-arrangement`. SKILL.md gives the commands and the files; this file gives the judgment. The score format and the check's limits are in pianoize's `docs/arranging.md`, under "The score format" and "Checking".

The goal is a piano arrangement for a falling-notes video, written for two hands at an intermediate-to-advanced level from the cover, the melody and, where there is one, the band's transcription. A listener should know the song at once and feel its groove, and a viewer should be able to read every note as it falls.

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
- **too many notes for a hand**, more than five or wider than a ninth: thin the inner voices.

Then split the copied notes between the hands: the low notes to `L`, the rest to `R`, and the tune on top to `M`. Record each copied place in `notes.md`.

## Where no one sings

In a section without vocal, an intro, an interlude, a bridge or an ending, an instrument carries the tune. The cover blends the band into one piano part there, so its top note is often an accompaniment voice, and such a section sounds weaker than the sung ones.

- **The right hand takes the instrument line that carries the tune**, from its `I` line ("The instrument lines" in `reading-the-dump.md`): a brass or synth riff, a guitar or flute lead. Keep its rhythm and its notes, and write it as `M`, in the octave where it sits above the accompaniment, rather than the cover's top note.
- **The left hand still comes from the cover:** its groove and the chords, as in the sung sections.
- **Without a source**, or where no instrument line carries a tune, take the hook from the cover's top line.

## Infer and fill

The transcriptions differ from the song in places: a chord dropped or wrong, a phrase of the melody missing or an octave off, a hit smeared over two attacks. Where the dump is wrong or silent, infer what the song plays from the same passage elsewhere in the song, the bass line, the melody's long notes and the key, and write that. Record each place in `notes.md` with what you inferred and why: the user listens there first.

## One velocity

pianoize plays every note at one velocity, with no dynamics, so weight comes from register, doubling and note count. A chorus can take octaves in the left hand, a fuller right hand and the melody doubled an octave below on `R`; a verse is thinner, a single bass line and two-note chords. A hit is loud by being many notes at once, low and high. A quiet passage is few notes in the middle register.

## Readable when falling

- **Fewer, better notes.** Every note falls as its own bar, and clutter reads as noise. Three-note voicings beat five, a doubled inner note adds nothing, and a fast repeated figure the eye can't follow is better as one held note.
- **No slivers.** Write nothing much shorter than a sixteenth unless it is a deliberate grace note.
- **One pattern per section.** A left-hand figure kept through a section reads better than a new one every bar.

## The hands

- **The melody is the top right-hand note.** One `M` note at a time, and nothing on `R` above it while it sounds. Write it an octave up where the cover plays it there.
- **Doubling the melody:** its octave goes under it on `R` (`M 0:E5:4` with `R 0:E4:4`). Never the melody's own pitch on `R` at its tick: that strikes one key twice.
- **The right hand's inner voices** sit under the melody, chord tones within about an octave below it.
- **The left hand stays inside a ninth**: a bass with its fifth, octave or tenth above, in the register below middle C. The check flags a span wider than a tenth and lists one wider than a ninth.
- **The hands stay apart:** the left hand's top below the right hand's bottom at every moment.
- **Jumps take time.** A hand moving 15 semitones or more in under 0.2 s, 22 or more in under 0.36 s, or more than 26 at any speed is flagged; keep a figure compact, or give the hand a rest to move in.

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

## Fixing the check

Each finding names its bar, position, hand and rule. Fix every flagged one; never quiet the check by marking notes `~` that aren't passing tones or by moving the melody off `M`.

- **`notes`, `N held`:** more than five keys in one hand at an attack, notes still held from earlier attacks included. End the held notes before the attack, or drop doubled and inner notes.
- **`notes`, `struck twice`:** one pitch struck twice in one hand at one tick, mostly `M` doubled on `R`. Drop the `R` note, or move it an octave down.
- **`span`:** a hand's held keys wider than a tenth (flagged) or a ninth (listed). Move the outer note an octave in, drop it, or end a held note sooner. A listed span may stay where the music needs it, now and then.
- **`jump`:** a hand's attack moving too far too fast from its previous one, measured between the middles of the two attacks. Voice the chord near the one before, keep the figure compact, or drop the note that stretches the leap.
- **`crossing`:** the left hand's top at or above the right hand's bottom. Move the left-hand note an octave down or the `R` note up, or end the earlier note before the other hand's attack.
- **`melody`:** an `M` note under another right-hand note: an `R` note above the melody, struck with it or while it is held, an `R` note still held above a new `M` note, or two `M` notes at once. Voice `R` under the melody, end the held note before the `M` attack, or keep one `M` note and move the other to `R` under it.
- **`harmony`:** an `R` or `L` note outside its chord at its onset. Decide what is wrong: the note (move it to a chord tone), the chord (the notes say another: fix the chord, and `notes.md`), the chord's position (the change comes earlier or later), or nothing, because it is a real passing tone: mark it `~`.
