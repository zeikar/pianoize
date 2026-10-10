---
name: polish-cover
description: This skill should be used when the user wants a song's harmony timeline refined or a tsumugi-piano-cover MIDI polished with pianoize, e.g. "refine the harmony timeline of this song", "reconcile chordotomy's chords with the tsumugi transcription", "polish this tsumugi cover", "fix the wrong chords and slips in the piano cover", "judge the cover's candidates", "check my correction spec". Runs the local pianoize commands, weighs chordotomy's timeline, tsumugi's transcription and the cover's notes into one refined timeline, judges every candidate the finder lists, writes the correction spec, and leaves the final A/B listening to the user. Not for making a cover, a transcription or a chord timeline from audio.
---

# Refine a song's harmony and polish its tsumugi piano cover

pianoize polishes a piano cover made by tsumugi-piano-cover instead of arranging the song again. This skill runs it in two phases:

1. **Harmony.** Weigh chordotomy's chord timeline, tsumugi's transcription and the cover's notes against each other, and write a refined harmony timeline.
2. **Cover.** Judge every place the finder flags in the cover against that timeline, and write a correction spec that pianoize applies to a copy of the cover.

pianoize's commands are deterministic and never call an LLM. You write two small JSON files, `harmony-edits.json` and `corrections.json`; pianoize validates them and writes the timeline and the MIDI. Never write a timeline or a MIDI file any other way. You cannot hear the result, so the user's A/B listening at the end is the final gate.

## Rules

- **No analysis is the answer key.** chordotomy's chords, tsumugi's markers and the cover's notes each get things wrong. Weigh them against each other and check the notes before calling anything a mistake.
- **Inputs are read-only.** Never modify, move or overwrite the timeline, the cover, the transcription or the melody MIDI.
- **Write only into `<out>`.** Never change pianoize's own files.
- **Never paste song content into the repository.** A song's chords, notes, markers, lyrics and times stay in `<out>` under `work/`, which is never committed: none of it goes into docs, tests, code, commit messages or issues.
- **Audio never leaves the machine.** Upload nothing.

## Inputs

Ask the user for any input that is missing and stop until you have it; pianoize makes none of them.

- `<timeline>`: chordotomy's timeline of the song, `<stem>.chords.json` (or `<stem>.edited.chords.json`, saved by chordotomy's viewer with the user's corrections).
- `<cover>`: the cover MIDI made by tsumugi-piano-cover.
- `<source>`: tsumugi's transcription, `source.mid`, with its chord markers and its bass track.
- `<melody>`: tsumugi's melody MIDI.
- `<out>`: an output directory under `work/`, named by the user (`work/<song>/`). Create it with `mkdir -p`.
- For the renders at the end: FluidSynth on `PATH` and a piano SoundFont (`--soundfont`, or `$PIANOIZE_SOUNDFONT`).

Single-quote every path in a command, writing a `'` inside it as `'\''`: song file names carry spaces, brackets and other characters the shell would read.

## Running pianoize

