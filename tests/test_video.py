import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np
import pytest
import soundfile
from conftest import SAMPLE_RATE
from typer.testing import CliRunner

from pianoize import serve, video
from pianoize.cli import app

# Looked up at import, before fake_fluidsynth makes shutil.which answer every name.
NODE = shutil.which("node")
FFMPEG = shutil.which("ffmpeg")
FFPROBE = shutil.which("ffprobe")

needs_video_tools = pytest.mark.skipif(
    None in (NODE, FFMPEG, FFPROBE)
    or not Path("/Applications/Google Chrome.app").is_dir()
    or not (video.VIEWER / "node_modules" / "playwright-core").is_dir(),
    reason="needs node, ffmpeg and ffprobe on PATH, Google Chrome and the viewer's playwright-core",
)
real_fluidsynth = pytest.mark.skipif(
    shutil.which("fluidsynth") is None or not os.environ.get("PIANOIZE_SOUNDFONT"),
    reason="needs fluidsynth on PATH and PIANOIZE_SOUNDFONT",
)


def test_the_title_card_ends_at_the_dashes_and_trims_blank_lines():
    text = "\n\nTitle  \n\nSub\n\n---\n\nCredits\nMore\n\n\n"

    assert video.cards(text) == {"title": ["Title", "", "Sub"]}


def test_a_file_without_dashes_is_all_title():
    assert video.cards("Title\nSub\n") == {"title": ["Title", "Sub"]}


def test_cards_refuse_an_empty_title_card():
    with pytest.raises(video.VideoError, match="title card is empty"):
        video.cards("\n---\nCredits\n")


def test_the_thumbnail_shows_the_moment_with_the_most_notes_on_screen():
    notes = [
        {"pitch": 60, "hand": "right", "on": 0.0, "off": 0.5},
        *({"pitch": p, "hand": "left", "on": 5.0, "off": 5.5} for p in (40, 44, 47)),
    ]

    # The three notes at 5 s come on screen one fall time, 3 s, before it: the earliest step
    # past 2 s shows them, and their middle pitch centres it.
    assert video.thumbnail_moment(notes, 10.0) == {"music_seconds": 2.25, "pitch": 44}


def test_a_thumbnail_without_notes_shows_the_start_at_middle_c():
    assert video.thumbnail_moment([], 1.0) == {"music_seconds": 0.0, "pitch": 60}


def test_timeline_rounds_the_music_up_to_a_frame():
    moments = video.timeline(1.3, 1.0)

    assert moments.music_start == 3.0
    assert moments.music_end == pytest.approx(3.0 + 78 / 60)
    assert moments.end == moments.music_end
    assert moments.frames == round(moments.end * 60)


def test_timeline_takes_the_midi_when_it_is_longer():
    assert video.timeline(1.0, 2.0).music_end == pytest.approx(3.0 + 2.0)


def test_timeline_rounds_a_partial_frame_up():
    assert video.timeline(1.31, 0.0).music_end == pytest.approx(3.0 + 79 / 60)


def test_pad_puts_silence_around_the_clip(tmp_path, synth):
    wav = tmp_path / "in.wav"
    soundfile.write(wav, synth, SAMPLE_RATE)
    moments = video.timeline(1.0, 1.0)

    video.pad(wav, tmp_path / "out.wav", moments)

    clip, _ = soundfile.read(wav, dtype="float32")  # the file's 16-bit values, not the float
    padded, rate = soundfile.read(tmp_path / "out.wav", dtype="float32")
    front = round(moments.music_start * SAMPLE_RATE)
    assert rate == SAMPLE_RATE
    assert len(padded) == round(moments.end * SAMPLE_RATE)
    assert not np.any(padded[:front])
    assert np.array_equal(padded[front : front + len(clip)], clip)
    assert not np.any(padded[front + len(clip) :])


