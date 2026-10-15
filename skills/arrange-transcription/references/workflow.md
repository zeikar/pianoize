# The arranger's workflow: from the band transcription alone (experimental)

What the arranger subagent does when `arrange-transcription` dispatches it: the steps, the rules and the report. SKILL.md is the main session's side: it gathers the inputs, dispatches you and talks to the user. Paths here, `references/…` and `../<skill>/…`, are from this skill's directory.

You arrange a song for a falling-notes video (Synthesia style) from tsumugi's transcription of the whole band, `source.mid`, with a track per instrument, a tempo map and chord markers, and from tsumugi's transcription of the sung melody where the song has one. You read the band bar by bar, decide the chords and arrange the band for two hands in a score; pianoize builds the score into MIDI on a tempo grid it makes from the transcription, and checks that it is playable and fits your chords.

The path exists for its terms: tsumugi-piano-cover's weights are CC BY-NC 4.0, while the transcriber's code and weights are MIT, so an arrangement that never touches the cover carries no such terms. Its first trial left the left hand unsettled ("Density" in `references/band-to-piano.md`), so the user sets each section's left hand at the listening.

pianoize's commands are deterministic and never call an LLM. You write two text files, `notes.md` and `score.txt`; pianoize builds the MIDI from the score. Never write a MIDI file any other way. You cannot hear the result, so the user's listening at the end is the final gate.

## Rules

- **Clean room.** The only inputs are tsumugi's transcription, tsumugi's melody MIDI, and what pianoize makes from them in `<out>`. Never read, dump, copy from or compare against any of these, in `<out>` or anywhere else:
  - tsumugi-piano-cover's cover MIDI, or anything made from it;
  - a polished cover;
  - a refined timeline;
  - the `bars.txt`, `notes.md`, `score.txt` or `arranged.mid` of an `arrange-cover` or `polish-cover` run.

  If `<out>` holds `cover.regrid.mid` or such a run's files, stop and report it: the main session asks for another directory. Record the inputs under "Clean room" at the top of `notes.md`.
- **No input is the answer key.** The transcription, its chord markers and the melody are models' transcriptions, and each is wrong in places. Weigh them against each other and against the song's own repeats before writing a note.
- **Inputs are read-only.** Never modify, move or overwrite the source or the melody.
- **Write only into `<out>`.** Never change pianoize's own files.
- **Never paste song content into the repository.** A song's chords, notes, markers, lyrics and times stay in `<out>` under `work/`, which is never committed: none of it goes into docs, tests, code, commit messages or issues.
- **You write the score and the notes; pianoize builds and checks.** Never write or edit a MIDI file yourself.
- **You cannot hear it.** Never claim the arrangement sounds right. The user's listening decides.
- **Audio never leaves the machine.** Upload nothing.

## Running pianoize

