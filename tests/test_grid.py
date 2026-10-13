import mido
import pytest
from test_regrid import HICCUP
from typer.testing import CliRunner

from pianoize import bars, grid, notes
from pianoize.cli import app
from pianoize.dump import lines

BAR = 1920  # at 480 ticks a beat, in 4/4


def track(name: str | None, events: list[tuple[int, mido.Message | mido.MetaMessage]], end: int):
    """A track from (tick, message) pairs, closed by an end_of_track at tick `end`."""
    found = mido.MidiTrack()
    if name is not None:
        found.append(mido.MetaMessage("track_name", name=name))
    now = 0
    for tick, message in sorted(events, key=lambda e: e[0]):
        found.append(message.copy(time=tick - now))
        now = tick
    found.append(mido.MetaMessage("end_of_track", time=end - now))
    return found


def played(channel: int, program: int, notes_: list[tuple[int, int | None, int]]):
    """(tick, message) pairs of a program change and (on, off, pitch) notes; an off of None leaves
    the note open."""
    events = [(0, mido.Message("program_change", channel=channel, program=program))]
    for on, off, pitch in notes_:
        events.append((on, mido.Message("note_on", channel=channel, note=pitch, velocity=80)))
        if off is not None:
            events.append((off, mido.Message("note_off", channel=channel, note=pitch)))
    return events


def source_midi(
    tempos: list[tuple[int, float]] | None = None,
    piano: list[tuple[int, int | None, int]] | None = None,
) -> mido.MidiFile:
    """A file shaped like tsumugi's transcription: a conductor with tempos, a time signature,
    text and lyrics; a track of chord markers; an empty unnamed track; then the band."""
    tempos = tempos or [(0, 120), (BAR, 100)]
    conductor = [
        (tick, mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(b))) for tick, b in tempos
    ]
    conductor += [
        (0, mido.MetaMessage("time_signature", numerator=4, denominator=4)),
        (0, mido.MetaMessage("text", text="words")),
        (BAR, mido.MetaMessage("lyrics", text="la")),
    ]
    chords = [
        (0, mido.MetaMessage("marker", text="C")),
        (BAR, mido.MetaMessage("marker", text="F")),
    ]
    bass = played(3, 33, [(0, 960, 36), (BAR, 2 * BAR - 480, 38), (2 * BAR, None, 41)])
    bass.append((960, mido.MetaMessage("marker", text="bass marker")))
    piano = piano or [(0, 480, 60), (BAR, BAR + 480, 64)]
    last_off = max(off for _, off, _ in piano if off is not None)
    midi = mido.MidiFile(type=1, ticks_per_beat=480)
    midi.tracks += [
        track("Predicted Tempo Map", conductor, max(2 * BAR, tempos[-1][0]) + 100),
        track("Predicted Chords", chords, 2 * BAR),
        mido.MidiTrack([mido.MetaMessage("end_of_track")]),
        track("piano", played(1, 0, piano), last_off + BAR),
        track("electric_bass", bass, 3 * BAR),
        track("strings", played(4, 48, [(0, BAR, 72)]), BAR),
        track("drums", played(9, 0, [(0, 120, 36)]), BAR),
    ]
    return midi


def final_tick(found: mido.MidiTrack) -> int:
    return sum(m.time for m in found)


def of_type(found: mido.MidiTrack, *kinds: str) -> list[tuple[int, mido.Message]]:
    at, out = 0, []
    for m in found:
        at += m.time
        if m.type in kinds:
            out.append((at, m))
    return out


def test_the_default_build_has_a_conductor_then_piano_and_bass():
    built = grid.build(source_midi(), list(grid.DEFAULT_TRACKS))
    assert built.type == 1
    assert built.ticks_per_beat == 480
    assert [t.name for t in built.tracks] == ["", "piano", "electric_bass"]


def test_the_conductor_holds_every_tempo_signature_and_marker_by_tick():
    built = grid.build(source_midi(), list(grid.DEFAULT_TRACKS))
    conductor = built.tracks[0]
    assert {m.type for m in conductor} == {"set_tempo", "time_signature", "marker", "end_of_track"}
    found = [
        (t, m.type, getattr(m, "text", None))
        for t, m in of_type(conductor, "set_tempo", "time_signature", "marker")
    ]
    assert found == [
        (0, "set_tempo", None),
        (0, "time_signature", None),
        (0, "marker", "C"),
        (960, "marker", "bass marker"),
        (BAR, "set_tempo", None),
        (BAR, "marker", "F"),
    ]
    assert final_tick(conductor) == 3 * BAR  # the latest end of any source track


def test_the_copied_tracks_keep_their_messages_but_the_conductor_ones():
    source = source_midi()
    built = grid.build(source, list(grid.DEFAULT_TRACKS))
    for copy, original in zip(built.tracks[1:], [source.tracks[3], source.tracks[4]], strict=True):
        kept = [m for m in original if m.type not in grid.CONDUCTOR and m.type != "end_of_track"]
        assert [m.type for m in copy][:-1] == [m.type for m in kept]
        assert copy[0].name == original.name
        assert of_type(copy, "program_change") == of_type(original, "program_change")
        assert of_type(copy, "note_on", "note_off") == of_type(original, "note_on", "note_off")
        assert not of_type(copy, "marker")
        assert final_tick(copy) == final_tick(original)


