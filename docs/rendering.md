# Rendering

How pianoize turns a two-hand arrangement into a falling-notes video: the notes as JSON, the title card, a preview in a browser, and the MP4 with its thumbnail and description. The commands read the MIDI `build-arrangement` writes ([docs/arranging.md](arranging.md)) and render it with the SoundFont as `pianoize render` does ([docs/evaluation.md](evaluation.md#rendering-a-midi-file)). The CLI never calls an LLM, and the same inputs give the same JSON, audio and frames. The reasons are in [docs/decisions.md](decisions.md).

```
pianoize export-arrangement ARRANGED.mid -o ARRANGED.json
pianoize preview-video ARRANGED.mid --cards CARDS.txt
pianoize render-video ARRANGED.mid --cards CARDS.txt -o OUT.mp4
```

## The arrangement JSON

`pianoize export-arrangement ARRANGED.mid -o OUT.json` writes the notes of a two-hand MIDI as the JSON the viewer draws. The viewer reads nothing else about the music. The MIDI must have a track named `Right Hand` and one named `Left Hand`, as `build-arrangement` names them.

| field | meaning |
| --- | --- |
| `format_version` | The format's version, `1`. |
| `notes` | Every note of both hands, sorted by `on`, then `pitch`, then `hand` (`left` before `right`). |
| `notes[].pitch` | The MIDI pitch, 21 to 108: the 88 keys, A0 to C8. |
| `notes[].hand` | `right` or `left`, from the track the note is on. |
| `notes[].on` | The onset in seconds, through the MIDI's tempo map, rounded to 6 decimals. |
| `notes[].off` | The end in seconds, rounded the same way. A pitch struck again before its note-off ends at the new strike. |

The file has one note a line, so a re-run diffs clean:

```json
{"format_version": 1, "notes": [
{"pitch": 72, "hand": "right", "on": 0.0, "off": 0.5},
{"pitch": 48, "hand": "left", "on": 0.0, "off": 2.0},
{"pitch": 74, "hand": "right", "on": 0.5, "off": 1.0},
{"pitch": 76, "hand": "right", "on": 1.0, "off": 2.0}
]}
```

It prints the notes per hand and the MIDI's length, from its first tick to its last, which is where the pedal and the ring-out end:

```
notes: 3 right hand, 1 left hand
length: 2.0 s
```

- **Errors.** An `-o` that is the MIDI, under any spelling the disk takes for it, is refused with `would overwrite an input` and exits 2. A MIDI without a `Right Hand` or a `Left Hand` track, with two tracks of one name, or with a pitch off the keyboard prints `error: …` and exits 1, writing nothing.
- **Repeatable.** The same MIDI gives byte-identical JSON.
- **Breaking changes.** A change to this format is breaking and bumps `format_version`. `viewer/roll.js` refuses a file with another version, and `tests/test_roll.py` checks that this page's example, the export and the viewer agree on the number.

## The cards file

A cards file is a UTF-8 text file with the title card's lines, and optionally a line with only `---` and the video description's credits, which the video doesn't draw. It lives in `work/` with the song's text; the song's title and artists are not in the repository.

```
A Made-up Song
Someone

---
Arrangement: tsumugi-piano-cover, edited
Piano sound: a made-up credit line
```

- **Splitting.** The title card ends at the file's first line that is `---` once stripped; without one, the whole file is the title card. Nothing after that line is drawn.
- **Trimming.** Each line loses its trailing spaces, and the title card loses its blank lines at the start and the end. A blank line inside it stays, and takes a line's room. Its first line is drawn large, the rest smaller.
- **The description** is the text after `---`, which `render-video` writes to `OUT.txt` with each line's trailing spaces and the blank lines at its start and end trimmed: the credits, the attributions in [What goes into a video](decisions.md#what-goes-into-a-video) and the SoundFont's credit line from [MIDI is rendered with FluidSynth](decisions.md#midi-is-rendered-with-fluidsynth), and any hashtags.
- **Errors.** An empty title card is refused with `error: …` and exit 1. A cards file that can't be read as UTF-8 is refused the same way.

## Previewing

`pianoize preview-video ARRANGED.mid --cards CARDS.txt [--soundfont SF2] [--gain G]` serves the video as a page to watch in a browser. `--soundfont` defaults to `$PIANOIZE_SOUNDFONT`, and `--gain` to 0.5, as in `render`.

```
peak 0.412
preview: http://127.0.0.1:52341/
press Ctrl-C to stop
```

It exports the notes, renders the audio with FluidSynth, pads it to the video's timeline ([below](#the-timeline)), and prints the peak, with a `warning: peak … may clip; lower --gain` on stderr at 0.99 or more. Then it serves the page and waits.

- **The URL** is on 127.0.0.1 only, on a free port, so nothing off the machine can read the song.
- **The player** is under the picture: play and pause, the time and a seek bar. A click on the picture or Space plays or pauses, and the arrow keys seek 5 s.
- **The effects panel**, opened with "Effects" beside the player, has a slider for each of the glow, the flare, the beam and the sparks, from 0% (off) to 200%, and a reset. It changes only what this page draws: the video draws `style.js`'s values, so a level worth keeping goes into `style.js`. The picture follows the hidden `<audio>` element's clock, so a seek moves the picture too. The page loads its audio whole, so the preview needs no range requests.
- **Stopping.** Ctrl-C stops it, and so do `kill <pid>` and closing the terminal: SIGTERM and SIGHUP take the same path as Ctrl-C.
- **Scratch files.** The run's files are in a `.preview-*` directory beside the MIDI, which the stop removes, so the song's files stay in `work/`.
- **Errors.** As for `render-video` below. The preview needs no Node, Chrome or ffmpeg, only a browser.

## Rendering the video

`pianoize render-video ARRANGED.mid --cards CARDS.txt -o OUT.mp4 [--soundfont SF2] [--gain G]` writes the MP4, and beside it what an upload needs: `OUT.jpg`, its [thumbnail](#the-thumbnail), and `OUT.txt`, its description, the cards file's text after `---`, when it has any. One run does this, in order:

1. Exports the notes, checks the cards and picks the thumbnail's moment.
2. Renders the audio with FluidSynth and pads it to the timeline.
3. Starts the local server on 127.0.0.1.
4. Captures the page in Chrome, a PNG per frame.
5. Pipes the frames and the audio into ffmpeg.
6. Captures the thumbnail once, and has ffmpeg encode it as a JPEG.
7. Replaces `OUT.txt`, `OUT.jpg` and `OUT.mp4` with the results.

Its scratch directory, `.video-*`, sits beside `OUT.mp4` and is removed when the run ends. The files are replaced only at the end, so a failed or interrupted run leaves any existing ones as they were. It prints the peak, the same warning, then the frame count, the video's length and the files written beside it:

```
peak 0.412
frames: 5400
length: 90.0 s
thumbnail: video.jpg
description: video.txt
```

A video named with `.jpg` or `.txt` is refused, since its thumbnail or description would take its name.

### The thumbnail

1280×720, YouTube's size, as a JPEG. It shows the moment with the most notes on screen, falling or sounding, among the music's quarter-seconds, the earliest on a tie. The frame there is zoomed in by 4/3, the keys kept at the bottom, and centred on the middle pitch of those notes. A dark band fades down over its top, and the title card's lines go on it: the first large, the last as a small tag in the right hand's light, any between them as a subtitle. A line too wide for the band shrinks to fit. Its sizes and colours are `style.js`'s `thumbnail`; it is drawn at the frame's size and scaled down by ffmpeg.

### The timeline

| part | seconds |
| --- | --- |
| Title card | 0 to 3, over the roll as the first notes fall in, fading out over its last `cards.fadeSeconds` (0.5, in `viewer/style.js`) |
| Music | from 3 (`INTRO_SECONDS`, one `fall.seconds` of `viewer/style.js`, so the first notes land as it starts) to the later of the audio's end and the MIDI's end, rounded up to a whole frame; the video ends there |

The audio's end is FluidSynth's release tail; the MIDI's end is its last tick. The frame rate is `FPS` = 60. These constants are in `src/pianoize/video.py`.

### The format

1920×1080 at 60 fps. H.264 (libx264, CRF 18), yuv420p, tagged BT.709. AAC at 192 kbit/s. The moov atom is at the front (`+faststart`), so it plays while it downloads.

### The tools

- **Chrome** is the installed Google Chrome, driven through `playwright-core` from `viewer/`. No browser is downloaded.
- **ffmpeg** and **FluidSynth** run as subprocesses. They are separately installed tools.
- **Node.js** runs `viewer/capture.mjs`. Install its one dependency once, in `viewer/`, with `npm ci`.

### Errors

Usage errors exit 2: an `-o` that is the MIDI, the cards file or the SoundFont (`would overwrite an input`), a MIDI or cards file that does not exist, and no `--soundfont` with `$PIANOIZE_SOUNDFONT` unset. Everything else prints `error: …` and exits 1:

- an `-o` that is a directory, before anything renders;
- `node not found on PATH; install Node.js`;
- `ffmpeg not found on PATH; install ffmpeg`;
- `playwright-core is not installed; run npm ci in …/viewer`;
- the arrangement and cards errors above, a SoundFont FluidSynth can't load, a missing FluidSynth, and a failed ffmpeg, whose last lines are printed;
- `node failed (N); its error is above`, when Chrome did not start or the page did not load.

Ctrl-C and `kill` stop the capture and ffmpeg, close Chrome, and leave no scratch directory.

### Repeatability

Two renders of the same inputs with the same Chrome and ffmpeg gave identical frames, and identical MP4 bytes. Chrome updates itself, so the frames can change between Chrome versions.

## The viewer

`viewer/` is the page, plain ES modules with no build step. Python serves it and the run's files, and Chrome captures it. It is also published on GitHub Pages ([below](#on-github-pages)).

| file | what it is for |
| --- | --- |
| `index.html`, `style.css`, `controls.css` | The page: the canvas, the player under it, and on the home page the project's introduction and the file picker. `controls.css` styles the picker and the player, `style.css` the rest. The CSS takes its colours, font and corner radius from `style.js` through custom properties that `main.js` sets; only the page's own layout sizes are in it. |
| `style.js` | Every colour, the frame's sizes, and the fall time (`fall.seconds`). No other module holds one. Timing that is not the fall time lives in Python. |
| `keyboard.js` | The 88 keys: their layout, the positions and sizes of the white and black keys, and drawing them, each lit by the hand pressing it, with the felt's shadow and the black keys' bevels. |
| `falling.js` | Draws the falling notes and their glow. |
| `sparks.js` | The light where a note meets its key: the flare, the beam and the sparks, each a function of the time alone. |
| `effects.js` | The effects panel under the player, and `tune()`, which scales the glow, the flare, the beam and the sparks by its levels. |
| `roll.js` | The data: `FORMAT_VERSION`, loading the notes, the title card's opacity at a time, which keys are pressed, and the falling notes' rectangles. |
| `draw.js` | Draws one frame at a time `t` on the canvas: the roll's background, the falling notes under the keyboard and the light over both, or a card. |
| `picker.js` | The file picker: takes the chosen or dropped files, checks the JSON and the audio, and shows what is missing and what went wrong. It draws nothing. |
| `transport.js` | The player: play and pause, the time, the seek bar, and the click and keys for them, over the `<audio>` element. |
| `main.js` | Loads the manifest and the notes, and runs the page in one of its three modes. |
| `capture.mjs` | Loads the page in Chrome and writes a PNG per frame to stdout, with Chrome's fast PNG encoder. |
| `social.png` | The page's link preview (`og:image`), which is also the README's hero and the repository's social preview: a 1920×960 frame the viewer drew from made-up notes, beside the name and the tagline. |
| `social.html`, `social.mjs` | Draw `social.png`. The page holds the notes, the text and its layout, with the colours and the font from `style.js`; `node social.mjs` captures it in Chrome, without the GPU so that a run with nothing changed writes the same bytes. Run it again when the look changes. |
| `test/` | Node tests of the layout, the data, the sparks and the effects' tuning. |

- **The manifest.** The run's directory is served at `/run/`. `/run/manifest.json` names the run's `arrangement.json` and `audio.wav`, and holds the cards' lines and the timeline's `music_start`, `music_end` and `end`.
- **Three modes.** With a run and no query, the page is the preview: the canvas fills the window above the player, and a frame is drawn at the audio's time on every animation frame. With `?capture` only the canvas shows, at its own size, and the page draws nothing by itself; `capture.mjs` calls `window.pianoize.drawAt(t)` for frame `i` at `t = i / FPS` and screenshots it. Where `run/manifest.json` is a 404, as on GitHub Pages, it is the home page. It fetches the run's files by relative paths, so it works below a path too.
- **The sync rule.** A key lights while `on <= tMusic < off`, where `tMusic` is the video's time minus `music_start`. A note's key lights on the first frame at or after its onset, so within one frame (1/60 s) of the sound's start. The sync test measured the key lighting on the onset's frame, while the Salamander piano's attack passes −40 dBFS (0.01) about 20 ms later. The flare, the beam and the sparks start at the note-on too, and none reaches the keys' bottom 40 pixels, which the test reads.
- **Tests.** `cd viewer && npm ci && npm test` runs the Node tests. They need no browser.
- **The npm cache** is npm's default, `~/.npm`.

The Python tests are `tests/test_roll.py`, `tests/test_video.py` and `tests/test_serve.py`. `uv run --frozen pytest -m "not video"` skips the slow ones that capture in Chrome and encode. The sync test also needs `PIANOIZE_SOUNDFONT` and FluidSynth.

### On GitHub Pages

The page is at <https://zeikar.dev/pianoize/>; `zeikar.github.io/pianoize/` redirects there. It is the project's home page: what pianoize does, the stage with an empty keyboard and the file picker on it, the player, and the steps that make an arrangement. It asks for two files, chosen with its button or dropped anywhere on the page:

- **The arrangement JSON**, from `pianoize export-arrangement`, which the arranging skills run beside the render. A file that isn't JSON, has another `format_version`, has no `notes` array or has a pitch off the 88 keys is refused with its error. A MIDI is refused with a pointer to `export-arrangement`.
- **Its audio**, such as the WAV `pianoize render` writes from the same MIDI. Any audio the browser plays will do; its metadata is read in a scratch element first, and audio the browser can't play is refused. It is required: the `<audio>` element is the page's clock.

A refused file replaces nothing, so what plays keeps playing. The error shows in the picker while a file is missing, and under the player once both play.

The files are read in the browser and sent nowhere. The picker lists which of the two it has, so they can come one at a time. A pick replaces the files of the kinds it holds: new audio keeps the arrangement, and a new arrangement on the same audio keeps its place. Once both are there, the picker gives way to the stage, with "Choose other files" under the player, and the page scrolls the stage and the player into view with the focus on Play. On a short window the stage narrows so that both fit one screen. The audio's 0 s is the music's 0 s, so there are no cards and no lead-in: notes that start in the first 3 s (`fall.seconds`) are already falling at 0 s. On a phone the picker sits under the stage, since the roll is too short to hold it.

`.github/workflows/pages.yml` publishes it on a push to `main` that touches `viewer/` or the workflow, and on a manual run. The repository's Pages source is set to GitHub Actions; without that, the deploy fails. It uploads only `index.html`, the stylesheets, the `*.js` modules and `social.png`, not `capture.mjs`, `social.html`, `social.mjs`, the tests or the npm files.
