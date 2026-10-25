# The arranger's workflow

What the arranger subagent does when an arranging skill dispatches it: the steps, the rules and the report. The skill's `SKILL.md` is the main session's side: it gathers the inputs, dispatches you and talks to the user.

Your prompt names four files by absolute path: this workflow, a front end, a right-hand file and a left-hand file. Read all four first. Every rule file they and this one name by bare name, `reading-the-dump.md`, `arranging-rules.md` and the rest, sits beside this file in the same directory, `<root>/arranging/`.

You arrange a song for a falling-notes video (Synthesia style) from what your front end gives: tsumugi's transcriptions of the song's band and of its sung melody, or the piano cover tsumugi-piano-cover made of it with the melody and the band. You read them bar by bar, decide the chords and write a score for two hands as your hand files say; pianoize builds the score into MIDI on the tempo grid your front end makes, and checks that it fits your chords and, where a hand file keeps a hand within the check's limits, that the hand can play it.

pianoize's commands are deterministic and never call an LLM. You write two text files, `notes.md` and `score.txt`; pianoize builds the MIDI from the score. Never write a MIDI file any other way. You cannot hear the result, so the user's listening at the end is the final gate.

## Rules

- **No input is the answer key.** `C`, the chord markers, the melody and the band's transcription are models' transcriptions, and each is wrong in places. Weigh them against each other and against the song's own repeats before writing a note.
- **Inputs are read-only.** Never modify, move or overwrite the cover, the melody or the source MIDI.
- **Write only into `<out>`.** Never change pianoize's own files.
- **Never paste song content into the repository.** A song's chords, notes, markers, lyrics and times stay in `<out>` under `work/`, which is never committed: none of it goes into docs, tests, code, commit messages or issues.
- **You write the score and the notes; pianoize builds and checks.** Never write or edit a MIDI file yourself.
- **You cannot hear it.** Never claim the arrangement sounds right. The user's listening decides.
- **Audio never leaves the machine.** Upload nothing.

## Running pianoize

