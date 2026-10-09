import os
import shutil

import mido
import pytest
import soundfile
from typer.testing import CliRunner

from pianoize import render
from pianoize.cli import app

real_fluidsynth = pytest.mark.skipif(
    shutil.which("fluidsynth") is None or not os.environ.get("PIANOIZE_SOUNDFONT"),
    reason="needs fluidsynth on PATH and PIANOIZE_SOUNDFONT",
)


def _two_channel_midi() -> mido.MidiFile:
    mid = mido.MidiFile(ticks_per_beat=480)
    track = mido.MidiTrack()
    mid.tracks.append(track)
    track.append(mido.MetaMessage("set_tempo", tempo=400000, time=0))
    track.append(mido.Message("control_change", channel=0, control=0, value=3, time=0))
    track.append(mido.Message("program_change", channel=0, program=5, time=0))
    track.append(mido.Message("control_change", channel=0, control=64, value=127, time=0))
    track.append(mido.Message("control_change", channel=1, control=64, value=0, time=0))
    for channel in (0, 1):
        track.append(mido.Message("note_on", channel=channel, note=60, velocity=80, time=0))
    for channel in (0, 1):
        track.append(mido.Message("note_off", channel=channel, note=60, time=480))
    return mid


def _messages(mid: mido.MidiFile, type_: str) -> list:
    return [m for track in mid.tracks for m in track if m.type == type_]


def test_normalize_keeps_overlapping_same_pitch_notes_on_two_channels():
    out = render.normalize(_two_channel_midi())

    assert {m.channel for m in _messages(out, "note_on")} == {0, 1}


def test_normalize_moves_the_drum_channel_to_a_free_one_with_program_zero():
    mid = _two_channel_midi()
    mid.tracks[0].insert(1, mido.Message("program_change", channel=9, program=40, time=0))
    mid.tracks[0].append(mido.Message("note_on", channel=9, note=62, velocity=80, time=0))

    out = render.normalize(mid)

    channels = {m.channel for m in _messages(out, "note_on")}
    assert channels == {0, 1, 2}
    assert 9 not in {m.channel for track in out.tracks for m in track if hasattr(m, "channel")}
    assert {(m.channel, m.program) for m in _messages(out, "program_change")} == {
        (0, 0),
        (1, 0),
        (2, 0),
    }
    assert all(m.value == 0 for m in _messages(out, "control_change") if m.control == 0)


def test_normalize_keeps_tempo_and_each_channels_sustain():
    out = render.normalize(_two_channel_midi())

    assert [m.tempo for m in _messages(out, "set_tempo")] == [400000]
    pedal = {m.channel: m.value for m in _messages(out, "control_change") if m.control == 64}
    assert pedal == {0: 127, 1: 0}


def test_render_returns_the_clips_peak(tmp_path, make_midi, fake_fluidsynth):
    wav = tmp_path / "out.wav"

    peak = render.render(make_midi([("C:maj", 4)]), wav, tmp_path / "font.sf2")

    assert peak == pytest.approx(float(abs(fake_fluidsynth.clip).max()), abs=1e-4)
    assert fake_fluidsynth.calls[0]["wav"] == wav
    assert not fake_fluidsynth.calls[0]["mid"].exists()


def test_failed_render_raises_with_stderr_and_leaves_no_temp_file(
    tmp_path, make_midi, fake_fluidsynth
):
    fake_fluidsynth.fail = "bad soundfont"

    with pytest.raises(render.RenderError, match="bad soundfont"):
        render.render(make_midi([("C:maj", 4)]), tmp_path / "out.wav", tmp_path / "font.sf2")

    assert not fake_fluidsynth.calls[0]["mid"].exists()
    assert not fake_fluidsynth.calls[0]["mid"].parent.exists()
    assert not (tmp_path / "out.wav").exists()


def test_empty_audio_raises(tmp_path, make_midi, fake_fluidsynth):
    fake_fluidsynth.clip = fake_fluidsynth.clip[:0]

    with pytest.raises(render.RenderError, match="no"):
        render.render(make_midi([("C:maj", 4)]), tmp_path / "out.wav", tmp_path / "font.sf2")


