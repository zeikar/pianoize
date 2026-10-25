---
name: arrange-cover
description: This skill should be used when the user wants a two-hand piano arrangement of a song written with pianoize from a tsumugi-piano-cover MIDI and, where the song has one, tsumugi's melody MIDI and its transcription of the band, e.g. "arrange this song for two hands", "write the piano arrangement from the cover and the melody", "make a Synthesia arrangement of this cover", "build and check my score", "revise bars 30 to 34 of the arrangement". Gathers the inputs and dispatches pianoize's arranger subagent, which dumps the cover, the melody and the band bar by bar, writes a per-bar two-hand score that keeps the original's groove, its signature hits and the band parts the cover leaves out, has the local pianoize CLI build it into MIDI and check that it is playable (or in full mode, for listening, its tune and harmony), and renders it; relays its report, and the user's answers back to it, and leaves the final listening to the user. It is the default for a sung song. For an instrumental, a song with no sung melody, use arrange-transcription unless the user asks for the cover. Not for making a cover, a transcription or a melody from audio, for polishing the cover note by note (that is polish-cover), or for rendering the falling-notes video.
---

# Arrange a song for two hands from its piano cover and melody

pianoize arranges a song for a falling-notes video (Synthesia style) from the piano cover tsumugi-piano-cover made of it, and tsumugi's transcription of its sung melody, where the song has one. tsumugi's transcription of the whole band, with a track per instrument, is read under the cover in every bar where there is one: its bass, its drums, a backing vocal and the parts the cover leaves out make the arrangement richer and keep its chords and stops honest. A score for two hands is written bar by bar; pianoize builds it into MIDI on the cover's tempo grid and checks that it fits the score's chords and, unless it is a full arrangement, that it is playable.

**The arranging runs in a subagent, `pianoize:arranger`.** It reads the long dump, writes the score and loops the build and the check in its own context, following the rule files its prompt names. You, the main session, gather the inputs, dispatch it, relay its report to the user and the user's answers back to it. Don't read the dump or write the score yourself: that is what keeps your context free for the user.

## Inputs

Ask the user for any input that is missing and stop until you have it. The `prepare-song` skill (`../prepare-song/SKILL.md`) makes them, `pianoize prepare` writing `cover.mid`, `melody.mid` (where the song has one) and `source.mid` into the song's directory; when they are missing, offer that skill and stop.

- `<cover>`: the cover MIDI made by tsumugi-piano-cover.
- `<melody>`, optional: tsumugi's melody MIDI, its lead vocal track. An instrumental has none, unless `prepare --melody-track` named an instrument's track. Without one, the tune is found in the band's instrument lines (offer `<source>` if you don't have it) or in the cover's top line.
- `<source>`, optional but asked for: tsumugi's transcription of the whole band, `source.mid`, a track per instrument. Ask for it once; without it, the arrangement is written from the cover and the melody alone.
- `<out>`: an output directory under `work/`, named by the user (`work/<song>/`).
- `<mode>`: `playable`, the default, both hands within the check's limits; or `full`, when the user asks for every band part over what two hands can play. A full arrangement is for listening: no limits on the hands, every band part the score holds clearly. It needs `<source>`: without one, ask for it, or write a playable one and tell the user why.
- For the render at the end: FluidSynth on `PATH` and a piano SoundFont, `<sf2>`, unless `$PIANOIZE_SOUNDFONT` names one. Without either, the arranger exports anyway and gives the MIDI in place of the WAV.

## The command line

**Plugin root:** `${CLAUDE_PLUGIN_ROOT}`. Read **`../../arranging/main-session.md`** and follow it: from this plugin root it settles the command line and `<root>`, and it gives the rules and the steps that dispatch the arranger with the prompt below.

## Modes

| `<mode>` | `Right hand:` | `Left hand:` |
| --- | --- | --- |
| `playable`, the default | `<root>/arranging/right-hand-playable.md` | `<root>/arranging/left-hand-cover.md` |
| `full` | `<root>/arranging/right-hand-full.md` | `<root>/arranging/left-hand-band-layers.md` |

Dispatch the arranger with this prompt, its `Right hand:` and `Left hand:` lines from the mode's row:
```
Skill: arrange-cover
Workflow: <root>/arranging/workflow.md
Front end: <root>/arranging/front-end-cover.md
Right hand: <the mode's right hand above>
Left hand: <the mode's left hand above>
Command line: <the command line>
Docs: <the docs directory>
Cover: '<cover>'
Melody: '<melody>' (or: none)
Source: '<source>' (or: none)
Out: '<out>'
SoundFont: '<sf2>' (or: $PIANOIZE_SOUNDFONT, or: none)
Task: arrange
```

## Output files

All in `<out>`. The front end adds this one; the rest are under "Output files" in `../../arranging/main-session.md`.

| file | written by | holds |
| --- | --- | --- |
| `cover.regrid.mid` | `regrid` | the cover with its tempo hiccups regridded, used as the cover |

## Additional resources

- **`../../arranging/main-session.md` and `../../arranging/workflow.md`:** the two sides. Yours: the command line, the rules, the steps from dispatch to approval, and the output files. The arranger's: its rules, commands, steps, `notes.md` outline and report, and the rule files it reads beside it, how to read the dump and the arranging rules every arrangement shares.
- **`../../arranging/front-end-cover.md`:** the cover regridded, how to read `C` and the melody off it, copying the cover, and the comparison with the band.
- **`../../arranging/right-hand-playable.md`, `../../arranging/left-hand-cover.md`, `../../arranging/right-hand-full.md` and `../../arranging/left-hand-band-layers.md`:** the hands, paired as "Modes" pairs them: a playable arrangement's within the check's limits, the left from the cover; a full one's for listening, the band's parts layer by layer.
- **pianoize's `agents/arranger.md` and `docs/arranging.md`:** the subagent's definition, its tools limited to the shell and the files; the score format, every command, the check's limits and the output formats.
