# Preparing a song

How pianoize makes a song's arranging inputs from its recording. `pianoize setup` installs tsumugi and tsumugi-piano-cover once, pinned, outside the repository. `pianoize prepare` decodes the recording, transcribes it with tsumugi, takes its melody and generates its piano cover: `source.mid`, `melody.mid` and `cover.mid`, which [docs/arranging.md](arranging.md) starts from. Both models run as separately installed tools, each with its own interpreter; pianoize imports neither. The reasons are in [docs/decisions.md](decisions.md#song-preparation-the-models-move-out-of-work-2026-10-13).

```
pianoize setup
pianoize prepare AUDIO -o DIR
```

## Setup

`pianoize setup` clones tsumugi and tsumugi-piano-cover at their pins, builds an environment for each, and downloads tsumugi's checkpoints and the cover's weights, about 1.6 GB of weights in all. It prints "pianoize home:" and the home's path first, then each step before it runs: `cloning <url> at <short commit> into <directory>`, each uv command with the directory it runs in, and each download, the cover's as `downloading anime-song/tsumugi-piano-cover revision <revision> into <hub cache>`, followed by the snapshot's path once it is there. uv's and huggingface_hub's progress shows on stderr as it goes.

### What goes where

The pianoize home is `$PIANOIZE_HOME`, else `$XDG_CACHE_HOME/pianoize`, else `~/.cache/pianoize`, made absolute. It is flat:

| in the home | what it is |
| --- | --- |
| `tsumugi/` | tsumugi's clone, with its environment in `tsumugi/.venv`, made by `uv sync --locked --extra stem` from tsumugi's own lock, and tsumugi's checkpoints in its `checkpoints/` and `beat_chord_checkpoints/` (below) |
| `tsumugi.commit` | the commit the clone is at, its marker |
| `tsumugi-piano-cover/` | tsumugi-piano-cover's clone: the generator, `piano_cover`, and Cover Studio's worker, `cover_studio/tsumugi_worker.py`, which runs tsumugi with the settings the cover model was trained on |
| `tsumugi-piano-cover.commit` | its marker |
| `tsumugi-piano-cover.venv/` | the generator's environment: Python 3.12 with only what `piano_cover.generate` imports, torch 2.13.0, numpy, symusic, safetensors and huggingface_hub |
| `stem-splitter/` | the stem splitter's weights, `stem_splitter.pt` (`STEM_SPLITTER_CACHE`) |

- **The cover's weights**, about 750 MB, go in the Hugging Face hub cache: `$HF_HUB_CACHE`, else `$HF_HOME/hub`, else `$XDG_CACHE_HOME/huggingface/hub`, else `~/.cache/huggingface/hub`. They are the snapshot `models--anime-song--tsumugi-piano-cover/snapshots/12c81996ec0c7c5cb77d9d8c0a2a25234a7620fe/` there, and count as installed when it holds five files: `piano_cover/model.safetensors`, `piano_cover/config.json`, `piano_ar/model.safetensors`, `piano_ar/config.json` and `README.md`, the model card. Setup downloads them with huggingface_hub's `snapshot_download`, run by the generator environment's interpreter with that cache as its `cache_dir`, so they land where pianoize looks whatever other Hugging Face variables are set. The generator reads them from the snapshot, so generating needs no network.
- **tsumugi's own checkpoints** (MIT), about 850 MB: nine files in the clone's `checkpoints/` and `beat_chord_checkpoints/`, from `anime-song/instrument_agnostic_amt`, and `stem-splitter/stem_splitter.pt`, from `anime-song/stem-splitter`. Setup fetches them with tsumugi's own fetch functions, run by tsumugi's interpreter in its clone, then checks each file's SHA-256 against the sum the [tsumugi row](decisions.md#m1-license-check-2026-10-08) records. So `prepare` downloads nothing.
- **uv's own places.** uv builds both environments through its cache (`uv cache dir`, `~/.cache/uv` by default), which every uv project on the machine shares. Both environments run Python 3.12; where none is installed, uv downloads its own (`uv python dir`, `~/.local/share/uv/python` by default).

### Pins