def test_shortened_constants_are_read_at_call_time(monkeypatch, tmp_path, synth):
    monkeypatch.setattr(video, "INTRO_SECONDS", 0.5)
    wav = tmp_path / "in.wav"
    soundfile.write(wav, synth, SAMPLE_RATE)

    moments = video.timeline(1.0, 0.5)
    video.pad(wav, tmp_path / "out.wav", moments)

    assert (moments.music_start, moments.music_end, moments.end) == (0.5, 1.5, 1.5)
    assert moments.frames == 90
    assert soundfile.info(tmp_path / "out.wav").frames == round(1.5 * SAMPLE_RATE)


def test_prepare_fills_the_run_directory(tmp_path, fake_fluidsynth, hands_midi):
    run = tmp_path / "run"
    run.mkdir()

    moments, peak = video.prepare(
        hands_midi([(0, 480, 72, 80)], [(0, 480, 48, 80)]),
        "Title\n---\nCredits\n",
        tmp_path / "font.sf2",
        run,
        0.25,
    )

    assert sorted(p.name for p in run.iterdir()) == [
        "arrangement.json",
        "audio.wav",
        "manifest.json",
    ]
    assert peak == pytest.approx(0.5, abs=0.01)
    assert fake_fluidsynth.calls[0]["gain"] == 0.25
    assert soundfile.info(run / "audio.wav").frames == round(moments.end * SAMPLE_RATE)


@pytest.fixture
def inputs(tmp_path, hands_midi) -> dict[str, Path]:
    midi = tmp_path / "arranged.mid"
    hands_midi([(0, 480, 72, 80)], [(0, 480, 48, 80)]).save(midi)
    cards = tmp_path / "cards.txt"
    cards.write_text("Title\n---\nCredits\n", encoding="utf-8")
    font = tmp_path / "font.sf2"
    font.write_bytes(b"sf2")
    return {"midi": midi, "cards": cards, "soundfont": font}


@pytest.fixture
def fake_tools(monkeypatch, tmp_path) -> None:
    """Paths no tool is at, so a test that reaches node or ffmpeg fails."""
    tools = video.Tools(str(tmp_path / "bin" / "node"), str(tmp_path / "bin" / "ffmpeg"))
    monkeypatch.setattr(video, "tools", lambda: tools)


def _script(path: Path, body: str) -> str:
    """A fake tool: a Python script with this body, written to `path` and made executable."""
    path.write_text(f"#!{sys.executable}\n{body}", encoding="utf-8")
    path.chmod(0o755)
    return str(path)


def _encoders(monkeypatch, tmp_path: Path, ffmpeg_exit: int) -> None:
    """Make video.tools give a node that writes a few bytes and an ffmpeg that reads them, writes
    b"encoded" to its output and exits with `ffmpeg_exit`."""
    (tmp_path / "bin").mkdir()
    node = _script(tmp_path / "bin" / "node", "import sys\nsys.stdout.buffer.write(b'frames')\n")
    ffmpeg = _script(
        tmp_path / "bin" / "ffmpeg",
        "import sys\nsys.stdin.buffer.read()\n"
        f"open(sys.argv[-1], 'wb').write(b'encoded')\nsys.exit({ffmpeg_exit})\n",
    )
    monkeypatch.setattr(video, "tools", lambda: video.Tools(node, ffmpeg))


@pytest.fixture
def stopped(monkeypatch) -> list:
    """The servers serve.stop has stopped."""
    servers = []
    stop = serve.stop

    def spy(server):
        stop(server)
        servers.append(server)

    monkeypatch.setattr(serve, "stop", spy)
    return servers


def _render(inputs: dict[str, Path], out: Path):
    args = ["render-video", str(inputs["midi"]), "--cards", str(inputs["cards"])]
    return CliRunner().invoke(app, [*args, "--soundfont", str(inputs["soundfont"]), "-o", str(out)])


def test_render_video_replaces_the_output(inputs, tmp_path, monkeypatch, fake_fluidsynth, stopped):
    _encoders(monkeypatch, tmp_path, 0)
    out = tmp_path / "out.mp4"
    out.write_bytes(b"old")

    result = _render(inputs, out)

    assert result.exit_code == 0, result.output
    # The one-second clip outlasts the half-second MIDI: 3 + 1 seconds at 60 frames.
    assert "frames: 240\nlength: 4.0 s\n" in result.output
    assert f"thumbnail: {tmp_path / 'out.jpg'}\n" in result.output
    assert out.read_bytes() == b"encoded"
    assert (tmp_path / "out.jpg").read_bytes() == b"encoded"
    assert len(stopped) == 1
    assert not list(tmp_path.glob(".video-*"))


