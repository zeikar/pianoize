---
name: arrange-transcription
description: This experimental skill should be used only when the user asks for a two-hand piano arrangement written with pianoize from tsumugi's transcription of the band alone, without tsumugi-piano-cover's cover, e.g. "arrange from the transcription only", "clean-room arrangement without the cover", "arrange the band for piano from source.mid", "revise the transcription-only arrangement". Gathers the inputs and dispatches pianoize's arranger subagent, which builds a tempo grid from the transcription, dumps the band's piano, bass, drums and instrument lines bar by bar, writes a per-bar two-hand score that arranges the band for piano, has the local pianoize CLI build it into MIDI and check that it is playable, and renders it; relays its report, and the user's answers back to it, and leaves the final listening to the user. Not the default: given a cover MIDI, or without that request, use arrange-cover. Not for making a transcription or a melody from audio, for polishing a cover (that is polish-cover), or for rendering the falling-notes video.
---

# Arrange a song for two hands from its band transcription (experimental)

pianoize arranges a song for a falling-notes video (Synthesia style). This experimental path starts from tsumugi's transcription of the whole band, `source.mid`, with a track per instrument, a tempo map and chord markers, and from tsumugi's transcription of the sung melody where the song has one. The band is read bar by bar and arranged for two hands in a score; pianoize builds the score into MIDI on a tempo grid it makes from the transcription, and checks that it is playable and fits the score's chords.

The path exists for its terms. tsumugi-piano-cover's weights are CC BY-NC 4.0, so its cover and anything made from it are treated as non-commercial. The transcriber's code and weights are MIT, so an arrangement that never touches the cover carries no such terms. `arrange-cover` stays the default: this path's first trial left the left hand unsettled, and the skill is kept to be run again with a newer model or a tuned prompt.

**The arranging runs in a subagent, `pianoize:arranger`.** It reads the long dump, writes the score and loops the build and the check in its own context, following **`references/workflow.md`**. You, the main session, gather the inputs, dispatch it, relay its report to the user and the user's answers back to it. Don't read the dump or write the score yourself: that is what keeps your context free for the user.

## Rules

- **Clean room.** The only inputs are tsumugi's transcription and tsumugi's melody MIDI. Never give the arranger tsumugi-piano-cover's cover MIDI or anything made from it, a polished cover, a refined timeline, or an `arrange-cover` or `polish-cover` run's files. If the user offers one, decline it and say why: it would bring the cover's notes, and its terms, into an arrangement that must have neither.
- **The arranger arranges.** Changes to the score, the notes or the MIDI go through it, revisions included.
- **Never paste song content into the repository.** A song's chords, notes, markers, lyrics and times stay in `work/`, which is never committed: none of it goes into docs, tests, code, commit messages or issues.
- **Nobody can hear it but the user.** Never claim the arrangement sounds right. The user's listening decides.
- **Audio never leaves the machine.** Upload nothing.

## Inputs

Ask the user for any input that is missing and stop until you have it. The `prepare-song` skill (`../prepare-song/SKILL.md`) makes them, `pianoize prepare` writing `source.mid` and `melody.mid` (where the song has one) into the song's directory; when they are missing, offer that skill and stop.

- `<source>`: tsumugi's transcription of the whole band, `source.mid`: a track per instrument, the drums among them, a tempo map and chord markers.
- `<melody>`, optional: tsumugi's melody MIDI, the transcriber's lead vocal track. An instrumental has none, unless `prepare --melody-track` named an instrument's track.
- `<out>`: an output directory under `work/` of its own, named by the user (`work/<song>-transcription/`). If it holds `cover.regrid.mid` or an `arrange-cover` or `polish-cover` run's files, ask for another.
- For the render at the end: FluidSynth on `PATH` and a piano SoundFont, `<sf2>`, unless `$PIANOIZE_SOUNDFONT` names one. Without either, the arranger exports anyway and gives the MIDI in place of the WAV.

## The command line