def test_silent_audio_raises_and_leaves_no_file(tmp_path, make_midi, fake_fluidsynth):
    fake_fluidsynth.clip = fake_fluidsynth.clip * 0

    with pytest.raises(render.RenderError, match="silent"):
        render.render(make_midi([("C:maj", 4)]), tmp_path / "out.wav", tmp_path / "font.sf2")

    assert not (tmp_path / "out.wav").exists()


def test_normalize_fails_when_the_drum_channel_cannot_move():
    mid = mido.MidiFile()
    mid.tracks.append(mido.MidiTrack())
    for channel in range(16):
        mid.tracks[0].append(mido.Message("note_on", channel=channel, note=60, velocity=80))

    with pytest.raises(render.RenderError, match="channel"):
        render.normalize(mid)


def test_normalize_without_a_drum_channel_needs_no_free_channel():
    mid = mido.MidiFile()
    mid.tracks.append(mido.MidiTrack())
    for channel in range(16):
        if channel != 9:
            mid.tracks[0].append(mido.Message("note_on", channel=channel, note=60, velocity=80))

    assert len(_messages(render.normalize(mid), "note_on")) == 15


def test_missing_binary_raises(tmp_path, make_midi):
    with pytest.raises(render.RenderError, match="not found"):
        render.render(
            make_midi([("C:maj", 4)]),
            tmp_path / "out.wav",
            tmp_path / "font.sf2",
            fluidsynth="no-such-fluidsynth",
        )


def test_cli_render_needs_a_soundfont(tmp_path, make_midi, monkeypatch):
    monkeypatch.delenv("PIANOIZE_SOUNDFONT", raising=False)
    mid = tmp_path / "in.mid"
    make_midi([("C:maj", 4)]).save(mid)

    result = CliRunner().invoke(app, ["render", str(mid), "-o", str(tmp_path / "out.wav")])

    assert result.exit_code == 2
    assert "--soundfont" in result.output


def test_cli_render_prints_the_peak_from_the_env_soundfont(
    tmp_path, make_midi, fake_fluidsynth, monkeypatch
):
    monkeypatch.setenv("PIANOIZE_SOUNDFONT", str(tmp_path / "font.sf2"))
    mid = tmp_path / "in.mid"
    make_midi([("C:maj", 4)]).save(mid)

    result = CliRunner().invoke(app, ["render", str(mid), "-o", str(tmp_path / "out.wav")])

    assert result.exit_code == 0
    assert result.stdout.startswith("peak 0.5")


def test_cli_render_reports_a_render_error(tmp_path, make_midi, fake_fluidsynth, monkeypatch):
    monkeypatch.setenv("PIANOIZE_SOUNDFONT", str(tmp_path / "font.sf2"))
    fake_fluidsynth.fail = "boom"
    mid = tmp_path / "in.mid"
    make_midi([("C:maj", 4)]).save(mid)

    result = CliRunner().invoke(app, ["render", str(mid), "-o", str(tmp_path / "out.wav")])

    assert result.exit_code == 1
    assert "error:" in result.output and "boom" in result.output


@pytest.mark.fluidsynth
@real_fluidsynth
def test_real_render(tmp_path, make_midi):
    wav = tmp_path / "out.wav"

    peak = render.render(make_midi([("C:maj", 4)]), wav, os.environ["PIANOIZE_SOUNDFONT"])

    info = soundfile.info(wav)
    assert peak > 0.01
    # 4 beats at 120 BPM is 2.0 s; Salamander's release tail adds about 3 s (4.88 s measured).
    assert 2.0 < info.duration < 8.0


def test_cli_render_warns_when_the_peak_is_near_clipping(
    tmp_path, make_midi, fake_fluidsynth, monkeypatch
):
    monkeypatch.setenv("PIANOIZE_SOUNDFONT", str(tmp_path / "font.sf2"))
    fake_fluidsynth.clip = fake_fluidsynth.clip * 2
    mid = tmp_path / "in.mid"
    make_midi([("C:maj", 4)]).save(mid)

    result = CliRunner().invoke(
        app, ["render", str(mid), "-o", str(tmp_path / "out.wav"), "--gain", "0.8"]
    )

    assert result.exit_code == 0
    assert fake_fluidsynth.calls[0]["gain"] == 0.8
    assert "warning" in result.output
