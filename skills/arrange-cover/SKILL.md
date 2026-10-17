---
name: arrange-cover
description: This skill should be used when the user wants a two-hand piano arrangement of a song written with pianoize from a tsumugi-piano-cover MIDI and, where the song has one, tsumugi's melody MIDI and its transcription of the band, e.g. "arrange this song for two hands", "write the piano arrangement from the cover and the melody", "make a Synthesia arrangement of this cover", "build and check my score", "revise bars 30 to 34 of the arrangement". Gathers the inputs and dispatches pianoize's arranger subagent, which dumps the cover, the melody and the band bar by bar, writes a per-bar two-hand score that keeps the original's groove, its signature hits and the band parts the cover leaves out, has the local pianoize CLI build it into MIDI and check that it is playable (or in full mode, for listening, its tune and harmony), and renders it; relays its report, and the user's answers back to it, and leaves the final listening to the user. Not for making a cover, a transcription or a melody from audio, for polishing the cover note by note (that is polish-cover), or for rendering the falling-notes video.
---

# Arrange a song for two hands from its piano cover and melody

pianoize arranges a song for a falling-notes video (Synthesia style) from the piano cover tsumugi-piano-cover made of it, and tsumugi's transcription of its sung melody, where the song has one. tsumugi's transcription of the whole band, with a track per instrument, is read under the cover in every bar where there is one: its bass, its drums, a backing vocal and the parts the cover leaves out make the arrangement richer and keep its chords and stops honest. A score for two hands is written bar by bar; pianoize builds it into MIDI on the cover's tempo grid and checks that it fits the score's chords and, unless it is a full arrangement, that it is playable.

**The arranging runs in a subagent, `pianoize:arranger`.** It reads the long dump, writes the score and loops the build and the check in its own context, following **`references/workflow.md`**. You, the main session, gather the inputs, dispatch it, relay its report to the user and the user's answers back to it. Don't read the dump or write the score yourself: that is what keeps your context free for the user.

## Rules

- **The arranger arranges.** Changes to the score, the notes or the MIDI go through it, revisions included.
- **Never paste song content into the repository.** A song's chords, notes, markers, lyrics and times stay in `work/`, which is never committed: none of it goes into docs, tests, code, commit messages or issues.
- **Nobody can hear it but the user.** Never claim the arrangement sounds right. The user's listening decides.
- **Audio never leaves the machine.** Upload nothing.

## Inputs

Ask the user for any input that is missing and stop until you have it. The `prepare-song` skill (`../prepare-song/SKILL.md`) makes them, `pianoize prepare` writing `cover.mid`, `melody.mid` (where the song has one) and `source.mid` into the song's directory; when they are missing, offer that skill and stop.

- `<cover>`: the cover MIDI made by tsumugi-piano-cover.
- `<melody>`, optional: tsumugi's melody MIDI, its lead vocal track. An instrumental has none, unless `prepare --melody-track` named an instrument's track. Without one, the tune is found in the band's instrument lines (offer `<source>` if you don't have it) or in the cover's top line.
- `<source>`, optional but asked for: tsumugi's transcription of the whole band, `source.mid`, a track per instrument. Ask for it once; without it, the arrangement is written from the cover and the melody alone.
- `<out>`: an output directory under `work/`, named by the user (`work/<song>/`).
- `<mode>`: `playable`, the default, both hands within the check's limits; or `full`, when the user asks for every band part over what two hands can play. A full arrangement is for listening: no limits on the hands, every band part the score holds clearly. It needs `<source>`: without one, ask for it, or write a playable one and tell the user why.
- For the render at the end: FluidSynth on `PATH` and a piano SoundFont, `<sf2>`, unless `$PIANOIZE_SOUNDFONT` names one. Without either, the arranger exports anyway and gives the MIDI in place of the WAV.

## The command line

