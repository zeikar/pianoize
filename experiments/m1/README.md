# M1: model trial

Runs the existing audio-to-piano models and the melody extractors on one song and scores them against a human piano cover. Why and how it is scored: [docs/decisions.md](../../docs/decisions.md) and [docs/evaluation.md](../../docs/evaluation.md).

## Inputs

The scripts read two recordings, kept in `work/` and never committed:

- `SONG_MP3`: the original recording.
- `COVER_MP3`: the human piano cover.

Each script takes them from the environment (`SONG_MP3=... COVER_MP3=... bash experiments/m1/02_decode_input.sh`). Scripts that need only one say so in their header.

## Scripts, in planned order

The scripts land in later tasks; until then only `env.sh` exists. Run each with `bash`, from anywhere. Each sources `env.sh`.

| script | does |
| --- | --- |
| `env.sh` | sourced by the others: containment variables, `fetch`; never source it in your own shell |
| `00_fluidsynth.sh` | installs FluidSynth with Homebrew, records the formulas |
| `01_soundfont.sh` | downloads the piano SoundFont |
| `02_decode_input.sh` | decodes the recordings into `input/` |
| `03_validate.sh` | checks render, analysis and scoring on a synthetic progression (`make_synthetic.py`), then scores the human cover and the decoded original |
| `04_demucs.sh` | separates stems |
| `05_game.sh` | melody with GAME |
| `06_basic_pitch.sh` | melody with Basic Pitch |
| `07_torchcrepe.sh` | fallback melody with torchcrepe; written only if neither GAME nor Basic Pitch yields a melody (not needed in this run) |
| `08_tsumugi.sh` | piano cover with tsumugi |
| `09_etude.sh` | piano cover with Etude |
| `10_results.sh` | builds the results table |
| `11_leak_check.sh` | checks nothing was written outside `work/m1` |

Pop2Piano is reference only. It runs from `work/m1/pop2piano/run.sh`, which is not committed.

## Where things land

Everything is under `work/m1/`, which is gitignored:

`input`, `stems`, `melody`, `covers`, `results`, `models`, `upstream` (cloned programs), `envs` (one virtual environment per program), `cache` (uv, pip, Hugging Face, torch and temp files), `soundfonts`.

`env.sh` moves `XDG_CACHE_HOME` into `work/m1/cache`. chordotomy's Beat This! weights stay in the real cache (`~/.cache/chordotomy`), so a script that runs chordotomy prefixes the call with `XDG_CACHE_HOME="$CHORDOTOMY_XDG_CACHE_HOME"`. The Homebrew install is the one thing outside `work/m1`. `11_leak_check.sh` checks the rest.

## Rules the scripts follow

- Idempotent. An existing clone, environment, completed download or output is reused. Downloads and `.part` files: see `fetch` in `env.sh`.
- Every upstream program runs as a subprocess: its own environment's interpreter, on its own entry point, from its own checkout. Nothing here imports an upstream package. Licenses: [docs/decisions.md](../../docs/decisions.md#m1-license-check-2026-10-08).
- `pianoize` and `chordotomy` are called by their venv binaries, never through `uv run`.

## Removal

```sh
rm -rf work/m1
```

Then `brew uninstall` the formulas listed in `work/m1/brew-new-formulas.txt`. Read that file before deleting `work/m1`.
