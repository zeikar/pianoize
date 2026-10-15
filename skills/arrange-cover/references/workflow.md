# The arranger's workflow: from the cover, the melody and the band

What the arranger subagent does when `arrange-cover` dispatches it: the steps, the rules and the report. SKILL.md is the main session's side: it gathers the inputs, dispatches you and talks to the user. Paths here, `references/…` and `../<skill>/…`, are from this skill's directory.

You arrange a song for a falling-notes video (Synthesia style) from the piano cover tsumugi-piano-cover made of it and tsumugi's transcription of its sung melody, where the song has one. tsumugi's transcription of the whole band, `source.mid`, a track per instrument, is read under the cover in every bar where you have it: its bass, its drums, its backing vocal and the parts the cover leaves out. You read them bar by bar, decide the chords and write a score for two hands; pianoize builds the score into MIDI on the cover's tempo grid and checks that it is playable and fits your chords.

pianoize's commands are deterministic and never call an LLM. You write two text files, `notes.md` and `score.txt`; pianoize builds the MIDI from the score. Never write a MIDI file any other way. You cannot hear the result, so the user's listening at the end is the final gate.

## Rules

- **No input is the answer key.** The cover, its chord markers, the melody and the band's transcription are models' transcriptions, and each is wrong in places. Weigh them against each other and against the song's own repeats before writing a note.
- **Inputs are read-only.** Never modify, move or overwrite the cover, the melody or the source MIDI.
- **Write only into `<out>`.** Never change pianoize's own files.
- **Never paste song content into the repository.** A song's chords, notes, markers, lyrics and times stay in `<out>` under `work/`, which is never committed: none of it goes into docs, tests, code, commit messages or issues.
- **You write the score and the notes; pianoize builds and checks.** Never write or edit a MIDI file yourself.
- **You cannot hear it.** Never claim the arrangement sounds right. The user's listening decides.
- **Audio never leaves the machine.** Upload nothing.

## Running pianoize

