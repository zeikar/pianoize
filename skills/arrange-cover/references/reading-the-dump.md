# Reading the dump

How to read `<out>/bars.txt`, the dump `pianoize dump-bars` writes, and turn it into `notes.md`: the sections, a chord per bar, the melody, the hits and the stops, and with a source the band under the cover. The workflow gives the commands and the files; this file gives the reading. The dump's format is in pianoize's `docs/arranging.md`, under "Dumping".

The dump is your only view of the song. It is models' transcriptions, the cover, the melody and, with a source, the band's instruments, and each is wrong in places. Read what the notes agree on, and check every guess against the song's repeats.

## The lines

Four made-up bars, dumped with a source, `--every-bar` and `--drums`:

```
=== bar 1  0:00.00  0:F
C 0:F2(16,70),C4(8,62),F4(8,64),A5(4,90)  4:C6(4,92)  8:A5(4,88)  12:G5(0,38),G5(4,86)
V 0:A4(4)  4:C5(4)  8:A4(3.5)  12:G4(3.5)
D kick 0 8  snare 4 12  hihat 0 2 4 6 8 10 12 14  cymbal 0
I vocal_harmony  0:F4(4)  4:A4(4)  8:F4(3.5)  12:E4(3.5)
I strings  0:C5(16)
I electric_bass  0:F2(8)  8:F2(6)  14:E2(2)
=== bar 2  0:02.00  0:F
C 0:D2(8,72),A3(6,66),C4(6,68),F4(6,64),F5(6,94)  7:A#1(1,110),A#2(1,108),D4(1,112),F4(1,110),A#4(1,114),D5(1,112)
V 0:F4(6)  12:D4(2)  14:F4(2)
D kick 0 7  snare 7  cymbal 7
I strings  0:C5(6)  7:D5(1)
I electric_bass  0:D2(6)  7:A#1(1)
=== bar 3  0:04.00  0:Bb
C 0:A#1(15.5,70),F3(3.5,60),A#3(3.5,60),D4(3.5,60),D6(8,92)  4:F3(3.5,60),A#3(3.5,60),D4(3.5,60)  8:F3(3.5,60),A#3(3.5,60),D4(3.5,60),C6(7.5,90)  12:F3(3.5,60),A#3(3.5,60),D4(3.5,60)
V 0:D5(8)  8:C5(0)  8:C5(7)
D kick 0
I synth_lead  0:F5(0.5)  2:F5(0.5)  4:F5(0.5)  6:F5(0.5)  8:F5(0.5)  10:F5(0.5)  12:F5(0.5)  14:F5(0.5)
I electric_bass  0:A#1(16)
=== bar 4  0:06.00  0:Bb
C 0:A#1(6,72),F3(2,64),A#3(2,64),D4(2,64),D5(2,90)  2:F5(2,86)  4:A#5(2,84)  6:A#1(2,70),A5(2,82)  8:F2(8,70),A3(8,60),C4(8,60),F4(8,60),C6(8,88)
V
D kick 0 6 8  snare 4 12  hihat 0 2 4 6 8 10 12 14  other 14
I brass  0:D5(2)  2:F5(2)  4:A#5(2)  6:A5(2)  8:C6(8)
I strings  0:D4(8)  8:C4(8)
I electric_bass  0:A#1(6)  6:A#1(2)  8:F2(8)
```

- **The header:** the bar's number, the time it starts (`m:ss.ss`, which the user can find in the song) and the cover's chord markers, each at its position (`0:F`).
- **`C`:** the cover's attacks. Each is a position, then the notes struck there, lowest first, each as `name(duration,velocity)`.
- **`V`:** the melody, one note at a time, each as `position:name(duration)`.
- **`D`:** with `--drums`, the drums' hits in the bar, grouped as `kick`, `snare`, `hihat`, `cymbal` and `other`, each with its positions; a bar without drums prints `D ` alone. "The drums" below reads them.
- **`I`:** only with a source, in every bar with `--every-bar`, sung bars included, and without it only in a bar whose `V` line is empty: one line per instrument of tsumugi's transcription that strikes a note in the bar, named as tsumugi names its tracks (`brass`, `flute_pipe`, `distorted_guitar`, `electric_bass`), then its top line, the highest note of each attack, as `position:name(duration)`; with `--every-note`, each attack's every note, lowest first, comma-separated, as `0:C4(8),G4(8)`. A note held into the bar from the one before prints only in the bar it was struck in.

Pitches are spelled with sharps: `A#1` is the B♭ you write `Bb1` in the score. `C4` is middle C.

## Positions and decimals

