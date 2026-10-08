import mido
import pytest
from typer.testing import CliRunner

from pianoize import melody
from pianoize.cli import app

# 120 bpm: a beat is 0.5 s. The timeline starts at 0.05 s, so C:maj covers 0.05-2.05 s.
PROGRESSION = [("C:maj", 4), ("N", 2), ("G:maj", 2, "B")]
TICKS = 480


def melody_midi(*events: tuple[float, float, int], channel: int = 0) -> mido.MidiFile:
    """A one-track MIDI at 120 bpm with (onset_s, offset_s, pitch) notes."""
    messages = []
    for onset, offset, pitch in events:
        messages.append((onset, "note_on", pitch))
        messages.append((offset, "note_off", pitch))
    messages.sort(key=lambda m: m[0])
    mid = mido.MidiFile(ticks_per_beat=TICKS)
    track = mido.MidiTrack()
    mid.tracks.append(track)
    track.append(mido.MetaMessage("set_tempo", tempo=500000, time=0))
    last = 0
    for seconds, kind, pitch in messages:
        tick = round(seconds * 2 * TICKS)
        track.append(mido.Message(kind, note=pitch, velocity=64, channel=channel, time=tick - last))
        last = tick
    return mid


def test_notes_pairs_across_tracks_and_ignores_drums():
    mid = melody_midi((1.0, 1.5, 64))
    other = mido.MidiTrack()
    other.append(mido.Message("note_on", note=67, velocity=80, time=0))
    other.append(mido.Message("note_on", note=67, velocity=0, time=TICKS))  # velocity 0 ends it
    other.append(mido.Message("note_on", note=36, velocity=80, channel=9, time=0))
    mid.tracks.append(other)
    assert melody.notes(mid) == [(0.0, 0.5, 67), (1.0, 1.5, 64)]


def test_notes_closes_a_dangling_note_at_the_end_of_the_file():
    mid = mido.MidiFile(ticks_per_beat=TICKS)
    track = mido.MidiTrack()
    mid.tracks.append(track)
    track.append(mido.Message("note_on", note=60, velocity=80, time=0))
    track.append(mido.Message("note_on", note=62, velocity=80, time=TICKS))
    assert melody.notes(mid) == [(0.0, 0.5, 60), (0.5, 0.5, 62)]


def test_monophonic_keeps_the_highest_of_a_double_and_cuts_at_the_next_onset():
    polyphonic = [
        melody.Note(*n) for n in [(0.0, 2.0, 60), (0.02, 1.0, 64), (0.5, 1.5, 62), (1.0, 2.0, 65)]
    ]
    assert melody.monophonic(polyphonic) == [(0.02, 0.5, 64), (0.5, 1.0, 62), (1.0, 2.0, 65)]


def test_monophonic_groups_by_the_first_onset_not_by_chaining():
    chained = [melody.Note(*n) for n in [(0.0, 1.0, 60), (0.025, 1.0, 62), (0.05, 1.0, 64)]]
    assert [p for _, _, p in melody.monophonic(chained)] == [62, 64]


def test_pitch_name():
    assert melody.pitch_name(60) == "C4"
    assert melody.pitch_name(66) == "F#4"


def test_clashes_counts_by_onset_and_sums_duration_per_segment(make_timeline):
    # C:maj 0.05-2.05, N 2.05-3.05, G:maj/B 3.05-4.05
    chords = make_timeline(PROGRESSION)
    report = melody.clashes(
        [
            (0.55, 0.95, 64),  # E over C: consonant
            (1.05, 1.45, 62),  # D over C: clash
            (3.55, 3.95, 71),  # B over G:maj/B: the slash bass is a tone
        ],
        chords,
    )
    assert (report.consonant_notes, report.clashing_notes) == (2, 1)
    assert report.note_ratio == 1 / 3
    assert report.consonant_seconds == pytest.approx(0.8)
    assert report.clashing_seconds == pytest.approx(0.4)
    assert report.duration_ratio == pytest.approx(0.4 / 1.2)
    assert report.clashes == [melody.Clash(1.05, 62, "C:maj")]


