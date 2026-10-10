import mido
import pytest
from typer.testing import CliRunner

from pianoize import evidence, notes, synthetic
from pianoize.cli import app

# The cover and the melody play 120 bpm at 500 ticks per beat, so a tick is a millisecond and
# the notes below are (on_ms, off_ms, pitch, velocity). Each chord lasts two seconds.
MS_TICKS = 500
PROGRESSION = [("C:maj", 4), ("F:maj", 4), ("G:maj", 4)]
COVER = [
    # C major, with the melody's D5 on top.
    (0, 2000, 48, 80),
    (0, 2000, 52, 80),
    (0, 2000, 55, 80),
    (500, 1000, 74, 90),
    # F major without its third.
    (2000, 4000, 53, 80),
    (2000, 4000, 60, 80),
    # G major.
    (4000, 6000, 43, 80),
    (4000, 6000, 47, 80),
    (4000, 6000, 50, 80),
]
# D4 under the cover's D5, then an F#4 the cover never plays.
MELODY = [(500, 1000, 62, 90), (1000, 2000, 66, 90)]

# The transcription counts 60 bpm at 480 ticks per beat, so 480 ticks are a second; its tempo
# sits only on the conductor track.
MARKERS = [(0, "Am7"), (1440, "Bb")]
BASS = [
    (0, 720, 36, 80),  # C2 for 1.5 s
    (720, 960, 31, 80),  # G1 for 0.5 s
    (960, 1920, 29, 80),  # F1 under F
    (1920, 2400, 31, 80),  # G1 for 1 s
    (2400, 2640, 38, 80),  # D2 for 0.5 s
]
LYRICS = ("la la", "words")


def source_midi(tick_midi) -> mido.MidiFile:
    meta = [(tick, mido.MetaMessage("marker", text=text)) for tick, text in MARKERS]
    meta += [
        (0, mido.MetaMessage("track_name", name="tempo")),  # so an empty name matches no track
        (0, mido.MetaMessage("lyrics", text=LYRICS[0])),
        (0, mido.MetaMessage("text", text=LYRICS[1])),
    ]
    source = tick_midi([], tempos=[(0, 60)], meta=meta)
    for name, played in (("electric_bass", BASS), ("piano", [(0, 2880, 70, 80)])):
        named = tick_midi(played, meta=[(0, mido.MetaMessage("track_name", name=name))])
        source.tracks.append(named.tracks[0])
    return source


def table(tick_midi, protect=True):
    timeline = synthetic.timeline(PROGRESSION, offset=0.0)
    cover = notes.read(tick_midi(COVER, ticks_per_beat=MS_TICKS))
    melody = notes.read(tick_midi(MELODY, ticks_per_beat=MS_TICKS))
    source = source_midi(tick_midi)
    return evidence.rows(
        timeline,
        cover,
        notes.protected(cover, melody) if protect else set(),
        evidence.markers(source),
        evidence.track_notes(source, "electric_bass"),
        melody,
    )


def column(rows, name):
    return [row[name] for row in rows]


def test_a_row_per_segment_with_the_timeline_columns(tick_midi):
    rows = table(tick_midi)
    assert list(rows[0]) == list(evidence.COLUMNS)
    assert rows[0] == {
        "#": "0",
        "time": "0:00.00",
        "beats": "0-4",
        "chord": "C:maj",
        "candidates": "C:maj C:min C:7",
        "edited": "",
        "marker": "Am7",
        "transcribed bass": "C 75%",
        "cover tones": "C 33%, E 33%, G 33%",
        "coverage": "1.000",
        "missing": "",
        "melody": "F# 67%, D 33%",
    }
    assert column(rows, "time") == ["0:00.00", "0:02.00", "0:04.00"]
    assert column(rows, "beats") == ["0-4", "4-8", "8-12"]


def test_markers_land_in_the_segments_they_sound_in(tick_midi):
    # The one active at the segment's start, then any starting inside it, as written.
    assert column(table(tick_midi), "marker") == ["Am7", "Am7, Bb", "Bb"]


def test_the_bass_column_reads_the_named_track_on_the_files_tempo_map(tick_midi):
    # The piano's A# is not the bass, and at the default 120 bpm the F1 would fall under C.
    assert column(table(tick_midi), "transcribed bass") == ["C 75%", "F 100%", "G 67%"]


def test_a_tie_goes_to_the_pitch_class_with_the_lower_note(tick_midi):
    # A G2-D3 power chord in the bass: G is its bass, though D comes first from C.
    timeline = synthetic.timeline([("G:maj", 4)], offset=0.0)
    bass = notes.read(tick_midi([(0, 2000, 43, 80), (0, 2000, 50, 80)], ticks_per_beat=MS_TICKS))
    (row,) = evidence.rows(timeline, [], set(), [], bass, [])
    assert row["transcribed bass"] == "G 50%"


def test_missing_lists_the_triad_tones_the_cover_never_sounds(tick_midi):
    rows = table(tick_midi)
    assert column(rows, "missing") == ["", "A", ""]
    assert column(rows, "coverage") == ["1.000", "1.000", "1.000"]


def test_the_melody_is_left_out_of_the_cover_tones_but_read_from_the_transcription(tick_midi):
    rows = table(tick_midi)
    assert rows[0]["cover tones"] == "C 33%, E 33%, G 33%"
    # F# is the transcription's alone: the cover never plays it.
    assert column(rows, "melody") == ["F# 67%, D 33%", "", ""]

    unprotected = table(tick_midi, protect=False)
    assert unprotected[0]["cover tones"] == "C 31%, E 31%, G 31%, D 8%"
    assert unprotected[0]["coverage"] == "0.923"


