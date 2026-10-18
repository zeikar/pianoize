"""The falling-notes video's timing, cards and padded audio, the capture and encode that make the
MP4, and the thumbnail and description that go with it."""

import json
import math
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

import mido
import numpy as np
import soundfile

from . import render, roll, serve

FPS = 60
FALL_SECONDS = 3.0  # style.js's fall.seconds: how long a note is on screen before it sounds
# Where the music starts: one fall time, so the first notes fall in under the title card and land
# as the music starts.
INTRO_SECONDS = FALL_SECONDS
THUMBNAIL_SIZE = (1280, 720)  # YouTube's
MOMENT_STEP = 0.25  # seconds between the music times a thumbnail is chosen from
# The viewer is page assets, not Python, so it stays at the checkout's top level rather than
# inside the package; pianoize runs from a checkout.
VIEWER = Path(__file__).resolve().parents[2] / "viewer"


class VideoError(Exception):
    pass


def cards(text: str) -> dict[str, list[str]]:
    """The title card's lines: the cards file up to its first `---` line, or all of it. What
    follows a `---` line is the description's text, which the video doesn't draw."""
    lines = text.splitlines()
    at = next((i for i, line in enumerate(lines) if line.strip() == "---"), len(lines))
    title = _trim(lines[:at])
    if not title:
        raise VideoError("the title card is empty")
    return {"title": title}


def description(text: str) -> str | None:
    """The video's description: the cards file after its first `---` line, each line's trailing
    spaces and the blank lines at its start and end trimmed. None when there is none."""
    lines = text.splitlines()
    at = next((i for i, line in enumerate(lines) if line.strip() == "---"), None)
    body = [] if at is None else _trim(lines[at + 1 :])
    return "\n".join(body) + "\n" if body else None


