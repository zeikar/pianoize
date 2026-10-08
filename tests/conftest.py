import json
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path

import mido
import numpy as np
import pytest
import soundfile

from pianoize import synthetic
from pianoize.synthetic import Progression

SAMPLE_RATE = 44100


@pytest.fixture
def make_timeline() -> Callable[..., dict]:
    return synthetic.timeline


@pytest.fixture
def make_midi() -> Callable[..., mido.MidiFile]:
    return synthetic.midi


@pytest.fixture
def write_timeline(tmp_path: Path) -> Callable[..., Path]:
    def write(progression: Progression, name: str = "timeline.json", **kwargs) -> Path:
        path = tmp_path / name
        path.write_text(json.dumps(synthetic.timeline(progression, **kwargs)), encoding="utf-8")
        return path

    return write


@pytest.fixture
def synth() -> np.ndarray:
    """One second of a 440 Hz sine at amplitude 0.5: a clip with a known, nonzero peak."""
    t = np.arange(SAMPLE_RATE) / SAMPLE_RATE
    return (0.5 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)


class FakeFluidSynth:
    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.fail: str | None = None  # stderr to fail with
        self.clip = np.zeros(0, dtype=np.float32)


@pytest.fixture
def fake_fluidsynth(monkeypatch, synth) -> FakeFluidSynth:
    """Stands in for the fluidsynth binary: checks the argv shape, records the call and writes
    `fake.clip` (the `synth` tone by default) to the -F path."""
    fake = FakeFluidSynth()
    fake.clip = synth
    monkeypatch.setattr(shutil, "which", lambda name: f"/fake/bin/{name}")

    def run(argv, **kwargs):
        assert kwargs.get("check") is True
        assert argv[0] == "/fake/bin/fluidsynth"
        assert argv[1:7] == ["-ni", "-q", "-R", "0", "-C", "0"]
        assert argv[7] == "-g"
        assert argv[9:13] == ["-r", "44100", "-T", "wav"]
        assert argv[13] == "-F"
        wav, soundfont, mid = argv[14:]
        assert Path(mid).exists()
        fake.calls.append(
            {
                "gain": float(argv[8]),
                "wav": Path(wav),
                "soundfont": Path(soundfont),
                "mid": Path(mid),
            }
        )
        soundfile.write(wav, fake.clip, SAMPLE_RATE)
        if fake.fail is not None:  # after the write: a failed run can leave a partial file
            raise subprocess.CalledProcessError(1, argv, stderr=fake.fail)
        return subprocess.CompletedProcess(argv, 0)

    monkeypatch.setattr(subprocess, "run", run)
    return fake
