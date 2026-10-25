import mido
import pytest
from test_dump import named, source_midi
from test_playability import _check_cli, _cover_file

from pianoize import backing
from pianoize.arrangement import parse
from pianoize.bars import Meter
from pianoize.evidence import EvidenceError
from pianoize.notes import tempo_map

# At 480 ticks a beat: 120 a sixteenth, 60 a half-sixteenth, 1920 a 4/4 bar, 120 bpm unless a
# test sets the tempos.
METER = Meter(480, 4, 4)
BAR = 1920
NONE = "harmony backing: 0 unbacked, 0 semitone"


def band(tick_midi, piano=(), bass=(), markers=(), tempos=None, ticks_per_beat=480):
    """A source as tsumugi writes it: the tempo on a track of its own, the (tick, text) markers
    on another, then a `piano` and an `electric_bass` track of (on_tick, off_tick, pitch) notes."""
    chords = [(tick, mido.MetaMessage("marker", text=text)) for tick, text in markers]
    return source_midi(
        tick_midi,
        named(tick_midi, "Predicted Chords", [], extra=chords),
        named(tick_midi, "piano", [(*note, 80) for note in piano]),
        named(tick_midi, "electric_bass", [(*note, 80) for note in bass]),
        tempos=tempos,
        ticks_per_beat=ticks_per_beat,
    )


def unbacked(where, detail):
    """The list of one unbacked note in bar 1, at `where`, with its detail."""
    return f"bar 1 pos {where}  LH  unbacked  {detail}\nharmony backing: 1 unbacked, 0 semitone"


@pytest.fixture
def backed(tick_midi, write_score):
    """The backing list for a score of `format 1` and the lines given, on an eight-bar 4/4 cover
    with the tempos given, against `source` or else `band`'s source of the parts given."""

    def run(*lines, piano=(), bass=(), markers=(), tempos=None, source=None, **tracks):
        cover = tick_midi([(0, BAR * 8, 60, 80)], tempos=tempos)
        score = parse(write_score(*lines).read_text(encoding="utf-8"), METER.sixteenths_per_bar)
        if source is None:
            source = band(tick_midi, piano, bass, markers, tempos)
        found = backing.items(score, METER, tempo_map(cover), source, **tracks)
        return backing.report(found, METER)

    return run


@pytest.mark.parametrize(
    "part", [{"bass": [(0, BAR, 36)]}, {"piano": [(0, BAR, 60)]}, {"markers": [(0, "C")]}]
)
def test_a_root_the_bass_the_band_piano_or_the_marker_backs_is_not_listed(backed, part):
    assert backed("bar 1 | C", "  L 0:C2:4", **part) == NONE


@pytest.mark.parametrize(
    ("parts", "detail"),
    [
        ({}, "G3  bass -  piano -  marker -"),
        ({"bass": [(0, BAR, 34)]}, "G3  bass A#1  piano -  marker -"),
        ({"markers": [(0, "N")]}, "G3  bass -  piano -  marker N"),
    ],
)
def test_a_note_nothing_backs_is_listed_with_the_three_parts(backed, parts, detail):
    assert backed("bar 1 | C", "  L 0:G3:4", **parts) == unbacked(0, detail)


def test_the_list_names_each_part_held_and_the_marker_in_force(backed):
    # The bass backs A#1, and E3~ sits over it, so only E3's semitone against F4 is listed.
    parts = {"piano": [(0, BAR, 62), (0, BAR, 65)], "bass": [(0, BAR, 34)]}
    assert backed("bar 1 | N.C.", "  L 4:A#1+E3~+G3:4", markers=[(0, "A#:m7")], **parts) == (
        "bar 1 pos 4  LH  unbacked  G3  bass A#1  piano D4 F4  marker A#:m7\n"
        "bar 1 pos 4  LH  semitone  E3 against piano F4\n"
        "harmony backing: 1 unbacked, 1 semitone"
    )


@pytest.mark.parametrize(
    ("bass", "left", "found"),
    [(48, "C2", unbacked(0, "C2  bass -  piano -  marker -")), (47, "B1", NONE)],
)
def test_a_bass_note_backs_only_at_or_below_b2(backed, bass, left, found):
    assert backed("bar 1 | N.C.", f"  L 0:{left}:4", bass=[(0, BAR, bass)]) == found


