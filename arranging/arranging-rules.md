# Arranging rules

How to write the score, whatever your front end and your hands: what to keep of the song, what to take from the band, what to leave out, and how to answer each finding of `pianoize check-arrangement`. The workflow gives the commands and the files; this file gives the judgment every arrangement shares, and your front end and your two hand files give the rest. The score format and the check's limits are in pianoize's `docs/arranging.md`, under "The score format" and "Checking".

The goal is a piano arrangement for a falling-notes video, written from the inputs your front end gives, for two hands as your right- and left-hand files write them. A listener should know the song at once and feel its groove, and a viewer should be able to read every note as it falls.

## Keep the feel

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

## Where no one sings

In a section without vocal, an intro, an interlude, a bridge or an ending, an instrument carries the tune, and such a section sounds weaker than the sung ones.

- **The right hand takes the instrument line that carries the tune**, from its `I` line ("The instrument lines" in `reading-the-dump.md`): a brass or synth riff, a guitar or flute lead. Keep its rhythm and its notes, and write it as `M`, in the octave where it sits above the accompaniment, rather than `C`'s top note.
- **The left hand** plays there as your left-hand file says, as in the sung sections.

## Take from the band

With a source, the dump shows the band under `C` in every bar. `C` leaves parts of the band out, as your front end says; take back the ones the song is known by. Record what each section takes under "The band" in `notes.md`.

- **The backing vocal under the melody.** Where `vocal_harmony` sings with the lead, `R` takes its line under `M`, a third or a sixth below, in the octave your right-hand file says. Its notes are chord tones, or passing tones marked `~`.
- **Riffs and fills in the voice's gaps** go on top of the right hand where `V` rests, as "Where no one sings" says of a section.
- **Stops and breakdowns follow the band, not `C`.** Where the drums and the band stop after a hit, end every accompaniment note there, even where `C` lets a chord ring. Where the drums thin to a kick on the downbeat and the band holds its chords, drop the section's running figure: hold the chords, or keep only the figure the band keeps going there.
- **A repeat copies only what repeats.** A copied section takes its source's texture with it: check each copied bar's `D` and `I` lines against its source bar's, and override where the band drops out, holds or changes figure.

## Infer and fill

The transcriptions differ from the song in places: a chord dropped or wrong, a phrase of the melody missing or an octave off, a hit smeared over two attacks. Where the dump is wrong or silent, infer what the song plays from the same passage elsewhere in the song, the bass line, the melody's long notes and the key, and write that. Record each place in `notes.md` with what you inferred and why: the user listens there first.

## Leave out the transcription's errors

- slivers and one-sixteenth blips no other part confirms;
- a very fast run rounded onto the grid into a false line;
- a note off the chord against the other parts;
- a note held on past the band's next chord.

## One velocity

pianoize plays every note at one velocity, with no dynamics, so weight comes from register, doubling and note count. A hit is loud by being many notes at once, low and high. A quiet passage is few notes in the middle register.

## Readable when falling

- **No slivers.** Write nothing much shorter than a sixteenth unless it is a deliberate grace note.
- **One pattern per section.** A left-hand figure kept through a section reads better than a new one every bar.
- **Never one key struck again on every eighth,** even where the band's synth does that: on a piano it sounds like a stuck note, and as it falls it reads as one.

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

- **`notes`, `N held`:** more than seven keys in one hand at an attack, notes still held from earlier attacks included. End the held notes before the attack, or drop doubled and inner notes.
- **`notes`, `struck twice`:** one pitch struck twice in one hand at one tick, mostly `M` doubled on `R`. Drop the `R` note, or move it an octave down.
- **`span`:** a hand's held keys wider than a twelfth (flagged) or a tenth (listed). Move the outer note an octave in, drop it, or end a held note sooner. A listed span may stay where the music needs it, now and then.
- **`jump`:** a hand's attack moving too far too fast from its previous one, measured between the middles of the two attacks: 19 semitones or more in under 0.2 s, 26 or more in under 0.36 s, or more than 36 at any speed. Voice the chord near the one before, keep the figure compact, or drop the note that stretches the leap.
- **`crossing`:** the left hand's top at or above the right hand's bottom. Move the left-hand note an octave down or the `R` note up, or end the earlier note before the other hand's attack.
- **`melody`:** an `M` note under another right-hand note: an `R` note above the melody, struck with it or while it is held, an `R` note still held above a new `M` note, or two `M` notes at once. Voice `R` under the melody, end the held note before the `M` attack, or keep one `M` note and move the other to `R` under it.
- **`harmony`:** an `R` or `L` note outside its chord at its onset. Decide what is wrong: the note (move it to a chord tone), the chord (the notes say another: fix the chord, and `notes.md`), the chord's position (the change comes earlier or later), or nothing, because it is a real passing tone: mark it `~`.
