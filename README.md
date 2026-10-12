# pianoize

Turn a song recording into a piano arrangement, rendered as falling notes.

Status: M1 tooling runs: `pianoize evaluate`, `render` and `melody-clashes`. The M1 experiment scripts are in [`experiments/m1/`](experiments/m1/README.md); their outputs stay in `work/`. M2 tooling runs: `pianoize harmony-evidence`, `refine-timeline`, `find-candidates` and `apply-corrections`, driven by the [`polish-cover`](skills/polish-cover/SKILL.md) Claude Code skill. M3 tooling runs: `pianoize regrid`, `dump-bars`, `build-arrangement` and `check-arrangement`, driven by the [`arrange-cover`](skills/arrange-cover/SKILL.md) skill. The first full-song arrangement is approved. M4 tooling runs: `pianoize export-arrangement`, `preview-video` and `render-video` ([docs/rendering.md](docs/rendering.md)).

## Direction so far

- **Harmony from several imperfect sources, refined by an LLM.** A [chordotomy](https://github.com/zeikar/chordotomy) timeline gives beats, chords, bass and key; tsumugi's transcription gives another reading. Web chord charts may come later as a third, pasted by the user. Each gets things wrong, so none is the answer key. An LLM skill weighs them against each other and against the notes, and writes one refined harmony timeline. chordotomy itself stays an analyzer.
- **The arrangement starts from tsumugi-piano-cover.** M1 compared the audio-to-piano models that run on a Mac; tsumugi-piano-cover kept the most harmony and sounded best, so pianoize starts from its cover ([decision](docs/decisions.md#the-arrangement-first-the-video-last)).
- **M2: an LLM polishes the cover, code applies it.** Code lists the places that may need work: chords that disagree with the refined harmony, notes that sound like slips, awkward voice leading and stumbling timing. An agent judges each one and writes a correction spec for those worth fixing. Deterministic code applies it to a copy of the cover ([docs/polishing.md](docs/polishing.md)). It works, but at the listening gate an arrangement an agent wrote sounded better than the polished cover, so polishing is no longer the main path.
- **M3: an agent writes the arrangement, code renders and checks it.** An agent session following an `arrange-cover` skill reads the cover and the melody, and tsumugi's transcription of the band where there is one, and writes a per-bar score for two hands into `work/`. pianoize turns the score into MIDI on the cover's tempo grid, every note at one velocity, and checks that it is playable and fits the harmony ([decision](docs/decisions.md#m3-an-agent-writes-the-arrangement-2026-10-11)).
- **Falling-notes output.** A piano roll drawn over time needs no bar lines or time signature.

## Rules

- Audio never leaves the machine.
- Recordings, and anything made from them (MIDI, arrangement JSON, video, the checkpoints a song is scored on), are never committed. Neither are chord charts copied from websites. All of it stays in the gitignored `work/`.
- Model weights with non-commercial terms are never committed. They are downloaded on first use, with their terms shown.
- Videos carry only the piano pianoize renders: never the original audio, nor vocals separated from it.

## Layout

- `src/pianoize/`: the arrangement engine, in Python
- `viewer/`: the falling-notes page and its capture script, plain HTML, CSS and ES modules, with playwright-core installed by `npm ci` in `viewer/`
- `experiments/`: [M1 model trial](experiments/m1/README.md) scripts; the scripts and their environments live in `work/m1/`
- `docs/`: [design decisions](docs/decisions.md), [the score format and the arranging commands](docs/arranging.md), and [the arrangement JSON, the viewer and the video commands](docs/rendering.md)
- `skills/`: the Claude Code skills; [`polish-cover`](skills/polish-cover/SKILL.md) drives the M2 polishing commands, and [`arrange-cover`](skills/arrange-cover/SKILL.md) the M3 arranging commands
- `.claude-plugin/`: the manifests that make the repository a Claude Code plugin and its own marketplace
- `work/`: recordings and everything made from them, gitignored

The engine and the viewer meet at a documented arrangement JSON: the notes and the hand playing each ([docs/rendering.md](docs/rendering.md#the-arrangement-json)).

## Development

Requires [uv](https://docs.astral.sh/uv/). The viewer also needs [Node.js](https://nodejs.org/); `render-video` needs Node, the installed Google Chrome, ffmpeg and FluidSynth.

```sh
uv sync --extra dev
uv run pianoize --version
uv run pytest
uv run ruff check . && uv run ruff format --check .
(cd viewer && npm ci && npm test)
```

Scoring and rendering need [FluidSynth](https://www.fluidsynth.org/), a piano SoundFont and [chordotomy](https://github.com/zeikar/chordotomy), installed separately. Options and environment variables are in [docs/evaluation.md](docs/evaluation.md). The polishing commands, their file formats and the skill that runs them are in [docs/polishing.md](docs/polishing.md); the arranging commands, the score format and their skill are in [docs/arranging.md](docs/arranging.md); the arrangement JSON, the cards file and the video commands are in [docs/rendering.md](docs/rendering.md).

```sh
uv run pianoize render song.mid -o song.wav
uv run pianoize evaluate --original original.chords.json --checkpoints checkpoints.json \
  --out-dir work/trial name=result.mid
uv run pianoize render-video arranged.mid --cards cards.txt -o video.mp4
```

## License

[MIT](LICENSE). The models pianoize runs are installed separately and keep their own terms ([docs/decisions.md](docs/decisions.md#licenses)).
