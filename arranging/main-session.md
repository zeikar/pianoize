# The main session's side of an arranging skill

What you, the main session, do when an arranging skill runs: settle the command line, dispatch the arranger subagent with the prompt your `SKILL.md` gives, relay its report to the user and the user's answers back to it. The arranger follows `workflow.md`, with the front end and the hand files your `SKILL.md` names.

## The command line

- **Plugin root:** the one your `SKILL.md` shows. If that is a directory with a `pyproject.toml` in it, the skill runs from the pianoize Claude Code plugin, and that directory is the plugin's own copy of pianoize: the command line is `uv run --project '<plugin root>'` followed by pianoize and its command, run from the current directory, and the docs are in `<plugin root>/docs/`. Otherwise (empty, still a placeholder, or no `pyproject.toml` there) there is no plugin root: in a pianoize checkout, it is `uv run` followed by pianoize, run there, with the docs in its `docs/`; anywhere else, tell the user to install the pianoize plugin, and stop.
- Below, `<root>` is the plugin root, or without one, the checkout's root.
- Without `uv` on `PATH` (`command -v uv`), tell the user to install it (https://docs.astral.sh/uv/) and stop.
- The arranger writes score format version 1. If it reports that pianoize expects another version, the skill and pianoize are out of step: tell the user, and stop.

## Rules

- **The arranger arranges.** Changes to the score, the notes or the MIDI go through it, revisions included.
- **Never paste song content into the repository.** A song's chords, notes, markers, lyrics and times stay in `work/`, which is never committed: none of it goes into docs, tests, code, commit messages or issues.
- **Nobody can hear it but the user.** Never claim the arrangement sounds right. The user's listening decides.
- **Audio never leaves the machine.** Upload nothing.

## Workflow

1. **Inputs and tools.** Gather the inputs your `SKILL.md` lists, check for `uv`, settle the command line, and create `<out>` with `mkdir -p`, single-quoting the path.
2. **Dispatch the arranger** with the Agent tool: `subagent_type` `pianoize:arranger`, a `name` such as `arranger-<song>` so you can reach it again, and the prompt your `SKILL.md` gives. If no `pianoize:arranger` type is available, dispatch a general-purpose agent with the same prompt, its first line `First read <root>/agents/arranger.md and act as it says.` That agent has every tool, so the definition's limit to the shell and the files rests on its instructions there. Tell the user in one line that the arrangement has started and that a full song takes a while, then wait for the arranger to finish: don't poll its files.
3. **Read its report.** If it stopped on an error it can't fix, an input it can't read or a score format pianoize doesn't take, tell the user, and stop. If it asks the user something, ask them, send the answer to the same arranger with SendMessage, and wait again.
4. **Ask the user to listen.** Relay the report in the user's language: which hands are written for listening and which within the check's limits, as the report says; the WAV to listen to (or the MIDI, without a render), and that they can watch it fall too, since dropping `arranged.json` and `arranged.wav` on https://zeikar.dev/pianoize/ plays them there, read in the browser and uploaded nowhere; the places to listen first, by bar and time; the repeats a change to a copied-from bar changed; the gaps; each regridded span, where they listen to the song and count its bars; and each section's figures the report names, for them to call too thin, too busy or right. Ask them to approve, or to name the places to change by bar or time, and stop until they answer.
5. **Revise.** Send their words, verbatim, to the same arranger with SendMessage as `Task: revise: <their words>`, wait for its report, and go back to step 4. To change the combination your `SKILL.md` dispatched, another mode say, keep the first version to compare: make a new `<out>`, copy `score.txt` and `notes.md` into it, and send the new `Right hand:`, `Left hand:` and `Out:` lines with the task. If the arranger can't be reached, a new conversation say, dispatch a new one with step 2's prompt and that task: `notes.md` and `score.txt` hold everything decided so far.
6. **Approval.** Send `Task: approved: <their words>` to the arranger, which records it in `notes.md`; with no arranger to reach, dispatch a new one with step 2's prompt and that task.

## Output files

All in `<out>`, written by the arranger and the commands it runs. Your `SKILL.md` lists the files its front end adds.

| file | written by | holds |
| --- | --- | --- |
| `bars.txt` | `dump-bars` | `C`, the melody, and with a source the drums and the instrument lines, bar by bar |
| `notes.md` | the arranger | the inputs and the grid's tracks where the front end records them, the sections, the chords, the melody, the band and what was taken from it, the figures, the hits and stops, every inferred, filled or copied place, the comparison with the band, the vocal notes left out, the harmony backing, the gaps, and the revisions |
| `score.txt` | the arranger | the two-hand score, format version 1 |
| `arranged.mid` | `build-arrangement` | the two-hand MIDI on the tempo grid the front end made |
| `arranged.wav` | `render` | the render for the user to listen to |
| `arranged.json` | `export-arrangement` | the notes the falling-notes viewer plays with `arranged.wav` |
