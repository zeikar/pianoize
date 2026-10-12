# Arranging

How pianoize turns an arrangement an agent writes into a two-hand MIDI. An agent session reads a tsumugi-piano-cover MIDI and tsumugi's melody, and writes a per-bar score for two hands into `work/`. pianoize builds the score into MIDI on the cover's tempo grid, every note at one velocity, and checks that it is playable and fits its own chords. The CLI never calls an LLM: the same score and cover give byte-identical MIDI. The reasons are in [docs/decisions.md](decisions.md#m3-an-agent-writes-the-arrangement-2026-10-11).

## Workflow

The [`arrange-cover` skill](#running-the-skill) runs it in these steps. The commands lay out the song and check the score; the agent decides every note.

1. **Dump.** [`dump-bars`](#dumping) prints the cover's attacks and tsumugi's melody bar by bar, on the cover's sixteenth grid.
2. **Read.** The agent reads the dump whole and writes its notes: the sections and their bars, which sections repeat which, a chord per bar, the melody's entries, and the hits and stop-times. The cover's notes and markers are evidence, not truth.
3. **Write, section by section.** The agent writes the [score](#the-score-format) one section at a time, reusing a repeated section with a [copy](#copies-and-overrides).
4. **Build.** [`build-arrangement`](#building) turns the score into a two-hand MIDI on the cover's tempo map.
5. **Check and fix.** [`check-arrangement`](#checking) checks that each hand can play the score and that the accompaniment fits the score's own chords. The agent fixes every flagged finding, after each section and at the end, until the check prints `clean`.
6. **Render.** `pianoize render` ([docs/evaluation.md](evaluation.md#rendering-a-midi-file)) turns the MIDI into a WAV.
7. **Listen.** The agent cannot hear the result, so the user is the last gate. They approve it, or name places; the agent revises those bars, overriding a copied bar where the copy is the cause, and builds, checks and renders again.

## The score format

A score is a UTF-8 text file (a byte order mark is allowed), `score.txt` in the skill. It is read line by line, each line stripped first, so any line may be indented. Blank lines are skipped, and so are comments, lines starting with `#`; a `#` later in a line is no comment (`F#4`).

- **The format line.** The first line that is neither blank nor a comment is `format 1`, the format's version. A score without it, or with another number, is refused: `line 1: expected 'format 1', found 'bar 1 | C'`.
- **Sections.** `== verse` starts a section, and `== chorus | pedal=none` one with a [pedal](#pedal) for its bars. The name is for the reader; the build and the check don't use it.
- **Bars.** `bar N | CHORDS` starts bar N, and `bar N | CHORDS | pedal=MODE` one with its own pedal. The [hand lines](#hand-lines) after it, up to the next bar, section or copy line, belong to it. Bars count from 1 and come in order: each new bar is the one after the last bar defined, by a `bar` line or a [copy](#copies-and-overrides) (`expected bar 5`). A bar without hand lines is a rest.

A score needs at least one bar, and the build and the check need at least one note.

### Chords

One chord fills the bar: `bar 3 | Am`. Several take a position each, in sixteenths from the bar's start and strictly ascending: `bar 3 | 0:Am 8:G/B 12:C`. Each chord holds from its position to the next, and the first also from the bar's start. A bar needs a chord; `N.C.` is no chord. Chords are split at spaces, so a symbol has none inside.

A symbol is a root, a quality, optional tensions and an optional slash bass. The qualities, on root C:

| symbol | chord | semitones above the root | tones on C |
| --- | --- | --- | --- |
| `C` | major | 0 4 7 | C E G |
| `Cm` | minor | 0 3 7 | C Eb G |
| `C7` | dominant seventh | 0 4 7 10 | C E G Bb |
| `CM7` | major seventh | 0 4 7 11 | C E G B |
| `Cm7` | minor seventh | 0 3 7 10 | C Eb G Bb |
| `CmM7` | minor major seventh | 0 3 7 11 | C Eb G B |
| `Cm6` | minor sixth | 0 3 7 9 | C Eb G A |
| `C6` | sixth | 0 4 7 9 | C E G A |
| `Cdim7` | diminished seventh | 0 3 6 9 | C Eb Gb A |
| `Cm7b5` | half-diminished seventh | 0 3 6 10 | C Eb Gb Bb |
| `Csus4` | suspended fourth | 0 5 7 | C F G |
| `C7sus4` | seventh, suspended fourth | 0 5 7 10 | C F G Bb |
| `Cadd9` | added ninth | 0 2 4 7 | C D E G |
| `CM9` | major ninth | 0 2 4 7 11 | C D E G B |
| `Caug` | augmented | 0 4 8 | C E G# |

- **The root** is a letter `A` to `G` with an optional `#` or `b`: `F#m`, `Bb7`, `Ebsus4`. Qualities are case-sensitive: `M7` is the major seventh, `m7` the minor.
- **Tensions** follow the quality in parentheses, separated by commas: `9`, `b9`, `11`, `#11`, `13` and `b13`, 2, 1, 5, 6, 9 and 8 semitones above the root. `C7(9,13)`, `Am7(11)`, `C(b13)`.
- **A slash bass** comes last: `G/B`, `Bbadd9/D`, `Am7(9)/G`.
- **The tones the check accepts** under a chord are its quality's, its tensions and its slash bass. Nothing is checked under `N.C.`.

Any other symbol is refused. An unknown quality's error lists the valid ones: `bar 2: bad chord 'Cmaj7' (qualities: '', m, 7, M7, m7, mM7, m6, 6, dim7, m7b5, sus4, 7sus4, add9, M9, aug)`.

### Pedal

A section's `pedal=` is the default for its bars, and a bar's own `pedal=` sets that bar alone. A section without one keeps the previous section's, and a score starts at `chord`.

| mode | the pedal |
| --- | --- |
| `chord` | lifts at each chord of the bar and goes down again |
| `none` | lifts at the bar's start and stays up through the bar |
| a list, `0,x6,8` | lifts at each position and goes down again, except at a position written with `x`, where it only lifts |

The pedal goes down again 1/16 beat after its lift (see [Building](#building)). List positions are sixteenths, strictly ascending. A bar that doesn't lift at its start keeps the pedal as the bar before left it: after `pedal=0,x8`, a bar with `pedal=4` stays up until 4.

### Hand lines

After a bar line come up to three hand lines, one per role, each at most once a bar:

| role | hand | plays |
| --- | --- | --- |
| `M` | right | the melody |
| `R` | right | the right hand's other notes, under the melody |
| `L` | left | the left hand |

A line is its role and its tokens, separated by spaces: `M 0:E5:4 4:D5~:2 6.5:C5:1.5`. A token is `pos:notes:dur`:

- **`pos`** is where the notes start, in sixteenths from the bar's start: `0` is the downbeat and `4` the second beat in 4/4. A decimal places a note between sixteenths: `6.5` is a thirty-second after `6`. It runs from 0 up to, not including, the bar's length.
- **`notes`** is a note name, or several joined by `+` and struck together: `G4+C5`. A name is a letter, an optional `#` or `b`, and an octave digit. `C4` is middle C (MIDI 60) and `B3` the key below it; `Bb3` and `A#3` are the same key. A trailing `~` marks a passing tone, a note off the chord on purpose: `D5~`, `E4+F4~`.
- **`dur`** is how long the notes sound, in sixteenths, more than zero: `4` is a beat in 4/4 and `1.5` a dotted sixteenth. A duration may run past the bar line: `0:A4:20` in a 4/4 bar sounds on into the next bar.

A position or a duration is digits with an optional decimal point, which a digit must follow: `4`, `6.5` and `.5` are read, while `5.`, a sign and an exponent are refused. A sixteenth is a quarter of the cover's ticks per beat, and each position and duration lands on the nearest tick; a duration that rounds to no tick is refused.

`M` plays one note at a time. The check flags an `M` note below any right-hand note sounding at its onset, a second `M` note included, so an octave doubling of the melody goes under it on `R`. `R` striking the melody's own pitch at the melody's tick strikes one key twice, which the check flags too. `~` matters only on `R` and `L`: the melody is never checked against the chord.

### Copies and overrides

`bars A-B = C-D` defines bars A to B as a copy of bars C to D: each copied bar takes its source's chords, pedal setting and every hand line, moved by A − C bars. A is the next bar to define, the two ranges are as long (`bars 9-9 = 1-1` copies one bar), and the source is defined before A. The copy takes its source as it stands at the copy line, and a copied range can be copied again. The copied bars belong to the section the copy line is in, but keep their source's pedal.

A `bar N` line for a bar a copy defined overrides it. Written anywhere after the copy, it replaces the copied bar whole: chords, pedal and hand lines, so it carries every hand line the bar needs. It keeps the copied bar's section and pedal unless it sets `pedal=` itself. An override changes its bar only: a copy already taken from that bar keeps the bar as it was copied, and a copy written after the override copies the override. Each copied bar can be overridden once; a second `bar N`, or one for a bar no copy defined, is refused (`bar 4 is defined twice`).

### Meter

The score has no meter of its own. The build, the check and the dump take it from the cover's `time_signature`: a bar holds 16 sixteenths in 4/4, and 12 in 3/4 and in 6/8. Positions count sixteenths in every meter. A cover without a time signature is 4/4, the MIDI default, which also holds before a first signature written after tick 0. A cover whose meter changes is refused, naming the tick: `the cover changes meter at tick 92160, 4/4 to 3/4; the score format needs one meter`. So is a cover whose ticks per beat don't divide by 4, or whose bar doesn't hold a whole number of sixteenths.

### Errors

Reading stops at the first error, which names where it is: the bar and the token (`bar 3: token '4:H4:2': bad note 'H4'`), the copy (`bars 9-12: source 1-5 has a different length`), or the line outside any bar (`line 2: M line outside a bar`).

### Example

A made-up phrase, two bars written out, then repeated with a new ending:

```
format 1
# A made-up phrase: two bars, then the same two with a new ending.
== verse | pedal=chord
bar 1 | F
  M 0:A4:4 4:C5:4 8:A4:4 12:G4:4
  R 0:C4+F4:8 8:C4+F4:4
  L 0:F2:12 12:E2~:4
bar 2 | 0:Dm7 8:Bb | pedal=0,x6,8
  M 0:F4:6 8:D5:8
  R 0:A3+C4:6 8:F4:8
  L 0:D2:6 8:Bb1:8
bars 3-4 = 1-2
bar 4 | 0:C7sus4 8:C7 | pedal=chord
  M 0:G4:8 8:E4:8
  R 0:Bb3+C4:8 8:Bb3+C4:8
  L 0:C2+C3:16
```

- Bar 1's bass steps down through `E2~`, a passing tone, to bar 2's D.
- Bar 2 changes chord at its middle and stops short: the notes end at 6 and the pedal lifts there without going down (`x6`), so the bar is silent until the chord at 8.
- Bars 3 and 4 copy bars 1 and 2. Bar 4 is then overridden with a new ending. Its `pedal=chord` replaces the list it would otherwise keep from bar 2.

On a 4/4 cover, `check-arrangement` prints `clean` for it.

## Building

`pianoize build-arrangement SCORE.txt --cover COVER.mid -o OUT.mid` reads the score on the cover's meter and writes it as a type 1 MIDI at the cover's resolution. It prints the notes per hand, the pedal presses and the length, here for the example on a 120 bpm cover:

```
notes: 27 right hand, 8 left hand
pedal presses: 8
length: 8.5 s
```

- **Tracks.** Track 0, `Right Hand`, plays `M` and `R` on channel 0; track 1, `Left Hand`, plays `L` on channel 1. Each starts with its name and program 0, the acoustic grand piano. Track 0 also carries the cover's meter as a `time_signature` and the cover's tempo changes up to the build's end (120 bpm before the cover's first tempo). So the MIDI shares the cover's ticks and tempo map, and bar N of the score sounds where bar N of the cover does.
- **Ticks.** A token at `pos` in bar N starts `pos` sixteenths after the start of bar N and ends `dur` sixteenths later, each rounded to the nearest tick.
- **Velocity.** Every note-on has velocity 88 and every note-off 0. pianoize writes no dynamics, by the user's choice: most piano covers barely vary them ([decision](decisions.md#playable-arrangements)). Loudness is the render's `--gain`.
- **Restrikes.** A pitch struck again in the same hand while its earlier note still sounds cuts that note short, so a falling-notes view draws two notes: it ends 1/32 beat before the new strike, but lasts at least 1/16 beat where the new strike leaves room, and never ends later than written. Two strikes of one pitch in one hand at one tick can't be told apart: the first is cut to 1/16 beat, and the check flags them. The other hand's notes are never cut.
- **The tail.** The build ends one beat after the last note-off. The notes that end last ring on until 1/8 beat before that end, so the arrangement doesn't stop dead. Both tracks end there.
- **The pedal.** The sustain pedal (CC 64, 127 down and 0 up) follows each bar's [pedal mode](#pedal): a lift at each chord, at the bar's start or at each listed position, and a press 1/16 beat after each lift that goes down again. Both tracks carry the same pedal, each on its own channel, since sustain is per channel. A pedal still down at the end comes up at the build's end.
- **The re-press.** Where an attack would ring a semitone or a minor ninth against a note the pedal is holding, one released since the pedal went down, the pedal lifts at that attack and goes down again 1/16 beat later. A note whose key is still down doesn't count: a lift wouldn't stop it.
- **One tick, in order.** At one tick a lift comes first, then note-offs, a press and note-ons. A pitch released and struck at one tick sounds again, and a press doesn't catch the notes released at its tick.
- **Writing.** The file is written through a temporary file beside it that replaces it atomically, so a failed run leaves an existing `OUT.mid` as it was. The same score and cover give byte-identical output.
- **Errors.** An `-o` that is the score or the cover, under any spelling the disk takes for it, is refused with `would overwrite an input` and exits 2. A malformed score fails on its first [error](#errors), naming the bar and the token (`error: SCORE.txt: bar 3: token '4:H4:2': bad note 'H4'`), and exits 1, writing nothing. So do a score without notes (`the score has no notes`), a score not in UTF-8, and a cover the score can't be placed on: a type 2 file, whose tracks share no timeline, or a cover whose [meter](#meter) changes.

## Checking

`pianoize check-arrangement SCORE.txt --cover COVER.mid` checks the notes the build plays: the score read on the cover's meter, with restrikes cut as the build cuts them. It writes no file. The pedal and the tail are left out, so a note lasts from its onset to its end as written. Jumps are timed in seconds on the cover's tempo map. The limits are for an intermediate-to-advanced player ([decision](decisions.md#playable-arrangements)).

A hand's attack is a tick where it strikes a note. A note is held at an attack when it was struck at or before it and is not yet released; a note released at that tick is not held. A key is a pitch, however many notes sound on it.

| rule | flagged | detail |
| --- | --- | --- |
| `notes` | at an attack of one hand, more than 5 keys held in it; or one pitch struck twice in one hand at one tick, such as an `M` note doubled on `R` | `6 held: C4 D4 E4 F4 G4 A4`, `C5 struck twice` |
| `span` | at an attack of one hand, its held keys spanning more than 16 semitones, a major tenth. 15 or 16, wider than a major ninth, is listed, not flagged | `17 semitones, C3 to F4` |
| `jump` | the centre of a hand's attack, halfway between its lowest and highest struck notes, moving from the hand's previous attack by 15 semitones or more in under 0.2 s, by 22 or more in under 0.36 s, or by more than 26 at any speed | `15 semitones in 100 ms` |
| `crossing` | at any attack, the left hand's highest held note at or above the right hand's lowest | `top C4 at or above RH bottom C4` |
| `melody` | an `M` note below the highest right-hand note held at its onset, another `M` note included | `E4 under G4` |
| `harmony` | an `R` or `L` note not marked `~` whose pitch class is not among its [chord](#chords)'s tones at its onset. `M` notes are never checked, and nothing under `N.C.` | `L F3 over C` |

The report groups the findings by rule, in the table's order, each group headed `rule: N (K flagged)` and its findings by time, then hand:

```
span: 1 (0 flagged)
  bar 1 pos 0  LH  span  15 semitones, C3 to D#4 (listed, not flagged)
melody: 1 (1 flagged)
  bar 2 pos 4.5  RH  melody  E5 under G5
harmony: 1 (1 flagged)
  bar 2 pos 0  LH  harmony  L F3 over C
problems: 2
```

A finding's line gives the bar and position of its attack, the hand (`RH` or `LH`), the rule and the detail, two spaces apart. A span listed but not flagged ends `(listed, not flagged)`. Pitches are spelled with sharps. The last line is `problems: K`, counting the flagged findings, or `clean` when none is flagged, so listed spans can still print above `clean`.

The command exits 1 while any finding is flagged, and 0 otherwise. A score or cover it can't read prints `error: …` and exits 1, as `build-arrangement` does; a missing file or a bad option exits 2.

## Dumping

`pianoize dump-bars COVER.mid --melody MELODY.mid [--bars A-B]` prints the cover and the melody bar by bar, three lines a bar, for the agent to arrange from. Two bars of a made-up cover:

```
=== bar 1  0:00.00  0:F
C 0:F2(16,70),C4(8,62),F4(8,64),A5(4,90)  4:C6(4,92)  8:A5(4,88)  12:G5(0,38),G5(4,86)
V 0:A4(4)  4:C5(4)  8:A4(3.5)  12:G4(3.5)
=== bar 2  0:02.00  0:F
C 0:D2(8,72),A3(6,66),C4(6,68),F4(6,64),F5(6,94)  7:A#1(1,110),A#2(1,108),D4(1,112),F4(1,110),A#4(1,114),D5(1,112)
V 0:F4(6)  12:D4(2)  14:F4(2)
```

- **The header** is `=== bar N`, the bar's start as `m:ss.ss` on the cover's tempo map, and each marker starting in the bar as `pos:text`, two spaces apart. Markers are the cover's `marker` messages, tsumugi's chord guesses, with each run of spaces and line breaks read as one space. `text` and `lyrics` messages, which can carry the song's words, are never read, in either file.
- **`C`** lists the cover's attacks, two spaces apart: the notes whose onsets round to one position, by pitch, each as `name(duration,velocity)`. Notes come from every track, drums left out.
- **`V`** lists the notes of `--melody`, tsumugi's melody, by onset, each as `pos:name(duration)`. They are placed by their seconds on the cover's tempo map, so a melody at another resolution lands on the cover's bars.
- **Positions and durations** are in sixteenths. Every tick, onsets and ends alike, is rounded to the nearest half-sixteenth, a tie going later, before its bar and position are taken. So an onset up to a quarter of a sixteenth before a bar line prints at `0:` of the bar it anticipates, and a duration is the distance between its rounded ends: `(0)` is a sliver whose start and end round to the same half-sixteenth, less than half a sixteenth long.
- **Pitches** are spelled with sharps: B♭ reads `A#`. `C4` is middle C.
- **The bars** run from 1 to the cover's last, a partial last bar counted whole, or past it to the last bar a cover note, a melody note or a marker rounds into. A bar with nothing in it still prints, with empty `C` and `V` lines.
- **`--bars A-B`** prints bars A to B, both included. A range not written `A-B`, starting below 1 or running backwards exits 2; one past the last bar prints what exists of it, which can be nothing.

A cover whose [meter](#meter) changes, or a type 2 cover, prints `error: …` and exits 1.

## Running the skill

The `arrange-cover` skill in `skills/arrange-cover/` runs the [workflow](#workflow) above: its `SKILL.md` gives the steps and the files, and `references/` the judgment it draws on, the arranging rules and how to read the dump. It ships in the same Claude Code plugin as `polish-cover`; the plugin's layout and how to install it are in [docs/polishing.md](polishing.md#running-the-skill).
