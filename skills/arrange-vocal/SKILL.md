---
name: arrange-vocal
description: This skill should be used when the user wants a two-hand piano arrangement of a sung song written with pianoize from tsumugi's transcription of the band and its melody, without tsumugi-piano-cover's cover. It is the default for a sung song, e.g. "arrange this song for two hands", "arrange this song", "write the piano arrangement", "make a Synthesia arrangement of this song", "revise bars 30 to 34 of the arrangement". Its arranger subagent writes a per-bar score, a right hand for listening, the melody on top with the backing vocal and the band piano's line under it, over a left hand written as a pianist's accompaniment that one hand can play; the local pianoize CLI builds it, checks it, lists the left-hand notes the band doesn't back and renders it for the user to approve by ear. For an instrumental, a song with no sung melody, use arrange-transcription, and for a sung song too when the user asks for one both hands can play or a full one, the band's layers in both hands; for the cover's arrangement, when the user asks for it, use arrange-cover. Not for preparing a song's inputs (that is prepare-song), for polishing a cover (that is polish-cover), or for rendering the falling-notes video.
---

# Arrange a sung song for two hands from its band transcription and melody

pianoize arranges a song for a falling-notes video (Synthesia style). This path, for a sung song, starts from tsumugi's transcription of the whole band, `source.mid`, with a track per instrument, a tempo map and chord markers, and from tsumugi's transcription of the sung melody. The band is read bar by bar and arranged in a score: a right hand written for listening, the melody on top with the backing vocal and the band piano's line under it, over a left hand written as a pianist's accompaniment that one hand can play. pianoize builds the score into MIDI on a tempo grid it makes from the transcription, checks it, and lists the left-hand notes the band doesn't back.

It is the default for a sung song because, beside the cover's arrangement, whose left hand the user preferred, and the transcription's full one, whose right hand the user preferred, that right hand over a pianist's left hand won outright. tsumugi-piano-cover's weights are CC BY-NC 4.0, and the transcriber's code and weights are MIT, so this arrangement, which never touches the cover, carries no such terms. `arrange-cover` runs when the user asks for the cover's arrangement.

**The arranging runs in a subagent, `pianoize:arranger`.** It reads the long dump, writes the score and loops the build and the check in its own context, following the rule files its prompt names. You, the main session, gather the inputs, dispatch it, relay its report to the user and the user's answers back to it. Don't read the dump or write the score yourself: that is what keeps your context free for the user.

## Rules

- **Clean room.** The only inputs are tsumugi's transcription and tsumugi's melody MIDI. Never give the arranger tsumugi-piano-cover's cover MIDI or anything made from it, a polished cover, a refined timeline, or an `arrange-cover` or `polish-cover` run's files. If the user offers one, decline it and say why: it would bring the cover's notes, and its terms, into an arrangement that must have neither.

## Inputs

Ask the user for any input that is missing and stop until you have it. The `prepare-song` skill (`../prepare-song/SKILL.md`) makes them, `pianoize prepare` writing `source.mid` and `melody.mid` into the song's directory; when they are missing, offer that skill and stop.

- `<source>`: tsumugi's transcription of the whole band, `source.mid`: a track per instrument, the drums among them, a tempo map and chord markers.
- `<melody>`: tsumugi's melody MIDI, the transcriber's lead vocal track. A sung song has one, so ask for it. Where `prepare` printed `melody.mid: none`, tsumugi heard no lead vocal: the song is an instrumental, so offer `arrange-transcription` (`../arrange-transcription/SKILL.md`) and stop.
- `<out>`: an output directory under `work/` of its own, named by the user (`work/<song>-vocal/`). If it holds `cover.regrid.mid` or an `arrange-cover` or `polish-cover` run's files, ask for another.
- For the render at the end: FluidSynth on `PATH` and a piano SoundFont, `<sf2>`, unless `$PIANOIZE_SOUNDFONT` names one. Without either, the arranger exports anyway and gives the MIDI in place of the WAV.

## The command line

**Plugin root:** `${CLAUDE_PLUGIN_ROOT}`. Read **`../../arranging/main-session.md`** and follow it: from this plugin root it settles the command line and `<root>`, and it gives the rules and the steps that dispatch the arranger with the prompt below.

## The combination

One front end and one file per hand, with no mode.

Dispatch the arranger with this prompt:
```
Skill: arrange-vocal
Workflow: <root>/arranging/workflow.md
Front end: <root>/arranging/front-end-transcription.md
Right hand: <root>/arranging/right-hand-full.md
Left hand: <root>/arranging/left-hand-accompaniment.md
Command line: <the command line>
Docs: <the docs directory>
Source: '<source>'
Melody: '<melody>'
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
- **`../../arranging/right-hand-full.md` and `../../arranging/left-hand-accompaniment.md`:** the hands: the right for listening, the melody on top and the band's parts in its register under it; the left as a pianist's accompaniment, within the check's limits.
- **pianoize's `agents/arranger.md` and `docs/arranging.md`:** the subagent's definition, its tools limited to the shell and the files; the score format, every command, the check's limits and the output formats.
