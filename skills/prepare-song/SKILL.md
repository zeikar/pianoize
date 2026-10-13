---
name: prepare-song
description: This skill should be used when the user wants a song's arranging inputs made with pianoize from a YouTube link or an audio file, e.g. "prepare this song", "get the cover and melody for this link", "download and transcribe this song", "set up tsumugi". Downloads a link's audio with yt-dlp, has the local pianoize CLI install tsumugi and tsumugi-piano-cover once, transcribe the song with tsumugi, take its melody and generate its piano cover, reports what it wrote, and offers the files to an arranging skill. Not for arranging (that is arrange-cover or arrange-transcription), for polishing a cover (that is polish-cover), or for rendering the audio or the falling-notes video.
---

# Prepare a song for arranging

pianoize arranges a song from files made from its recording: tsumugi's transcription of the band, `source.mid`; its sung melody, `melody.mid`; and tsumugi-piano-cover's piano cover, `cover.mid`. This skill makes them. Given a link, you download the audio. `pianoize setup` installs the two models once, pinned, outside the repository. `pianoize prepare` decodes the audio, transcribes it, takes the melody and generates the cover.

pianoize's commands never call an LLM. You run them, wait for them and report what they wrote; nothing here asks you to judge the music.

## Rules

- **Audio never leaves the machine.** The download and the models run here. Upload nothing.
- **Never commit, and never paste song content into the repository.** The audio and every file made from it stay in `<song>` under `work/`, which is never committed. The song's title, link, track list and note counts go into no docs, tests, code, commit messages or issues.
- **Install nothing on `PATH`.** yt-dlp runs from uv's cache through `uvx`, and `pianoize setup` installs into its own home. Never install a tool yourself: tell the user what is missing, and stop.
- **An existing `source.mid` is kept.** Each transcription is one draw, so `prepare` reuses it, as it reuses every output it finds. Redoing any step is the user's call: only when they ask, delete that output and the ones made from it, as "Reusing outputs" in the docs lists, and run `prepare` again.
- **Relay the terms.** The first `pianoize setup` prints the terms of tsumugi-piano-cover's weights before it downloads them: CC BY-NC 4.0, attribution, non-commercial use only. Tell the user, and that the cover, and anything arranged from it, is treated as non-commercial.

## Inputs

Ask the user for any input that is missing and stop until you have it.

- `<link>`, a YouTube link, or `<audio>`, an audio file: wav, flac, ogg or mp3. Convert any other format, an m4a for one, locally first: `ffmpeg -i '<file>' '<song>/<file stem>.flac'`.
- `<song>`: this recording's directory, `work/<name>/`, with a name the user gives. Create it with `mkdir -p`. `prepare` reuses any of its outputs it finds there, by name alone, so a directory that holds another recording's files would mix two songs: ask for another.

Single-quote every path in a command, writing a `'` inside it as `'\''`: song file names carry spaces, brackets and other characters the shell would read.

## Running pianoize

