---
name: arrange-cover
description: This skill should be used when the user wants a two-hand piano arrangement of a song written with pianoize from a tsumugi-piano-cover MIDI and tsumugi's melody MIDI, e.g. "arrange this song for two hands", "write the piano arrangement from the cover and the melody", "make a Synthesia arrangement of this cover", "build and check my score", "revise bars 30 to 34 of the arrangement". Dumps the cover and the melody bar by bar, writes a per-bar two-hand score that keeps the original's groove and its signature hits, has the local pianoize CLI build it into MIDI and check that it is playable, renders it, and leaves the final listening to the user. Not for making a cover, a transcription or a melody from audio, for polishing the cover note by note (that is polish-cover), or for rendering the falling-notes video.
---

# Arrange a song for two hands from its piano cover and melody

pianoize arranges a song for a falling-notes video (Synthesia style) from two inputs: the piano cover tsumugi-piano-cover made of it, and tsumugi's transcription of its sung melody. You read both bar by bar, decide the chords and write a score for two hands; pianoize builds the score into MIDI on the cover's tempo grid and checks that it is playable and fits your chords.

pianoize's commands are deterministic and never call an LLM. You write two text files, `notes.md` and `score.txt`; pianoize builds the MIDI from the score. Never write a MIDI file any other way. You cannot hear the result, so the user's listening at the end is the final gate.

## Rules

- **No input is the answer key.** The cover, its chord markers and the melody are models' transcriptions, and each is wrong in places. Weigh them against each other and against the song's own repeats before writing a note.
- **Inputs are read-only.** Never modify, move or overwrite the cover or the melody MIDI.
- **Write only into `<out>`.** Never change pianoize's own files.
- **Never paste song content into the repository.** A song's chords, notes, markers, lyrics and times stay in `<out>` under `work/`, which is never committed: none of it goes into docs, tests, code, commit messages or issues.
- **You write the score and the notes; pianoize builds and checks.** Never write or edit a MIDI file yourself.
- **You cannot hear it.** Never claim the arrangement sounds right. The user's listening decides.
- **Audio never leaves the machine.** Upload nothing.

## Inputs

Ask the user for any input that is missing and stop until you have it; pianoize makes none of them.

- `<cover>`: the cover MIDI made by tsumugi-piano-cover.
- `<melody>`: tsumugi's melody MIDI, its lead vocal track.
- `<out>`: an output directory under `work/`, named by the user (`work/<song>/`). Create it with `mkdir -p`.
- For the render at the end: FluidSynth on `PATH` and a piano SoundFont (`--soundfont`, or `$PIANOIZE_SOUNDFONT`).

Single-quote every path in a command, writing a `'` inside it as `'\''`: song file names carry spaces, brackets and other characters the shell would read.

## Running pianoize

