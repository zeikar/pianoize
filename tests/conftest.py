import json
import os
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import mido
import numpy as np
import pytest
import soundfile

from pianoize import synthetic, tsumugi
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


# The fake programs' shared start: append the call to the log, as a JSON line, so calls from
# every fake stay in one order.
_LOG_CALL = """import json, os, shutil, sys
from pathlib import Path
with open({log!r}, "a") as f:
    f.write(json.dumps({{"argv": sys.argv, "cwd": os.getcwd()}}) + "\\n")
args = sys.argv[1:]
"""


class FakePython:
    def __init__(self, path: Path, log: Path) -> None:
        self.path = path
        self.log = log

    def records(self) -> list[dict]:
        """Every fake program's calls in order, each its raw argv and its cwd."""
        if not self.log.exists():
            return []
        return [json.loads(line) for line in self.log.read_text().splitlines()]

    def calls(self) -> list[list[str]]:
        """Every fake program's argv in order, the program named by its file name."""
        return [[Path(r["argv"][0]).name, *r["argv"][1:]] for r in self.records()]


@pytest.fixture
def fake_python(tmp_path, monkeypatch) -> FakePython:
    """An interpreter script that logs its calls. As `-c CODE REPO REVISION CACHE` it stands in
    for setup's snapshot download: it writes the weights files into CACHE's snapshot of REPO at
    REVISION, leaving out $FAKE_PYTHON_LEAVE_OUT, and prints the snapshot. HF_HUB_CACHE is set to
    tmp_path/hub."""
    monkeypatch.setenv("HF_HUB_CACHE", str(tmp_path / "hub"))
    log = tmp_path / "calls.jsonl"
    script = tmp_path / "fake-python"
    script.write_text(
        f"#!{sys.executable}\n"
        + _LOG_CALL.format(log=str(log))
        + f"""
rest = args[args.index("-c") + 2:] if "-c" in args else []
if len(rest) == 3:
    repo, revision, cache = rest
    snapshot = Path(cache) / ("models--" + repo.replace("/", "--")) / "snapshots" / revision
    for name in {tsumugi.WEIGHTS_FILES!r}:
        if name != os.environ.get("FAKE_PYTHON_LEAVE_OUT"):
            (snapshot / name).parent.mkdir(parents=True, exist_ok=True)
            (snapshot / name).write_text("weights")
    print(snapshot)
else:
    sys.exit(f"fake python: unexpected arguments {{args}}")
""",
        encoding="utf-8",
    )
    script.chmod(0o755)
    return FakePython(script, log)


class FakeInstallers(FakePython):
    def __init__(self, python: FakePython, home: Path) -> None:
        super().__init__(python.path, python.log)
        self.home = home


@pytest.fixture
def fake_installers(tmp_path, monkeypatch, fake_python) -> FakeInstallers:
    """`git` and `uv` scripts first on PATH that log their calls with the fake interpreter's,
    PIANOIZE_HOME set to tmp_path/home and the test run from tmp_path. `git clone URL DIR` makes
    DIR, with the cover worker when URL is the cover's, then fails if $FAKE_GIT_CLONE_FAILS is
    set; `git checkout` only logs. `uv sync` and `uv venv DIR` put the fake interpreter where the
    env's python goes; `uv pip install` only logs."""
    # A fake handed the wrong cwd then writes into tmp_path, never into the repo's .venv.
    monkeypatch.chdir(tmp_path)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    log_call = _LOG_CALL.format(log=str(fake_python.log))
    git = f"""
if args[0] == "clone":
    url, directory = args[-2:]
    Path(directory).mkdir()
    if url == {tsumugi.COVER_URL!r}:
        worker = Path(directory) / "cover_studio" / "tsumugi_worker.py"
        worker.parent.mkdir()
        worker.write_text("")
    if os.environ.get("FAKE_GIT_CLONE_FAILS"):
        sys.exit("fatal: fake git: clone failed")
elif args[0] != "checkout":
    sys.exit(f"fake git: unexpected arguments {{args}}")
"""
    uv = f"""
# Real uv's project commands, such as `uv sync`, warn about a VIRTUAL_ENV that is not the
# project's env; setup drops it, and this checks it does.
if "VIRTUAL_ENV" in os.environ:
    sys.exit("fake uv: VIRTUAL_ENV is set")
if args[0] == "sync":
    python = Path.cwd() / ".venv" / "bin" / "python"
elif args[0] == "venv":
    python = Path(args[-1]) / "bin" / "python"
elif args[:2] == ["pip", "install"]:
    python = None
else:
    sys.exit(f"fake uv: unexpected arguments {{args}}")
if python is not None:
    python.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy({str(fake_python.path)!r}, python)
"""
    for name, body in (("git", git), ("uv", uv)):
        script = bin_dir / name
        script.write_text(f"#!{sys.executable}\n" + log_call + body, encoding="utf-8")
        script.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("PIANOIZE_HOME", str(tmp_path / "home"))
    # As `uv run pianoize` leaves it: pianoize's own venv.
    monkeypatch.setenv("VIRTUAL_ENV", str(tmp_path / "pianoize-venv"))
    return FakeInstallers(fake_python, tmp_path / "home")
