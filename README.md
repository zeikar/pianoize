# pianoize

Turn a song recording into a piano arrangement, rendered as falling notes.

Status: M1 tooling runs: `pianoize evaluate`, `render` and `melody-clashes`. The M1 experiment scripts are in [`experiments/m1/`](experiments/m1/README.md); their outputs stay in `work/`.

## Direction so far

- **Harmony from several imperfect sources, refined by an LLM.** A [chordotomy](https://github.com/zeikar/chordotomy) timeline gives beats, chords, bass and key; web chord charts and tsumugi's transcription give other readings. Each gets things wrong, so none is the answer key. An LLM skill weighs them against each other and against the notes, and writes one refined harmony timeline. chordotomy itself stays an analyzer.
- **The arrangement starts from tsumugi-piano-cover.** M1 compared the audio-to-piano models that run on a Mac; tsumugi-piano-cover kept the most harmony and sounded best, so pianoize starts from its cover ([decision](docs/decisions.md#the-arrangement-first-the-video-last)).
- **An LLM corrects the cover, code applies it.** Where the cover departs from the refined harmony, an agent writes a correction spec. Deterministic code applies it to the cover.
- **Falling-notes output.** A piano roll drawn over time needs no bar lines or time signature.

## Rules

- Audio never leaves the machine.
- Recordings, and anything made from them (MIDI, arrangement JSON, video, the checkpoints a song is scored on), are never committed. Neither are chord charts copied from websites. All of it stays in the gitignored `work/`.
- Model weights with non-commercial terms are never committed. They are downloaded on first use, with their terms shown.
- Videos carry only the piano pianoize renders: never the original audio, nor vocals separated from it.

## Layout

- `src/pianoize/`: the arrangement engine, in Python
- `viewer/`: the falling-notes renderer, for the web (not started)
- `experiments/`: [M1 model trial](experiments/m1/README.md) scripts; the scripts and their environments live in `work/m1/`
- `docs/`: [design decisions](docs/decisions.md), and later the arrangement JSON schema
- `work/`: recordings and everything made from them, gitignored

The engine and the viewer will meet at a documented arrangement JSON: notes, the hand playing each, and the chord names to overlay. The engine will export MIDI as well.

## Development

Requires [uv](https://docs.astral.sh/uv/).

```sh
uv sync --extra dev
uv run pianoize --version
uv run pytest
uv run ruff check . && uv run ruff format --check .
```

Scoring and rendering need [FluidSynth](https://www.fluidsynth.org/), a piano SoundFont and [chordotomy](https://github.com/zeikar/chordotomy), installed separately. Options and environment variables are in [docs/evaluation.md](docs/evaluation.md).

```sh
uv run pianoize render song.mid -o song.wav
uv run pianoize evaluate --original original.chords.json --checkpoints checkpoints.json \
  --out-dir work/trial name=result.mid
```