- **The command line** is in your dispatch prompt: below, `pianoize <command> …` stands for it. Its first run may build pianoize's environment, so allow a few minutes.
- **The docs:** the docs directory your prompt names holds `arranging.md`, which documents the score format and the arranging commands with their rules, limits and output, the grid under "Building the grid from a transcription" and the dump under "Dumping"; `render` is in `evaluation.md` beside it, and `export-arrangement` in `rendering.md`. `pianoize <command> --help` lists a command's options. Read the section a step names whenever its rules matter.
- **Quoting.** Single-quote every path in a command, writing a `'` inside it as `'\''`: song file names carry spaces, brackets and other characters the shell would read.
- **Errors.** A failing command prints `error: …` naming the item at fault (`bar 3: token '4:H4:2': bad note 'H4'`). Fix that item and run the same command again. Exit 2 is a usage error: report its message. An error naming the cover, the melody or the source (a type 2 file, a meter change, ticks per beat that don't divide by 4) can't be fixed, since the inputs are read-only: stop, and report it. The one exception is a missing track: where `build-grid` refuses a track the source lacks, one of its defaults or one a `--track` names, or `check-arrangement` refuses a `--piano-track` or `--bass-track` name the source lacks, its error lists the tracks the source names, and the right names fix it. `check-arrangement` also exits 1 while its report flags a finding: that is work for step 7, not an error.
- **The score format.** Every score starts with the line `format 1`. If pianoize refuses that line and expects another version, the skill and pianoize are out of step: stop, and report it.

## Steps

`<melody>`, `<source>` and `<out>` are the paths your prompt gives, with `<cover>` where your front end reads one; `<melody>` may be none, and `<source>` where your front end allows it. After step 1, `'<cover>'` is the cover your front end makes.

1. **Front end:** follow your front-end file's steps. They make `'<cover>'`, the cover of every later command, and record what they must in `notes.md`.
2. **Dump:** `pianoize dump-bars '<cover>' --melody '<melody>' --source '<source>' --every-bar --drums > '<out>/bars.txt'`. Leave out `--melody '<melody>'` without a melody, and `--source '<source>' --every-bar --drums` without a source. Add `--every-note` when your right-hand file asks for it: `pianoize dump-bars '<cover>' --melody '<melody>' --source '<source>' --every-bar --every-note --drums > '<out>/bars.txt'`. Each bar gets a header with its time and the chord markers, a `C` line of attacks, read as your front end says, and a `V` line of the melody, positions and durations in sixteenths; with a source, a `D` line of the drums and an `I` line per instrument that plays in the bar, its top line, or with `--every-note` its every note, sung bars included ("Dumping" in the docs). Bar N of the dump is bar N of the score. To read a section closely, run the same dump with `--bars A-B`, its first and last bars, and without the redirect: it prints to the screen and leaves `bars.txt` as it is.
3. **Read `<out>/bars.txt` whole**, following `reading-the-dump.md` and your front end, and write `<out>/notes.md`:
   - the sections with their bars, and which later sections repeat which;
   - a chord per bar, with its position where it changes inside the bar. `C`'s notes and the markers are evidence, not truth: decide from the bass, the long notes and the repeats, and with a source, from the band's own bass ("Finding the chord" in `reading-the-dump.md`);
   - the melody's entries and pickups, and its octave in each section, as your front end gives it;
   - in each section without vocal, the instrument line that carries the tune; without a melody, in every section ("The melody" in `reading-the-dump.md`);
   - with a source, each section's rhythm section under "Rhythm section": its drums, its strums and the bass line ("The drums" in `reading-the-dump.md`);
   - with a source, each section's band under "The band" ("The instrument lines" in `reading-the-dump.md`): a backing vocal, a pulse, a riff or a fill under the voice, and what the score takes from each;
   - each section's figures, as your hand files say;
   - the hits, stop-times, breakdowns and syncopations, by bar and position;
   - every place where the transcription is wrong or silent, what you infer there, and the gaps.
4. **Write `<out>/score.txt` one section at a time**, in bar order, following `arranging-rules.md`, your front end and your two hand files ("The score format" in the docs). Write every bar from 1 on, a silent one as a bar with `N.C.` and no hand lines. A chord quality the table lacks doesn't stop you: write the nearest one, mark any extra chord tone `~`, and record the place under "Gaps" in `notes.md` ("Chords and passing tones" in `arranging-rules.md`). After each section, run steps 6 and 7 and fix every flagged finding before writing the next. A score looks like this:
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
5. **Repeats:** write a section that repeats an earlier one as `bars A-B = C-D`. A repeat copies only what repeats: compare each copied bar's `V`, `D` and `I` lines with its source bar's. Where the melody or the band differs in a copied bar, where the drums drop out, a breakdown holds its chords or the band stops, override that bar: a `bar N | …` block after the copy, which replaces the copied bar whole, so give it every hand line the bar needs. Record each copy and override in `notes.md`. Editing a bar that a copy was taken from changes every copy of it. To keep a repeat as it was, override that copied bar with the old lines, and say in your report which repeats changed.
6. **Build:** `pianoize build-arrangement '<out>/score.txt' --cover '<cover>' -o '<out>/arranged.mid'`. It prints the notes per hand, the pedal presses and the length ("Building" in the docs). Once the score is complete, the length is about the cover's.
7. **Check:** `pianoize check-arrangement '<out>/score.txt' --cover '<cover>' --melody '<melody>' --source '<source>'`, leaving out `--melody '<melody>'` without a melody and `--source '<source>'` without a source. Where "Grid tracks" in `notes.md` records tracks other than the defaults, pass its chords track as `--piano-track` and its bass track as `--bass-track`; a band without a piano or a bass needs no option, since a default the source lacks reads none. Add the flags your right-hand file names, then do what your left-hand file asks of the check. Without a melody the vocal-notes report is skipped, and the check does not verify the tune. The `melody` rule stays: it still flags an `M` note under another right-hand note. It lists the findings by rule, `notes`, `span`, `jump`, `crossing`, `melody` and `harmony`, each line naming its bar, position and hand; the report's last line is `problems: K` or `clean` ("Checking" in the docs). Fix every flagged finding as "Fixing the check" in `arranging-rules.md` says, then run steps 6 and 7 again, until it prints `clean` and exits 0. A span marked `(listed, not flagged)` may stay. Two lists follow the report; they never stop `clean`, but each line is your choice:
   - **The vocal notes** the top of the right hand leaves out, `bar N pos P  melody missing  E5 (2)`, and their count: an inner voice under the top doesn't play one. Add each on top of the right hand, usually on `M` in the octave the melody is in there, or record under "Melody left out" in `notes.md` why it stays out.
   - **With a source, the left-hand notes the band doesn't back**, `bar N pos P  LH  unbacked  …` or `bar N pos P  LH  semitone  …`, and their count, `harmony backing: K unbacked, J semitone` ("The left hand against the band" in the docs). Fix each line with a note the band backs, or justify it under "Harmony backing" in `notes.md`, naming what backs the note or the band part it is taken from.
8. **Compare with the band**, where your front end has that step.
9. **Render and export:** `pianoize render '<out>/arranged.mid' -o '<out>/arranged.wav'`, adding `--soundfont '<sf2>'` when your prompt names one. If it warns that the peak could clip, render again with a lower `--gain`. Then `pianoize export-arrangement '<out>/arranged.mid' -o '<out>/arranged.json'`, the notes the falling-notes viewer plays with the WAV. Without FluidSynth or a SoundFont, export anyway, and say so in the report.
10. **Report** to the main session, which relays it to the user:
    - the files: `<out>/arranged.wav` (or, without a render, `<out>/arranged.mid`) and `<out>/arranged.json`;
    - the check's last line, the count of vocal notes left out and the harmony backing count;
    - the places `notes.md` lists as inferred, filled, copied from the cover, copied from an earlier section or changed at step 8, each by bar and time (the dump's header gives a bar's time), and the gaps it records;
    - each regridded span: the user listens to the song there and counts its bars, since `regrid` can take a real tempo change for a hiccup;
    - the repeats a change to a copied-from bar or a section's figure changed (step 5);
    - each section's figures, where `notes.md` records them, named from "Figures" and "Left-hand figures", for the user to call too thin, too busy or right;
    - each hand as its file says: written for listening, or within the check's limits;
    - any question for the user, first.
11. **Revise**, when your task is `revise: <the user's words>`: change the bars they name. A change to a section's figure or density, recorded under "Figures" or "Left-hand figures" in `notes.md`, changes it as a whole, not bar by bar: its entry first, then every bar of the section and of its copies to match, overrides included. For one bar a copy defined, write an override, so the rest of the copy stays as it is. Editing a copied-from bar changes its copies too (step 5). Record each change and the user's reason under "Revisions" in `notes.md`, then run steps 6 and 7 again, step 8 for the bars you changed without undoing what the user asked for, and steps 9 and 10. When your task is `approved: <the user's words>`, record the approval under "Revisions" in `notes.md` and report that you did.

`notes.md` is yours to shape; this outline covers what the steps above and your files need, each section where a step or a file asks for it:

```markdown
# <song>: arranging notes
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
- bar 5, position 2: the verse enters, an octave up, above the left hand's chords
- intro, bars 1-4: the brass riff carries the tune
## Melody left out
- bar 30, position 6: E5, a grace note of the transcription
## The band
- verse: a synth pulses eighths; a guitar fill in the voice's gap at bar 8
- chorus: a backing vocal a third under the lead, taken on `R`
## Rhythm section
- verse: kick 0 and 10, snare 4 and 12, hi-hat in eighths; the guitar strums eighths; the bass walks into each bar
## Figures
- verse: the bass held through the bar, the top voice one note held, the guitar's sixteenths in `L`
## Left-hand figures
- verse, first half: a broken chord, root octave at 0, fifth at 6, upper root at 10, tenth at 12
## Hits and stops
- bar 12: a hit at 7 with a crash, then a stop to the end of the bar
- bars 60-63: a breakdown, the drums on the downbeat only, the band holding its chords
## Inferred, filled and copied
- bar 18: `C` drops the chord; G inferred from the bass and the repeat at bar 34
- bar 12: the hit copied from the cover, its strays cleaned
## Compared with the band
- bar 41: the band's bass holds E under the cover's C; written C/E
## Harmony backing
- bar 22, position 4: G3 kept in `L`; the strings hold G4 there, which the check doesn't read
## Gaps
- bar 30: the song plays a sus2 chord; written as add9
## Revisions
- bar 44: the melody's last note held longer (the user: "it cuts off")
```
