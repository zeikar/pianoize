"""The falling-notes video's timing, cards and padded audio, and the capture and encode that make
the MP4."""

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
INTRO_SECONDS = 6.0  # where the music starts
CREDITS_SECONDS = 6.0
# The viewer is page assets, not Python, so it stays at the checkout's top level rather than
# inside the package; pianoize runs from a checkout.
VIEWER = Path(__file__).resolve().parents[2] / "viewer"


class VideoError(Exception):
    pass


def cards(text: str) -> dict[str, list[str]]:
    """Split a cards file at its first `---` line into the title and credits cards' lines."""
    lines = text.splitlines()
    if "---" not in (line.strip() for line in lines):
        raise VideoError("the cards file has no '---' line between the title and the credits")
    at = next(i for i, line in enumerate(lines) if line.strip() == "---")
    found = {"title": _trim(lines[:at]), "credits": _trim(lines[at + 1 :])}
    for name, card in found.items():
        if not card:
            raise VideoError(f"the {name} card is empty")
    return found


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
    end = music_end + CREDITS_SECONDS
    return Timeline(INTRO_SECONDS, music_end, end, round(end * FPS))


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


def manifest(card_lines: dict[str, list[str]], timeline: Timeline) -> dict:
    """What the page reads from /run/manifest.json: the names of the run's files, the cards'
    lines and the timeline's seconds."""
    return {
        "arrangement": "arrangement.json",
        "audio": "audio.wav",
        "cards": card_lines,
        "timeline": {
            "music_start": timeline.music_start,
            "music_end": timeline.music_end,
            "end": timeline.end,
        },
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
    moments = timeline(info.frames / info.samplerate, roll.length(midi))
    pad(rendered, run_dir / "audio.wav", moments)
    rendered.unlink()
    (run_dir / "manifest.json").write_text(
        json.dumps(manifest(card_lines, moments), indent=2) + "\n", encoding="utf-8"
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


def render_video(
    midi: mido.MidiFile,
    cards_text: str,
    soundfont: Path,
    out: Path,
    gain: float,
) -> tuple[Timeline, float]:
    """Render the falling-notes MP4 to `out`; return the timeline and the render's peak."""
    # Checked now, since the replace that would fail comes after the whole capture.
    if out.is_dir():
        raise VideoError(f"{out} is a directory")
    found = tools()
    # The scratch directory sits beside the destination, so the final replace is atomic and a
    # failed render leaves any existing destination as it was.
    with tempfile.TemporaryDirectory(dir=out.parent, prefix=".video-") as tmp:
        run_dir = Path(tmp)
        moments, peak = prepare(midi, cards_text, soundfont, run_dir, gain)
        partial = run_dir / "out.mp4"
        server = serve.start(VIEWER, run_dir)
        try:
            encode(found, serve.url(server), moments, run_dir / "audio.wav", partial)
        finally:
            serve.stop(server)
        partial.replace(out)
    return moments, peak
