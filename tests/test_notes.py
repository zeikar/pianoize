import mido
import pytest

from pianoize import melody, notes
from pianoize.notes import NoteError
from pianoize.timeline import KEYS, beat_position

# 480 ticks per beat: 120 bpm for the first two beats, then 60 bpm.
TWO_TEMPOS = [(0, 120), (960, 60)]


def note(onset: float, pitch: int, velocity: int = 80) -> notes.Note:
    tick = round(onset * 1000)
    return notes.Note(tick, tick + 100, pitch, velocity, 0, onset, onset + 0.1)


def test_pairing_across_a_tempo_change(tick_midi):
    midi = tick_midi([(480, 960, 60, 80), (960, 1440, 62, 70)], tempos=TWO_TEMPOS)
    first, second = notes.read(midi)
    assert (first.on_tick, first.off_tick, first.pitch, first.velocity) == (480, 960, 60, 80)
    assert (first.onset, first.offset) == pytest.approx((0.5, 1.0))
    assert first.id == "t480p60"
    assert (second.onset, second.offset) == pytest.approx((1.0, 2.0))  # 60 bpm: a beat is 1 s


def test_read_pairs_like_melody_notes(tick_midi):
    midi = tick_midi(
        [(0, 960, 60, 80), (480, 1200, 67, 50), (600, 1500, 67, 60)],
        tempos=TWO_TEMPOS,
        meta=[(480, mido.Message("note_on", note=60, velocity=0))],  # ends the 60 early
    )
    midi.tracks[0].append(mido.Message("note_on", note=72, velocity=50, time=0))  # dangling
    midi.tracks[0].append(mido.MetaMessage("end_of_track", time=480))
    found = [(n.onset, n.offset, n.pitch) for n in notes.read(midi)]
    assert len(found) == 4  # the re-strike ended the first 67; the 60's later note-off is stray
    assert found[0][2] == 60 and found[0][1] == pytest.approx(notes.read(midi)[1].onset)
    assert found == pytest.approx(melody.notes(midi))


def test_tempo_on_another_track_is_honoured(tick_midi):
    midi = tick_midi([(960, 1440, 60, 80)])
    tempo_track = mido.MidiTrack([mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(60), time=0)])
    midi.tracks.insert(0, tempo_track)
    (found,) = notes.read(midi)
    assert (found.onset, found.offset) == pytest.approx((2.0, 3.0))


def test_tick_midi_places_a_control_change_at_its_tick(tick_midi):
    cc = mido.Message("control_change", control=64, value=127)
    midi = tick_midi([(0, 100, 60, 80)], meta=[(50, cc)])
    assert [(m.type, m.time) for m in midi.tracks[0]][:3] == [
        ("note_on", 0),
        ("control_change", 50),
        ("note_off", 50),
    ]


def test_tick_at_inverts_onset(tick_midi):
    on_ticks = [0, 100, 479, 960, 1000, 1537, 2400]
    midi = tick_midi([(t, t + 50, 60 + i, 80) for i, t in enumerate(on_ticks)], tempos=TWO_TEMPOS)
    found = notes.read(midi)
    assert [notes.tick_at(midi, n.onset) for n in found] == on_ticks
    assert [notes.tick_at(midi, n.offset) for n in found] == [t + 50 for t in on_ticks]


def test_check_editable_accepts_one_track(tick_midi):
    notes.check_editable(tick_midi([(0, 100, 60, 80), (0, 100, 64, 80)]))


def test_check_editable_refuses_two_tracks(tick_midi):
    midi = tick_midi([(0, 100, 60, 80)])
    other = tick_midi([(0, 100, 64, 80)])
    midi.tracks.append(other.tracks[0])
    with pytest.raises(NoteError, match="2 tracks"):
        notes.check_editable(midi)


def test_check_editable_refuses_two_channels(tick_midi):
    midi = tick_midi([(0, 100, 60, 80), (0, 100, 64, 80)])
    for message in midi.tracks[0]:
        if message.type in ("note_on", "note_off") and message.note == 64:
            message.channel = 1
    with pytest.raises(NoteError, match="2 channels"):
        notes.check_editable(midi)


def test_check_editable_refuses_a_duplicate_id(tick_midi):
    # Same pitch struck twice on one tick: the second strike ends the first, both get t0p60.
    midi = tick_midi([(0, 100, 60, 80), (0, 200, 60, 80)])
    with pytest.raises(NoteError, match="t0p60"):
        notes.check_editable(midi)


def test_clusters_group_by_the_first_onset():
    found = [note(0.0, 60), note(0.020, 64), note(0.040, 67), note(1.0, 72)]
    groups = notes.clusters(found)
    assert [[n.pitch for n in g] for g in groups] == [[60, 64], [67], [72]]


def test_protected_matches_octave_up_and_unison():
    melody = [note(1.0, 60), note(2.0, 62)]
    cover = [note(1.010, 72), note(2.0, 62)]
    assert notes.protected(cover, melody) == {c.id for c in cover}


def test_protected_refuses_below_non_top_and_far_notes():
    melody = [note(1.0, 60), note(2.0, 60), note(3.0, 60)]
    below = note(1.0, 48)  # an octave under the melody
    covered = note(2.0, 60)  # same pitch class, but a higher note starts with it
    cover_top = note(2.010, 64)
    far = note(3.080, 60)  # 80 ms away
    assert notes.protected([below, covered, cover_top, far], melody) == set()


def test_beat_position_extrapolates_both_ends():
    timeline = {"beats": [1.0, 1.5, 2.0, 3.0]}
    assert beat_position(timeline, 1.25) == pytest.approx(0.5)
    assert beat_position(timeline, 2.5) == pytest.approx(2.5)
    assert beat_position(timeline, 0.5) == pytest.approx(-1.0)  # 0.5 s beat interval at the start
    assert beat_position(timeline, 4.0) == pytest.approx(4.0)  # 1 s beat interval at the end


def test_keys_are_the_24_labels():
    assert len(KEYS) == 24 and KEYS[0] == "C:maj" and KEYS[-1] == "B:min"