- **The command line** is in your dispatch prompt: below, `pianoize <command> …` stands for it. Its first run may build pianoize's environment, so allow a few minutes.
- **The docs:** the docs directory your prompt names holds `arranging.md`, which documents the score format and the arranging commands with their rules, limits and output; `render` is in `evaluation.md` beside it, and `export-arrangement` in `rendering.md`. `pianoize <command> --help` lists a command's options. Read the section a step names whenever its rules matter.
- **Quoting.** Single-quote every path in a command, writing a `'` inside it as `'\''`: song file names carry spaces, brackets and other characters the shell would read.
- **Errors.** A failing command prints `error: …` naming the item at fault (`bar 3: token '4:H4:2': bad note 'H4'`). Fix that item and run the same command again. Exit 2 is a usage error: report its message. An error naming the cover, the melody or the source (a type 2 file, a meter change, ticks per beat that don't divide by 4) can't be fixed, since the inputs are read-only: stop, and report it. `check-arrangement` also exits 1 while its report flags a finding: that is work for step 7, not an error.
- **The score format.** Every score starts with the line `format 1`. If pianoize refuses that line and expects another version, the skill and pianoize are out of step: stop, and report it.

## Steps

`<cover>`, `<melody>`, `<source>` and `<out>` are the paths your prompt gives; `<melody>` and `<source>` may be none.

1. **Regrid:** `pianoize regrid '<cover>' -o '<out>/cover.regrid.mid'`. It writes a copy of the cover with the tempo hiccups of its beat tracking regridded, so the song's bars fall on the grid's ("Regridding" in the docs). From here on, every `'<cover>'` in a command stands for that copy, `'<out>/cover.regrid.mid'`. `no tempo hiccups` is the usual answer, since `prepare` puts the transcription on a steady grid where its fit was applied. If it prints spans (`bars 40-43: … BPM -> 5 bars at 120.00`) instead, record each under "Regridded spans" in `notes.md`: the user checks each by ear.
2. **Dump:** with a source, `pianoize dump-bars '<cover>' --melody '<melody>' --source '<source>' --every-bar --drums > '<out>/bars.txt'`; without one, `pianoize dump-bars '<cover>' --melody '<melody>' > '<out>/bars.txt'`. Leave out `--melody '<melody>'` without a melody. Each bar gets a header with its time and the cover's chord markers, a `C` line of the cover's attacks and a `V` line of the melody, positions and durations in sixteenths; with a source, a `D` line of the drums and an `I` line per instrument that plays in the bar, its top line, sung bars included ("Dumping" in the docs). Bar N of the dump is bar N of the score. To read a section closely, run the same dump with `--bars A-B`, its first and last bars, and without the redirect: it prints to the screen and leaves `bars.txt` as it is.
3. **Read `<out>/bars.txt` whole**, following **`references/reading-the-dump.md`**, and write `<out>/notes.md`:
   - the sections with their bars, and which later sections repeat which;
   - a chord per bar, with its position where it changes inside the bar. The cover's notes and markers are evidence, not truth: decide from the bass, the long notes and the repeats, and with a source, from the band's own bass ("Finding the chord" in `references/reading-the-dump.md`);
   - the melody's entries, its pickups and the octave the cover plays it in;
   - in each section without vocal, the instrument line that carries the tune; without a melody, in every section ("The melody" in `references/reading-the-dump.md`);
   - with a source, each section's band ("The drums" and "The instrument lines" in `references/reading-the-dump.md`): its drum pattern, the bass line, a backing vocal, a pulse, a riff or a fill under the voice, and what the score takes from each;
   - the hits, stop-times, breakdowns and syncopations, by bar and position;
   - every place where the transcription is wrong or silent, and what you infer there.
4. **Write `<out>/score.txt` one section at a time**, in bar order, following **`references/arranging-rules.md`** ("The score format" in the docs). Write every bar from 1 on, a silent one as a bar with `N.C.` and no hand lines. A chord quality the table lacks doesn't stop you: write the nearest one, mark any extra chord tone `~`, and record the place under "Gaps" in `notes.md` ("Chords and passing tones" in `references/arranging-rules.md`). After each section, run steps 6 and 7 and fix every flagged finding before writing the next. A score looks like this:
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
7. **Check:** `pianoize check-arrangement '<out>/score.txt' --cover '<cover>' --melody '<melody>'`, leaving out `--melody` without a melody: the vocal-notes report is then skipped, and the check does not verify the tune. The `melody` rule stays: it still flags an `M` note under another right-hand note. It lists the findings by rule, `notes`, `span`, `jump`, `crossing`, `melody` and `harmony`, each line naming its bar, position and hand; the report's last line is `problems: K` or `clean` ("Checking" in the docs). Fix every flagged finding as "Fixing the check" in `references/arranging-rules.md` says, then run steps 6 and 7 again, until it prints `clean` and exits 0. A span marked `(listed, not flagged)` may stay. After the report come the vocal notes the top of the right hand leaves out, `bar N pos P  melody missing  E5 (2)`, and their count: an inner voice under the top doesn't play one. They never stop `clean`, but each is your choice: add it on top of the right hand, usually on `M` in the octave the melody is in there, or record under "Melody left out" in `notes.md` why it stays out.
8. **Compare with the band**, with a source, once the whole score checks clean. Read the dump again a section at a time beside the score, bar by bar, copies and overrides included, and fix what disagrees:
   - each chord's bass against `electric_bass`'s line, where the band holds another bass for a beat or more;
   - each bar where the drums or the band hit, stop, hold their chords or drop out, against what the score plays there;
   - the backing vocal, pulses, riffs and fills `notes.md` records, against what the score took of them.

   Record each change under "Compared with the band" in `notes.md`, then run steps 6 and 7 again until clean.
9. **Render and export:** `pianoize render '<out>/arranged.mid' -o '<out>/arranged.wav'`, adding `--soundfont '<sf2>'` when your prompt names one. If it warns that the peak could clip, render again with a lower `--gain`. Then `pianoize export-arrangement '<out>/arranged.mid' -o '<out>/arranged.json'`, the notes the falling-notes viewer plays with the WAV. Without FluidSynth or a SoundFont, export anyway, and say so in the report.
10. **Report** to the main session, which relays it to the user:
    - the files: `<out>/arranged.wav` (or, without a render, `<out>/arranged.mid`) and `<out>/arranged.json`;
    - the check's last line and the count of vocal notes left out;
    - the places `notes.md` lists as inferred, filled, copied from the cover, copied from an earlier section or changed at step 8, each by bar and time (the dump's header gives a bar's time), and the gaps it records;
    - each regridded span: the user listens to the song there and counts its bars, since `regrid` can take a real tempo change for a hiccup;
    - the repeats a change to a copied-from bar changed (step 5);
    - any question for the user, first.
11. **Revise**, when your task is `revise: <the user's words>`: change the bars they name. For a bar a copy defined, write an override, so the rest of the copy stays as it is. Editing a copied-from bar changes its copies too (step 5). Record each change and the user's reason under "Revisions" in `notes.md`, then run steps 6 and 7 again, step 8 for the bars you changed without undoing what the user asked for, and steps 9 and 10. When your task is `approved: <the user's words>`, record the approval under "Revisions" in `notes.md` and report that you did.

`notes.md` is yours to shape; this outline covers what the steps above need:

```markdown
# <song>: arranging notes
## Regridded spans
- bars 40-43: 5 bars at 120.00; to check by ear
## Sections
- intro: bars 1-4
- verse 2: bars 37-52, copies verse 1 (bars 5-20); overrides 44 and 51
## Chords
- bar 2: 0:C 12:G/B
## Melody
- bar 5, position 2: the verse enters; the cover plays it an octave up
- intro, bars 1-4: the brass riff carries the tune
## The band
- verse: kick 0 and 10, snare 4 and 12; the bass walks into each bar; a synth pulses eighths
- chorus: a backing vocal a third under the lead, taken on `R`
## Melody left out
- bar 30, position 6: E5, a grace note of the transcription the cover doesn't play
## Hits and stops
- bar 12: a hit at 7, then a stop to the end of the bar
- bars 60-63: a breakdown, the drums on the downbeat only, the band holding its chords
## Inferred, filled and copied
- bar 18: the cover drops the chord; G inferred from the bass and the repeat at bar 34
- bar 12: the hit copied from the cover, its strays cleaned
## Compared with the band
- bar 41: the band's bass holds E under the cover's C; written C/E
## Gaps
- bar 30: the song plays a sus2 chord; written as add9
## Revisions
- bar 44: the melody's last note held longer (the user: "it cuts off")
```