- Positions and durations count sixteenths. In 4/4 the beats fall on `0`, `4`, `8` and `12`, the off-beat eighths on `2`, `6`, `10` and `14`, and the odd numbers are the sixteenths between. In 3/4 the beats are `0`, `4` and `8`; in 6/8 the two dotted beats are `0` and `6`.
- Everything is rounded to the nearest half-sixteenth, so `.5` is the finest step. A lone `.5` among whole positions is a loose onset, halfway between two sixteenths: write it on the one the same figure uses in the bars around it or in its repeats. Three onsets a beat at `0`, `1.5` and `2.5` (then `4`, `5.5`, `6.5` and on) are eighth-note triplets, which the rounding has bent: write them at `0`, `1.333` and `2.667`, each `1.333` long.
- An onset played a hair before a bar line already prints at `0:` of the bar it anticipates. A real anticipation, a push, prints late in the bar before (`14:` or `15:`) and holds over the bar line.
- `(0)` is a sliver, under half a sixteenth long: almost always a stray of the transcription.

## Markers are a model's guesses

The markers are the chords a model predicted, and the cover was generated from those predictions, so its notes often follow a wrong marker too. A marker and the cover agreeing is one reading, not two. Decide each chord from the notes, and treat the marker as a hint.

The guesses go wrong in known ways. A minor seventh is read as the major chord on its third, and a minor chord over its third as the major chord on that bass: bar 2's marker says `F`, while its bass is D under A, C and F, which is `Dm7`. An augmented chord is read as major. A long melody note pulls the guess toward a chord built on it. A marker can also come a beat early or late: it prints where the model put it.

## Finding the chord

- **The bass decides first.** The lowest note of the bar's first attack, held long, is the root or the slash bass: bar 1's `F2(16,70)` and bar 3's `A#1(15.5,70)`. With a source, the band's own bass, `electric_bass`'s `I` line, outranks the cover's lowest note: where it holds another note for a beat or more, the chord sits over that bass, unless it is a blip, one short note the section's repeats don't have. A step between two roots, like bar 1's `14:E2` into bar 2's D, is a passing bass: mark it `~` in `L`.
- **Then the long notes above it.** Notes held a beat or more in the middle register are the chord: bar 1's `C4` and `F4` over `F2` make F. Short high notes are the melody and its ornaments.
- **Leave the melody out.** The `V` notes, and the cover's top line where it doubles them, pass through notes outside the chord.
- **A bass that moves inside the bar moves the chord.** Write the chord at the position the bass changes, or as a slash chord over a passing bass (`C/E`).
- **When a bar is unclear**, read the same bar in a repeat of its section: a chorus played three times usually shows the chord plainly in one of them.

## Hits, stops and syncopation

- **A hit** is an attack with many notes, low and high at once, louder than the bars around it, and short: bar 2's attack at `7`, six notes at velocities 108 to 114 against 60 to 94 in the bars around it, each one sixteenth long. Hits often fall off the beat.
- **A stop** is a stretch with no `C` attack and no note held through it, often right after a hit, while `V` goes on: bar 2 from 8 to the end, where the melody sings `12:D4` and `14:F4` alone. Check the durations: a gap without attacks is no stop when the notes before it are still sounding.
- **Syncopation** is a run of the bass and the chords on off-beats (`2`, `6`, `10`, `14`, or odd sixteenths), or a chord at `14` that changes the harmony before the next bar.
- **Density** shows the texture: compare how many attacks each bar has. A bar suddenly thinner or busier than its neighbours is a break, a fill or a hit.

Velocity only helps you find these moments. The arrangement has a single velocity, so a hit is written with its notes and its timing ("One velocity" in `arranging-rules.md`).

## The drums

With `--drums`, the `D` line shows the kit. It is the plainest view of the song's form and of its stops.

- **The groups:** `kick`, `snare`, `hihat`, `cymbal` and `other`, each with its positions in sixteenths, as bar 1's `D kick 0 8  snare 4 12  hihat 0 2 4 6 8 10 12 14  cymbal 0`. A group that doesn't play in the bar is left out; a bar without drums prints `D ` alone.
- **The kick is where the bass is struck.** Bass and kick lock together, so the kick's positions are where the left hand's bass falls.
- **The snare is the backbeat**, mostly `4` and `12` in 4/4.
- **The hi-hat's rate is the pulse**, eighths or sixteenths. It sets how fast the section moves, not what the left hand strikes.
- **A crash**, in `cymbal`, marks a hit, as bar 2's at `7`, or the start of a section, as bar 1's at `0`.
- **`other`**, the toms among it, is mostly fills, at the end of a phrase or into the next section, as bar 4's at `14`.
- **A change of pattern is a change of section.** A new kick pattern, or half-time, where the snare moves from `4 12` to `8` alone, starts a section, even where the chords go on as before.
- **A breakdown** is the kit thinned to a kick on the downbeat, or dropped, while the band holds its chords, as in bar 3. The arrangement thins with it: it holds its chords, or keeps only the figure the band keeps going there, such as bar 3's pulse.
- **Bars without drums are a change of texture**, an intro or a breakdown, not a stop. A stop is only where `C` and the `I` lines show no attack and no note held through it, as "A stop" above reads the durations: bar 2 after its hit.
- **The strums** are the guitars' `I` lines: their positions are the strum pattern, and their top note is the top of a voicing, not a tune.
- **Runs of `.5`.** Where a whole track, or the cover, prints half a sixteenth early, bar after bar, at `3.5`, `7.5` and `11.5` while the drums play `4`, `8` and `12`, that is the transcription's offset for the track, not the band pushing. Write it on the sixteenth where the drums are. Its downbeat notes then print at `15.5` of the bar before, and belong to `0` of the next. A real push is the band together ahead of the beat, the kick or a crash with it, and comes back in the section's repeats.

