import subprocess

import mido
import numpy as np
import pytest
import soundfile
from conftest import SAMPLE_RATE
from typer.testing import CliRunner

from pianoize import stems, tsumugi
from pianoize.cli import app
from pianoize.tsumugi import Install

pytestmark = [
    pytest.mark.tsumugi,
    pytest.mark.skipif(bool(Install.from_env().missing()), reason="needs pianoize setup"),
]

SECONDS = 2


def _stereo(path, signal):
    path.parent.mkdir(parents=True, exist_ok=True)
    soundfile.write(path, np.stack([signal, signal], axis=1).astype(np.float32), SAMPLE_RATE)


def _tone(hertz, harmonics=1):
    t = np.arange(SECONDS * SAMPLE_RATE) / SAMPLE_RATE
    return sum(0.3 / k * np.sin(2 * np.pi * k * hertz * t) for k in range(1, harmonics + 1))


def test_the_worker_measures_synthesized_stems(tmp_path, tick_midi):
    """A sine at A4 in `other`, a harmonic tone at A3 for the first second of `vocals`, silence
    in the rest."""
    directory = tmp_path / "stems" / "song"
    vocals = _tone(220, harmonics=5)
    vocals[SAMPLE_RATE:] = 0
    signals = {"other": _tone(440), "vocals": vocals}
    for stem in ("guitar", "other", "piano", "vocals"):
        signal = signals.get(stem, np.zeros(SECONDS * SAMPLE_RATE))
        _stereo(directory / f"song_{stem}.wav", signal)
    out = tmp_path / "stems.npz"

    done = subprocess.run(
        [Install.from_env().tsumugi_python, tsumugi.STEM_WORKER, "--stems", directory,
         "--out", out],
        capture_output=True, text=True,
    )  # fmt: skip

    assert done.returncode == 0, done.stderr
    table = stems.load(out)
    assert table.stems == ("guitar", "other", "piano", "vocals")

    def frames(start, end):
        return slice(round(start / table.frame_seconds), round(end / table.frame_seconds))

    middle = table.levels["other"][:, frames(0.5, 1.5)]
    assert (middle.argmax(axis=0) + table.low_pitch == 69).all()
    assert np.allclose(table.vocals_pitch[frames(0.2, 0.8)], 57, atol=0.2)
    assert np.isnan(table.vocals_pitch[frames(1.2, 1.8)]).all()

    def track(name, notes):
        meta = [(0, mido.MetaMessage("track_name", name=name))]
        return tick_midi([(on, off, pitch, 80) for on, off, pitch in notes], meta=meta)

    cover = tmp_path / "cover.mid"
    track("Piano", [(0, 96, 60)]).save(cover)
    # 960 ticks a second at tick_midi's 120 bpm.
    for name, notes, stem in (
        ("melody", [(0, 960, 57)], "vocals"),
        ("synth_lead", [(0, 1920, 69)], "other"),
    ):
        line = tmp_path / f"{name}.mid"
        track(name, notes).save(line)
        argv = ["check-line", str(line), "--cover", str(cover), "--stems", str(out)]
        result = CliRunner().invoke(app, argv)
        assert result.exit_code == 0, result.output
        assert result.output == f"audio check: {stem}, 0 of 1 notes unsupported, 0 untranscribed\n"


def test_measure_separates_and_measures_a_recording(tmp_path):
    samples = 3 * SAMPLE_RATE
    t = np.arange(samples) / SAMPLE_RATE
    wav = tmp_path / "song.wav"
    _stereo(wav, 0.3 * np.sin(2 * np.pi * 220 * t) + 0.2 * np.sin(2 * np.pi * 440 * t))
    out, log = tmp_path / "scratch" / "stems.npz", tmp_path / "stems.log"
    out.parent.mkdir()

    tsumugi.measure(Install.from_env(), wav, out, log)

    table = stems.load(out)
    assert table.stems == ("guitar", "other", "piano", "vocals")
    # The readings are centred: a frame every 512 samples from the first.
    assert len(table.vocals_level) == 1 + samples // 512