def test_render_video_keeps_the_output_when_ffmpeg_fails(
    inputs, tmp_path, monkeypatch, fake_fluidsynth, stopped
):
    _encoders(monkeypatch, tmp_path, 1)
    out = tmp_path / "out.mp4"
    out.write_bytes(b"old")

    result = _render(inputs, out)

    assert result.exit_code == 1
    assert "error: ffmpeg failed (1)" in result.output
    assert out.read_bytes() == b"old"
    assert len(stopped) == 1
    assert not list(tmp_path.glob(".video-*"))


def test_render_video_refuses_a_directory_before_rendering(
    inputs, tmp_path, fake_fluidsynth, fake_tools
):
    out = tmp_path / "out.mp4"
    out.mkdir()

    result = _render(inputs, out)

    assert result.exit_code == 1
    assert f"error: {out} is a directory" in result.output
    assert fake_fluidsynth.calls == []


@pytest.mark.parametrize("target", ["midi", "cards", "soundfont"])
def test_render_video_refuses_to_overwrite_an_input(inputs, fake_fluidsynth, fake_tools, target):
    before = inputs[target].read_bytes()

    result = _render(inputs, inputs[target])

    assert result.exit_code == 2
    assert "would overwrite an input" in " ".join(result.output.split())
    assert inputs[target].read_bytes() == before


def test_render_video_refuses_a_thumbnail_over_an_input(
    inputs, tmp_path, fake_fluidsynth, fake_tools
):
    # A video named like the cards file but .mp4 would put its thumbnail on a .jpg input.
    picture = tmp_path / "cards.jpg"
    picture.write_bytes(b"input")
    inputs = {**inputs, "cards": picture}

    result = _render(inputs, tmp_path / "cards.mp4")

    assert result.exit_code == 2
    assert "would overwrite an input" in " ".join(result.output.split())
    assert picture.read_bytes() == b"input"


def test_render_video_refuses_a_video_named_like_its_thumbnail(
    inputs, tmp_path, fake_fluidsynth, fake_tools
):
    result = _render(inputs, tmp_path / "out.jpg")

    assert result.exit_code == 1
    assert "must not end in .jpg" in result.output


def test_render_video_refuses_a_midi_without_hand_tracks(
    inputs, tmp_path, tick_midi, fake_fluidsynth, fake_tools
):
    tick_midi([(0, 480, 60, 80)]).save(inputs["midi"])
    out = tmp_path / "out.mp4"

    result = _render(inputs, out)

    assert result.exit_code == 1
    assert "error: no 'Right Hand' track" in result.output
    assert fake_fluidsynth.calls == []
    assert not out.exists()
    assert not list(tmp_path.glob(".video-*"))


def test_render_video_names_a_missing_ffmpeg(inputs, tmp_path, monkeypatch):
    # Every other name gets a path, so no real tool is consulted.
    monkeypatch.setattr(
        shutil, "which", lambda name: None if name == "ffmpeg" else f"/fake/bin/{name}"
    )
    before = sorted(tmp_path.iterdir())

    result = _render(inputs, tmp_path / "out.mp4")

    assert result.exit_code == 1
    assert "error: ffmpeg not found on PATH; install ffmpeg" in result.output
    assert sorted(tmp_path.iterdir()) == before  # no MP4 and no .video-* scratch


def _encode(tmp_path: Path, node: str, ffmpeg: str) -> None:
    """encode with node and ffmpeg replaced by Python scripts with these bodies."""
    tools = video.Tools(_script(tmp_path / "node", node), _script(tmp_path / "ffmpeg", ffmpeg))
    moments = video.timeline(1.0, 1.0)
    video.encode(tools, "http://127.0.0.1:1/", moments, tmp_path / "a.wav", tmp_path / "o.mp4")


