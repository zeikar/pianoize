import re
import signal
from pathlib import Path

import mido
import numpy as np
import pytest
import soundfile
from conftest import SAMPLE_RATE
from typer.testing import CliRunner

from pianoize.cli import app

OUTPUTS = ("song.wav", "source.mid", "melody.mid", "cover.mid")
# Not stem_splitter's 44.1 kHz, so a resample would show.
RATE = 48000


@pytest.fixture
def flac(tmp_path, synth) -> Path:
    """The `synth` tone in stereo at 48 kHz as a FLAC, so the decode is a real conversion."""
    path = tmp_path / "in" / "song.flac"
    path.parent.mkdir()
    soundfile.write(path, np.stack([synth, -synth], axis=1), RATE)
    return path


def prepare(*args: str | Path):
    return CliRunner().invoke(app, ["prepare", *map(str, args)])


def listing(out: Path) -> list[str]:
    """The directory's entries, hidden ones too, so a leftover scratch directory shows."""
    return sorted(p.name for p in out.iterdir())


def option(argv: list[str], name: str) -> str:
    return argv[argv.index(name) + 1]


def test_prepare_writes_the_four_files_and_a_summary(fake_install, flac, tmp_path):
    out = tmp_path / "out"

    result = prepare(flac, "-o", out)

    assert result.exit_code == 0, result.output
    assert listing(out) == sorted([*OUTPUTS, "transcribe.log", "generate.log"])
    info = soundfile.info(out / "song.wav")
    assert (info.format, info.subtype) == ("WAV", "PCM_16")
    assert (info.samplerate, info.channels, info.frames) == (RATE, 2, SAMPLE_RATE)
    log = (out / "transcribe.log").read_text(encoding="utf-8").splitlines()
    assert "Loading AMT model on cpu" in log
    assert not any(line.startswith("@@") for line in log)
    assert (out / "generate.log").read_text(encoding="utf-8").endswith(": 1 note\n")
    worker, generator = (r["argv"] for r in fake_install.records())
    assert option(worker, "--audio") == str(out / "song.wav")
    assert option(generator, "--source") == str(out / "source.mid")
    melody = mido.MidiFile(out / "melody.mid")
    assert [t.name for t in melody.tracks] == ["", "melody"]
    assert {m.type for m in melody.tracks[0]} == {"set_tempo", "time_signature", "end_of_track"}
    lines = result.output.splitlines()
    for step, log_name in (("transcribing", "transcribe.log"), ("generating", "generate.log")):
        assert any(
            line.startswith(step) and line.endswith(f"; log: {out / log_name}") for line in lines
        )
    assert any(re.fullmatch(r"transcribe: \d+ s", line) for line in lines)
    assert any(re.fullmatch(r"generate: \d+ s", line) for line in lines)
    assert lines[-4:] == [
        "song.wav: 0.9 s",
        "source.mid: 6 tracks: Predicted Tempo Map 0, Predicted Chords 0, (unnamed) 0, piano 1, "
        "melody 1, drums 1",
        "melody.mid: 1 notes",
        "cover.mid: 1 notes, 0.5 s",
    ]


