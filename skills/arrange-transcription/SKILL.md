---
name: arrange-transcription
description: This skill should be used when the user wants a two-hand piano arrangement written with pianoize from tsumugi's transcription of the band alone, without tsumugi-piano-cover's cover. It is the default for an instrumental, a song with no sung melody such as game or film background music, and is used for a sung song when the user asks for it, e.g. "arrange this instrumental", "arrange this game BGM", "arrange this instrumental from the transcription only", "clean-room arrangement of this instrumental", "arrange the band's layers for piano from source.mid", "a playable arrangement of this song", "revise the transcription-only arrangement". Its arranger subagent writes a per-bar score that arranges the band for piano; the local pianoize CLI builds it, checks it (its tune and harmony in a full arrangement, the default, for listening; each hand too in a playable one) and renders it for the user to approve by ear. For a sung song use arrange-vocal, unless the user asks for a full arrangement, the band's layers in both hands (this skill, full), one both hands can play (this skill, playable), or the cover's (arrange-cover). Not for making a transcription or a melody from audio, for polishing a cover (that is polish-cover), or for rendering the falling-notes video.
---

# Arrange a song for two hands from its band transcription

pianoize arranges a song for a falling-notes video (Synthesia style). This path starts from tsumugi's transcription of the whole band, `source.mid`, with a track per instrument, a tempo map and chord markers, and from tsumugi's transcription of the sung melody where the song has one. The band is read bar by bar and arranged for two hands in a score; pianoize builds the score into MIDI on a tempo grid it makes from the transcription, and checks that it fits the score's chords and, in a playable arrangement, that each hand can play it.

tsumugi-piano-cover's weights are CC BY-NC 4.0, so its cover and anything made from it are treated as non-commercial. The transcriber's code and weights are MIT, so an arrangement that never touches the cover carries no such terms. This path is the default for an instrumental, where the user preferred it to an arrangement from the cover. For a sung song `arrange-vocal` is the default, clean-room too: this path's full right hand over a pianist's accompaniment.

**The arranging runs in a subagent, `pianoize:arranger`.** It reads the long dump, writes the score and loops the build and the check in its own context, following the rule files its prompt names. You, the main session, gather the inputs, dispatch it, relay its report to the user and the user's answers back to it. Don't read the dump or write the score yourself: that is what keeps your context free for the user.

## Rules

- **Clean room.** The only inputs are tsumugi's transcription and tsumugi's melody MIDI. Never give the arranger tsumugi-piano-cover's cover MIDI or anything made from it, a polished cover, a refined timeline, or an `arrange-cover` or `polish-cover` run's files. If the user offers one, decline it and say why: it would bring the cover's notes, and its terms, into an arrangement that must have neither.

## Inputs

Ask the user for any input that is missing and stop until you have it. The `prepare-song` skill (`../prepare-song/SKILL.md`) makes them, `pianoize prepare` writing `source.mid` and `melody.mid` (where the song has one) into the song's directory; when they are missing, offer that skill and stop.

- `<source>`: tsumugi's transcription of the whole band, `source.mid`: a track per instrument, the drums among them, a tempo map and chord markers.
- `<melody>`, optional: tsumugi's melody MIDI, the transcriber's lead vocal track. An instrumental has none, unless `prepare --melody-track` named an instrument's track.
- `<out>`: an output directory under `work/` of its own, named by the user (`work/<song>-transcription/`). If it holds `cover.regrid.mid` or an `arrange-cover` or `polish-cover` run's files, ask for another.
- `<mode>`: `full`, the default, for listening: the band's parts layer by layer, no limits on the hands; or `playable`, when the user asks for one both hands can play.
- For the render at the end: FluidSynth on `PATH` and a piano SoundFont, `<sf2>`, unless `$PIANOIZE_SOUNDFONT` names one. Without either, the arranger exports anyway and gives the MIDI in place of the WAV.

## The command line

**Plugin root:** `${CLAUDE_PLUGIN_ROOT}`. Read **`../../arranging/main-session.md`** and follow it: from this plugin root it settles the command line and `<root>`, and it gives the rules and the steps that dispatch the arranger with the prompt below.

## Modes

| `<mode>` | `Right hand:` | `Left hand:` |
| --- | --- | --- |
| `full`, the default | `<root>/arranging/right-hand-full.md` | `<root>/arranging/left-hand-band-layers.md` |
| `playable` | `<root>/arranging/right-hand-playable.md` | `<root>/arranging/left-hand-accompaniment.md` |

Dispatch the arranger with this prompt, its `Right hand:` and `Left hand:` lines from the mode's row:
```
Skill: arrange-transcription
Workflow: <root>/arranging/workflow.md
Front end: <root>/arranging/front-end-transcription.md
Right hand: <the mode's right hand above>
Left hand: <the mode's left hand above>
Command line: <the command line>
Docs: <the docs directory>
Source: '<source>'
Melody: '<melody>' (or: none)
Out: '<out>'
SoundFont: '<sf2>' (or: $PIANOIZE_SOUNDFONT, or: none)
Task: arrange
```

## Output files

All in `<out>`. The front end adds these two; the rest are under "Output files" in `../../arranging/main-session.md`.

| file | written by | holds |
| --- | --- | --- |
| `grid.mid` | `build-grid` | the transcription's tempo map, time signature and chord markers, with its band piano and bass |
| `grid.regrid.mid` | `regrid` | the grid with its tempo hiccups regridded, used as the cover |

## Additional resources

- **`../../arranging/main-session.md` and `../../arranging/workflow.md`:** the two sides. Yours: the command line, the rules, the steps from dispatch to approval, and the output files. The arranger's: its rules, commands, steps, `notes.md` outline and report, and the rule files it reads beside it, how to read the dump and the arranging rules every arrangement shares.
- **`../../arranging/front-end-transcription.md`:** the arranger's clean room, the grid and its regrid, how to read `C` and the melody without a cover.
- **`../../arranging/right-hand-full.md`, `../../arranging/left-hand-band-layers.md`, `../../arranging/right-hand-playable.md` and `../../arranging/left-hand-accompaniment.md`:** the hands, paired as "Modes" pairs them: a full arrangement's for listening, the band's parts layer by layer; a playable one's within the check's limits, the left as a pianist's accompaniment.
- **pianoize's `agents/arranger.md` and `docs/arranging.md`:** the subagent's definition, its tools limited to the shell and the files; the score format, every command, the check's limits and the output formats.