- **Plugin root:** `${CLAUDE_PLUGIN_ROOT}`. If that is a directory with a `pyproject.toml` in it, this skill runs from the pianoize Claude Code plugin, and that directory is the plugin's own copy of pianoize: run `uv run --project "<plugin root>" pianoize <command> …` from the current directory. Its first run builds the environment, so allow a few minutes. Otherwise (empty, still a `${…}` placeholder, or no `pyproject.toml` there) there is no plugin root: in a pianoize checkout, run `uv run pianoize <command> …` there; anywhere else, tell the user to install the pianoize plugin, and stop.
- Without `uv` on `PATH`, tell the user to install it (https://docs.astral.sh/uv/) and stop.
- Below, `pianoize <command> …` stands for that command line.
- **The docs:** `<plugin root>/docs/polishing.md`, or `docs/polishing.md` in the checkout, documents the four polishing commands with their rules, thresholds and file formats; `render` is in `docs/evaluation.md` beside it. `pianoize <command> --help` lists a command's options. Read the section a step names whenever its rules matter.
- **Errors.** A failing command prints `error: …` naming the item at fault (`edits[3]: unknown note t1920p62`). Fix that item and run the same command again. Exit 2 is a usage error: show its message.

This skill is written for version 11 of chordotomy's timeline (`schema_version`). pianoize refuses a timeline of any other version, naming both: tell the user the timeline comes from another chordotomy version, and stop.

## Phase 1: the refined harmony timeline

1. **Gather the evidence:** `pianoize harmony-evidence '<cover>' '<timeline>' --source '<source>' --melody '<melody>' -o '<out>/evidence.md' > /dev/null`, then read the file: the command also prints the whole table, so send that to `/dev/null` on every run. It writes one row per segment: chordotomy's chord and candidates, tsumugi's marker and transcribed bass, the cover's tones, coverage and missing tones, and the melody ("Harmony evidence" in the docs). The bass track is `electric_bass` unless `--bass-track` names another. A name the file lacks is an error that lists its tracks: pick the bass track from them. For a transcription without a bass track, pass `--bass-track ""`.
2. **Decide** every segment where the sources disagree on the triad or the bass, following **`references/reconcile-harmony.md`**.
3. **Write `<out>/harmony-edits.json`**, one edit per span to change ("Refined harmony timeline" in the docs):
   ```json
   {
     "inputs": {"timeline": {"path": "<timeline>", "sha256": "<the timeline's SHA-256>"}},
     "edits": [
       {"start_beat": 24, "end_beat": 28, "chord": "A:min", "bass": "C",
        "reason": "the transcribed bass and the cover's tones agree on A minor over C",
        "readings": {"chordotomy": "C:maj", "marker": "Am/C", "bass": "C", "cover": "A C E"}}
     ]
   }
   ```
   The beats come from the `beats` column, the end exclusive. Get the hash with `shasum -a 256 '<timeline>'`.
4. **Refine:** `pianoize refine-timeline '<timeline>' '<out>/harmony-edits.json' -o '<out>/<stem>.refined.chords.json'`, `<stem>` being the timeline's file name without `.chords.json`. Always refine the original timeline: to change something, revise the edits file and run this again. Never refine the refined file.
5. **Confirm:** run step 1 again with `'<out>/<stem>.refined.chords.json'` as the timeline and `-o '<out>/evidence.refined.md'`. Every edited row reads the chord you decided, `edited` is `yes` there, and every other row keeps its chord. Otherwise revise the edits and repeat steps 4 and 5.
6. **Write `<out>/harmony-report.md`:** for each disagreement, its time and beats, each source's reading, your choice and the reason, the ones left as chordotomy has them included.

If nothing needs an edit, skip steps 3 to 5 and use `<timeline>` as the refined timeline. Tell the user that chordotomy's viewer opens the refined timeline with the recording if they want to look, and go on without waiting.

## Phase 2: polish the cover

`<refined>` is the refined timeline from Phase 1, final before judging starts. If the harmony must change during Phase 2, refine again, run step 1 again, delete every `harmony`, `voice:leap` and `voice:bass-late` verdict and the edits citing them, and judge those again ("When the harmony changes" in `references/judge-candidates.md`).

1. **Find the candidates:** `pianoize find-candidates '<cover>' --timeline '<refined>' --melody '<melody>' -o '<out>/candidates.json'`. It prints one line per candidate and a count per category: `harmony`, `glitch`, `voice` and `timing` ("Candidates" in the docs lists the kinds).
2. **Judge every candidate** in `<out>/candidates.json`, `fix` or `keep`, following **`references/judge-candidates.md`**. Read each one's `measurements`, `context` and `suggested`. A suggestion is a starting point, not proof.
3. **Write `<out>/corrections.json`**, correction spec version 1 ("Correction spec" in the docs):
   ```json
   {
     "spec_version": 1,
     "inputs": {"cover": {"path": "…", "sha256": "…"}, "melody": {"path": "…", "sha256": "…"}},
     "verdicts": [
       {"candidate": "glitch:short:t1920p62", "time": 2.0, "action": "fix",
        "reason": "an isolated 20 ms flick between two chords"},
       {"candidate": "timing:off-grid:t3840p67", "time": 4.0, "action": "keep",
        "reason": "a pickup into the next phrase"}
     ],
     "edits": [
       {"op": "delete", "candidate": "glitch:short:t1920p62", "note": "t1920p62",
        "reason": "a slip"}
     ]
   }
   ```
   Copy `inputs.cover` and `inputs.melody` from `candidates.json`, each verdict's `time` from its candidate, and exact ticks from `suggested` or from the note ids in `context` (`t{on_tick}p{pitch}`).
4. **Check the spec:** `pianoize find-candidates '<cover>' --timeline '<refined>' --melody '<melody>' --spec '<out>/corrections.json' -o '<out>/candidates.after.json' --report '<out>/candidates-report.md'`, always on the original cover. It validates the spec, applies it in memory, finds the candidates again and names every note by its id in the original cover (`add-{id}` for an added note). Every candidate gets a status, `fixed`, `kept`, `still present` or `unjudged`, and `candidates-report.md` lists them all by id, with category/kind, time, status and reason. The command prints each `still present` and `unjudged` line with a count per status, and exits 1 while there is any. Answer each as `references/judge-candidates.md` says: a new candidate on a note an edit already touches, or on an `add-{id}` note, means revising that edit, never adding a second one. Run it again until it prints `all candidates judged` and exits 0. Fixed means gone: only this run proves a fix.
5. **Apply:** `pianoize apply-corrections '<cover>' '<out>/corrections.json' --melody '<melody>' -o '<out>/<cover stem>-polished.mid'`.
6. **Check the notes against the harmony:** `pianoize harmony-evidence '<out>/<cover stem>-polished.mid' '<refined>' --melody '<melody>' -o '<out>/check.md' > /dev/null`, then read the file. Where you fixed a chord, `missing` is empty and `coverage` is at least 0.6 (`coverage_below`). If not, revise the spec and repeat from step 4. The table's `missing` covers every segment, short ones included, so it can name tones where no candidate was: that is information, not new work.
7. **Render both covers:** `mkdir -p '<out>/renders'`, then `pianoize render '<cover>' -o '<out>/renders/<cover stem>.wav'` and `pianoize render '<out>/<cover stem>-polished.mid' -o '<out>/renders/<cover stem>-polished.wav'`, adding `--soundfont '<sf2>'` when `$PIANOIZE_SOUNDFONT` is not set. Without FluidSynth or a SoundFont, tell the user and give them the two MIDI paths instead.
8. **Ask the user to listen.** Give them the two files and the places the edits change: for each edit in `corrections.json`, its op, its note (or the added note's `add-{id}`) and its time: the note's onset as a `context` line shows it, or the cited candidate's `time`. Don't list `fixed` lines instead: a `fix` verdict on a mistyped id is `fixed` too. Ask them to listen A/B, then approve or name the places to revert, and stop until they answer. Don't claim the polished cover sounds better: you have not heard it.
9. **Revert** what they name: drop the edits there and set the candidates those edits cited to `keep`, with the user's reason. Run step 4 again: a `fix` verdict the dropped edits had been resolving now shows `still present` (set it to `keep` with the same reason, or revise it), and anything new needs a verdict. Then steps 5 to 8 again, until the user approves.

## Output files

All in `<out>`:

| file | written by | holds |
| --- | --- | --- |
| `evidence.md`, `evidence.refined.md` | `harmony-evidence` | the evidence table, before and after the edits |
| `harmony-edits.json` | you | the chord edits, each with its reason and readings |
| `<stem>.refined.chords.json` | `refine-timeline` | the refined timeline, schema 11 |
| `harmony-report.md` | you | each disagreement: the readings, the choice, the reason |
| `candidates.json` | `find-candidates` | the candidates in the original cover |
| `corrections.json` | you | the correction spec: a verdict per candidate, an edit per fix |
| `candidates.after.json`, `candidates-report.md` | `find-candidates --spec` | the candidates left, and every candidate's status and reason |
| `<cover stem>-polished.mid` | `apply-corrections` | the polished cover; the original stays as it was |
| `check.md` | `harmony-evidence` | the polished cover's notes against the refined harmony |
| `renders/<cover stem>.wav`, `renders/<cover stem>-polished.wav` | `render` | the two covers to compare |

## Additional resources

- **`references/reconcile-harmony.md`:** weighing the evidence columns and deciding a segment's chord.
- **`references/judge-candidates.md`:** `fix` or `keep` per kind, writing the edits, answering the `--spec` run.
- **pianoize's `docs/polishing.md`** (see "Running pianoize"): every command, rule, threshold and file format.
