import re
import signal
from pathlib import Path

import mido
import numpy as np
import pytest
import soundfile
from conftest import SAMPLE_RATE
from test_steady import bent_transcription, random_transcription
from typer.testing import CliRunner

from pianoize import notes
from pianoize.cli import app

OUTPUTS = ("song.wav", "transcription.mid", "source.mid", "melody.mid", "cover.mid")
# What a run reuses with every output there: a source.mid already made needs no transcription.mid.
REUSED = ("song.wav", "source.mid", "melody.mid", "cover.mid")
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


def test_prepare_writes_the_five_files_and_a_summary(fake_install, flac, tmp_path):
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
    # The fake's transcription strikes its three notes at once.
    assert "tempo grid: keeping tsumugi's tempo map: 1 distinct attacks, fewer than 300" in lines
    assert (out / "source.mid").read_bytes() == (out / "transcription.mid").read_bytes()
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
    assert reused == [f"reusing {out / name}" for name in REUSED]


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
    for name in ("song.wav", "source.mid", "melody.mid", "cover.mid"):
        (out / name).unlink()
    calls = len(fake_install.calls())

    result = prepare(flac, "-o", out)

    assert result.exit_code == 0, result.output
    assert [call[1:3] for call in fake_install.calls()[calls:]] == [["-m", "piano_cover.generate"]]
    lines = result.output.splitlines()
    assert lines[0] == f"reusing {out / 'transcription.mid'}"
    assert any(line.startswith("tempo grid: ") for line in lines)
    assert soundfile.info(out / "song.wav").samplerate == RATE
    assert listing(out) == sorted([*OUTPUTS, "transcribe.log", "generate.log"])


def test_a_directory_from_before_the_grid_is_reused_as_it_is(fake_install, flac, tmp_path):
    out = tmp_path / "out"
    assert prepare(flac, "-o", out).exit_code == 0
    (out / "transcription.mid").unlink()
    calls = len(fake_install.records())

    result = prepare(flac, "-o", out)

    assert result.exit_code == 0, result.output
    assert len(fake_install.records()) == calls
    reused = [line for line in result.output.splitlines() if line.startswith("reusing ")]
    assert reused == [f"reusing {out / name}" for name in REUSED]
    assert "transcription.mid" not in listing(out)


def test_a_steady_transcription_is_gridded(fake_install, flac, tmp_path):
    fixture = fake_install.log.with_name("transcription.mid")
    bent_transcription().save(fixture)
    out = tmp_path / "out"

    result = prepare(flac, "-o", out)

    assert result.exit_code == 0, result.output
    assert (out / "transcription.mid").read_bytes() == fixture.read_bytes()
    segments = notes.tempo_map(mido.MidiFile(out / "source.mid"))
    assert len(segments) == 2
    assert segments[1][1] == pytest.approx(0.5)
    # The melody is taken from the gridded file, not from tsumugi's.
    assert notes.tempo_map(mido.MidiFile(out / "melody.mid")) == segments
    assert "tempo grid: 120.00 bpm, first downbeat at 0.500 s, " in result.output
    # The bent map runs 8 of its 48 bars at half speed.
    assert (
        "tempo grid: tsumugi also ran 17% of its seconds at 60.00 bpm; the grid takes 120.00, "
        "the octave it held longer; check the bars by ear"
    ) in result.output
    _, generator = (r["argv"] for r in fake_install.records())
    assert option(generator, "--source") == str(out / "source.mid")


def test_a_transcription_with_no_steady_tempo_keeps_its_map(fake_install, flac, tmp_path):
    midi = random_transcription()
    # The fixture's one track is the piano; prepare takes the melody from a track of that name.
    midi.tracks.append(mido.MidiTrack([mido.MetaMessage("track_name", name="melody")]))
    midi.save(fake_install.log.with_name("transcription.mid"))
    out = tmp_path / "out"

    result = prepare(flac, "-o", out)

    assert result.exit_code == 0, result.output
    assert (out / "cover.mid").is_file()
    assert (out / "source.mid").read_bytes() == (out / "transcription.mid").read_bytes()
    assert "tempo grid: keeping tsumugi's tempo map: best fit " in result.output


def test_the_same_transcription_grids_to_the_same_bytes(fake_install, flac, tmp_path):
    bent_transcription().save(fake_install.log.with_name("transcription.mid"))
    out = tmp_path / "out"
    assert prepare(flac, "-o", out).exit_code == 0
    first = (out / "source.mid").read_bytes()
    for name in ("source.mid", "melody.mid", "cover.mid"):
        (out / name).unlink()

    result = prepare(flac, "-o", out)

    assert result.exit_code == 0, result.output
    assert (out / "source.mid").read_bytes() == first


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


def test_an_instrumental_prepares_without_a_melody(fake_install, flac, tmp_path):
    fake_install.log.with_name("no-melody").touch()
    out = tmp_path / "out"

    result = prepare(flac, "-o", out)

    assert result.exit_code == 0, result.output
    assert listing(out) == sorted(
        [
            "song.wav",
            "transcription.mid",
            "source.mid",
            "cover.mid",
            "transcribe.log",
            "generate.log",
        ]
    )
    assert fake_install.records()[-1]["argv"][1:3] == ["-m", "piano_cover.generate"]
    assert (
        "melody.mid: none: no track named 'melody'; --melody-track NAME takes a track as the melody"
        in result.output.splitlines()
    )


def test_melody_track_takes_the_named_track(fake_install, flac, tmp_path):
    out = tmp_path / "out"

    result = prepare(flac, "-o", out, "--melody-track", "piano")

    assert result.exit_code == 0, result.output
    assert [t.name for t in mido.MidiFile(out / "melody.mid").tracks] == ["", "piano"]
    assert "melody.mid: 1 notes" in result.output.splitlines()


def unboxed(output: str) -> str:
    """Typer's usage-error box with its borders removed and its wrapped lines joined."""
    return " ".join(output.translate(str.maketrans("", "", "│╭╮╰╯─")).split())


UNKNOWN_TRACK = (
    "no track named 'nope'; tracks named: 'Predicted Tempo Map', 'Predicted Chords', 'piano', "
    "'melody', 'drums'"
)


def test_an_unknown_melody_track_is_a_usage_error(fake_install, flac, tmp_path):
    out = tmp_path / "out"

    result = prepare(flac, "-o", out, "--melody-track", "nope")

    assert result.exit_code == 2
    assert UNKNOWN_TRACK in unboxed(result.output)
    assert "--melody-track" in result.output
    assert listing(out) == ["song.wav", "source.mid", "transcribe.log", "transcription.mid"]
    calls = len(fake_install.records())

    result = prepare(flac, "-o", out, "--melody-track", "piano")

    assert result.exit_code == 0, result.output
    assert f"reusing {out / 'source.mid'}" in result.output.splitlines()
    assert len(fake_install.records()) == calls + 1


def test_an_unknown_melody_track_is_refused_on_a_finished_directory(fake_install, flac, tmp_path):
    out = tmp_path / "out"
    assert prepare(flac, "-o", out).exit_code == 0
    calls = len(fake_install.records())
    before = {p.name: p.read_bytes() for p in out.iterdir()}

    result = prepare(flac, "-o", out, "--melody-track", "nope")

    assert result.exit_code == 2
    assert UNKNOWN_TRACK in unboxed(result.output)
    assert len(fake_install.records()) == calls
    assert {p.name: p.read_bytes() for p in out.iterdir()} == before

    result = prepare(flac, "-o", out, "--melody-track", "melody")

    assert result.exit_code == 0, result.output
    assert f"reusing {out / 'melody.mid'}" in result.output.splitlines()
