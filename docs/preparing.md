# Preparing a song

How pianoize makes a song's arranging inputs from its recording. `pianoize setup` installs tsumugi and tsumugi-piano-cover once, pinned, outside the repository. `pianoize prepare` decodes the recording, transcribes it with tsumugi, fits a steady tempo grid to the transcription, takes its melody and generates its piano cover: `transcription.mid`, `source.mid`, `melody.mid` and `cover.mid`. [docs/arranging.md](arranging.md) starts from the last three. An instrumental has no melody, and `melody.mid` is then left out or taken from the track `--melody-track` names. Both models run as separately installed tools, each with its own interpreter; pianoize imports neither. The reasons are in [docs/decisions.md](decisions.md#preparing-a-song).

```
pianoize setup
pianoize prepare AUDIO -o DIR [--melody-track NAME]
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
- **tsumugi's own checkpoints** (MIT), about 850 MB: nine files in the clone's `checkpoints/` and `beat_chord_checkpoints/`, from `anime-song/instrument_agnostic_amt`, and `stem-splitter/stem_splitter.pt`, from `anime-song/stem-splitter`. Setup fetches them with tsumugi's own fetch functions, run by tsumugi's interpreter in its clone, then checks each file's SHA-256 against the sum [docs/decisions.md](decisions.md#models-weights-and-tools-in-use) records. So `prepare` downloads nothing.
- **uv's own places.** uv builds both environments through its cache (`uv cache dir`, `~/.cache/uv` by default), which every uv project on the machine shares. Both environments run Python 3.12; where none is installed, uv downloads its own (`uv python dir`, `~/.local/share/uv/python` by default).

### Pins

| what | pin |
| --- | --- |
| tsumugi | commit `a700b8c` |
| tsumugi-piano-cover | commit `4f5c435` |
| tsumugi's checkpoints | each file's SHA-256 |
| the cover's weights | revision `12c8199` of `anime-song/tsumugi-piano-cover` |
| the generator's torch | 2.13.0 |

They are the tsumugi and tsumugi-piano-cover rows of [the license records](decisions.md#models-weights-and-tools-in-use), which give the full hashes and the licenses, with the SHA-256 sums listed under them, and the constants in `src/pianoize/tsumugi.py`; the two change together. tsumugi's environment takes every version from tsumugi's lock. tsumugi's checkpoints are fetched from their repositories' `main`, so they are pinned by content: a file whose SHA-256 differs from its recorded sum stops setup. The generator's other packages are not pinned.

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
- **FFmpeg's shared libraries**, which tsumugi's torchcodec loads to read the audio; `prepare` needs them, not setup. On macOS, Homebrew's (`brew install ffmpeg`). tsumugi's locked torchcodec 0.16 has no rpath to them, so pianoize sets `DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib` for the worker's process only, unless it is set already. Homebrew's FFmpeg is a GPL build, loaded only inside tsumugi's process, as [the license decisions](decisions.md#licenses) record.
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
| `transcription.mid` | tsumugi, through Cover Studio's worker | the band's transcription as tsumugi wrote it: a track per instrument, `drums` among them, the tempo map (`Predicted Tempo Map`), the chord markers (`Predicted Chords`) and the lead vocal, `melody`. It is kept and read only when `source.mid` is made |
| `source.mid` | pianoize, from `transcription.mid` | the transcription on a steady tempo grid ([below](#the-tempo-grid)), or a byte copy of it when the fit is not applied |
| `melody.mid` | pianoize, from `source.mid` | an unnamed first track with `source.mid`'s tempo changes and time signatures, no chord markers, then its `melody` track, or the track `--melody-track` names. An instrumental has no `melody` track, and then no `melody.mid` |
| `cover.mid` | tsumugi-piano-cover's generator, `piano_cover.generate`, from `source.mid` | the piano cover, seed 0 |
| `transcribe.log` | the transcription | tsumugi's output |
| `generate.log` | the generation | the generator's output |

A made-up run prints:

```
transcribing with tsumugi, about twice the song's length on an Apple-silicon Mac; log: /…/work/a-made-up-song/transcribe.log
transcribe: 431 s
tempo grid: 128.00 bpm, first downbeat at 0.512 s, 91% of 5210 attacks within a quarter sixteenth (29 ms)
tempo grid: tsumugi also ran 24% of its seconds at 64.00 bpm; the grid takes 128.00, the octave it held longer; check the bars by ear
generating the cover with tsumugi-piano-cover, about a third of the song's length on an Apple-silicon Mac; log: /…/work/a-made-up-song/generate.log
generate: 68 s
song.wav: 212.4 s
source.mid: 8 tracks: Predicted Tempo Map 0, Predicted Chords 0, (unnamed) 0, piano 1210, electric_bass 640, strings 455, melody 398, drums 1302
melody.mid: 398 notes
cover.mid: 2214 notes, 210.9 s
```

- **Each tool step** prints a line as it starts, naming its log, and its wall time in seconds when it ends. The decode and the melody print nothing. Every path printed is absolute.
- **The grid** prints one `tempo grid:` line when `source.mid` is made: the fit, or why it is not applied ([below](#the-tempo-grid)).
- **The summary** is the last four lines: `song.wav`'s length in seconds; `source.mid`'s tracks, each with its notes, in the file's order, a track without a name as `(unnamed)`; `melody.mid`'s notes, or on an instrumental `melody.mid: none: no track named 'melody'; --melody-track NAME takes a track as the melody`; `cover.mid`'s notes and its length in seconds. A note is a note-on with a velocity above 0. Every run that succeeds prints it, from reused files too.
- **The logs** hold each tool's output and errors in order, written a line at a time, so `tail -f` follows a run, and a progress bar's redraws come as lines of their own. The `@@` lines the worker streams to Cover Studio's page are left out. tsumugi's log names the device as it loads each model (`Loading … on mps`). A step that runs again starts its log afresh; a failed step's log stays.

### The tempo grid

tsumugi's tempo map comes from a beat tracker, which can run at half speed over a long stretch of a song and squeeze bars elsewhere. The bar lines then fall off the song's downbeats, and the cover model, which builds its beat rows from `source.mid`'s tempo map, bends its rhythm with them ([why](decisions.md#the-steady-tempo-grid)). So `prepare` fits one steady tempo to the transcription (`src/pianoize/steady.py`) and writes `source.mid` on it, before the melody and the cover are made. A fit that isn't good leaves the map alone, and `source.mid` is then tsumugi's file as it was.

- **An n/16 bar is read as n/4** first, its ticks and its tempo's bpm four times as many, so every event keeps its seconds. tsumugi writes stretches of a 4/4 song 4/16, the beat it tracked on the sixteenth: a 170 bpm beat becomes a quarter at 42.5 bpm, whose sixteenths are the song's quarters, so its eighths fall between them and the fit fails. Read as quarters, those bars are the 4/4 bars around them.
- **The attacks** are every note-on of every track, drums included, as distinct seconds rounded to the millisecond, so a chord counts once. Drums mark the beat best.
- **The tempo band** is 15% either side of tsumugi's dominant tempo, the median of its tempo segments weighted by their seconds, so the search cannot settle on double or half speed: a nearest-sixteenth cost always prefers double.
- **The octave** is tsumugi's to choose, since the attacks can't for eighth-note music: a nearest-sixteenth grid fits double at least as well, and eighths alone fit half as well as sixteenths. The band is around the dominant tempo, so the grid takes the octave tsumugi held longer. When half or double the fit holds any of the map's seconds, `prepare` prints a second line naming it ([below](#the-tempo-grid)), since the bars are then worth a listen.
- **The search** fits a sixteenth grid, a tempo and an offset: every tempo in the band on a 0.01 bpm step, and 32 offsets within a sixteenth. Its cost is the attacks' mean distance to the nearest sixteenth, each distance capped at three eighths of a sixteenth so a slip, an ornament or a triplet doesn't pull the grid. The step is 0.01 bpm because over a 5-minute song a 0.01 bpm error drifts 18 ms, so a coarse pass would miss it.
- **On the grid** means within a quarter of a sixteenth, 22 ms at 170 bpm. The window scales with the tempo so that attacks placed at random land on the grid half the time at every tempo; with a fixed window no single percentage could gate every song.
- **A good fit** has at least 300 distinct attacks and at least 70% of them on the grid. The best grid the search finds for randomly timed attacks over 60 s reaches 62% with 300 attacks, whatever the tempo, and up to 73% with 100; real transcriptions are far above both.
- **A sustained stretch the grid misses** refuses the fit, whether tsumugi's map tracked the change or not. The attacks are cut into spans of 10 s, and a span with at least 20 attacks counts as missed in either of two cases. Under 60% of its attacks are on the grid (random attacks are on it half the time). Or its tempo has changed: some other tempo, 0.5 to 2 times the fit and not within 5% of it, half or double it, has a beat occupancy of at least 0.8 and 0.3 above the fit's. Beat occupancy is the share of the span's quarter-note beats, at the span's best phase, that carry an attack within the window. Uniform eighths or sixteenths at the fit's tempo fill every beat of it, so nothing beats it; a quarter-note section at 120 bpm under a 150 bpm fit fills 1.0 of its own beats and about 0.2 of the fit's. Three missed spans in a row, 30 s, refuse it; a shorter intro or coda is allowed. On the two transcriptions it was tried on, the second test song and an instrumental, no span has changed tempo, and the misses never run past two spans, whatever the alignment.
- **The first downbeat** comes from tsumugi's own bar lines. Each bar line inside a tempo segment within 5% of the fitted tempo votes for the sixteenth of the bar it falls on, and that sixteenth must hold more than half of the votes. Where tsumugi's tempo is right its bars are right. A tempo a little off passes the 5% test but drifts through every sixteenth of the bar, so it gets no majority. A downbeat within the window of a bar line counts as the bar line.
- **What changes** is the tempo map and the ticks, never a note's time. The new map is the steady tempo from tick 0. When the song starts off a downbeat, bar 1 is a pickup bar at the tempo that fits it into the seconds before the first downbeat, and the steady tempo starts at bar 2; this keeps tick 0 at 0 s and the bar lines on the downbeats. Every event of every track moves to the tick nearest its seconds, so it keeps them within half a tick. Type, resolution, track order, tsumugi's meter and every other message stay as they were, except a time signature whose bar is not the first one's length, which is dropped: the grid keeps tsumugi's first meter through the song.
- **When it is applied,** the line is `tempo grid: B bpm, first downbeat at D s, P% of N attacks within a quarter sixteenth (W ms)`. When half or double the fit also holds any of tsumugi's seconds, one more line follows: `tempo grid: tsumugi also ran P% of its seconds at C bpm; the grid takes B, the octave it held longer; check the bars by ear`. When tsumugi's meter changes its bar length, as when its beat tracking flips to the other octave mid-song, another follows: `tempo grid: tsumugi changes meter at tick T, 2/2 to 1/2; the grid keeps 2/2 through the song; check the bars by ear`.
- **It is not applied** when one of these holds, and `source.mid` is then a byte copy of `transcription.mid`. The line is `tempo grid: keeping tsumugi's tempo map: ` and the reason:
  - `N distinct attacks, fewer than 300`.
  - The first meter is not a whole number of sixteenths (the error is `bars.first_meter`'s own text).
  - `best fit B bpm puts P% of N attacks within a quarter sixteenth, under 70%`.
  - `B bpm does not hold through the song: K spans of 10 s in a row miss it`, then either `; their beats sit nearer C bpm` or `, under 60% of their attacks on the grid`.
  - `none of tsumugi's bars run within 5% of B bpm, so the downbeats are unknown`.
  - `tsumugi's bars agree on no downbeat: the most-voted sixteenth holds K of M bar lines`.
- **The limits.** One steady tempo or none: a song that really changes tempo, or has a rubato stretch, keeps its seconds there and its bar lines sit off the bars, because the grid does not follow it. A song tsumugi tracks at the wrong octave for most of its length grids at that octave, every note keeping its seconds, and the second line above is the warning; the attacks can't settle it for eighth-note music (the second test song fits half speed 87% against 89%). Notes are not quantized: they keep their seconds.
- **`regrid` stays** ([docs/arranging.md](arranging.md#regridding)) for covers made before the grid and for songs whose fit is not applied.

### Devices and time

tsumugi runs on CUDA, else MPS, else the CPU; the generator on CUDA, else the CPU. On an Apple-silicon Mac, the transcription takes about twice the song's length, on MPS, and the cover about a third of it, on the CPU: in M1, 496 s and 75 s for a 251 s song.

### Reusing outputs

A step whose output is already in `DIR` is skipped, with `reusing <path>`, and the steps after it read that file. Each output is matched by its name alone, each on its own: `prepare` doesn't check which recording, or which `source.mid`, a file came from. `transcription.mid` is looked for only when `source.mid` is missing. So:

- **One directory per recording.** Run another recording into a directory that holds a song's files, and it reuses them.
- **A failed or stopped run** is finished by running the same command again: what it finished is reused.
- **Redoing a step** means deleting its output and every output made from it:

  | to redo | delete |
  | --- | --- |
  | `song.wav` | all five: `song.wav`, `transcription.mid`, `source.mid`, `melody.mid` and `cover.mid` |
  | `transcription.mid` | it and the three made from it: `source.mid`, `melody.mid` and `cover.mid`. A new transcription is a new draw |
  | `source.mid` | it, `melody.mid` and `cover.mid`: it is gridded again from `transcription.mid`, which is transcribed first if there is none |
  | `melody.mid` | `melody.mid` alone |
  | `cover.mid` | `cover.mid` alone |

- **A directory from before the grid** has a raw `source.mid` and no `transcription.mid`. It is reused as it is and runs no tool; nothing is migrated. To grid its draw, copy `source.mid` to `transcription.mid`, then delete `source.mid`, `melody.mid` and `cover.mid`. This applies to a directory made before 2026-10-14.
- **`--melody-track`.** A known name reuses an existing `melody.mid`, whichever track it was made from; delete `melody.mid` to take another track. An unknown name is refused before `melody.mid` is reused.

The install is checked before any step, so even a run that would reuse all five needs it.

### Writing

Each output appears whole or not at all. `song.wav`, `source.mid` and `melody.mid` are written by pianoize to a scratch file beside their destination and renamed into place. The tools write `transcription.mid` and `cover.mid` into a scratch directory, `.prepare-*` in `DIR`, from which each is renamed into place once its step succeeds. The scratch directory also holds tsumugi's stems while it runs, and is removed when the run ends, whether it succeeds, fails or is [stopped](#stopping). A run killed outright, by SIGKILL (`kill -9`) or a crash, leaves its `.prepare-*` directory behind, and later runs don't sweep it: delete it by hand. Either way, a failed or stopped step leaves no output, never a partial one, and a file `prepare` reuses is a finished one.

### Stopping

Ctrl-C, `kill` (SIGTERM) and closing the terminal (SIGHUP) stop it the same way: a running tool is terminated and waited for, the scratch directory is removed, and `prepare` exits 130 with no message. The outputs finished before the stop stay, for the next run to reuse.

### Errors

Usage errors exit 2: an `AUDIO` that doesn't exist or is a directory, no `-o`, a `DIR` whose `song.wav` would be `AUDIO` itself (`would overwrite an input`), and a `--melody-track` the transcription doesn't have (`no track named 'NAME'; tracks named: …`, listing the named tracks). Everything else prints one line and exits 1. Most name their step, and a tool's failure names the tool:

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
- **melody** fails on a `source.mid` without a tempo map. A missing `melody` track is no error: an instrumental has no `melody.mid`. A missing track named by `--melody-track` is a usage error, above.
- **A file in `DIR` that isn't MIDI**, reused as `transcription.mid`, `source.mid`, `melody.mid` or `cover.mid`, fails as `<path>: cannot read MIDI: …`. A corrupt `transcription.mid` fails every rerun that needs it; delete it to transcribe again.
- **A `DIR` that can't be made**, or an output that can't be moved into place, prints the system's error.

A failed step keeps every output made before it, and its log.

### Determinism

tsumugi's transcription is one draw, not a result a second run repeats ([decision](decisions.md#preparing-a-song)), so `transcription.mid` is kept and reused rather than made again. The grid is deterministic: the same `transcription.mid` gives a byte-identical `source.mid`. The cover is generated with seed 0. On the development Mac the same `source.mid` gave a byte-identical `cover.mid` on the CPU; this page claims no more for other machines.

## Running the skill

The `prepare-song` skill in `skills/prepare-song/` makes a song's arranging inputs from a YouTube link or an audio file: its `SKILL.md` gives the steps and the files, and `references/download.md` the download, yt-dlp run through `uvx` from uv's cache. It checks for uv and ffmpeg, downloads the audio for a link, runs `pianoize setup` and `pianoize prepare`, reports the summary (on an instrumental, `melody.mid` is none unless `--melody-track NAME` names an instrument's track), and offers the result to `arrange-cover` or `arrange-transcription` ([docs/arranging.md](arranging.md#running-the-skills)) without starting the arrangement. It ships in the same Claude Code plugin as the other skills; the plugin's layout and how to install it are in [docs/polishing.md](polishing.md#running-the-skill).
