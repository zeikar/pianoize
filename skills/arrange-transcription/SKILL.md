---
name: arrange-transcription
description: This experimental skill should be used only when the user asks for a two-hand piano arrangement written with pianoize from tsumugi's transcription of the band alone, without tsumugi-piano-cover's cover, e.g. "arrange from the transcription only", "clean-room arrangement without the cover", "arrange the band for piano from source.mid", "revise the transcription-only arrangement". Builds a tempo grid from the transcription, dumps the band's piano, bass, drums and instrument lines bar by bar, writes a per-bar two-hand score that arranges the band for piano, has the local pianoize CLI build it into MIDI and check that it is playable, renders it, and leaves the final listening to the user. Not the default: given a cover MIDI, or without that request, use arrange-cover. Not for making a transcription or a melody from audio, for polishing a cover (that is polish-cover), or for rendering the falling-notes video.
---

# Arrange a song for two hands from its band transcription (experimental)

pianoize arranges a song for a falling-notes video (Synthesia style). This experimental path starts from tsumugi's transcription of the whole band, `source.mid`, with a track per instrument, a tempo map and chord markers, and from tsumugi's transcription of the sung melody where the song has one. You read the band bar by bar, decide the chords and arrange the band for two hands in a score; pianoize builds the score into MIDI on a tempo grid it makes from the transcription, and checks that it is playable and fits your chords.

The path exists for its terms. tsumugi-piano-cover's weights are CC BY-NC 4.0, so its cover and anything made from it are treated as non-commercial. The transcriber's code and weights are MIT, so an arrangement that never touches the cover carries no such terms. `arrange-cover` stays the default: this path's first trial left the left hand unsettled ("Density" in `references/band-to-piano.md`), and the skill is kept to be run again with a newer model or a tuned prompt.

pianoize's commands are deterministic and never call an LLM. You write two text files, `notes.md` and `score.txt`; pianoize builds the MIDI from the score. Never write a MIDI file any other way. You cannot hear the result, so the user's listening at the end is the final gate.

## Rules

- **Clean room.** The only inputs are tsumugi's transcription, tsumugi's melody MIDI, and what pianoize makes from them in `<out>`. Never read, dump, copy from or compare against any of these, in `<out>` or anywhere else:
  - tsumugi-piano-cover's cover MIDI, or anything made from it;
  - a polished cover;
  - a refined timeline;
  - the `bars.txt`, `notes.md`, `score.txt` or `arranged.mid` of an `arrange-cover` or `polish-cover` run.

  If the user offers one, decline it and say why: it would bring the cover's notes, and its terms, into an arrangement that must have neither. `<out>` is a directory of its own: if it holds `cover.regrid.mid` or such a run's files, ask for another. Record the inputs under "Clean room" at the top of `notes.md`.
- **No input is the answer key.** The transcription, its chord markers and the melody are models' transcriptions, and each is wrong in places. Weigh them against each other and against the song's own repeats before writing a note.
- **Inputs are read-only.** Never modify, move or overwrite the source or the melody.
- **Write only into `<out>`.** Never change pianoize's own files.
- **Never paste song content into the repository.** A song's chords, notes, markers, lyrics and times stay in `<out>` under `work/`, which is never committed: none of it goes into docs, tests, code, commit messages or issues.
- **You write the score and the notes; pianoize builds and checks.** Never write or edit a MIDI file yourself.
- **You cannot hear it.** Never claim the arrangement sounds right. The user's listening decides.
- **Audio never leaves the machine.** Upload nothing.

## Inputs

Ask the user for any input that is missing and stop until you have it. The `prepare-song` skill (`../prepare-song/SKILL.md`) makes them, `pianoize prepare` writing `source.mid` and `melody.mid` (where the song has one) into the song's directory; when they are missing, offer that skill and stop.

- `<source>`: tsumugi's transcription of the whole band, `source.mid`: a track per instrument, the drums among them, a tempo map and chord markers.
- `<melody>`, optional: tsumugi's melody MIDI, the transcriber's lead vocal track. An instrumental has none, unless `prepare --melody-track` named an instrument's track. Without one, leave `--melody '<melody>'` out of steps 3 and 7.
- `<out>`: an output directory under `work/` of its own, named by the user (`work/<song>-transcription/`). Create it with `mkdir -p`.
- For the render at the end: FluidSynth on `PATH` and a piano SoundFont (`--soundfont`, or `$PIANOIZE_SOUNDFONT`).

Single-quote every path in a command, writing a `'` inside it as `'\''`: song file names carry spaces, brackets and other characters the shell would read.

## Running pianoize

