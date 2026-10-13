# Downloading the audio

How to get a link's audio into `<song>`. SKILL.md gives `<song>` and the rules; follow them where they add to these.

**Quoting.** The pasted link, the page URL yt-dlp prints and the file name are untrusted text. In every command that takes `<url>`, `<audio>` or a path built from it, single-quote the argument, writing each `'` in it as `'\''`. Double quotes would let `$(…)` or backticks run.

yt-dlp runs through `uvx`, from uv's cache, so nothing is installed on `PATH`, and the file stays on the machine.

1. **Check the tools** with step 1 of SKILL.md before downloading anything: the download needs `uvx` and ffmpeg.
2. **Download.** In `<song>`, run `uvx --from 'yt-dlp[default,deno]@latest' yt-dlp --no-playlist -I 1 -x --audio-format mp3 --print after_move:webpage_url --print after_move:filepath -- '<url>'`, in a subshell, `(cd '<song>' && uvx …)`, so the session's directory stays where it was. Allow a timeout of up to 10 minutes.
   - `@latest` takes the newest yt-dlp on every run, since an old one stops working when YouTube changes, and the `deno` extra brings the JavaScript runtime yt-dlp needs for YouTube. The first run fetches them, about 40 MB, into uv's cache; later runs reuse it.
   - It fetches one video's audio as mp3, since pianoize's decoder reads wav, flac, ogg and mp3 but not m4a or webm. A link to a video in a playlist takes that video. For a playlist or channel link with no video in it, that is the playlist's first video: tell the user which one, by its title and page URL.
   - It prints two lines: the video's canonical page URL, then the file's absolute path. The file is named `<title> [<id>].mp3`, such as `A Made-up Song [abc123].mp3`, and stays in `<song>`. Use that path as `<audio>`.
3. **If yt-dlp fails,** show its message and stop. Report a private, removed or restricted video to the user as such; don't work around it.
4. **Keep `<audio>`** for the rest of the session, so a second request for the same video needs no second download.