def test_no_chord_has_no_coverage_or_missing_tones(tick_midi):
    timeline = synthetic.timeline([("N", 2), ("C:maj", 2)], offset=0.0)
    cover = notes.read(tick_midi([(0, 1000, 61, 80)], ticks_per_beat=MS_TICKS))
    rows = evidence.rows(timeline, cover, set(), [], [], [])
    assert [(r["chord"], r["cover tones"], r["coverage"], r["missing"]) for r in rows] == [
        ("N", "C# 100%", "", ""),
        ("C:maj", "", "", "C E G"),
    ]


def test_markers_read_markers_only(tick_midi):
    found = evidence.markers(source_midi(tick_midi))
    assert found == [(0.0, "Am7"), (pytest.approx(3.0), "Bb")]


def test_an_unknown_track_is_refused_naming_the_tracks(tick_midi):
    with pytest.raises(evidence.EvidenceError, match="no track named 'bass'.*'electric_bass'"):
        evidence.track_notes(source_midi(tick_midi), "bass")


def test_a_file_without_track_names_says_so(tick_midi):
    with pytest.raises(evidence.EvidenceError, match="; tracks named: none$"):
        evidence.track_notes(tick_midi(BASS), "electric_bass")


def test_markdown_escapes_a_pipe_in_a_marker(tick_midi):
    timeline = synthetic.timeline([("C:maj", 4)], offset=0.0)
    text = evidence.markdown(evidence.rows(timeline, [], set(), [(0.0, "C|G")], [], []))
    header, rule, row = text.splitlines()
    assert header == "| " + " | ".join(evidence.COLUMNS) + " |"
    assert rule == "|" + " --- |" * len(evidence.COLUMNS)
    assert "| C\\|G |" in row


@pytest.fixture
def files(tmp_path, tick_midi, write_timeline):
    cover = tmp_path / "cover.mid"
    tick_midi(COVER, ticks_per_beat=MS_TICKS).save(cover)
    timeline = write_timeline(PROGRESSION, name="song.chords.json", offset=0.0)
    source = tmp_path / "source.mid"
    source_midi(tick_midi).save(source)
    melody = tmp_path / "melody.mid"
    tick_midi(MELODY, ticks_per_beat=MS_TICKS).save(melody)
    return cover, timeline, source, melody


def _cli(cover, timeline, *options):
    return CliRunner().invoke(app, ["harmony-evidence", str(cover), str(timeline), *options])


def _rows(text):
    """The markdown table's rows as lists of cells."""
    return [line[2:-2].split(" | ") for line in text.splitlines()[2:]]


def test_cli_prints_the_table_and_writes_it(tmp_path, files):
    cover, timeline, source, melody = files
    out = tmp_path / "evidence.md"
    result = _cli(cover, timeline, "--source", str(source), "--melody", str(melody), "-o", str(out))
    assert result.exit_code == 0, result.output
    assert out.read_text(encoding="utf-8") == result.stdout
    assert _rows(result.stdout)[1][6:] == ["Am7, Bb", "F 100%", "F 50%, C 50%", "1.000", "A", ""]
    assert not any(text in result.output for text in LYRICS)


def test_cli_without_source_or_melody_leaves_their_columns_empty(files):
    cover, timeline, _, _ = files
    result = _cli(cover, timeline)
    assert result.exit_code == 0, result.output
    first = _rows(result.stdout)[0]
    assert (first[6], first[7], first[11]) == ("", "", "")
    assert first[8] == "C 31%, E 31%, G 31%, D 8%"  # nothing carries the melody


@pytest.mark.parametrize("target", [0, 1, 2, 3])
def test_cli_refuses_to_overwrite_an_input(files, target):
    cover, timeline, source, melody = files
    before = [path.read_bytes() for path in files]
    result = _cli(
        cover, timeline, "--source", str(source), "--melody", str(melody), "-o", str(files[target])
    )
    assert result.exit_code == 2
    assert "would overwrite an input" in " ".join(result.output.split())
    assert [path.read_bytes() for path in files] == before


def test_cli_reports_an_unknown_bass_track_without_a_traceback(files):
    cover, timeline, source, _ = files
    result = _cli(cover, timeline, "--source", str(source), "--bass-track", "bass")
    assert result.exit_code == 1
    assert "error: " in result.output
    assert "no track named 'bass'" in result.output
    assert "Traceback" not in result.output


def test_cli_reads_no_bass_track_for_an_empty_name_and_keeps_the_markers(files):
    cover, timeline, source, _ = files
    result = _cli(cover, timeline, "--source", str(source), "--bass-track", "")
    assert result.exit_code == 0, result.output
    assert [row[6:8] for row in _rows(result.stdout)] == [
        ["Am7", ""],
        ["Am7, Bb", ""],
        ["Bb", ""],
    ]


def test_cli_refuses_a_type_2_source_without_a_traceback(files, tick_midi):
    cover, timeline, source, _ = files
    midi = source_midi(tick_midi)
    midi.type = 2
    midi.save(source)
    result = _cli(cover, timeline, "--source", str(source))
    assert result.exit_code == 1
    assert "error: a type 2 MIDI file's tracks share no timeline" in result.output