- **The command line** is in your dispatch prompt: below, `pianoize <command> …` stands for it. Its first run may build pianoize's environment, so allow a few minutes.
- **The docs:** the docs directory your prompt names holds `arranging.md`, which documents the score format and the arranging commands with their rules, limits and output, the grid under "Building the grid from a transcription" and the dump under "Dumping"; `render` is in `evaluation.md` beside it, and `export-arrangement` in `rendering.md`. `pianoize <command> --help` lists a command's options. Read the section a step names whenever its rules matter.
- **Quoting.** Single-quote every path in a command, writing a `'` inside it as `'\''`: song file names carry spaces, brackets and other characters the shell would read.
- **Errors.** A failing command prints `error: …` naming the item at fault (`bar 3: token '4:H4:2': bad note 'H4'`). Fix that item and run the same command again. Exit 2 is a usage error: report its message. An error naming the grid, the melody or the source (a type 2 file, a meter change, ticks per beat that don't divide by 4) can't be fixed, since the inputs are read-only (a missing track at step 1 excepted, which `--track` fixes): stop, and report it. `check-arrangement` also exits 1 while its report flags a finding: that is work for step 7, not an error.
- **The score format.** Every score starts with the line `format 1`. If pianoize refuses that line and expects another version, the skill and pianoize are out of step: stop, and report it.

## Steps

`<source>`, `<melody>` and `<out>` are the paths your prompt gives; `<melody>` may be none.

1. **Grid:** `pianoize build-grid '<source>' -o '<out>/grid.mid'`. It writes the grid that stands in for a cover: the transcription's tempo map and chord markers, with its `piano` and `electric_bass` tracks ("Building the grid from a transcription" in the docs). If it refuses a track the source lacks, its error lists the tracks the source names: choose the ones that carry the band's chords and its bass, and run it again with a `--track` for each, `pianoize build-grid '<source>' -o '<out>/grid.mid' --track '<chords>' --track '<bass>'`. Record the tracks the grid holds under "Grid tracks" in `notes.md`.
2. **Regrid:** `pianoize regrid '<out>/grid.mid' -o '<out>/grid.regrid.mid'`. It writes a copy of the grid with its tempo hiccups regridded ("Regridding" in the docs). From here on, every `'<grid>'` in a command stands for that copy, `'<out>/grid.regrid.mid'`, the cover of every command. If it prints spans (`bars 40-43: … BPM -> 5 bars at 120.00`) rather than `no tempo hiccups`, record each under "Regridded spans" in `notes.md`: the user checks each by ear.
3. **Dump:** `pianoize dump-bars '<grid>' --melody '<melody>' --source '<source>' --every-bar --drums > '<out>/bars.txt'`, leaving out `--melody '<melody>'` without a melody. Each bar gets a header with its time and the transcription's chord markers, and then these lines ("Dumping" in the docs), whose positions and durations count sixteenths:
   - `C`: the attacks of the grid's tracks, the band's piano and bass. It is what the band plays, not a pianist's part;
   - `V`: the melody;
   - `D`: the drums' hits, grouped as `kick`, `snare`, `hihat`, `cymbal` and `other`;
   - `I`: a line per instrument of the source that plays in the bar, its top line, in every bar, sung bars included.

   Bar N of the dump is bar N of the score. To read a section closely, run the same dump with `--bars A-B`, its first and last bars, and without the redirect: it prints to the screen and leaves `bars.txt` as it is.
4. **Read `<out>/bars.txt` whole**, following **`../arrange-cover/references/reading-the-dump.md`** for the lines, the markers, the chords, the drums and the instrument lines, and **`references/band-to-piano.md`** for the left hand and the melody. There is no cover here. What `arrange-cover`'s references say of the cover's notes is `C`, the band's piano and bass; their `'<cover>'` is `'<grid>'`; and where they run `dump-bars`, run step 3's dump with `--bars A-B` instead. `C`'s notes and the markers come from different models of the transcriber, so where they agree, that is two readings, not the one "Markers are a model's guesses" counts. In `reading-the-dump.md`'s "The melody", the bullets that compare `V` with the cover's top notes, write the melody where the cover plays it, or take the hook from the cover's top line are replaced by "The melody" in `references/band-to-piano.md`. Then write `<out>/notes.md`:
   - the sections with their bars, and which later sections repeat which;
   - a chord per bar, with its position where it changes inside the bar, decided from the bass, the long notes and the repeats;
   - the melody's entries and pickups, and the octave you choose for it in each section;
   - each section's rhythm section, its drums, strums and bass line, and the left-hand figure you choose for it;
   - the hits, stops and syncopations, by bar and position;
   - every place where the transcription is wrong or silent, what you infer there, and the gaps.
5. **Write `<out>/score.txt` one section at a time**, in bar order, following **`references/band-to-piano.md`** and these sections of **`../arrange-cover/references/arranging-rules.md`**:
   - "Keep the feel", except its first bullet, "The groove is the original's", whose place "Reading the rhythm section" in `references/band-to-piano.md` takes;
   - "Where no one sings", as `references/band-to-piano.md` adjusts it;
   - "Take from the band", reading its cover as `C`, the band's piano: the backing vocal under the melody, the bass's motion, the stops and breakdowns and the repeats, with a pulse as one of the figures "One figure per section" in `references/band-to-piano.md` chooses from;
   - "Infer and fill";
   - "Readable when falling";
   - "The hands", except its "Write it an octave up where the cover plays it there", which "The melody" in `references/band-to-piano.md` replaces;
   - "Pedal", "Chords and passing tones" and "Fixing the check".

   Not "Copy the cover where it renders a moment best", which reads a cover, nor "One velocity", whose verse texture "Density" in `references/band-to-piano.md` replaces. The score's shape is the example in step 4 of `../arrange-cover/references/workflow.md`; its grammar is "The score format" in the docs. Write every bar from 1 on, a silent one as a bar with `N.C.` and no hand lines. Write a section that repeats an earlier one as a copy, `bars A-B = C-D`, with overrides, as step 5 of `../arrange-cover/references/workflow.md` says, and record each in `notes.md`. After each section, run steps 6 and 7 and fix every flagged finding before writing the next.
6. **Build:** `pianoize build-arrangement '<out>/score.txt' --cover '<grid>' -o '<out>/arranged.mid'`. It prints the notes per hand, the pedal presses and the length ("Building" in the docs). Once the score is complete, the length is about the grid's.
7. **Check:** `pianoize check-arrangement '<out>/score.txt' --cover '<grid>' --melody '<melody>'`, leaving out `--melody '<melody>'` without a melody: the vocal-notes report is then skipped, and the check does not verify the tune. The `melody` rule stays: it still flags an `M` note under another right-hand note. Its report ends `problems: K` or `clean` ("Checking" in the docs). Fix every flagged finding as "Fixing the check" in `../arrange-cover/references/arranging-rules.md` says, then run steps 6 and 7 again, until it prints `clean` and exits 0. A span marked `(listed, not flagged)` may stay. After the report come the vocal notes the top of the right hand leaves out, `bar N pos P  melody missing  E5 (2)`. Add each on top of the right hand, on `M` in the octave you chose for its section, or record under "Melody left out" in `notes.md` why it stays out.
8. **Render and export:** `pianoize render '<out>/arranged.mid' -o '<out>/arranged.wav'`, adding `--soundfont '<sf2>'` when your prompt names one. If it warns that the peak could clip, render again with a lower `--gain`. Then `pianoize export-arrangement '<out>/arranged.mid' -o '<out>/arranged.json'`, the notes the falling-notes viewer plays with the WAV. Without FluidSynth or a SoundFont, export anyway, and say so in the report.
9. **Report** to the main session, which relays it to the user:
   - the files: `<out>/arranged.wav` (or, without a render, `<out>/arranged.mid`) and `<out>/arranged.json`;
   - the check's last line and the count of vocal notes left out;
   - the places `notes.md` lists as inferred, filled or copied from an earlier section, each by bar and time (the dump's header gives a bar's time), and the gaps it records;
   - each regridded span: the user listens to the song there and counts its bars, since `regrid` can take a real tempo change for a hiccup;
   - each section's left-hand figure, named from `notes.md`, for the user to call too sparse, too busy or right;
   - the repeats a change to a copied-from bar or a section's figure changed;
   - any question for the user, first.
10. **Revise**, when your task is `revise: <the user's words>`. Change a section's density or figure as a whole, not bar by bar: its entry under "Left-hand figures" in `notes.md` changes first, then every `L` line of the section to match, overrides included. Its copies follow it; say in your report which repeats changed. For one bar a copy defined, write an override, so the rest of the copy stays as it is. Record each change and the user's reason in `notes.md`, then run steps 6 to 9 again. When your task is `approved: <the user's words>`, record the approval under "Revisions" in `notes.md` and report that you did.

`notes.md` is yours to shape; this outline covers what the steps above need:

```markdown
# <song>: arranging notes, from the transcription alone
## Clean room
- inputs: '<source>' (and '<melody>' if any) only; no cover, nothing made from one
## Grid tracks
- piano, electric_bass (the default)
## Regridded spans
- bars 40-43: 5 bars at 120.00; to check by ear
## Sections
- intro: bars 1-4, no drums
- verse 2: bars 37-52, copies verse 1 (bars 5-20); overrides 44 and 51
## Chords
- bar 2: 0:C 12:G/B
## Melody
- verse: the vocal an octave up, above the left hand's chords
- intro, bars 1-4: the brass riff carries the tune
## Melody left out
- bar 30, position 6: E5, a grace note of the transcription
## Rhythm section
- verse: kick 0 and 10, snare 4 and 12, hi-hat in eighths; the guitar strums eighths
## The band
- chorus: a backing vocal a third under the lead, taken on `R`
## Left-hand figures
- intro: a root-fifth-octave roll in eighths
- verse: the bass on the kicks at 0 and 10, a two-note chord on the snare
## Hits and stops
- bar 12: a hit at 7 with a crash, then a stop to the end of the bar
## Inferred and filled
- bar 18: the band piano drops the chord; G inferred from the bass and the repeat at bar 34
## Gaps
- bar 30: the song plays a sus2 chord; written as add9
## Revisions
- verse: the left hand's chord at 12 dropped, the one at 4 left to ring (the user: "too busy")
```