- **Plugin root:** `${CLAUDE_PLUGIN_ROOT}`. If that is a directory with a `pyproject.toml` in it, this skill runs from the pianoize Claude Code plugin, and that directory is the plugin's own copy of pianoize: run `uv run --project "<plugin root>" pianoize <command> …` from the current directory. Its first run builds the environment, so allow a few minutes. Otherwise (empty, still a `${…}` placeholder, or no `pyproject.toml` there) there is no plugin root: in a pianoize checkout, run `uv run pianoize <command> …` there; anywhere else, tell the user to install the pianoize plugin, and stop.
- Without `uv` on `PATH`, tell the user to install it (https://docs.astral.sh/uv/) and stop.
- Below, `pianoize <command> …` stands for that command line.
- **The docs:** `<plugin root>/docs/preparing.md`, or `docs/preparing.md` in the checkout, documents both commands: what setup installs and where, `prepare`'s files, its reuse, its errors and its summary. `pianoize <command> --help` lists a command's options.
- **Errors.** A failing command prints `error: …` and exits 1, most naming the step, and the tool where one failed: `tsumugi transcribe failed (1): RuntimeError: …; log: …/transcribe.log`. Show the user the message and, where it names a log, the log's last lines (`tail -n 20 '<log>'`), and stop. A missing tool, `git not found on PATH` or `uv not found on PATH`, is the user's to install: tell them, and don't work around it. Exit 2 is a usage error: show its message. An error saying the tools are not installed under the pianoize home means step 3 didn't finish: run it.

## Workflow

1. **Check the tools,** for a link and a file alike, before anything downloads or installs:
   - `command -v uv`: setup, prepare and yt-dlp all run through it;
   - `command -v git`: setup clones the two models with it;
   - `command -v ffmpeg`: yt-dlp converts the audio with it, and tsumugi reads the audio through torchcodec, which loads FFmpeg's libraries. On macOS, Homebrew's ffmpeg provides both, and the libraries must be Homebrew's, since the worker looks only there: `ls /opt/homebrew/lib/libavutil*.dylib`.

   Without any of them, tell the user what to install (uv: https://docs.astral.sh/uv/; git: the system's; ffmpeg: `brew install ffmpeg` on macOS) and stop, installing nothing.
2. **Get the audio.** For a `<link>`, follow **`references/download.md`**: it leaves the audio in `<song>` and gives you `<audio>`. For a file, use it as `<audio>` where it is.
3. **Set up:** `pianoize setup`. Run it in the background and wait for it to end; its progress is the background task's output. The first run clones two repositories, builds two torch environments and downloads about 1.6 GB of weights, tsumugi's checkpoints and the cover's, which takes minutes. uv may also download a Python 3.12 into its own directory. Tell the user in one line before it starts, and go on without waiting for a reply. It prints the cover weights' terms before their download: relay them (see Rules). Later runs check the install, hash tsumugi's checkpoints and download nothing. A setup that failed or was stopped is finished by running it again, once the user has fixed the cause.
4. **Prepare:** `pianoize prepare '<audio>' -o '<song>'`, in the background. It decodes the audio to `song.wav`, transcribes it into `source.mid`, takes `melody.mid` from it and generates `cover.mid`. On an Apple-silicon Mac the transcription takes about twice the song's length and the cover about a third; tsumugi on the CPU takes longer. Tell the user the expected time once. Progress is in `<song>/transcribe.log`, then `<song>/generate.log`: check the current one with `tail -n 5 '<log>'` now and then, not continuously. A file `prepare` finds in `<song>` is reused (`reusing …`), so after a failure or a stop, the same command picks up where it stopped. A stopped run (Ctrl-C or `kill`) exits 130 with no message, keeping the outputs it finished.
5. **Report** the summary it prints last (the song's length, `source.mid`'s tracks with their notes, `melody.mid`'s notes, and `cover.mid`'s notes and length) and the files in `<song>`.
6. **Hand off, without starting the arrangement.** Ask the user which path to take, and stop until they answer:
   - **`../arrange-cover/SKILL.md`**, the default: `<song>/cover.mid` as its `<cover>`, `<song>/melody.mid` as `<melody>` and `<song>/source.mid` as `<source>`.
   - **`../arrange-transcription/SKILL.md`**, experimental: `<song>/source.mid` and `<song>/melody.mid`, and no cover. It avoids the cover's CC BY-NC terms. And the cover model builds its beats from `source.mid`'s tempo map, so where the beat tracking went wrong, bars at half speed or squeezed, the cover's rhythm bends with it, while the transcription's notes stay timed from the audio. But its first trial left the left hand unsettled, so `arrange-cover` stays the default (pianoize's `docs/decisions.md`, "The transcription-only arrangement, an experiment").

   Give them the chosen skill's inputs. Arranging starts when they ask for it.

## Output files

All in `<song>`:

| file | written by | holds |
| --- | --- | --- |
| `<title> [<id>].mp3` | yt-dlp, for a link | the downloaded audio, `<audio>` |
| `song.wav` | `prepare` | the audio as a 16-bit WAV at its own rate and channels |
| `source.mid` | `prepare`, with tsumugi | the band's transcription: a track per instrument, the drums among them, a tempo map, chord markers and the lead vocal, `melody` |
| `melody.mid` | `prepare` | the `melody` track on the transcription's tempo map and time signatures |
| `cover.mid` | `prepare`, with tsumugi-piano-cover | the piano cover generated from `source.mid`, seed 0 |
| `transcribe.log` | `prepare` | tsumugi's output: its progress, and its error after a failure |
| `generate.log` | `prepare` | the generator's output |

## Additional resources

- **`references/download.md`:** downloading a link's audio with yt-dlp through `uvx`, what it prints, a playlist link, and its failures.
- **pianoize's `docs/preparing.md`** (see "Running pianoize"): what setup installs and where, its pins and how to remove it, and `prepare`'s files, reuse, redoing a step, errors and summary.
