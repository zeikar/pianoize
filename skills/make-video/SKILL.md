---
name: make-video
description: This skill should be used when the user wants a finished pianoize arrangement made into a falling-notes video and its YouTube upload prepared, e.g. "make the video", "render the falling-notes video for this song", "prepare the YouTube upload", "write the title, description and tags", "make the thumbnail". Writes the title card, has the local pianoize CLI render the MP4 and its thumbnail, and writes upload.md beside them, with the title and the description, its credits and hashtags, in English with a Korean translation, the tags, and the upload settings the arrangement's terms allow. Leaves the uploading to the user. Not for preparing a song (prepare-song), arranging it (arrange-cover, arrange-transcription) or polishing a cover (polish-cover).
---

# Make the video and its upload

pianoize renders an approved two-hand arrangement as a falling-notes video. This skill writes the title card, has `pianoize render-video` write the MP4 and its thumbnail, and writes `upload.md`: what the user pastes into YouTube Studio, in English, the video's default language, and in Korean, its translation.

## Rules

- **Credits are facts, with a source.** The song's title, the work it comes from, its composer and its rights holder come from the user, the arrangement's `notes.md` or a source you name. Write nothing you can't source. A credit found only on a fan wiki or the like is marked unconfirmed in `upload.md`, and you name it to the user.
- **The terms follow the arrangement.** An arrangement made from tsumugi-piano-cover's cover, an `arrange-cover` run whose folder holds `cover.regrid.mid`, is treated as non-commercial: monetization off, and the credit "Arrangement based on tsumugi-piano-cover (CC BY-NC 4.0)". One from the transcription alone, an `arrange-transcription` run with "Clean room" atop its `notes.md`, carries no such terms. Either way the song's own rights holder decides: where the song is under a creator's fan-work guidelines, follow them (pianoize's `docs/decisions.md`, "What goes into a video").
- **The SoundFont's credit line goes in every description:** "Piano sound: Salamander Grand Piano V3 by Alexander Holm (CC BY 3.0), via FreePats" for the default, or another SoundFont's own required credit.
- **Never paste song content into the repository.** The title card, the video and `upload.md` stay in `<out>` under `work/`, which is never committed.
- **Audio never leaves the machine.** Upload nothing: the user uploads.
- **Nobody but the user can watch it.** Look at the thumbnail yourself, but never claim the video looks or sounds right.

## Inputs

Ask the user for any input that is missing and stop until you have it.

- `<out>`: the arrangement's folder under `work/`, with `arranged.mid` and `notes.md`. If `notes.md` records no approval under "Revisions", ask whether the arrangement is final, and stop until they answer.
- The song's facts: its title, the work it comes from (a game, a film, an album, an artist), its composer and its rights holder. Take what `notes.md` and the user give, and ask for the rest, or look it up and say where you found it.
- For the render: FluidSynth and ffmpeg on `PATH`, Node.js with `npm ci` run once in `<root>/viewer`, the installed Google Chrome, and a piano SoundFont, `<sf2>`, unless `$PIANOIZE_SOUNDFONT` names one. `render-video` names whatever is missing: tell the user, and stop.

## The command line

- **Plugin root:** `${CLAUDE_PLUGIN_ROOT}`. If that is a directory with a `pyproject.toml` in it, this skill runs from the pianoize Claude Code plugin, and that directory is the plugin's own copy of pianoize: the command line is `uv run --project '<plugin root>'` followed by pianoize and its command, run from the current directory, and the docs are in `<plugin root>/docs/`. Otherwise (empty, still a `${…}` placeholder, or no `pyproject.toml` there) there is no plugin root: in a pianoize checkout, it is `uv run` followed by pianoize, run there, with the docs in its `docs/`; anywhere else, tell the user to install the pianoize plugin, and stop.
- Below, `<root>` is the plugin root, or without one, the checkout's root, and `pianoize <command> …` stands for the command line.
- Without `uv` on `PATH` (`command -v uv`), tell the user to install it (https://docs.astral.sh/uv/) and stop.
- **The docs:** `rendering.md` in the docs directory documents `render-video`, the cards file, the thumbnail and the timeline. `pianoize render-video --help` lists the options.
- **Quoting.** Single-quote every path in a command, writing a `'` inside it as `'\''`.
- **Errors.** A failing command prints `error: …` and exits 1; exit 2 is a usage error. Show the user the message and stop.

## Workflow

1. **Inputs.** Check `<out>`, the approval and the facts. From the folder and the top of `notes.md`, note whether the arrangement came from the cover or the transcription alone, for its terms.
2. **The title card:** write `<out>/cards.txt`, the lines drawn over the opening notes and on the thumbnail ("The cards file" in the docs): the song's name first, then where it comes from, two or three lines in all. The first line is drawn large, and on the thumbnail the last is a small tag. For example:
   ```
   A Made-up Song
   A Made-up Game OST
   ```
3. **Render:** `pianoize render-video '<out>/arranged.mid' --cards '<out>/cards.txt' -o '<out>/arranged.mp4'`, adding `--soundfont '<sf2>'` when you have one, in the background: it takes a few times the song's length. It prints the peak, the frame count, the length and the thumbnail's path, `<out>/arranged.jpg`. If it warns that the peak could clip, render again with a lower `--gain`.
4. **Look at the thumbnail,** `<out>/arranged.jpg`: the title readable, not cut, not shrunk to a small size. A first line too long for the band shrinks to fit: shorten the card's lines and render again.
5. **Write `<out>/upload.md`** following **`references/upload.md`**.
6. **Report** in the user's language: the video, the thumbnail and `upload.md`; the monetization the terms allow; every credit marked unconfirmed; and that they watch the video before uploading it. Stop until they answer.
7. **Revise** what they ask. A change to the title card renders again; a change to the text edits `upload.md`.

## Output files

All in `<out>`:

| file | written by | holds |
| --- | --- | --- |
| `cards.txt` | you | the title card |
| `arranged.mp4` | `render-video` | the video, 1920×1080 at 60 fps |
| `arranged.jpg` | `render-video` | the thumbnail, 1280×720 |
| `upload.md` | you | the title, the description and the tags, in English and Korean, and the upload settings |

## Additional resources

- **`references/upload.md`:** what `upload.md` holds, its shape, and how to write its title, description, hashtags and tags in both languages.
- **pianoize's `docs/rendering.md`:** `render-video`, the cards file, the thumbnail and the timeline.
