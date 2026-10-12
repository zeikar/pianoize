import shutil
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pytest
import soundfile
from conftest import SAMPLE_RATE
from typer.testing import CliRunner

from pianoize import serve, video
from pianoize.cli import app


def test_cards_split_at_the_dashes_and_trim_blank_lines():
    text = "\n\nTitle  \n\nSub\n\n---\n\nCredits\nMore\n\n\n"

    assert video.cards(text) == {"title": ["Title", "", "Sub"], "credits": ["Credits", "More"]}


def test_cards_refuse_a_file_without_dashes():
    with pytest.raises(video.VideoError, match="---"):
        video.cards("Title\nCredits\n")


def test_cards_refuse_an_empty_credits_card():
    with pytest.raises(video.VideoError, match="credits card is empty"):
        video.cards("Title\n---\n\n")


def test_timeline_rounds_the_music_up_to_a_frame():
    moments = video.timeline(1.3, 1.0)

    assert moments.music_start == 6.0
    assert moments.music_end == pytest.approx(6.0 + 78 / 60)
    assert moments.end == pytest.approx(moments.music_end + 6.0)
    assert moments.frames == round(moments.end * 60)


def test_timeline_takes_the_midi_when_it_is_longer():
    assert video.timeline(1.0, 2.0).music_end == pytest.approx(6.0 + 2.0)


def test_timeline_rounds_a_partial_frame_up():
    assert video.timeline(1.31, 0.0).music_end == pytest.approx(6.0 + 79 / 60)


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
    monkeypatch.setattr(video, "CREDITS_SECONDS", 0.5)
    wav = tmp_path / "in.wav"
    soundfile.write(wav, synth, SAMPLE_RATE)

    moments = video.timeline(1.0, 0.5)
    video.pad(wav, tmp_path / "out.wav", moments)

    assert (moments.music_start, moments.music_end, moments.end) == (0.5, 1.5, 2.0)
    assert moments.frames == 120
    assert soundfile.info(tmp_path / "out.wav").frames == 2 * SAMPLE_RATE


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
    # The one-second clip outlasts the half-second MIDI: 6 + 1 + 6 seconds at 60 frames.
    assert "frames: 780\nlength: 13.0 s\n" in result.output
    assert out.read_bytes() == b"encoded"
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