@pytest.mark.parametrize(
    ("on", "off", "count"),
    [
        (480, 660, 1),  # three half-sixteenths, under an eighth
        (480, 720, 0),  # four
        (0, 960, 0),  # struck before the attack at 480, still sounding
        (490, 960, 0),  # 10 ticks late, its onset rounds to the attack's half-sixteenth
        (0, 480, 1),  # released at the attack
        (0, 470, 1),  # 10 ticks early, its end still rounds to the attack's half-sixteenth
    ],
)
def test_an_eighth_or_more_backs_while_its_rounded_ends_hold_the_attack(backed, on, off, count):
    report = backed("bar 1 | N.C.", "  L 4:C3:4", piano=[(on, off, 60)])
    assert report.splitlines()[-1] == f"harmony backing: {count} unbacked, 0 semitone"


def test_a_passing_tone_is_checked_only_as_the_lowest_left_hand_note(backed):
    assert backed("bar 1 | N.C.", "  L 0:F2~+A3~:4") == unbacked(0, "F2  bass -  piano -  marker -")
    # A semitone is listed for every struck note, ~ or not.
    piano = [(0, BAR, 54), (0, BAR, 70)]
    assert backed("bar 1 | N.C.", "  L 0:F2~+A3~:4", piano=piano) == (
        "bar 1 pos 0  LH  unbacked  F2  bass -  piano F#3 A#4  marker -\n"
        "bar 1 pos 0  LH  semitone  F2 against piano F#3\n"
        "bar 1 pos 0  LH  semitone  A3 against piano A#4\n"
        "harmony backing: 1 unbacked, 2 semitone"
    )


@pytest.mark.parametrize(
    ("root", "found"),
    [
        ("0:C2:16", NONE),  # still held under E3~
        ("0:C2:4", unbacked(4, "E3  bass C2  piano G4  marker -")),  # released at 4
    ],
)
def test_a_passing_tone_over_a_held_left_hand_note_is_not_checked(backed, root, found):
    lines = ("bar 1 | N.C.", f"  L {root} 4:E3~+G3:2")
    assert backed(*lines, piano=[(0, BAR, 67)], bass=[(0, BAR, 36)]) == found


# 13 and 1 above E3 and 1 below rub; 11 below (a major seventh), 14 and 25 above are colours.
@pytest.mark.parametrize(
    ("piano", "against"), [(65, "F4"), (53, "F3"), (51, "D#3"), (41, ""), (66, ""), (77, "")]
)
def test_a_minor_second_or_ninth_from_a_held_band_piano_note_is_listed(backed, piano, against):
    report = backed("bar 1 | N.C.", "  L 0:E3:4", piano=[(0, BAR, piano)], markers=[(0, "C")])
    listed = [f"bar 1 pos 0  LH  semitone  E3 against piano {against}"] if against else []
    assert report.splitlines() == [*listed, f"harmony backing: 0 unbacked, {len(listed)} semitone"]


@pytest.mark.parametrize("part", [{"bass": [(0, BAR, 41)]}, {"piano": [(0, 180, 41)]}])
def test_neither_the_bass_nor_a_band_piano_note_under_an_eighth_rubs(backed, part):
    # F2 is a semitone above E2, which the marker backs.
    assert backed("bar 1 | N.C.", "  L 0:E2:4", markers=[(0, "C")], **part) == NONE


@pytest.mark.parametrize(
    ("text", "classes"),
    [
        ("A#:m7/D", {10, 1, 5, 8, 2}),
        ("Bb:m7/D", {10, 1, 5, 8, 2}),
        ("Eb:7(b9)", {3, 7, 10, 1, 4}),
        ("A#", {10, 2, 5}),
        ("C:7(b9)", {0, 4, 7, 10, 1}),
        ("C:7(9,13)", {0, 4, 7, 10, 2, 9}),
        ("B:m7-5", {11, 2, 5, 9}),
        ("G:5", {7, 2}),
        ("C:foo", {0}),
        ("C:foo/E", {0, 4}),
        ("C:7(foo)", {0}),
    ],
)
def test_a_markers_text_reads_as_its_pitch_classes(text, classes):
    assert backing.marker_pitch_classes(text) == classes