def test_encode_names_an_ffmpeg_that_dies_without_hanging(tmp_path):
    node = """
import os, signal, sys, time
signal.signal(signal.SIGTERM, signal.SIG_IGN)  # as under Playwright: only a failed write ends it
signal.alarm(10)  # so a hang fails the test instead of stalling the suite
try:
    sys.stdout.buffer.write(bytes(1_000_000))
    sys.stdout.flush()
except BrokenPipeError:
    time.sleep(1)  # closing Chrome takes a moment
    os._exit(1)
"""
    # ffmpeg fails on node's first byte, by when node ignores SIGTERM, so only the closed pipe
    # can end node.
    ffmpeg = """
import sys
sys.stdin.buffer.read(1)
sys.exit("pipe:: Invalid data found when processing input")
"""
    start = time.monotonic()

    with pytest.raises(video.VideoError, match=r"^ffmpeg failed \(1\): pipe:: Invalid data"):
        _encode(tmp_path, node, ffmpeg)

    assert time.monotonic() - start < 5


def test_encode_names_a_node_that_fails_after_ffmpeg_succeeds(tmp_path):
    node = "import sys\nsys.stdout.buffer.write(b'frame')\nsys.exit(3)\n"
    ffmpeg = "import sys\nsys.stdin.buffer.read()\n"

    with pytest.raises(video.VideoError, match=r"^node failed \(3\)"):
        _encode(tmp_path, node, ffmpeg)


def test_encode_names_node_when_ffmpeg_fails_on_an_empty_input(tmp_path):
    node = "import sys\nsys.exit(1)\n"
    ffmpeg = """
import sys
if not sys.stdin.buffer.read():
    sys.exit("Output file does not contain any stream")
"""

    with pytest.raises(video.VideoError, match=r"^node failed \(1\)") as caught:
        _encode(tmp_path, node, ffmpeg)

    assert "ffmpeg" not in str(caught.value)


def test_encode_stops_node_when_ffmpeg_cannot_start(tmp_path, monkeypatch):
    started = []
    popen = subprocess.Popen

    def record(*args, **kwargs):
        process = popen(*args, **kwargs)
        started.append(process)
        return process

    monkeypatch.setattr(subprocess, "Popen", record)
    tools = video.Tools(
        _script(tmp_path / "node", "import time\ntime.sleep(10)\n"), str(tmp_path / "no-ffmpeg")
    )
    moments = video.timeline(1.0, 1.0)

    with pytest.raises(FileNotFoundError):
        video.encode(tools, "http://127.0.0.1:1/", moments, tmp_path / "a.wav", tmp_path / "o.mp4")

    [node] = started  # ffmpeg never started
    assert node.poll() is not None


@pytest.fixture
def short_cards(monkeypatch) -> None:
    """A half-second title, so a real render takes seconds."""
    monkeypatch.setattr(video, "INTRO_SECONDS", 0.5)


@pytest.fixture
def real_tools(monkeypatch) -> None:
    """The real node and ffmpeg, which video.tools cannot find once fake_fluidsynth makes
    shutil.which answer /fake/bin/<name> for every name."""
    monkeypatch.setattr(video, "tools", lambda: video.Tools(NODE, FFMPEG))


def _probe(mp4: Path) -> dict:
    argv = [FFPROBE, "-v", "error", "-show_streams", "-show_format", "-of", "json", str(mp4)]
    return json.loads(subprocess.run(argv, check=True, capture_output=True).stdout)


def _decode(mp4: Path, *args: str) -> bytes:
    """What ffmpeg writes to stdout when it decodes `mp4` with these output options."""
    argv = [FFMPEG, "-loglevel", "error", "-i", str(mp4), *args, "-"]
    return subprocess.run(argv, check=True, capture_output=True).stdout


def _framemd5(mp4: Path) -> list[str]:
    """A line per decoded video frame, with its timestamps and the MD5 of its pixels."""
    lines = _decode(mp4, "-map", "0:v", "-f", "framemd5").decode().splitlines()
    return [line for line in lines if not line.startswith("#")]


def _audio(mp4: Path) -> np.ndarray:
    raw = _decode(mp4, "-map", "0:a", "-ac", "1", "-ar", str(SAMPLE_RATE), "-f", "f32le")
    return np.frombuffer(raw, dtype="<f4")