| what | pin |
| --- | --- |
| tsumugi | commit `a700b8c` |
| tsumugi-piano-cover | commit `4f5c435` |
| tsumugi's checkpoints | each file's SHA-256 |
| the cover's weights | revision `12c8199` of `anime-song/tsumugi-piano-cover` |
| the generator's torch | 2.13.0 |

They are the tsumugi and tsumugi-piano-cover rows of the [M1 license check](decisions.md#m1-license-check-2026-10-08), with the full hashes, the licenses and the weights' SHA-256 sums, and the constants in `src/pianoize/tsumugi.py`; the two change together. tsumugi's environment takes every version from tsumugi's lock. tsumugi's checkpoints are fetched from their repositories' `main`, so they are pinned by content: a file whose SHA-256 differs from its recorded sum stops setup. The generator's other packages are not pinned.

### The terms

Before the download, setup prints the weights' terms:

```
tsumugi-piano-cover weights (piano_cover, piano_ar) by anime-song
License: CC BY-NC 4.0 (https://creativecommons.org/licenses/by-nc/4.0/)
Stated in: https://huggingface.co/anime-song/tsumugi-piano-cover (model card) and https://github.com/anime-song/tsumugi-piano-cover#license
Terms: attribution, non-commercial use only.
Code: MIT, https://github.com/anime-song/tsumugi-piano-cover
```

They print only on a run that downloads the cover's weights. A cover generated with these weights, and an arrangement made from it, is treated as non-commercial ([Licenses](decisions.md#licenses)).

### Running it again

What is in place is kept:

- **A clone** whose marker holds its pin and whose directory exists: `tsumugi: already at a700b8c`, `tsumugi-piano-cover: already at 4f5c435`.
- **The generator's environment:** `uv venv` runs only while its interpreter is missing.
- **tsumugi's checkpoints,** when all ten files are there: `tsumugi checkpoints: present`; setup still hashes them and downloads nothing.
- **The cover's weights,** when all five files are there: `weights: present at <snapshot>`.

`uv sync --locked --extra stem` and `uv pip install` run on every setup. On an installed environment they audit it in under a second, without the network, and they finish one an earlier setup left half done. So a setup that failed or was stopped is finished by running it again. A clone is made in `<name>.part` and renamed once checked out, so an interrupted clone never passes for one: the next setup clones it again.

### A clone at another commit

Setup never fetches or checks out another commit in place. A clone whose marker holds another commit, or that has no marker, stops it:

```
error: /…/tsumugi is at commit <commit or unknown>, not the pinned a700b8cde582cd95a3d20f460b3648f45734d06d; remove it and run setup again
```

Remove that directory and run setup again.

### Errors

Each prints `error: …` and exits 1:

- `git not found on PATH; install the system's git`, or `uv not found on PATH; install it from https://docs.astral.sh/uv/`. Both are checked before anything is cloned.
- A clone at another commit, [above](#a-clone-at-another-commit).
- `<program> <first argument> failed with exit code N; see the output above`, the program by its full path: `…/uv sync failed with exit code 2; see the output above`. git's, uv's or huggingface_hub's own message is above it. For the download, the program is the generator environment's interpreter, `…/tsumugi-piano-cover.venv/bin/python -I`.
- `cannot run <program> <first argument>: …`, a program that can't be started.
- `the download left out <paths>`, a download that ended without one of the five files.
- A checkpoint of tsumugi's whose SHA-256 isn't its recorded sum, naming the file and both hashes.
- The system's own error for anything else, such as a home that can't be made or written.

### Requirements

- **git and uv** on `PATH`.
- **FFmpeg's shared libraries**, which tsumugi's torchcodec loads to read the audio; `prepare` needs them, not setup. On macOS, Homebrew's (`brew install ffmpeg`). tsumugi's locked torchcodec 0.16 has no rpath to them, so pianoize sets `DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib` for the worker's process only, unless it is set already. Homebrew's FFmpeg is a GPL build, loaded only inside tsumugi's process, as the [M1 license check](decisions.md#m1-license-check-2026-10-08) records.
- **The network,** for setup's first run. `prepare` downloads nothing.

### Removing it

```sh
rm -rf ~/.cache/pianoize ~/.cache/huggingface/hub/models--anime-song--tsumugi-piano-cover \
  ~/.cache/huggingface/hub/.locks/models--anime-song--tsumugi-piano-cover
```

Where the variables above are set, remove the home and the hub cache's `models--anime-song--tsumugi-piano-cover` and `.locks/models--anime-song--tsumugi-piano-cover` they name instead. That removes the clones, both environments, tsumugi's checkpoints, the stem splitter's weights and the cover's weights. uv's cache, and any Python uv downloaded, serve other projects too and stay; `uv cache clean` empties the cache for all of them.

## Preparing a song

`pianoize prepare AUDIO -o DIR` (`--out-dir`) makes a song's arranging inputs from its recording, `AUDIO`: a wav, flac, ogg or mp3 file. It makes `DIR` if needed and writes, in order:

| file | made by | what it is |
| --- | --- | --- |
| `song.wav` | decoding `AUDIO` with libsndfile | the recording as a 16-bit PCM WAV at its own rate and channels; tsumugi's stem splitter resamples it to 44.1 kHz itself |
| `source.mid` | tsumugi, through Cover Studio's worker | the band's transcription: a track per instrument, `drums` among them, the tempo map (`Predicted Tempo Map`), the chord markers (`Predicted Chords`) and the lead vocal, `melody` |
| `melody.mid` | pianoize, from `source.mid` | an unnamed first track with `source.mid`'s tempo changes and time signatures, no chord markers, then its `melody` track |
| `cover.mid` | tsumugi-piano-cover's generator, `piano_cover.generate`, from `source.mid` | the piano cover, seed 0 |
| `transcribe.log` | the transcription | tsumugi's output |
| `generate.log` | the generation | the generator's output |

A made-up run prints:

```
transcribing with tsumugi, about twice the song's length on an Apple-silicon Mac; log: /…/work/a-made-up-song/transcribe.log
transcribe: 431 s
generating the cover with tsumugi-piano-cover, about a third of the song's length on an Apple-silicon Mac; log: /…/work/a-made-up-song/generate.log
generate: 68 s
song.wav: 212.4 s
source.mid: 8 tracks: Predicted Tempo Map 0, Predicted Chords 0, (unnamed) 0, piano 1210, electric_bass 640, strings 455, melody 398, drums 1302
melody.mid: 398 notes
cover.mid: 2214 notes, 210.9 s
```

- **Each tool step** prints a line as it starts, naming its log, and its wall time in seconds when it ends. The decode and the melody print nothing. Every path printed is absolute.
- **The summary** is the last four lines: `song.wav`'s length in seconds; `source.mid`'s tracks, each with its notes, in the file's order, a track without a name as `(unnamed)`; `melody.mid`'s notes; `cover.mid`'s notes and its length in seconds. A note is a note-on with a velocity above 0. Every run that succeeds prints it, from reused files too.
- **The logs** hold each tool's output and errors in order, written a line at a time, so `tail -f` follows a run, and a progress bar's redraws come as lines of their own. The `@@` lines the worker streams to Cover Studio's page are left out. tsumugi's log names the device as it loads each model (`Loading … on mps`). A step that runs again starts its log afresh; a failed step's log stays.

### Devices and time

tsumugi runs on CUDA, else MPS, else the CPU; the generator on CUDA, else the CPU. On an Apple-silicon Mac, the transcription takes about twice the song's length, on MPS, and the cover about a third of it, on the CPU: in M1, 496 s and 75 s for a 251 s song ([the tsumugi rows](decisions.md#m1-license-check-2026-10-08)).

### Reusing outputs

A step whose output is already in `DIR` is skipped, with `reusing <path>`, and the steps after it read that file. Each output is matched by its name alone, each on its own: `prepare` doesn't check which recording, or which `source.mid`, a file came from. So:

- **One directory per recording.** Run another recording into a directory that holds a song's files, and it reuses them.
- **A failed or stopped run** is finished by running the same command again: what it finished is reused.
- **Redoing a step** means deleting its output and every output made from it:

  | to redo | delete |
  | --- | --- |
  | `song.wav` | all four: `song.wav`, `source.mid`, `melody.mid` and `cover.mid` |
  | `source.mid` | `source.mid`, `melody.mid` and `cover.mid`: a new transcription is a new draw, and the melody and the cover come from it |
  | `melody.mid` | `melody.mid` alone |
  | `cover.mid` | `cover.mid` alone |

The install is checked before any step, so even a run that would reuse all four needs it.

### Writing

Each output appears whole or not at all. `song.wav` and `melody.mid` are written to a scratch file beside their destination and renamed into place. The tools write `source.mid` and `cover.mid` into a scratch directory, `.prepare-*` in `DIR`, from which each is renamed into place once its step succeeds. The scratch directory also holds tsumugi's stems while it runs, and is removed when the run ends, whether it succeeds, fails or is [stopped](#stopping). A run killed outright, by SIGKILL (`kill -9`) or a crash, leaves its `.prepare-*` directory behind, and later runs don't sweep it: delete it by hand. Either way, a failed or stopped step leaves no output, never a partial one, and a file `prepare` reuses is a finished one.

### Stopping

Ctrl-C, `kill` (SIGTERM) and closing the terminal (SIGHUP) stop it the same way: a running tool is terminated and waited for, the scratch directory is removed, and `prepare` exits 130 with no message. The outputs finished before the stop stay, for the next run to reuse.

### Errors

Usage errors exit 2: an `AUDIO` that doesn't exist or is a directory, no `-o`, and a `DIR` whose `song.wav` would be `AUDIO` itself (`would overwrite an input`). Everything else prints one line and exits 1. Most name their step, and a tool's failure names the tool:

```
error: not installed under <home>: <what is missing>; run `pianoize setup`
error: decode: cannot read <AUDIO>: <reason>; the decoder reads wav, flac, ogg and mp3
error: decode: cannot write <DIR>/song.wav: <reason>
error: tsumugi transcribe failed (<exit code>): <reason>; log: <DIR>/transcribe.log
error: tsumugi transcribe: a stage failed: <the warning line>; log: <DIR>/transcribe.log
error: <DIR>/song.wav: cannot read audio: <reason>
error: melody: <reason>
error: tsumugi-piano-cover generate failed (<exit code>): <reason>; log: <DIR>/generate.log
```

- **Not installed** is checked first. Each missing piece is named with its path, tsumugi's checkpoints among them: `tsumugi at a700b8c (…)`, `the tsumugi-piano-cover weights (…)`.
- **decode** refuses a format libsndfile doesn't read, an m4a for one (`Format not recognised`). Converting it locally keeps the audio on the machine: `ffmpeg -i song.m4a song.flac`.
- **A tool's failure** quotes, as its reason, the output's last line naming a Python exception (`RuntimeError: …`), else its last non-blank line that isn't an `@@` line, cut to 200 characters. Read the log for the rest. A tool that exits 0 without its file fails as `tsumugi transcribe wrote no …; log: …` or `tsumugi-piano-cover generate wrote no …; log: …`, and an interpreter that won't start as `cannot run <interpreter>: …`.
- **melody** fails on a `source.mid` without a `melody` track, `melody: no track named 'melody'; tracks named: …`, or without a tempo map.
- **A file in `DIR` that isn't MIDI**, reused as `source.mid`, `melody.mid` or `cover.mid`, fails as `<path>: cannot read MIDI: …`.
- **A `DIR` that can't be made**, or an output that can't be moved into place, prints the system's error.

A failed step keeps every output made before it, and its log.

### Determinism

tsumugi's transcription is one draw, not a result a second run repeats ([M1 results](decisions.md#m1-results-2026-10-09)), so `source.mid` is kept and reused rather than made again. The cover is generated with seed 0. Whether the same `source.mid` gives a byte-identical `cover.mid` on a given machine is what [docs/decisions.md](decisions.md#song-preparation-the-models-move-out-of-work-2026-10-13) records from the first real run; this page claims no more.

## Running the skill

The `prepare-song` skill in `skills/prepare-song/` makes a song's arranging inputs from a YouTube link or an audio file: its `SKILL.md` gives the steps and the files, and `references/download.md` the download, yt-dlp run through `uvx` from uv's cache. It checks for uv and ffmpeg, downloads the audio for a link, runs `pianoize setup` and `pianoize prepare`, reports the summary, and offers the result to `arrange-cover` or `arrange-transcription` ([docs/arranging.md](arranging.md#running-the-skills)) without starting the arrangement. It ships in the same Claude Code plugin as the other skills; the plugin's layout and how to install it are in [docs/polishing.md](polishing.md#running-the-skill).