@pytest.mark.parametrize("text", ["N", "Intro", "H:m", ""])
def test_no_chord_and_a_text_that_is_no_chord_back_nothing(text):
    assert backing.marker_pitch_classes(text) is None


@pytest.mark.parametrize(
    ("markers", "found"),
    [
        ([(0, "C"), (960, "F")], unbacked(4, "F2  bass -  piano -  marker C")),
        ([(0, "C"), (480, "F")], NONE),
        ([(0, "C"), (470, "F")], NONE),  # 10 ticks early: it rounds to the attack's half-sixteenth
    ],
)
def test_the_marker_in_force_is_the_last_at_or_before_the_attack(backed, markers, found):
    assert backed("bar 1 | N.C.", "  L 4:F2:4", markers=markers) == found


def test_a_source_at_another_resolution_lands_by_seconds(backed, tick_midi):
    # At 60 bpm and 240 ticks a beat, the source's tick 240 sounds at 1 s, the cover's bar 1
    # pos 8, where its marker and its C4 start; its ticks would say pos 2, its beats pos 4.
    source = band(
        tick_midi, [(240, 360, 60)], markers=[(240, "C")], tempos=[(0, 60)], ticks_per_beat=240
    )
    assert backed("bar 1 | N.C.", "  L 2:D2:2 4:D2:2 8:D3:4", source=source) == (
        "bar 1 pos 2  LH  unbacked  D2  bass -  piano -  marker -\n"
        "bar 1 pos 4  LH  unbacked  D2  bass -  piano -  marker -\n"
        "bar 1 pos 8  LH  unbacked  D3  bass -  piano C4  marker C\n"
        "harmony backing: 3 unbacked, 0 semitone"
    )


def strings(tick_midi):
    """A source whose only part is strings holding C4 through bar 1."""
    return source_midi(tick_midi, named(tick_midi, "strings", [(0, BAR, 60, 80)]))


def test_the_piano_track_names_the_band_piano_and_a_missing_default_reads_none(backed, tick_midi):
    lines = ("bar 1 | N.C.", "  L 0:C3:4")
    assert backed(*lines, source=strings(tick_midi)) == unbacked(0, "C3  bass -  piano -  marker -")
    assert backed(*lines, source=strings(tick_midi), piano_track="strings") == NONE


def test_an_empty_bass_track_reads_no_bass(backed):
    lines, bass = ("bar 1 | N.C.", "  L 0:C2:4"), [(0, BAR, 36)]
    assert backed(*lines, bass=bass) == NONE
    assert backed(*lines, bass=bass, bass_track="") == unbacked(0, "C2  bass -  piano -  marker -")


@pytest.mark.parametrize(
    "tracks", [{"piano_track": "piano"}, {"piano_track": "organ"}, {"bass_track": "synth_bass"}]
)
def test_a_track_name_passed_that_no_track_has_raises(backed, tick_midi, tracks):
    [name] = tracks.values()
    with pytest.raises(EvidenceError, match=f"^no track named '{name}'; tracks named: 'strings'$"):
        backed("bar 1 | N.C.", "  L 0:C3:4", source=strings(tick_midi), **tracks)


def test_right_hand_notes_are_never_listed(backed):
    # Nothing backs G4 or F4, and the band piano's F#4 is a semitone from both.
    assert backed("bar 1 | N.C.", "  M 0:G4:4", "  R 0:F4:4", piano=[(0, BAR, 66)]) == NONE


def test_the_list_runs_by_time_unbacked_before_semitone_then_by_pitch(backed):
    lines = ("bar 1 | N.C.", "  L 0:E2+A2+F#3:4 4:G2:4")
    found = backed(*lines, piano=[(0, BAR, 53)])
    assert found == backed(*lines, piano=[(0, BAR, 53)])  # the same inputs, the same text
    assert found == (
        "bar 1 pos 0  LH  unbacked  E2  bass -  piano F3  marker -\n"
        "bar 1 pos 0  LH  unbacked  A2  bass -  piano F3  marker -\n"
        "bar 1 pos 0  LH  unbacked  F#3  bass -  piano F3  marker -\n"
        "bar 1 pos 0  LH  semitone  E2 against piano F3\n"
        "bar 1 pos 0  LH  semitone  F#3 against piano F3\n"
        "bar 1 pos 4  LH  unbacked  G2  bass -  piano F3  marker -\n"
        "harmony backing: 4 unbacked, 2 semitone"
    )


