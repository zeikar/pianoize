import json
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import mido
import numpy as np
import pytest
import soundfile

from pianoize import synthetic
from pianoize.arrange import TRACKS
from pianoize.synthetic import Progression

SAMPLE_RATE = 44100


@pytest.fixture
def make_timeline() -> Callable[..., dict]:
    return synthetic.timeline


@pytest.fixture
def make_midi() -> Callable[..., mido.MidiFile]:
    return synthetic.midi


@pytest.fixture
def tick_midi() -> Callable[..., mido.MidiFile]:
    """A one-track MIDI from (on_tick, off_tick, pitch, velocity) tuples, a list of (tick, bpm)
    tempo changes (120 bpm from tick 0 when empty) and extra (tick, message) pairs, any mido
    message, which sort before a note on the same tick."""

    def build(
        notes: list[tuple[int, int, int, int]],
        tempos: list[tuple[int, float]] | None = None,
        meta: list[tuple[int, mido.Message | mido.MetaMessage]] | None = None,
        ticks_per_beat: int = 480,
    ) -> mido.MidiFile:
        events = [(tick, 1, mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(bpm)))
                  for tick, bpm in tempos or []]  # fmt: skip
        events += [(tick, 0, message) for tick, message in meta or []]
        for on, off, pitch, velocity in notes:
            events.append((on, 3, mido.Message("note_on", note=pitch, velocity=velocity)))
            events.append((off, 2, mido.Message("note_off", note=pitch)))
        track = mido.MidiTrack()
        now = 0
        for tick, _, message in sorted(events, key=lambda e: e[:2]):
            track.append(message.copy(time=tick - now))
            now = tick
        midi = mido.MidiFile(ticks_per_beat=ticks_per_beat)
        midi.tracks.append(track)
        return midi

    return build


@pytest.fixture
def hands_midi(tick_midi) -> Callable[..., mido.MidiFile]:
    """A type 1 MIDI as build-arrangement writes it: a Right Hand track on channel 0 with the
    tempos, then a Left Hand track on channel 1, each from (on_tick, off_tick, pitch, velocity)
    tuples."""

    def build(
        right: list[tuple[int, int, int, int]],
        left: list[tuple[int, int, int, int]],
        tempos: list[tuple[int, float]] | None = None,
        ticks_per_beat: int = 480,
    ) -> mido.MidiFile:
        def named(hand: str) -> mido.MetaMessage:
            return mido.MetaMessage("track_name", name=TRACKS[hand][0])

        first = tick_midi(right, tempos, [(0, named("RH"))], ticks_per_beat).tracks[0]
        second = tick_midi(left, None, [(0, named("LH"))], ticks_per_beat).tracks[0]
        midi = mido.MidiFile(type=1, ticks_per_beat=ticks_per_beat)
        midi.tracks.append(first)
        # tick_midi writes channel 0 only.
        midi.tracks.append(
            mido.MidiTrack(m if m.is_meta else m.copy(channel=TRACKS["LH"][1]) for m in second)
        )
        return midi

    return build


@pytest.fixture
def write_timeline(tmp_path: Path) -> Callable[..., Path]:
    def write(progression: Progression, name: str = "timeline.json", **kwargs) -> Path:
        path = tmp_path / name
        path.write_text(json.dumps(synthetic.timeline(progression, **kwargs)), encoding="utf-8")
        return path

    return write


@pytest.fixture
def write_score(tmp_path: Path) -> Callable[..., Path]:
    """Writes `format 1` and the lines given to score.txt and returns its path."""

    def write(*lines: str) -> Path:
        path = tmp_path / "score.txt"
        path.write_text("\n".join(["format 1", *lines]) + "\n", encoding="utf-8")
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
    real_run = subprocess.run

    def run(argv, **kwargs):
        if argv[0] != "/fake/bin/fluidsynth":  # e.g. a fake chordotomy in the same test
            return real_run(argv, **kwargs)
        assert kwargs.get("check") is True
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


class FakeChordotomy:
    def __init__(self, path: Path, log: Path) -> None:
        self.path = path
        self._log = log

    def calls(self) -> list[tuple[str, ...]]:
        if not self._log.exists():
            return []
        return [tuple(line.split("\t")) for line in self._log.read_text().splitlines()]


@pytest.fixture
def fake_chordotomy(tmp_path, write_timeline):
    """A chordotomy script that checks its argv, counts its calls and copies a fixture timeline
    to -o. `calls()` lists the (audio, engine) pairs it was given."""
    fixture = write_timeline([("C:maj", 4)], name="fixture.json")
    calls = tmp_path / "calls.txt"
    script = tmp_path / "bin" / "chordotomy"
    script.parent.mkdir()
    script.write_text(
        f"""#!{sys.executable}
import shutil, sys
argv = sys.argv[1:]
assert argv[0] == "analyze" and argv[2] == "-o", argv
assert argv[4] == "--force" and argv[5] == "--engine", argv
with open({str(calls)!r}, "a") as f:
    f.write(argv[1] + "\\t" + argv[6] + "\\n")
shutil.copy({str(fixture)!r}, argv[3])
""",
        encoding="utf-8",
    )
    script.chmod(0o755)
    return FakeChordotomy(script, calls)