def test_the_slash_bass_is_a_tone_only_where_it_is_written(make_timeline):
    plain = make_timeline([("G:maj", 2)])
    slash = make_timeline([("G:maj", 2, "B")])
    assert melody.clashes([(0.1, 0.4, 71)], slash).clashing_notes == 0
    assert melody.clashes([(0.1, 0.4, 70)], slash).clashing_notes == 1
    assert melody.clashes([(0.1, 0.4, 71)], plain).clashing_notes == 0  # B is the third anyway
    assert melody.clashes([(0.1, 0.4, 65)], plain).clashing_notes == 1


def test_a_sustained_note_counts_once_by_onset_but_splits_its_duration(make_timeline):
    chords = make_timeline([("C:maj", 2), ("G:maj", 2)])  # change at 1.05 s
    report = melody.clashes([(0.55, 1.55, 64)], chords)  # E: in C, not in G
    assert (report.consonant_notes, report.clashing_notes) == (1, 0)
    assert report.consonant_seconds == pytest.approx(0.5)
    assert report.clashing_seconds == pytest.approx(0.5)
    assert report.clashes == []


def test_n_and_time_before_the_first_beat_are_left_out_of_both_ratios(make_timeline):
    chords = make_timeline(PROGRESSION)
    report = melody.clashes(
        [
            (0.0, 0.55, 60),  # onset before beats[0]: no count, only 0.5 s counted
            (2.1, 2.9, 61),  # under N: nothing
            (1.8, 2.3, 61),  # onset in C (clash); the 0.25 s under N is dropped
        ],
        chords,
    )
    assert (report.consonant_notes, report.clashing_notes) == (0, 1)
    assert report.consonant_seconds == pytest.approx(0.5)
    assert report.clashing_seconds == pytest.approx(0.25)


def test_no_counted_notes_gives_no_ratio(make_timeline):
    report = melody.clashes([(2.1, 2.9, 61)], make_timeline(PROGRESSION))
    assert report.note_ratio is None
    assert report.duration_ratio is None


def _files(tmp_path, write_timeline, *events):
    midi = tmp_path / "melody.mid"
    melody_midi(*events).save(midi)
    return midi, write_timeline(PROGRESSION)


def test_cli_prints_the_ratios_and_the_clash_list(tmp_path, write_timeline):
    midi, chords = _files(tmp_path, write_timeline, (0.55, 0.95, 64), (1.05, 1.45, 66))
    result = CliRunner().invoke(app, ["melody-clashes", str(midi), str(chords)])
    assert result.exit_code == 0, result.output
    assert "notes: 1 consonant, 1 clashing" in result.output
    assert "clash ratio by notes: 50.0%" in result.output
    assert "clash ratio by duration: 50.0%" in result.output
    assert "0:01.1  F#4  over C:maj" in result.output


def test_cli_mono_cuts_a_double_voice(tmp_path, write_timeline):
    midi, chords = _files(tmp_path, write_timeline, (0.55, 0.95, 64), (0.56, 0.95, 66))
    plain = CliRunner().invoke(app, ["melody-clashes", str(midi), str(chords)])
    mono = CliRunner().invoke(app, ["melody-clashes", str(midi), str(chords), "--mono"])
    assert "notes: 1 consonant, 1 clashing" in plain.output
    assert "notes: 0 consonant, 1 clashing" in mono.output


def test_cli_says_n_a_when_nothing_is_counted(tmp_path, write_timeline):
    midi, chords = _files(tmp_path, write_timeline, (2.1, 2.9, 61))
    result = CliRunner().invoke(app, ["melody-clashes", str(midi), str(chords)])
    assert result.exit_code == 0
    assert "clash ratio by notes: n/a" in result.output


def test_cli_reports_a_bad_midi_or_timeline(tmp_path, write_timeline):
    midi, chords = _files(tmp_path, write_timeline, (0.55, 0.95, 64))
    junk = tmp_path / "junk.mid"
    junk.write_bytes(b"not midi")
    bad = tmp_path / "bad.chords.json"
    bad.write_text("{}", encoding="utf-8")
    for args in ([junk, chords], [midi, bad]):
        result = CliRunner().invoke(app, ["melody-clashes", *map(str, args)])
        assert result.exit_code == 1
        assert result.output.startswith("error:")
        assert "Traceback" not in result.output


def test_clock_rounds_before_splitting_minutes():
    from pianoize.cli import _clock

    assert _clock(59.96) == "1:00.0"
    assert _clock(61.24) == "1:01.2"