- **Plugin root:** `${CLAUDE_PLUGIN_ROOT}`. If that is a directory with a `pyproject.toml` in it, this skill runs from the pianoize Claude Code plugin, and that directory is the plugin's own copy of pianoize: run `uv run --project "<plugin root>" pianoize <command> …` from the current directory. Its first run builds the environment, so allow a few minutes. Otherwise (empty, still a `${…}` placeholder, or no `pyproject.toml` there) there is no plugin root: in a pianoize checkout, run `uv run pianoize <command> …` there; anywhere else, tell the user to install the pianoize plugin, and stop.
- Without `uv` on `PATH`, tell the user to install it (https://docs.astral.sh/uv/) and stop.
- Below, `pianoize <command> …` stands for that command line.
- **The docs:** `<plugin root>/docs/arranging.md`, or `docs/arranging.md` in the checkout, documents the score format and the arranging commands with their rules, limits and output, the grid under "Building the grid from a transcription" and the dump under "Dumping"; `render` is in `docs/evaluation.md` beside it, and `export-arrangement` in `docs/rendering.md`. `pianoize <command> --help` lists a command's options. Read the section a step names whenever its rules matter.
- **Errors.** A failing command prints `error: …` naming the item at fault (`bar 3: token '4:H4:2': bad note 'H4'`). Fix that item and run the same command again. Exit 2 is a usage error: show its message. An error naming the grid, the melody or the source (a type 2 file, a meter change, ticks per beat that don't divide by 4) can't be fixed, since the inputs are read-only (a missing track at step 1 excepted, which `--track` fixes): tell the user, and stop. `check-arrangement` also exits 1 while its report flags a finding: that is work for step 7, not an error.

This skill is written for score format version 1: the first line of every score is `format 1`. If pianoize refuses that line and expects another version, the skill and pianoize are out of step: tell the user, and stop.

## Workflow

1. **Grid:** `pianoize build-grid '<source>' -o '<out>/grid.mid'`. It writes the grid that stands in for a cover: the transcription's tempo map and chord markers, with its `piano` and `electric_bass` tracks ("Building the grid from a transcription" in the docs). If it refuses a track the source lacks, its error lists the tracks the source names: choose the ones that carry the band's chords and its bass, and run it again with a `--track` for each, `pianoize build-grid '<source>' -o '<out>/grid.mid' --track '<chords>' --track '<bass>'`. Record the tracks the grid holds under "Grid tracks" in `notes.md`.
2. **Regrid:** `pianoize regrid '<out>/grid.mid' -o '<out>/grid.regrid.mid'`. It writes a copy of the grid with its tempo hiccups regridded ("Regridding" in the docs). From here on, every `'<grid>'` in a command stands for that copy, `'<out>/grid.regrid.mid'`, the cover of every command. If it prints spans (`bars 40-43: … BPM -> 5 bars at 120.00`) rather than `no tempo hiccups`, record each under "Regridded spans" in `notes.md`: the user checks each by ear at step 9.
3. **Dump:** `pianoize dump-bars '<grid>' --melody '<melody>' --source '<source>' --every-bar --drums > '<out>/bars.txt'`, leaving out `--melody '<melody>'` without a melody. Each bar gets a header with its time and the transcription's chord markers, and then these lines ("Dumping" in the docs), whose positions and durations count sixteenths:
   - `C`: the attacks of the grid's tracks, the band's piano and bass. It is what the band plays, not a pianist's part;
   - `V`: the melody;
   - `D`: the drums' hits, grouped as `kick`, `snare`, `hihat`, `cymbal` and `other`;
   - `I`: a line per instrument of the source that plays in the bar, its top line, in every bar, sung bars included.

   Bar N of the dump is bar N of the score. To read a section closely, run the same dump with `--bars A-B`, its first and last bars, and without the redirect: it prints to the screen and leaves `bars.txt` as it is.
4. **Read `<out>/bars.txt` whole**, following **`../arrange-cover/references/reading-the-dump.md`** for the lines, the markers, the chords and the instrument lines, and **`references/band-to-piano.md`** for the rhythm section and the melody. There is no cover here. What `arrange-cover`'s references say of the cover's notes is `C`, the band's piano and bass; their `'<cover>'` is `'<grid>'`; and where they run `dump-bars`, run step 3's dump with `--bars A-B` instead. `C`'s notes and the markers come from different models of the transcriber, so where they agree, that is two readings, not the one "Markers are a model's guesses" counts. In `reading-the-dump.md`'s "The melody", the bullets that compare `V` with the cover's top notes, write the melody where the cover plays it, or take the hook from the cover's top line are replaced by "The melody" in `references/band-to-piano.md`. Then write `<out>/notes.md`:
   - the sections with their bars, and which later sections repeat which;
   - a chord per bar, with its position where it changes inside the bar, decided from the bass, the long notes and the repeats;
   - the melody's entries and pickups, and the octave you choose for it in each section;
   - each section's rhythm section, its drums, strums and bass line, and the left-hand figure you choose for it;
   - the hits, stops and syncopations, by bar and position;
   - every place where the transcription is wrong or silent, what you infer there, and the gaps.
5. **Write `<out>/score.txt` one section at a time**, in bar order, following **`references/band-to-piano.md`** and these sections of **`../arrange-cover/references/arranging-rules.md`**:
   - "Keep the feel", except its first bullet, "The groove is the original's", whose place "Reading the rhythm section" in `references/band-to-piano.md` takes;
   - "Where no one sings", as `references/band-to-piano.md` adjusts it;
   - "Infer and fill";
   - "Readable when falling";
   - "The hands", except its "Write it an octave up where the cover plays it there", which "The melody" in `references/band-to-piano.md` replaces;
   - "Pedal", "Chords and passing tones" and "Fixing the check".

   Not "Copy the cover where it renders a moment best", which reads a cover, nor "One velocity", whose verse texture "Density" in `references/band-to-piano.md` replaces. The score's shape is the example in step 4 of `../arrange-cover/SKILL.md`; its grammar is "The score format" in the docs. Write every bar from 1 on, a silent one as a bar with `N.C.` and no hand lines. Write a section that repeats an earlier one as a copy, `bars A-B = C-D`, with overrides, as step 5 of `../arrange-cover/SKILL.md` says, and record each in `notes.md`. After each section, run steps 6 and 7 and fix every flagged finding before writing the next.
6. **Build:** `pianoize build-arrangement '<out>/score.txt' --cover '<grid>' -o '<out>/arranged.mid'`. It prints the notes per hand, the pedal presses and the length ("Building" in the docs). Once the score is complete, the length is about the grid's.
7. **Check:** `pianoize check-arrangement '<out>/score.txt' --cover '<grid>' --melody '<melody>'`, leaving out `--melody '<melody>'` without a melody: the vocal-notes report is then skipped, and the check does not verify the tune. The `melody` rule stays: it still flags an `M` note under another right-hand note. Its report ends `problems: K` or `clean` ("Checking" in the docs). Fix every flagged finding as "Fixing the check" in `../arrange-cover/references/arranging-rules.md` says, then run steps 6 and 7 again, until it prints `clean` and exits 0. A span marked `(listed, not flagged)` may stay. After the report come the vocal notes the top of the right hand leaves out, `bar N pos P  melody missing  E5 (2)`. Add each on top of the right hand, on `M` in the octave you chose for its section, or record under "Melody left out" in `notes.md` why it stays out.
8. **Render and export:** `pianoize render '<out>/arranged.mid' -o '<out>/arranged.wav'`, adding `--soundfont '<sf2>'` when `$PIANOIZE_SOUNDFONT` is not set. If it warns that the peak could clip, render again with a lower `--gain`. Then `pianoize export-arrangement '<out>/arranged.mid' -o '<out>/arranged.json'`, the notes the falling-notes viewer plays with the WAV. Without FluidSynth or a SoundFont, export anyway, tell the user, and give them the MIDI path in place of the WAV.
9. **Ask the user to listen.** Give them `<out>/arranged.wav`, and tell them they can watch it fall too: dropping `arranged.json` and `arranged.wav` on https://zeikar.dev/pianoize/ plays them there, read in the browser and uploaded nowhere. Give them the places `notes.md` lists as inferred, filled or copied from an earlier section, each by bar and time (the dump's header gives a bar's time), and the gaps it records. Name each regridded span too: the user listens to the song there and counts its bars, since `regrid` can take a real tempo change for a hiccup. Ask them also about each section's left hand, naming its figure from `notes.md`: too sparse, too busy, or right. Ask them to approve, or to name the places to change by bar or time, and stop until they answer.
10. **Revise** what they name. Change a section's density or figure as a whole, not bar by bar: its entry under "Left-hand figures" in `notes.md` changes first, then every `L` line of the section to match, overrides included. Its copies follow it; tell the user which repeats changed. For one bar a copy defined, write an override, so the rest of the copy stays as it is. Record each change and the user's reason in `notes.md`, then run steps 6 to 9 again, until they approve. Record the approval in `notes.md`.

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

## Output files

All in `<out>`:

| file | written by | holds |
| --- | --- | --- |
| `grid.mid` | `build-grid` | the transcription's tempo map, time signature and chord markers, with its band piano and bass |
| `grid.regrid.mid` | `regrid` | the grid with its tempo hiccups regridded, used as `<grid>` |
| `bars.txt` | `dump-bars` | the band's piano and bass, the melody, the drums and the instrument lines, bar by bar |
| `notes.md` | you | the inputs and the grid's tracks, what step 4 records, the vocal notes left out, and the revisions |
| `score.txt` | you | the two-hand score, format version 1 |
| `arranged.mid` | `build-arrangement` | the two-hand MIDI on the grid's tempo map |
| `arranged.wav` | `render` | the render for the user to listen to |
| `arranged.json` | `export-arrangement` | the notes the falling-notes viewer plays with `arranged.wav` |

## Additional resources

- **`references/band-to-piano.md`:** reading the rhythm section, the left hand as a pianist's accompaniment, one figure per section, its density, and the right hand with the melody.
- **`../arrange-cover/references/reading-the-dump.md`:** the dump's lines, the instrument lines, the markers, finding the chords, the hits and the stops, and reading a long dump.
- **`../arrange-cover/references/arranging-rules.md`:** the sections step 5 names, with the parts `references/band-to-piano.md` replaces: keeping the feel, the sections where no one sings, inferring, readable when falling, voicing the hands, the pedal, the chords and passing tones, and fixing each check rule. Not copying the cover, nor "One velocity".
- **pianoize's `docs/arranging.md`** (see "Running pianoize"): the score format, every command, the check's limits and the output formats.
