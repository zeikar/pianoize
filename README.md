# pianoize

Turn a song recording into a piano arrangement, rendered as falling notes.

Status: skeleton. `pianoize --version` runs; nothing else does yet.

## Direction so far

- **Harmony from chordotomy.** Chords, bass line, beats and key come from a [chordotomy](https://github.com/zeikar/chordotomy) chord timeline. pianoize reads that JSON; chordotomy itself stays an analyzer.
- **Melody from a pretrained model.** The first candidate is openvpi's GAME (singing to notes); the fallback is Demucs vocal separation followed by Spotify's Basic Pitch. They are compared on one song before either is chosen. A melody corrected by hand in a DAW can replace the extracted one.
- **An LLM writes the arrangement, code plays it.** An agent reads the timeline and picks a texture per passage. Deterministic code turns that into notes.
- **Falling-notes output.** A piano roll drawn over time needs no bar lines or time signature.

## Rules

- Audio never leaves the machine.
- Recordings, and anything made from them (MIDI, arrangement JSON, video, the checkpoints a song is scored on), are never committed. They stay in the gitignored `work/`.
- Model weights with non-commercial terms are never committed. They are downloaded on first use, with their terms shown.
- Videos carry only the piano pianoize renders: never the original audio, nor vocals separated from it.

## Layout

- `src/pianoize/`: the arrangement engine, in Python
- `viewer/`: the falling-notes renderer, for the web (not started)
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