## The melody

- **Skip the strays.** A `(0)` sliver, like bar 3's `8:C5(0)` before `8:C5(7)`, a quick re-strike of the pitch just sung, and a blip far from the line around it are transcription noise.
- **Note the octave.** Compare `V` with the cover's top notes at the same positions. The cover often plays the melody an octave up, as in bars 1 to 3 (`V 0:A4(4)` against `A5(4,90)` in `C`). Write it where the cover plays it, which keeps the right hand above the accompaniment.
- **A dump without a melody** (an instrumental, dumped without `--melody`) has every `V` line empty: it is "Where `V` is silent" in every bar, and each bar has its `I` lines. Record the instrument that carries the tune per section.
- **Where `V` is silent**, an instrument usually carries the tune: find it in the `I` lines ("The instrument lines" below), or, without a source, in the cover's top line. Where all of them are silent and the song surely isn't, record the gap in `notes.md`.
- **Where `V` and the cover disagree on a pitch,** prefer the one that fits the chord and the phrase's repeats, and record the choice.

## The instrument lines

Where no one sings, in an intro, an interlude, a bridge or an ending, the tune moves to an instrument. The cover mashes the whole band into one piano part, so its top note there is often an accompaniment voice or two lines blended; the `I` lines keep each instrument apart. With `--every-bar` they print in every bar, so they also show what the band plays under the voice, which the cover often leaves out.

- **Find the line that carries the tune**: a riff or a lead with a shape of its own, in a register above the chords, that comes back when the section repeats. In bar 4, `brass` climbs `D5 F5 A#5`, falls to `A5` and lands on `C6`, and the cover's top line follows it: that is the hook. Note which instrument carries each section in `notes.md`.
- **Chords and the bass:** `strings`, `piano` and a strummed guitar mostly play chords, so their top line is the top of a voicing, not a tune (`--every-note` prints the whole voicing). `electric_bass` is the bass line: check your chord's bass against it ("Finding the chord").
- **A backing vocal**, `vocal_harmony`, mostly sings a second line with the lead, a third or a sixth from it, as bar 1's `F4 A4 F4 E4` under `A4 C5 A4 G4`: the right hand's inner voice under the melody ("Take from the band" in `arranging-rules.md`). Where the lead is silent, take it as a tune only where it is one.
- **They are transcriptions too.** A line can drop notes, split a held note, add a stray or jump an octave. Read it against the section's repeats and the cover, as you read `V`.
- **Under the voice**, the band often plays something worth keeping that the cover leaves out: a fill between two vocal phrases, a riff under the singing, a countermelody, or a pulse, a synth or strings repeating a chord tone in eighths, as bar 3's `synth_lead`. Record each per section under "The band" in `notes.md`. A fill where `V` rests can go on top of the right hand; under a sung note, the melody stays on top.

## Reading a long dump

A full song is 150 to 200 bars, three lines each, and with a source a `D` line and up to a dozen `I` lines more. Read it in passes:

1. **The headers.** Skim the bar times, the markers and the `D` lines for the section boundaries: where a chord pattern starts again, where the drums crash, change pattern or drop out, where the melody enters after a gap.
2. **The sections.** Most sections span 4, 8 or 16 bars. Name each with its bars in `notes.md`, and mark which later ones repeat which: the same markers, the same bass, the same melody.
3. **One section at a time.** Read each closely, as `pianoize dump-bars '<cover>' --melody '<melody>' --source '<source>' --every-bar --drums --bars 21-36` prints it (leaving out `--source '<source>' --every-bar --drums` without a source, and `--melody '<melody>'` without a melody), and write its chords, hits, stops, band and melody entries into `notes.md` before scoring it.
4. **The repeats.** Compare each repeat with its first appearance bar by bar. A changed melody line, an added hit, a different last bar, a dropped bar, or drums and a band that drop out, hold or change figure is an override, or a sign the repeat is not one. The cover model varies its own notes between repeats too; the `D` and `I` lines tell where the band itself changed.