@pytest.fixture
def files(tmp_path, tick_midi):
    """The eight-bar cover, a melody of E5 at 0 and the path a source is saved to."""
    melody = tmp_path / "melody.mid"
    tick_midi([(0, 480, 76, 100)]).save(melody)
    return _cover_file(tmp_path, tick_midi), melody, tmp_path / "source.mid"


FLAGGED = "harmony: 1 (1 flagged)\n  bar 1 pos 0  LH  harmony  L F3 over C\nproblems: 1\n"


@pytest.mark.parametrize(("left", "code", "printed"), [("C3", 0, "clean\n"), ("F3", 1, FLAGGED)])
def test_cli_lists_the_backing_last_and_keeps_the_findings_exit_code(
    tick_midi, write_score, files, left, code, printed
):
    cover, melody, source = files
    band(tick_midi).save(source)
    score = write_score("bar 1 | C", "  M 0:E5:4", f"  L 0:{left}:4")
    listed = unbacked(0, f"{left}  bass -  piano -  marker -") + "\n"
    sung = ["--melody", str(melody)]
    runs = [
        ([], printed),
        (["--source", str(source)], printed + listed),
        ([*sung, "--source", str(source)], printed + "melody missing: 0\n" + listed),
    ]
    for options, stdout in runs:
        result = _check_cli(score, cover, *options)
        assert (result.exit_code, result.stdout) == (code, stdout), result.output


def test_cli_refuses_a_type_2_source(tick_midi, write_score, files):
    cover, _, source = files
    mido.MidiFile(type=2, tracks=band(tick_midi).tracks).save(source)
    result = _check_cli(write_score("bar 1 | C", "  L 0:C3:4"), cover, "--source", str(source))
    assert result.exit_code == 1
    assert f"error: {source}: a type 2 MIDI file's tracks share no timeline" in result.output
    assert "Traceback" not in result.output


def test_cli_reads_the_band_piano_from_the_track_named(tick_midi, write_score, files):
    cover, _, source = files
    # tsumugi writes no piano track for a band without one.
    midi = band(tick_midi, bass=[(0, BAR, 33)], markers=[(0, "A:m")])
    midi.tracks = [track for track in midi.tracks if track.name != "piano"]
    midi.save(source)
    score = write_score("bar 1 | N.C.", "  L 0:A1:4 4:E3:4 8:D3:4")
    result = _check_cli(score, cover, "--source", str(source))
    listed = unbacked(8, "D3  bass A1  piano -  marker A:m")
    assert (result.exit_code, result.stdout) == (0, f"clean\n{listed}\n")
    for name in ("piano", "strings"):
        refused = _check_cli(score, cover, "--source", str(source), "--piano-track", name)
        assert (refused.exit_code, refused.stdout) == (1, "")
        tracks = "tracks named: 'Predicted Chords', 'electric_bass'"
        assert f"error: {source}: no track named '{name}'; {tracks}" in refused.output
        assert "Traceback" not in refused.output
    midi.tracks.append(named(tick_midi, "strings", [(0, BAR, 62, 80)]))
    midi.save(source)
    result = _check_cli(score, cover, "--source", str(source), "--piano-track", "strings")
    assert (result.exit_code, result.stdout) == (0, f"clean\n{NONE}\n")


def test_cli_reads_no_bass_with_an_empty_bass_track(tick_midi, write_score, files):
    cover, _, source = files
    band(tick_midi, bass=[(0, BAR, 33)]).save(source)
    score = write_score("bar 1 | N.C.", "  L 0:A1:4")
    assert _check_cli(score, cover, "--source", str(source)).stdout == f"clean\n{NONE}\n"
    result = _check_cli(score, cover, "--source", str(source), "--bass-track", "")
    listed = unbacked(0, "A1  bass -  piano -  marker -")
    assert (result.exit_code, result.stdout) == (0, f"clean\n{listed}\n")


@pytest.mark.parametrize("option", ["--piano-track", "--bass-track"])
def test_cli_refuses_a_track_name_without_a_source(write_score, files, option):
    result = _check_cli(write_score("bar 1 | C", "  L 0:C3:4"), files[0], option, "strings")
    assert result.exit_code == 2
    assert option in result.output and "--source" in result.output
