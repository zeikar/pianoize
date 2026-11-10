# The audio check

You can't hear the song, and its transcription is wrong in places: a ghost note, a note held on after it stopped sounding, a note a step off. Copying those errors is one way to go wrong; smoothing the line into a more pianistic one is the other, and lands further from the song. `pianoize check-line` compares a transcribed line with the stem table `pianoize prepare` measured from the recording's separated stems, and lists where the two disagree. This file says when to run it, how to read its list and how to weigh it. The command's rules and output are in pianoize's `docs/arranging.md`, under "Checking a line against the audio".

It applies where your prompt's `Stems:` line names a table, `<stems>`. With `Stems: none` nothing can be checked: read "A line the check can't cover" alone. A prompt with no `Stems:` line, from the cover, has no audio check.

## Running it

After the dump, step 2 of the workflow, and before you write a line of the score, check the lines that carry the tune:

- **The melody**, where you have one: `pianoize check-line '<melody>' --cover '<cover>' --stems '<stems>'`. It reads the melody's one track against the stem its name reads against, the vocals for a sung melody.
- **Each section's tune where no one sings**, and without a melody in every section: the `I` line you record as carrying it under "Melody" in `notes.md`, read over the section's bars, `pianoize check-line '<source>' --cover '<cover>' --stems '<stems>' --track '<track>' --bars A-B`, `<track>` named as the dump names it.

Each prints its list to the screen and writes no file. It exits 0 whatever it lists. An error that names `--stem` is a line the check can't cover, below; any other is fixed as the workflow's "Errors" says.

## Reading the list

Each line is placed as the dump places a note, `bar N pos P`, then the time in the recording, the kind, the transcribed note or the stretch's pitch with its length in sixteenths, and the detail. Made up:

```
bar 12 pos 4.5  0:23.41  pitch  E5 (2)  audio D5 90%
bar 12 pos 8  0:23.90  octave  E5 (1)  audio E4 75%
bar 13 pos 0  0:24.80  silent  G5 (4)  audio - 10%
bar 20 pos 6  0:40.11  untranscribed  A4 (2.5)  -7 dB
audio check: vocals, 3 of 361 notes unsupported, 1 untranscribed
```

- **`pitch`:** the audio sounds another pitch through the note, here D5. The share is how many of the note's frames give that reading: near 100% the audio is plain; a low share means the note slides, bends or shares its time with another sound.
- **`octave`:** the audio sounds the note an octave away. On the vocals it is most often the pitch tracker slipping an octave, not the singer. You choose the melody's octave per section, so it matters only for a note that leaves its phrase's octave.
- **`silent`:** under 30% of the note's frames sound, the share printed. A ghost note of the transcription, a note held on after the line stopped, or a quiet note the stem loses under the band.
- **`untranscribed`:** the audio sounds a pitch where no track of the file on that stem has a note, from the printed place, where its level rises, for the length printed. The level, `-7 dB`, is its loudness against the line's notes around it: near 0 it sounds like the line itself; ten dB or more under, it is more likely a held note's fading tail, a slide into the next note, a breath, reverb or a voice behind the lead; well over it, another part of the stem the transcription missed. The melody's file has one track, so its list can hold what the backing vocal sings: read the dump's `vocal_harmony` `I` line at that bar.
- **The last line** names the stem and counts the notes read, those it lists and the stretches. Where it lists most of the line's notes, the line isn't what that stem sounds: another instrument of the stem, or another track, carries it. Write that line as "A line the check can't cover" says rather than rewrite it from the list.

An empty list is no confirmation: a swell without an attack is never listed, and a legato pickup a tone from the next note of any track of the stem is read as a slide into it.

## Weighing it

The list is evidence, never the answer key. The table has errors of its own: an octave slip, a backing voice, reverb, another instrument of the stem (`other` holds the strings, the brass and the synths at once).

- **Weigh each line against the dump and the section's repeats.** A note the audio reads another way in every repeat of its phrase, where the chord and the bass allow the audio's pitch, is the transcription's error. A note the repeats keep as transcribed, or the audio reads another way in one repeat only, is more likely the table's.
- **Where the audio is clear, write its reading:** a high share for `pitch` and `octave`, and for `silent`, whose share is what sounds, a share near 0%, in every repeat of the passage; no other track of the stem there; and nothing in the dump against it. A `silent` note no other part confirms goes; a `pitch` note takes the audio's pitch.
- **Where it isn't, keep the transcription.**
- **Add an `untranscribed` stretch at its printed place only when its level is near the line's,** a few dB either side, and only where the song is poorer without it. A quiet pickup or a grace the singer barely sounds can be real in the recording and still wrong on a piano: struck at the one velocity every note has ("One velocity" in `arranging-rules.md`), it sounds as loud as the line and out of place.
- **Don't smooth the line.** A note the audio supports stays as it is, so the line keeps its leaps, its repeated notes and its uneven rhythm, as "Where no one sings" in `arranging-rules.md` says. The errors "Leave out the transcription's errors" names still go; nothing else is evened out.
- **The other rule files still hold.** An improvised solo keeps `instrumental-solos.md`: its passage is written new, so the list only confirms the peaks and landings it keeps. In a section the piano leads (`piano-led-sections.md`), check the tune as anywhere. On an instrument's stem a top note more than 10 dB under a chord tone within an octave of it is listed `pitch` with that tone as its reading: weigh only the listed notes that are the tune's.

## A line the check can't cover

Neither of these is an error to stop on:

- `check-line` exits 1 saying the line's stem `is not measured`: the table holds no bass and no drums, so a tune on the bass is one;
- it exits 1 saying there is `no stem for` the track: the instrument has no stem.

Don't name a stem with `--stem` to make it run: the line isn't in that stem, and the list would read another instrument. Record the line and the reason under "Audio check" in `notes.md`, write it from the transcription as the other rule files say, and name it in your report as not checked against the recording.

Where your prompt gives `Stems: none`, the song was prepared before the table existed: run nothing, record one line under "Audio check", `no stem table: nothing checked against the recording`, rather than one per line of the song, write every line from the transcription, and say so once in your report. The same holds for a note the list doesn't read, outside the pitches the table measures: a sung note under A2 or over C6, an instrument's outside C2 to B7. On an instrument's stem only a track's top line is read, so a tune that sits under another part of its track, a line under the chords it strums, say, isn't checked either.

## Recording it

Under "Audio check" in `notes.md`, record each place you changed, by bar and position, what you changed and why, and each line the audio is clear on that you left, and why. A place taken from the audio is recorded here only, not again under "Inferred, filled and copied". A melody note changed to the audio's pitch, or dropped as `silent`, then shows in step 7's list as `melody missing`, since the melody file keeps the transcribed pitch: record it under "Melody left out" with that reason. Your report names the places taken from the audio, by bar and time, and each line not checked against the recording.
