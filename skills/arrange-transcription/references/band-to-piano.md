# Arranging the band for piano

How to turn a band's transcription into a two-hand piano part: reading the rhythm section, writing the left hand as a pianist's accompaniment, choosing its density, and the right hand with the melody. SKILL.md gives the commands and the files; this file gives the judgment. It goes with `arrange-cover`'s two references, `../arrange-cover/references/reading-the-dump.md` and `../arrange-cover/references/arranging-rules.md` (paths from this skill's directory, as in SKILL.md), and replaces what they take from a cover.

A piano cover already has a pianistic accompaniment, and `arrange-cover` keeps its feel. A band transcription has none: a bass line, a drum kit, strummed guitars and a keyboard part, each written for its own player. So you arrange the band for piano: you decide what each hand plays from what the band plays, rather than copying any one part.

## Reading the rhythm section

- **The `D` line** groups the drums' hits: `kick`, `snare`, `hihat`, `cymbal` and `other`, each with its positions in sixteenths, as in `D kick 0 6 10  snare 4 12  hihat 0 2 4 6 8 10 12 14  cymbal 0`. A group that doesn't play in the bar is left out; a bar without drums prints `D ` alone.
- **The kick is where the bass is struck.** Bass and kick lock together, so the kick's positions are where the left hand's bass falls.
- **The snare is the backbeat**, mostly `4` and `12` in 4/4.
- **The hi-hat's rate is the pulse**, eighths or sixteenths. It sets how fast the section moves, not what the left hand strikes.
- **A crash**, in `cymbal`, marks a hit or the start of a section.
- **`other`**, the toms among it, is mostly fills, at the end of a phrase or into the next section.
- **A change of pattern is a change of section.** A new kick pattern, or half-time, where the snare moves from `4 12` to `8` alone, starts a section, even where the chords go on as before.
- **Bars without drums are a change of texture**, an intro or a breakdown, not a stop. The accompaniment there comes from the strums, the band piano's figure in `C`, or the bass. A stop is only where `C` and the `I` lines show no attack and no note held through it, as "A stop" in `reading-the-dump.md`'s "Hits, stops and syncopation" reads the durations.
- **The strums** are the guitars' `I` lines: their positions are the strum pattern, and their top note is the top of a voicing, not a tune.
- **The bass line** is `electric_bass`'s `I` line: its notes are the roots and the steps between them. Check your chords against it.
- **Runs of `.5`.** Where a whole track prints half a sixteenth early, bar after bar, at `3.5`, `7.5` and `11.5` while the drums play `4`, `8` and `12`, that is the transcription's offset for the track, not the band pushing. Write it on the sixteenth where the drums are. Its downbeat notes then print at `15.5` of the bar before, and belong to `0` of the next. A real push is the band together ahead of the beat, the kick or a crash with it, and comes back in the section's repeats.

## The left hand is a pianist's accompaniment

- **Its pitches come from the harmony and the bass line**: the chord you decided for the bar and the notes `electric_bass` plays, not the band piano's voicings or the guitars' top notes copied.
- **The bass is the lowest voice, with its motion kept.** Where the bass steps or walks to the next root, the left hand's lowest note moves with it; mark a passing step `~`.
- **The chord sits close above the bass, inside a ninth**, so the hand holds it without stretching and its move to the next chord passes the jump rule ("Jumps take time", under "The hands" in `arranging-rules.md`). Voice each chord near the one before.
- **Where the drums play, start from the main kicks and the backbeat, not every hit.** The bass where the kick marks the pattern's strong positions, a chord where the snare plays the backbeat. The hi-hat, the ghost kicks and every strum are the band's texture, which a pianist doesn't play.

## One figure per section

Choose each section's left-hand figure from its drum and strum pattern, name it under "Left-hand figures" in `notes.md`, and keep it through the section ("One pattern per section" in `arranging-rules.md`). Vary it only where the band does: a fill, a hit, the last bar into the next section. A few generic figures:

- **The bass on the kick, a chord on the backbeat**, for a steady beat.
- **A root-fifth-octave roll** where there are no drums: an intro, a breakdown, a ballad's verse.
- **Octaves on the beat** for a driving section.
- **Hits and silence** for stop-time: the left hand strikes with the band's hits and rests between them, the pedal lifted.

## Density

How much the left hand plays is the open question of this path. What the first trial taught:

- **A bass line alone sounds like a bass part, not a piano.** Single notes following `electric_bass` leave the left hand too sparse: give it the harmony too.
- **Striking on every kick, snare and strum is too busy.** A pianist does not play the kit.
- **In between is not settled yet.** The bass on the main kicks, with chords on the backbeat left to ring, was still not settled at the first trial's listening. So expect the user to set each section's density at the listening, and write every section's figure so it can be thinned or filled as a whole, not bar by bar: one figure, named under "Left-hand figures" in `notes.md` and written the same way in every bar of the section, so that its entry changes first and then every `L` line of the section to match.
- **A verse is thinner than a chorus.** Every note has one velocity, so weight comes from how many notes sound and how low: fewer attacks and smaller chords in a verse, fuller chords or octaves in a chorus.

## The right hand

### The melody

This replaces the clauses of `arrange-cover`'s references that read the melody off a cover: "Note the octave", "Where `V` and the cover disagree on a pitch" and the cover's top line in "Where `V` is silent", under "The melody" in `reading-the-dump.md`; "Write it an octave up where the cover plays it there", under "The hands" in `arranging-rules.md`; and "Without a source", under its "Where no one sings".

- **The melody is `V` alone**, kept to one voice as `check-arrangement --melody` keeps it: of notes sung together the highest, each ending where the next begins. Skip its strays as "Skip the strays" in `reading-the-dump.md` says.
- **Choose its octave to fit the hands**, not off a cover. The melody stays the top right-hand note and above the left hand, so a vocal that sits in the accompaniment's register goes up an octave. Choose one octave per section and record it under "Melody" in `notes.md`.
- **Without a melody** every `V` line is empty. The tune is the `I` line that carries it, chosen per section from the dump's instrument lines and recorded under "Melody" in `notes.md`, with its octave.
- **Where `V` is wrong or silent** while someone surely sings, check it against `vocal_harmony`'s `I` line, an instrument doubling the tune, and the section's repeats. `I melody` is `V`'s own track, so it can't confirm `V`. Write what the others agree on, and record the choice.

### Tunes, stabs and hits

- **Where no one sings**, the right hand takes the tune from the `I` lines, as "Where no one sings" in `arranging-rules.md` says, except its "The left hand still comes from the cover": the left hand there comes from this file.
- **The band piano's stabs and pushes**, from `C`: chord tones under the melody where the band piano strikes short, or ahead of the bar line, a push written as "Keep the feel" in `arranging-rules.md` says.
- **A hit** is where the crash and the instruments strike together, written as "Keep the feel" says.