def test_prepare_resolves_relative_paths(fake_install, flac, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    result = prepare("in/song.flac", "-o", "out")

    assert result.exit_code == 0, result.output
    for name in OUTPUTS:
        assert (tmp_path / "out" / name).is_file()
    worker = fake_install.records()[0]["argv"]
    assert option(worker, "--audio") == str(tmp_path / "out" / "song.wav")


def test_a_second_run_reuses_every_file(fake_install, flac, tmp_path):
    out = tmp_path / "out"
    assert prepare(flac, "-o", out).exit_code == 0
    calls = len(fake_install.records())

    result = prepare(flac, "-o", out)

    assert result.exit_code == 0, result.output
    assert len(fake_install.records()) == calls
    reused = [line for line in result.output.splitlines() if line.startswith("reusing ")]
    assert reused == [f"reusing {out / name}" for name in OUTPUTS]


def test_prepare_publishes_no_source_when_a_transcription_stage_failed(
    fake_install, flac, tmp_path
):
    fake_install.log.with_name("warns").touch()
    out = tmp_path / "out"

    result = prepare(flac, "-o", out)

    assert result.exit_code == 1
    assert "error: tsumugi transcribe: a stage failed: Warning: Velocity" in result.output
    assert listing(out) == ["song.wav", "transcribe.log"]


def test_a_reused_song_wav_that_cannot_be_read_is_an_error(fake_install, flac, tmp_path):
    out = tmp_path / "out"
    assert prepare(flac, "-o", out).exit_code == 0
    (out / "song.wav").write_bytes(b"not audio")

    result = prepare(flac, "-o", out)

    assert result.exit_code == 1
    assert result.output.splitlines()[-1].startswith(
        f"error: {out / 'song.wav'}: cannot read audio: "
    )


def test_a_run_with_the_transcription_kept_decodes_and_generates_again(
    fake_install, flac, tmp_path
):
    out = tmp_path / "out"
    assert prepare(flac, "-o", out).exit_code == 0
    for name in ("song.wav", "melody.mid", "cover.mid"):
        (out / name).unlink()
    calls = len(fake_install.calls())

    result = prepare(flac, "-o", out)

    assert result.exit_code == 0, result.output
    assert [call[1:3] for call in fake_install.calls()[calls:]] == [["-m", "piano_cover.generate"]]
    assert result.output.splitlines()[0] == f"reusing {out / 'source.mid'}"
    assert soundfile.info(out / "song.wav").samplerate == RATE
    assert listing(out) == sorted([*OUTPUTS, "transcribe.log", "generate.log"])


def test_prepare_refuses_to_overwrite_its_input(fake_install, synth, tmp_path):
    wav = tmp_path / "in" / "song.wav"
    wav.parent.mkdir()
    soundfile.write(wav, synth, SAMPLE_RATE)
    before = wav.read_bytes()

    result = prepare(wav, "-o", wav.parent)

    assert result.exit_code == 2
    assert "would overwrite an input" in " ".join(result.output.split())
    assert wav.read_bytes() == before
    assert fake_install.records() == []


def test_a_failing_transcription_keeps_the_decoded_song(fake_install, flac, tmp_path):
    fake_install.log.with_name("fail").touch()
    out = tmp_path / "out"

    result = prepare(flac, "-o", out)

    assert result.exit_code == 1
    log = out / "transcribe.log"
    assert f"error: tsumugi transcribe failed (1): RuntimeError: boom; log: {log}" in result.output
    assert listing(out) == ["song.wav", "transcribe.log"]


def test_a_stopped_run_stops_the_worker_and_leaves_no_scratch(
    fake_install, flac, interrupt_after_started, tmp_path
):
    fake_install.log.with_name("hang").touch()
    out = tmp_path / "out"

    result = prepare(flac, "-o", out)

    # Typer's KeyboardInterrupt path: exit 130, as a shell reports a SIGINT.
    assert result.exit_code == 130, result.output
    [proc] = interrupt_after_started
    assert proc.returncode == -signal.SIGTERM
    assert listing(out) == ["song.wav", "transcribe.log"]


def test_prepare_needs_the_tools_installed(monkeypatch, flac, tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("PIANOIZE_HOME", str(home))
    monkeypatch.setenv("HF_HUB_CACHE", str(tmp_path / "hub"))

    result = prepare(flac, "-o", tmp_path / "out")

    assert result.exit_code == 1
    assert result.output.startswith(f"error: not installed under {home}: tsumugi at ")
    assert result.output.endswith("; run `pianoize setup`\n")


def test_prepare_names_audio_it_cannot_decode(fake_install, tmp_path):
    text = tmp_path / "song.txt"
    text.write_text("not audio", encoding="utf-8")
    out = tmp_path / "out"

    result = prepare(text, "-o", out)

    assert result.exit_code == 1
    assert result.output == (
        f"error: decode: cannot read {text}: Format not recognised; "
        "the decoder reads wav, flac, ogg and mp3\n"
    )
    assert listing(out) == []
    assert fake_install.records() == []


def test_prepare_names_a_song_it_cannot_write(fake_install, flac, monkeypatch, tmp_path):
    def fail(*args, **kwargs):
        raise soundfile.LibsndfileError(2, prefix="Error opening 'song.wav': ")

    monkeypatch.setattr(soundfile, "write", fail)
    out = tmp_path / "out"

    result = prepare(flac, "-o", out)

    assert result.exit_code == 1
    assert result.output == f"error: decode: cannot write {out / 'song.wav'}: System error\n"
    assert listing(out) == []


def test_prepare_needs_a_melody_track(fake_install, flac, tmp_path):
    fake_install.log.with_name("no-melody").touch()
    out = tmp_path / "out"

    result = prepare(flac, "-o", out)

    assert result.exit_code == 1
    assert "error: melody: no track named 'melody'; tracks named: " in result.output
    assert listing(out) == ["song.wav", "source.mid", "transcribe.log"]
