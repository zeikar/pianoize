# Front end: the transcription alone

What you arrange from when this is your front end: tsumugi's transcription of the whole band, `source.mid`, with a track per instrument, a tempo map and chord markers, and tsumugi's transcription of the sung melody, where the song has one. pianoize builds a tempo grid from the transcription that stands in for a cover. The path exists for its terms: tsumugi-piano-cover's weights are CC BY-NC 4.0, while the transcriber's code and weights are MIT, so an arrangement that never touches the cover carries no such terms.

## Clean room

The only inputs are tsumugi's transcription, tsumugi's melody MIDI, and what pianoize makes from them in `<out>`. Never read, dump, copy from or compare against any of these, in `<out>` or anywhere else:

- tsumugi-piano-cover's cover MIDI, or anything made from it;
- a polished cover;
- a refined timeline;
- the `bars.txt`, `notes.md`, `score.txt` or `arranged.mid` of an `arrange-cover` or `polish-cover` run.

If `<out>` holds `cover.regrid.mid` or such a run's files, stop and report it: the main session asks for another directory. Record the inputs under "Clean room" at the top of `notes.md`.

## Inputs

`<source>` and `<melody>` are the paths your prompt gives; `<melody>` may be none.

## Grid and regrid

Step 1 of the workflow, in two commands:

1. **Grid:** `pianoize build-grid '<source>' -o '<out>/grid.mid'`. It writes the grid that stands in for a cover: the transcription's tempo map and chord markers, with its `piano` and `electric_bass` tracks ("Building the grid from a transcription" in the docs). If it refuses a track the source lacks, its error lists the tracks the source names: choose the ones that carry the band's chords and its bass, and run it again with a `--track` for each, `pianoize build-grid '<source>' -o '<out>/grid.mid' --track '<chords>' --track '<bass>'`. Record the tracks the grid holds under "Grid tracks" in `notes.md`.
2. **Regrid:** `pianoize regrid '<out>/grid.mid' -o '<out>/grid.regrid.mid'`. It writes a copy of the grid with its tempo hiccups regridded ("Regridding" in the docs). From here on, every `'<cover>'` in a command stands for that copy, `'<out>/grid.regrid.mid'`, the cover of every command. If it prints spans (`bars 40-43: … BPM -> 5 bars at 120.00`) rather than `no tempo hiccups`, record each under "Regridded spans" in `notes.md`: the user checks each by ear.

## The dump

A piano cover already has a pianistic accompaniment; a band transcription has none: a bass line, a drum kit, strummed guitars and a keyboard part, each written for its own player. So you arrange the band for piano: you decide what each hand plays from what the band plays, rather than copying any one part.

- **`C` is the attacks of the grid's tracks, the band's piano and bass.** It is what the band plays, not a pianist's part.
- **`C`'s notes and the markers come from different models of the transcriber,** so where they agree, that is two readings, not one.
- **The bass line is `electric_bass`'s `I` line:** check your chords against it.
- **A bar without drums**, an intro or a breakdown, takes its accompaniment from the strums, the band piano's figure in `C`, or the bass.
- **The band piano's stabs and pushes**, from `C`: chord tones under the melody where the band piano strikes short, or ahead of the bar line, a push written as "Keep the feel" in `arranging-rules.md` says.
- **A hit** is where the crash and the instruments strike together, written as "Keep the feel" says.

## The melody

- **The melody is `V` alone**, kept to one voice as `check-arrangement --melody` keeps it: of notes sung together the highest, each ending where the next begins. Skip its strays as "Skip the strays" in `reading-the-dump.md` says.
- **Choose its octave to fit the hands**, not off a cover. The melody stays the top right-hand note and above the left hand, so a vocal that sits in the accompaniment's register goes up an octave. Choose one octave per section and record it under "Melody" in `notes.md`.
- **Without a melody** every `V` line is empty. The tune is the `I` line that carries it, chosen per section from the dump's instrument lines and recorded under "Melody" in `notes.md`, with its octave.
- **Where `V` is wrong or silent** while someone surely sings, check it against `vocal_harmony`'s `I` line, an instrument doubling the tune, and the section's repeats. `I melody` is `V`'s own track, so it can't confirm `V`. Write what the others agree on, and record the choice.
