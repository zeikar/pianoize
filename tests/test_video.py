import numpy as np
import pytest
import soundfile
from conftest import SAMPLE_RATE

from pianoize import video


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