- **Plugin root:** `${CLAUDE_PLUGIN_ROOT}`. If that is a directory with a `pyproject.toml` in it, this skill runs from the pianoize Claude Code plugin, and that directory is the plugin's own copy of pianoize: the command line is `uv run --project '<plugin root>'` followed by pianoize and its command, run from the current directory, and the docs are in `<plugin root>/docs/`. Otherwise (empty, still a `${…}` placeholder, or no `pyproject.toml` there) there is no plugin root: in a pianoize checkout, it is `uv run` followed by pianoize, run there, with the docs in its `docs/`; anywhere else, tell the user to install the pianoize plugin, and stop.
- Below, `<root>` is the plugin root, or without one, the checkout's root.
- Without `uv` on `PATH` (`command -v uv`), tell the user to install it (https://docs.astral.sh/uv/) and stop.
- The arranger writes score format version 1. If it reports that pianoize expects another version, the skill and pianoize are out of step: tell the user, and stop.

## Workflow

1. **Inputs and tools.** Gather the inputs, check for `uv`, settle the command line, and create `<out>` with `mkdir -p`, single-quoting the path.
2. **Dispatch the arranger** with the Agent tool: `subagent_type` `pianoize:arranger`, a `name` such as `arranger-<song>` so you can reach it again, and the prompt below. If no `pianoize:arranger` type is available, dispatch a general-purpose agent with the same prompt, its first line `First read <root>/agents/arranger.md and act as it says.` That agent has every tool, so the definition's limit to the shell and the files rests on its instructions there. Tell the user in one line that the arrangement has started and that a full song takes a while, then wait for the arranger to finish: don't poll its files.
   ```
   Skill: arrange-cover
   Workflow: <root>/skills/arrange-cover/references/workflow.md
   Command line: <the command line>
   Docs: <the docs directory>
   Cover: '<cover>'
   Melody: '<melody>' (or: none)
   Source: '<source>' (or: none)
   Out: '<out>'
   SoundFont: '<sf2>' (or: $PIANOIZE_SOUNDFONT, or: none)
   Mode: <mode>
   Task: arrange
   ```
3. **Read its report.** If it stopped on an error it can't fix, an input it can't read or a score format pianoize doesn't take, tell the user, and stop. If it asks the user something, ask them, send the answer to the same arranger with SendMessage, and wait again.
4. **Ask the user to listen.** Relay the report in the user's language: the mode, and in full mode that no one could play it as written; the WAV to listen to (or the MIDI, without a render), and that they can watch it fall too, since dropping `arranged.json` and `arranged.wav` on https://zeikar.dev/pianoize/ plays them there, read in the browser and uploaded nowhere; the places to listen first, by bar and time; the repeats a change to a copied-from bar changed; the gaps; each regridded span, where they listen to the song and count its bars; and in full mode, each section's figures, for them to call too thin, too busy or right. Ask them to approve, or to name the places to change by bar or time, and stop until they answer.
5. **Revise.** Send their words, verbatim, to the same arranger with SendMessage as `Task: revise: <their words>`, wait for its report, and go back to step 4. To switch modes, keep the first version to compare: make a new `<out>`, copy `score.txt` and `notes.md` into it, and send the new `Mode:` and `Out:` lines with the task. If the arranger can't be reached, a new conversation say, dispatch a new one with step 2's prompt and that task: `notes.md` and `score.txt` hold everything decided so far.
6. **Approval.** Send `Task: approved: <their words>` to the arranger, which records it in `notes.md`; with no arranger to reach, dispatch a new one with step 2's prompt and that task.

## Output files

All in `<out>`, written by the arranger and the commands it runs:

| file | written by | holds |
| --- | --- | --- |
| `cover.regrid.mid` | `regrid` | the cover with its tempo hiccups regridded, used as the cover |
| `bars.txt` | `dump-bars` | the cover's attacks, the melody, and with a source the drums and the instrument lines, bar by bar |
| `notes.md` | the arranger | the sections, the chords, the melody's entries, the band and what was taken from it, the hits and stops, every inferred, filled or copied place, the comparison with the band, the gaps, and the revisions |
| `score.txt` | the arranger | the two-hand score, format version 1 |
| `arranged.mid` | `build-arrangement` | the two-hand MIDI on the cover's tempo grid |
| `arranged.wav` | `render` | the render for the user to listen to |
| `arranged.json` | `export-arrangement` | the notes the falling-notes viewer plays with `arranged.wav` |

## Additional resources

- **`references/workflow.md`:** the arranger's rules, commands, steps, `notes.md` outline and report.
- **`references/reading-the-dump.md`:** the dump's lines, the markers, finding the chords, the hits, the stops, the melody, the drums and the instrument lines, and reading a long dump.
- **`references/arranging-rules.md`:** keeping the feel, copying the cover, the sections where no one sings, taking from the band, inferring, voicing the hands, the pedal, and fixing each check rule.
- **pianoize's `agents/arranger.md`:** the subagent's definition, its tools limited to the shell and the files.
- **pianoize's `docs/arranging.md`:** the score format, every command, the check's limits and the output formats.