def thumbnail_moment(notes: list[dict], music_seconds: float) -> dict:
    """Where the thumbnail looks: the music time, in MOMENT_STEP steps, with the most notes on
    screen, falling within one fall time of their onset or sounding, the earliest on a tie; and
    the middle pitch of those notes, which it centres on (middle C with none)."""
    best_time, best = 0.0, []
    last = math.floor(max(music_seconds - FALL_SECONDS, 0.0) / MOMENT_STEP)
    for step in range(last + 1):
        t = step * MOMENT_STEP
        shown = [n["pitch"] for n in notes if n["on"] < t + FALL_SECONDS and n["off"] > t]
        if len(shown) > len(best):
            best_time, best = t, shown
    pitch = sorted(best)[len(best) // 2] if best else 60
    return {"music_seconds": best_time, "pitch": pitch}


def _trim(lines: list[str]) -> list[str]:
    lines = [line.rstrip() for line in lines]
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    return lines


@dataclass(frozen=True)
class Timeline:
    music_start: float
    music_end: float
    end: float
    frames: int


def timeline(audio_seconds: float, midi_seconds: float) -> Timeline:
    """The video's seconds. The music runs to the later of the audio and the MIDI, rounded up
    to a whole frame."""
    # The epsilon keeps an exact frame (1.3 s is 78 frames) from tipping to the next on
    # floating-point noise in the product.
    frames = math.ceil(max(audio_seconds, midi_seconds) * FPS - 1e-9)
    music_end = INTRO_SECONDS + frames / FPS
    # The video ends with the music: the credits go in its description.
    return Timeline(INTRO_SECONDS, music_end, music_end, round(music_end * FPS))


def pad(wav_in: Path, wav_out: Path, timeline: Timeline) -> None:
    """Write `wav_in` with silence in front and after, so its clock is the video's clock."""
    info = soundfile.info(wav_in)
    audio, rate = soundfile.read(wav_in, dtype="float32", always_2d=True)
    total = round(timeline.end * rate)
    front = round(timeline.music_start * rate)
    out = np.zeros((total, audio.shape[1]), dtype=np.float32)
    kept = audio[: total - front]
    out[front : front + len(kept)] = kept
    soundfile.write(wav_out, out, rate, subtype=info.subtype)


def manifest(card_lines: dict[str, list[str]], timeline: Timeline, thumbnail: dict) -> dict:
    """What the page reads from /run/manifest.json: the names of the run's files, the cards'
    lines, the timeline's seconds and the thumbnail's moment."""
    return {
        "arrangement": "arrangement.json",
        "audio": "audio.wav",
        "cards": card_lines,
        "timeline": {
            "music_start": timeline.music_start,
            "music_end": timeline.music_end,
            "end": timeline.end,
        },
        "thumbnail": thumbnail,
    }


def prepare(
    midi: mido.MidiFile,
    cards_text: str,
    soundfont: Path,
    run_dir: Path,
    gain: float,
) -> tuple[Timeline, float]:
    """Fill `run_dir` with what the page needs; return the timeline and the render's peak."""
    card_lines = cards(cards_text)
    data = roll.export(midi)
    (run_dir / "arrangement.json").write_text(roll.dump(data), encoding="utf-8")
    rendered = run_dir / "render.wav"
    peak = render.render(midi, rendered, soundfont, gain=gain)
    info = soundfile.info(rendered)
    music_seconds = roll.length(midi)
    moments = timeline(info.frames / info.samplerate, music_seconds)
    pad(rendered, run_dir / "audio.wav", moments)
    rendered.unlink()
    shown = thumbnail_moment(data["notes"], music_seconds)
    (run_dir / "manifest.json").write_text(
        json.dumps(manifest(card_lines, moments, shown), indent=2) + "\n", encoding="utf-8"
    )
    return moments, peak


@dataclass(frozen=True)
class Tools:
    node: str
    ffmpeg: str


def tools() -> Tools:
    """node and ffmpeg's paths, once the viewer's playwright-core is known to be installed."""
    node = shutil.which("node")
    if node is None:
        raise VideoError("node not found on PATH; install Node.js")
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise VideoError("ffmpeg not found on PATH; install ffmpeg")
    if not (VIEWER / "node_modules" / "playwright-core").is_dir():
        raise VideoError(f"playwright-core is not installed; run npm ci in {VIEWER}")
    return Tools(node, ffmpeg)


def encode(tools: Tools, url: str, moments: Timeline, audio: Path, out: Path) -> None:
    """Capture the page at `url` frame by frame in Chrome and encode the frames, with the padded
    `audio`, into the MP4 `out`."""
    capture = [
        tools.node, str(VIEWER / "capture.mjs"),
        "--url", url, "--frames", str(moments.frames), "--fps", str(FPS),
    ]  # fmt: skip
    encoder = [
        tools.ffmpeg, "-loglevel", "error", "-y",
        "-f", "image2pipe", "-c:v", "png", "-framerate", str(FPS), "-i", "pipe:",
        "-i", str(audio),
        # Left alone, ffmpeg converts the RGB frames with BT.601's matrix and tags nothing, and
        # players take untagged HD as BT.709, which shifts the page's colours. scale converts
        # and tags the matrix and range; the encoder takes the primaries and transfer from the
        # frames too, overriding -color_primaries and -color_trc, so setparams tags those.
        "-vf", "scale=out_color_matrix=bt709:out_range=tv,"
               "setparams=color_primaries=bt709:color_trc=bt709",
        "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        str(out),
    ]  # fmt: skip
    _pipe(capture, encoder)


def snapshot(tools: Tools, url: str, out: Path) -> None:
    """Capture the page's thumbnail once in Chrome, and encode it as the JPEG `out` at
    THUMBNAIL_SIZE."""
    capture = [
        tools.node, str(VIEWER / "capture.mjs"),
        "--url", url, "--frames", "1", "--fps", "1", "--thumbnail",
    ]  # fmt: skip
    width, height = THUMBNAIL_SIZE
    encoder = [
        tools.ffmpeg, "-loglevel", "error", "-y",
        "-f", "image2pipe", "-c:v", "png", "-i", "pipe:",
        "-vf", f"scale={width}:{height}", "-frames:v", "1", "-q:v", "2",
        str(out),
    ]  # fmt: skip
    _pipe(capture, encoder)


def _pipe(capture: list[str], encoder: list[str]) -> None:
    """Run node's capture into ffmpeg's encoder, and name whichever failed."""
    node = subprocess.Popen(capture, stdout=subprocess.PIPE)
    ffmpeg = None
    try:
        try:
            ffmpeg = subprocess.Popen(encoder, stdin=node.stdout, stderr=subprocess.PIPE)
        finally:
            # Only ffmpeg holds the frames' pipe from here, so an ffmpeg that dies leaves node's
            # next write with a broken pipe rather than blocked on a pipe nobody reads.
            node.stdout.close()
        _, stderr = ffmpeg.communicate()
        if ffmpeg.returncode != 0:
            # A node that failed first (Chrome did not start, the page did not load) left ffmpeg
            # an empty input; node's error is the one that explains it, on stderr already.
            if node.poll() not in (None, 0):
                raise VideoError(f"node failed ({node.returncode}); its error is above")
            tail = "\n".join(stderr.decode(errors="replace").strip().splitlines()[-5:])
            raise VideoError(f"ffmpeg failed ({ffmpeg.returncode}): {tail}")
        if node.wait() != 0:
            raise VideoError(f"node failed ({node.returncode}); its error is above")
    except BaseException:
        # Stops whatever still runs; a process already waited on ignores both calls. node gets
        # SIGTERM, not SIGKILL, and first: Playwright's handler closes Chrome and deletes its
        # profile.
        node.terminate()
        node.wait()
        if ffmpeg is not None:
            ffmpeg.kill()
            ffmpeg.wait()
        raise


def companions(out: Path) -> tuple[Path, Path]:
    """The thumbnail and the description render_video writes beside the MP4 `out`."""
    return out.with_suffix(".jpg"), out.with_suffix(".txt")


def render_video(
    midi: mido.MidiFile,
    cards_text: str,
    soundfont: Path,
    out: Path,
    gain: float,
) -> tuple[Timeline, float, list[Path]]:
    """Render the falling-notes MP4 to `out`, with its thumbnail and, where the cards file has
    one, its description beside it (companions); return the timeline, the render's peak and the
    files written beside the MP4."""
    if out in companions(out):
        raise VideoError(
            f"{out}: a video's name must not end in .jpg or .txt, which its thumbnail and "
            "description take"
        )
    # Checked now, since the replace that would fail comes after the whole capture.
    for path in (out, *companions(out)):
        if path.is_dir():
            raise VideoError(f"{path} is a directory")
    found = tools()
    text = description(cards_text)
    # The scratch directory sits beside the destination, so the final replace is atomic and a
    # failed render leaves any existing destination as it was.
    with tempfile.TemporaryDirectory(dir=out.parent, prefix=".video-") as tmp:
        run_dir = Path(tmp)
        moments, peak = prepare(midi, cards_text, soundfont, run_dir, gain)
        partial, still = run_dir / "out.mp4", run_dir / "out.jpg"
        server = serve.start(VIEWER, run_dir)
        try:
            encode(found, serve.url(server), moments, run_dir / "audio.wav", partial)
            snapshot(found, serve.url(server), still)
        finally:
            serve.stop(server)
        thumbnail, about = companions(out)
        written = [thumbnail]
        if text is not None:
            (run_dir / "out.txt").write_text(text, encoding="utf-8")
            (run_dir / "out.txt").replace(about)
            written.append(about)
        still.replace(thumbnail)
        partial.replace(out)
    return moments, peak, written