- **Plugin root:** `${CLAUDE_PLUGIN_ROOT}`. If that is a directory with a `pyproject.toml` in it, this skill runs from the pianoize Claude Code plugin, and that directory is the plugin's own copy of pianoize: the command line is `uv run --project '<plugin root>'` followed by pianoize and its command, run from the current directory, and the docs are in `<plugin root>/docs/`. Otherwise (empty, still a `${…}` placeholder, or no `pyproject.toml` there) there is no plugin root: in a pianoize checkout, it is `uv run` followed by pianoize, run there, with the docs in its `docs/`; anywhere else, tell the user to install the pianoize plugin, and stop.
- Below, `<root>` is the plugin root, or without one, the checkout's root.
- Without `uv` on `PATH` (`command -v uv`), tell the user to install it (https://docs.astral.sh/uv/) and stop.
- The arranger writes score format version 1. If it reports that pianoize expects another version, the skill and pianoize are out of step: tell the user, and stop.

## Workflow

1. **Inputs and tools.** Gather the inputs, check for `uv`, settle the command line, and create `<out>` with `mkdir -p`, single-quoting the path.
2. **Dispatch the arranger** with the Agent tool: `subagent_type` `pianoize:arranger`, a `name` such as `arranger-<song>-transcription` so you can reach it again, and the prompt below. If no `pianoize:arranger` type is available, dispatch a general-purpose agent with the same prompt, its first line `First read <root>/agents/arranger.md and act as it says.` That agent has every tool, so the definition's limit to the shell and the files rests on its instructions there. Tell the user in one line that the arrangement has started and that a full song takes a while, then wait for the arranger to finish: don't poll its files.
   ```
   Skill: arrange-transcription
   Workflow: <root>/skills/arrange-transcription/references/workflow.md
   Command line: <the command line>
   Docs: <the docs directory>
   Source: '<source>'
   Melody: '<melody>' (or: none)
   Out: '<out>'
   SoundFont: '<sf2>' (or: $PIANOIZE_SOUNDFONT, or: none)
   Task: arrange
   ```
3. **Read its report.** If it stopped on an error it can't fix, an input it can't read or a score format pianoize doesn't take, tell the user, and stop. If it asks the user something, ask them, send the answer to the same arranger with SendMessage, and wait again.
4. **Ask the user to listen.** Relay the report in the user's language: the WAV to listen to (or the MIDI, without a render), and that they can watch it fall too, since dropping `arranged.json` and `arranged.wav` on https://zeikar.dev/pianoize/ plays them there, read in the browser and uploaded nowhere; the places to listen first, by bar and time; the repeats a change to a copied-from bar changed; the gaps; each regridded span, where they listen to the song and count its bars; and each section's left-hand figure, for them to call too sparse, too busy or right. Ask them to approve, or to name the places to change by bar or time, and stop until they answer.
5. **Revise.** Send their words, verbatim, to the same arranger with SendMessage as `Task: revise: <their words>`, wait for its report, and go back to step 4. If the arranger can't be reached, a new conversation say, dispatch a new one with step 2's prompt and that task: `notes.md` and `score.txt` hold everything decided so far.
6. **Approval.** Send `Task: approved: <their words>` to the arranger, which records it in `notes.md`; with no arranger to reach, dispatch a new one with step 2's prompt and that task.

## Output files

All in `<out>`, written by the arranger and the commands it runs:

| file | written by | holds |
| --- | --- | --- |
| `grid.mid` | `build-grid` | the transcription's tempo map, time signature and chord markers, with its band piano and bass |
| `grid.regrid.mid` | `regrid` | the grid with its tempo hiccups regridded, used as the cover |
| `bars.txt` | `dump-bars` | the band's piano and bass, the melody, the drums and the instrument lines, bar by bar |
| `notes.md` | the arranger | the inputs and the grid's tracks, the sections, chords, melody, rhythm section and left-hand figures, the vocal notes left out, and the revisions |
| `score.txt` | the arranger | the two-hand score, format version 1 |
| `arranged.mid` | `build-arrangement` | the two-hand MIDI on the grid's tempo map |
| `arranged.wav` | `render` | the render for the user to listen to |
| `arranged.json` | `export-arrangement` | the notes the falling-notes viewer plays with `arranged.wav` |

## Additional resources

- **`references/workflow.md`:** the arranger's clean-room rule, commands, steps, `notes.md` outline and report.
- **`references/band-to-piano.md`:** the left hand as a pianist's accompaniment, one figure per section, its density, and the right hand with the melody.
- **`../arrange-cover/references/reading-the-dump.md`:** the dump's lines, the markers, finding the chords, the hits and the stops, the drums, the instrument lines, and reading a long dump.
- **`../arrange-cover/references/arranging-rules.md`:** the sections the workflow names, with the parts `references/band-to-piano.md` replaces.
- **pianoize's `agents/arranger.md`:** the subagent's definition, its tools limited to the shell and the files.
- **pianoize's `docs/arranging.md`:** the score format, every command, the check's limits and the output formats.