def test_a_conductor_without_markers_leaves_them_on_the_copied_track():
    source = source_midi()
    # The bass with its marker, renamed.
    melody = mido.MidiTrack(
        m.copy(name="melody") if m.type == "track_name" else m for m in source.tracks[4]
    )
    source.tracks.append(melody)
    built = grid.build(source, ["melody"], conductor=("set_tempo", "time_signature"))
    conductor, copied = built.tracks
    assert {m.type for m in conductor} == {"set_tempo", "time_signature", "end_of_track"}
    assert final_tick(conductor) == 3 * BAR
    assert list(copied) == list(melody)


def test_a_note_only_the_end_of_track_closes_keeps_its_length():
    source = source_midi()
    built = grid.build(source, list(grid.DEFAULT_TRACKS))
    assert notes.read(built, [2])[-1].off_tick == 3 * BAR
    assert notes.read(source, [4])[-1].off_tick == 3 * BAR
    meter = bars.meter(built)
    assert bars.bar_count(built, meter) == bars.bar_count(source, bars.meter(source)) == 3


def test_tracks_are_copied_in_the_files_order():
    built = grid.build(source_midi(), ["strings", "electric_bass"])
    assert [t.name for t in built.tracks] == ["", "electric_bass", "strings"]


def test_two_builds_give_the_same_bytes(tmp_path):
    paths = [tmp_path / "a.mid", tmp_path / "b.mid"]
    for path in paths:
        grid.build(source_midi(), list(grid.DEFAULT_TRACKS)).save(path)
    assert paths[0].read_bytes() == paths[1].read_bytes()


def run(tmp_path, source: mido.MidiFile, *args: str, out: str = "grid.mid"):
    path = tmp_path / "source.mid"
    source.save(path)
    return CliRunner().invoke(app, ["build-grid", str(path), "-o", str(tmp_path / out), *args])


def test_cli_prints_the_conductor_and_each_track(tmp_path):
    result = run(tmp_path, source_midi())
    assert result.exit_code == 0, result.output
    assert result.output.splitlines() == [
        "conductor: 2 tempo changes, 1 time signatures, 3 markers",
        "piano: 2 notes",
        "electric_bass: 3 notes",
    ]
    assert mido.MidiFile(tmp_path / "grid.mid").tracks[1].name == "piano"


def test_cli_track_option_replaces_the_default(tmp_path):
    result = run(tmp_path, source_midi(), "--track", "strings")
    assert result.output.splitlines()[1:] == ["strings: 1 notes"]


def test_cli_lists_the_default_in_its_help():
    result = CliRunner().invoke(app, ["build-grid", "--help"], terminal_width=200)
    flat = " ".join(result.output.replace("│", " ").split())
    assert "--track" in flat
    assert "Default: piano, electric_bass." in flat


def no_tempo() -> mido.MidiFile:
    midi = source_midi()
    for found in midi.tracks:
        found[:] = [m for m in found if m.type != "set_tempo"]
    return midi


def type_two() -> mido.MidiFile:
    midi = source_midi()
    midi.type = 2
    return midi


@pytest.mark.parametrize(
    ("source", "args", "message"),
    [
        (source_midi(), ["--track", "oboe"], "no track named 'oboe'; tracks named: "),
        (no_tempo(), [], "no tempo map: no set_tempo message on any track"),
        (type_two(), [], "a type 2 MIDI file's tracks share no timeline to build a grid on"),
    ],
    ids=["unknown track", "no tempo", "type 2"],
)
def test_cli_refuses_what_it_cannot_build_on(tmp_path, source, args, message):
    result = run(tmp_path, source, *args)
    assert result.exit_code == 1
    assert message in " ".join(result.output.split())
    assert not (tmp_path / "grid.mid").exists()
    assert "Traceback" not in result.output


def test_the_missing_name_is_listed_with_the_tracks(tmp_path):
    result = run(tmp_path, source_midi(), "--track", "oboe")
    assert "'Predicted Tempo Map', 'Predicted Chords', 'piano', 'electric_bass'" in result.output


def test_cli_refuses_to_overwrite_its_input(tmp_path):
    source = tmp_path / "source.mid"
    source_midi().save(source)
    before = source.read_bytes()
    (tmp_path / "sub").mkdir()
    result = CliRunner().invoke(
        app, ["build-grid", str(source), "-o", str(tmp_path / "sub" / ".." / "source.mid")]
    )
    assert result.exit_code == 2
    assert "would overwrite an input" in " ".join(result.output.split())
    assert source.read_bytes() == before


def test_a_grid_of_a_hiccup_source_regrids(tmp_path):
    tempos = [(round(at * BAR), bpm) for at, bpm in HICCUP]
    piano = [(tick, tick + 240, 60) for tick in range(0, 10 * BAR, 480)]
    result = run(tmp_path, source_midi(tempos, piano))
    assert result.exit_code == 0, result.output
    again = CliRunner().invoke(
        app, ["regrid", str(tmp_path / "grid.mid"), "-o", str(tmp_path / "regrid.mid")]
    )
    assert again.exit_code == 0, again.output
    assert again.output.splitlines() == ["bars 3-6: 125.00, 159.09, 125.00 BPM -> 5 bars at 175.00"]


def test_a_grid_reads_as_a_cover(tick_midi):
    built = grid.build(source_midi(), list(grid.DEFAULT_TRACKS))
    found = lines(built, tick_midi([]))
    assert found[0].startswith("=== bar 1")
    assert "C" in found[0] and "bass marker" in found[0]
    assert found[1] == "C 0:C2(8,80),C4(4,80)"