def _bottoms(mp4: Path, first: int, last: int, rows: int) -> np.ndarray:
    """The bottom `rows` rows of frames `first` to `last`, both included, as RGB in an
    (n, rows, 1920, 3) array."""
    raw = _decode(
        mp4, "-map", "0:v", "-vf", f"select='between(n,{first},{last})',crop=iw:{rows}:0:ih-{rows}",
        # Each selected frame once, rather than resampled to a constant rate.
        "-fps_mode", "passthrough",
        "-f", "rawvideo", "-pix_fmt", "rgb24",
    )  # fmt: skip
    return np.frombuffer(raw, dtype=np.uint8).reshape(-1, rows, 1920, 3)


def _profiles() -> set[Path]:
    """Chrome profiles Playwright has left in the temp directory, which is node's os.tmpdir()."""
    return set(Path(tempfile.gettempdir()).glob("playwright_chromiumdev_profile-*"))


@pytest.mark.video
@needs_video_tools
def test_render_video_is_repeatable_and_in_format(
    tmp_path, hands_midi, fake_fluidsynth, real_tools, short_cards
):
    midi = hands_midi([(0, 480, 72, 80)], [(0, 480, 48, 80)])
    profiles = _profiles()

    for name in ("a.mp4", "b.mp4"):
        moments, _ = video.render_video(
            midi, "Title\n---\nCredits\n", tmp_path / "font.sf2", tmp_path / name, 0.5
        )

    # If these ever differ, run once with ffmpeg's -threads 1 to tell the capture from the
    # encoder before changing anything.
    assert _framemd5(tmp_path / "a.mp4") == _framemd5(tmp_path / "b.mp4")
    probe = _probe(tmp_path / "a.mp4")
    [picture] = [s for s in probe["streams"] if s["codec_type"] == "video"]
    [sound] = [s for s in probe["streams"] if s["codec_type"] == "audio"]
    assert (picture["width"], picture["height"], picture["r_frame_rate"]) == (1920, 1080, "60/1")
    assert (picture["codec_name"], picture["pix_fmt"]) == ("h264", "yuv420p")
    assert sound["codec_name"] == "aac"
    assert int(picture["nb_frames"]) == moments.frames
    assert float(probe["format"]["duration"]) == pytest.approx(moments.end, abs=1 / video.FPS)
    [still] = _probe(tmp_path / "a.jpg")["streams"]
    assert (still["codec_name"], still["width"], still["height"]) == (
        "mjpeg",
        *video.THUMBNAIL_SIZE,
    )
    assert not list(tmp_path.glob(".video-*"))
    assert not _profiles() - profiles


@pytest.mark.video
@pytest.mark.fluidsynth
@needs_video_tools
@real_fluidsynth
def test_a_key_lights_on_the_frame_its_sound_starts(tmp_path, hands_midi, short_cards):
    # A right-hand C4 at 1.0 s of music, 1.5 s of video after the short intro: about frame 90,
    # so the window below starts well after frame 0.
    midi = hands_midi([(960, 1440, 60, 80)], [])
    mp4 = tmp_path / "sync.mp4"
    soundfont = Path(os.environ["PIANOIZE_SOUNDFONT"])

    video.render_video(midi, "Title\n---\nCredits\n", soundfont, mp4, 0.5)

    # Salamander's C4 passes 0.01 about 20 ms after its note-on (1.520 s, frame 91), while
    # the page lights the key from the note-on's own frame (90).
    onset = np.argmax(np.abs(_audio(mp4)) > 0.01) / SAMPLE_RATE
    f_audio = math.floor(onset * video.FPS)
    first = f_audio - 10
    # The bottom 40 rows hold only white keys and the gaps between them, all grey until a key
    # lights in its hand's colour.
    bottom = _bottoms(mp4, first, f_audio + 10, 40)
    lit = (np.ptp(bottom, axis=-1) > 60).any(axis=(1, 2))
    assert lit.any() and not lit[0], lit
    f_video = first + int(np.argmax(lit))
    assert abs(f_video - f_audio) <= 1, (onset, f_audio, f_video)