- **Plugin root:** `${CLAUDE_PLUGIN_ROOT}`. If that is a directory with a `pyproject.toml` in it, this skill runs from the pianoize Claude Code plugin, and that directory is the plugin's own copy of pianoize: run `uv run --project "<plugin root>" pianoize <command> …` from the current directory. Its first run builds the environment, so allow a few minutes. Otherwise (empty, still a `${…}` placeholder, or no `pyproject.toml` there) there is no plugin root: in a pianoize checkout, run `uv run pianoize <command> …` there; anywhere else, tell the user to install the pianoize plugin, and stop.
- Without `uv` on `PATH`, tell the user to install it (https://docs.astral.sh/uv/) and stop.
- Below, `pianoize <command> …` stands for that command line.
- **The docs:** `<plugin root>/docs/arranging.md`, or `docs/arranging.md` in the checkout, documents the score format and the three arranging commands with their rules, limits and output; `render` is in `docs/evaluation.md` beside it. `pianoize <command> --help` lists a command's options. Read the section a step names whenever its rules matter.
- **Errors.** A failing command prints `error: …` naming the item at fault (`bar 3: token '4:H4:2': bad note 'H4'`). Fix that item and run the same command again. Exit 2 is a usage error: show its message. An error naming the cover (a type 2 file, a meter change, ticks per beat that don't divide by 4) can't be fixed, since the inputs are read-only: tell the user, and stop. `check-arrangement` also exits 1 while its report flags a finding: that is work for step 6, not an error.

This skill is written for score format version 1: the first line of every score is `format 1`. If pianoize refuses that line and expects another version, the skill and pianoize are out of step: tell the user, and stop.

## Workflow

1. **Dump:** `pianoize dump-bars '<cover>' --melody '<melody>' > '<out>/bars.txt'`. Each bar gets three lines: a header with its time and the cover's chord markers, a `C` line of the cover's attacks and a `V` line of the melody, positions and durations in sixteenths ("Dumping" in the docs). Bar N of the dump is bar N of the score.
2. **Read `<out>/bars.txt` whole**, following **`references/reading-the-dump.md`**, and write `<out>/notes.md`:
   - the sections with their bars, and which later sections repeat which;
   - a chord per bar, with its position where it changes inside the bar. The cover's notes and markers are evidence, not truth: decide from the bass, the long notes and the repeats;
   - the melody's entries, its pickups and the octave the cover plays it in;
   - the hits, stop-times and syncopations, by bar and position;
   - every place where the transcription is wrong or silent, and what you infer there.
3. **Write `<out>/score.txt` one section at a time**, in bar order, following **`references/arranging-rules.md`** ("The score format" in the docs). Write every bar from 1 on, a silent one as a bar with `N.C.` and no hand lines. A chord quality the table lacks doesn't stop you: write the nearest one, mark any extra chord tone `~`, and record the place under "Gaps" in `notes.md` ("Chords and passing tones" in `references/arranging-rules.md`). After each section, run steps 5 and 6 and fix every flagged finding before writing the next. A score looks like this:
   ```
   format 1
   # Made-up bars: the shape of a score, not a song.
   == intro | pedal=chord
   bar 1 | N.C.
   bar 2 | 0:C 12:G/B
     M 0:E5:6 6:D5:2 8:C5:4 12:D5:4
     R 0:G4:8 8:E4+G4:4 12:D4+G4:4
     L 0:C3:12 12:B2:4
   == verse
   bar 3 | Am
     M 0:C5:8 8:B4:4 12:A4:4
     R 0:E4:16
     L 0:A2+E3:12 12:G2~:4
   bars 4-5 = 2-3
   bar 5 | 0:F 8:G
     M 0:A4:8 8:B4:8
     R 0:C4+F4:8 8:D4+G4:8
     L 0:F2:8 8:G2:8
   ```
   `M` is the melody, `R` the rest of the right hand under it, `L` the left hand. A token is `position:notes:duration` in sixteenths, `+` joins notes struck together, and `~` marks a passing tone.
4. **Repeats:** write a section that repeats an earlier one as `bars A-B = C-D`. Where the melody or the band differs in a copied bar, override that bar: a `bar N | …` block after the copy, which replaces the copied bar whole, so give it every hand line the bar needs. Record each copy and override in `notes.md`. Editing a source bar changes its copies. To keep a repeat as it was, override that copied bar with the old lines, and tell the user which repeats changed.
5. **Build:** `pianoize build-arrangement '<out>/score.txt' --cover '<cover>' -o '<out>/arranged.mid'`. It prints the notes per hand, the pedal presses and the length ("Building" in the docs). Once the score is complete, the length is about the cover's.
6. **Check:** `pianoize check-arrangement '<out>/score.txt' --cover '<cover>'`. It lists the findings by rule, `notes`, `span`, `jump`, `crossing`, `melody` and `harmony`, each line naming its bar, position and hand, and ends with `problems: K` or `clean` ("Checking" in the docs). Fix every flagged finding as "Fixing the check" in `references/arranging-rules.md` says, then run steps 5 and 6 again, until it prints `clean` and exits 0. A span marked `(listed, not flagged)` may stay.
7. **Render:** `pianoize render '<out>/arranged.mid' -o '<out>/arranged.wav'`, adding `--soundfont '<sf2>'` when `$PIANOIZE_SOUNDFONT` is not set. If it warns that the peak could clip, render again with a lower `--gain`. Without FluidSynth or a SoundFont, tell the user and give them the MIDI path instead.
8. **Ask the user to listen.** Give them `<out>/arranged.wav` and the places `notes.md` lists as inferred, filled, copied from the cover or copied from an earlier section, each by bar and time (the dump's header gives a bar's time), and the gaps it records. Ask them to approve, or to name the places to change by bar or time, and stop until they answer.
9. **Revise** the bars they name. For a bar a copy defined, write an override, so the rest of the copy stays as it is. Editing a source bar changes its copies too (step 4). Record each change and the user's reason in `notes.md`, then run steps 5 to 8 again, until they approve. Record the approval in `notes.md`.

`notes.md` is yours to shape; this outline covers what the steps above need:

```markdown
# <song>: arranging notes
## Sections
- intro: bars 1-4
- verse 2: bars 37-52, copies verse 1 (bars 5-20); overrides 44 and 51
## Chords
- bar 2: 0:C 12:G/B
## Melody
- bar 5, position 2: the verse enters; the cover plays it an octave up
## Hits and stops
- bar 12: a hit at 7, then a stop to the end of the bar
## Inferred, filled and copied
- bar 18: the cover drops the chord; G inferred from the bass and the repeat at bar 34
- bar 12: the hit copied from the cover, its strays cleaned
## Gaps
- bar 30: the song plays a sus2 chord; written as add9
## Revisions
- bar 44: the melody's last note held longer (the user: "it cuts off")
```

## Output files

All in `<out>`:

| file | written by | holds |
| --- | --- | --- |
| `bars.txt` | `dump-bars` | the cover's attacks and the melody, bar by bar |
| `notes.md` | you | the sections, the chords, the melody's entries, the hits and stops, every inferred, filled or copied place, the gaps, and the revisions |
| `score.txt` | you | the two-hand score, format version 1 |
| `arranged.mid` | `build-arrangement` | the two-hand MIDI on the cover's tempo grid |
| `arranged.wav` | `render` | the render for the user to listen to |

## Additional resources

- **`references/reading-the-dump.md`:** the dump's lines, the markers, finding the chords, the hits, the stops and the melody, and reading a long dump.
- **`references/arranging-rules.md`:** keeping the feel, copying the cover, inferring, voicing the hands, the pedal, and fixing each check rule.
- **pianoize's `docs/arranging.md`** (see "Running pianoize"): the score format, every command, the check's limits and the output formats.
