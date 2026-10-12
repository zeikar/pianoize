import json

import mido
import pytest
from typer.testing import CliRunner

from pianoize import notes, roll
from pianoize.cli import app


def test_each_track_gives_its_hand(hands_midi):
    data = roll.export(hands_midi([(0, 480, 72, 80)], [(240, 960, 48, 80)]))

    assert data["format_version"] == 1
    assert data["notes"] == [
        {"pitch": 72, "hand": "right", "on": 0.0, "off": 0.5},
        {"pitch": 48, "hand": "left", "on": 0.25, "off": 1.0},
    ]


def test_notes_sort_by_onset_pitch_then_hand(hands_midi):
    data = roll.export(hands_midi([(0, 480, 60, 80), (480, 960, 50, 80)], [(0, 480, 60, 80)]))

    assert [(n["on"], n["pitch"], n["hand"]) for n in data["notes"]] == [
        (0.0, 60, "left"),
        (0.0, 60, "right"),
        (0.5, 50, "right"),
    ]


def test_seconds_follow_the_tempo_map(hands_midi):
    midi = hands_midi([(0, 480, 60, 80)], [(1920, 2400, 48, 80)], tempos=[(0, 120), (960, 60)])
    segments = notes.tempo_map(midi)

    data = roll.export(midi)

    late = next(n for n in data["notes"] if n["hand"] == "left")
    assert late["on"] == round(notes.seconds_at(segments, 480, 1920), 6)
    assert late["off"] == round(notes.seconds_at(segments, 480, 2400), 6)
    assert late["on"] == pytest.approx(0.5 * 2 + 1.0 * 2)  # two beats fast, two slow
    assert roll.length(midi) == pytest.approx(late["off"])


def test_a_restruck_pitch_ends_at_the_next_strike(hands_midi):
    midi = hands_midi([], [])
    # The second strike comes before the first note_off; the closing note_off then ends the second.
    midi.tracks[0].extend(
        [
            mido.Message("note_on", note=60, velocity=80, time=0),
            mido.Message("note_on", note=60, velocity=80, time=240),
            mido.Message("note_off", note=60, time=240),
        ]
    )

    data = roll.export(midi)

    assert [(n["on"], n["off"]) for n in data["notes"]] == [(0.0, 0.25), (0.25, 0.5)]


def test_one_hand_track_is_refused_by_name(hands_midi):
    midi = hands_midi([(0, 480, 60, 80)], [])
    del midi.tracks[1]

    with pytest.raises(roll.RollError, match="no 'Left Hand' track"):
        roll.export(midi)


def test_a_midi_without_names_is_refused(tick_midi):
    with pytest.raises(roll.RollError, match="no 'Right Hand' track"):
        roll.export(tick_midi([(0, 480, 60, 80)]))


def test_a_name_found_twice_is_refused(hands_midi):
    midi = hands_midi([], [])
    midi.tracks.append(midi.tracks[0].copy())

    with pytest.raises(roll.RollError, match="2 tracks are named 'Right Hand'"):
        roll.export(midi)


def test_a_pitch_off_the_keys_is_refused(hands_midi):
    with pytest.raises(roll.RollError, match="pitch 109"):
        roll.export(hands_midi([(0, 480, 109, 80)], []))


def test_the_dump_is_json_with_a_note_a_line(hands_midi):
    data = roll.export(hands_midi([(0, 480, 72, 80)], [(480, 960, 48, 80)]))

    text = roll.dump(data)

    assert json.loads(text) == data
    assert text.endswith("]}\n")
    assert text.splitlines()[1] == '{"pitch": 72, "hand": "right", "on": 0.0, "off": 0.5},'


def test_an_empty_roll_still_dumps_as_json(hands_midi):
    data = roll.export(hands_midi([], []))

    assert json.loads(roll.dump(data)) == data


def _run(*args):
    return CliRunner().invoke(app, ["export-arrangement", *map(str, args)])


def test_the_cli_writes_the_file(hands_midi, tmp_path):
    path = tmp_path / "arranged.mid"
    hands_midi([(0, 480, 72, 80), (480, 960, 74, 80)], [(0, 1920, 48, 80)]).save(path)
    out = tmp_path / "roll.json"

    result = _run(path, "-o", out)

    assert result.exit_code == 0, result.output
    assert "notes: 2 right hand, 1 left hand" in result.output
    assert "length: 2.0 s" in result.output
    assert len(json.loads(out.read_text(encoding="utf-8"))["notes"]) == 3


def test_the_cli_refuses_to_overwrite_its_input(hands_midi, tmp_path):
    path = tmp_path / "arranged.mid"
    hands_midi([(0, 480, 72, 80)], []).save(path)
    before = path.read_bytes()

    result = _run(path, "-o", path)

    assert result.exit_code == 2
    assert path.read_bytes() == before


def test_the_cli_reports_a_refusal_and_writes_nothing(tick_midi, tmp_path):
    path = tmp_path / "plain.mid"
    tick_midi([(0, 480, 60, 80)]).save(path)
    out = tmp_path / "roll.json"

    result = _run(path, "-o", out)

    assert result.exit_code == 1
    assert f"error: {path}: no 'Right Hand' track" in result.output
    assert not out.exists()


def test_two_runs_give_identical_bytes(hands_midi, tmp_path):
    path = tmp_path / "arranged.mid"
    hands_midi([(0, 480, 72, 80)], [(0, 960, 48, 80)], tempos=[(0, 100), (480, 90)]).save(path)

    assert _run(path, "-o", tmp_path / "a.json").exit_code == 0
    assert _run(path, "-o", tmp_path / "b.json").exit_code == 0

    assert (tmp_path / "a.json").read_bytes() == (tmp_path / "b.json").read_bytes()
