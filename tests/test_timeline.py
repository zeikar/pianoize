import json

import pytest

from pianoize import timeline as tl

PROGRESSION = [("C:maj", 4), ("G:7", 2, "B"), ("N", 2)]


def test_synthetic_timeline_loads(write_timeline):
    data = tl.load(write_timeline(PROGRESSION))

    assert data["schema_version"] == 11
    assert len(data["beats"]) == 8
    assert [s["inversion"] for s in data["segments"]] == ["root", "first", None]
    assert data["segments"][-1]["end_time"] == data["source"]["duration"]


@pytest.mark.parametrize("version", [10, None])
def test_wrong_schema_names_path(tmp_path, make_timeline, version):
    data = make_timeline(PROGRESSION)
    if version is None:
        del data["schema_version"]
    else:
        data["schema_version"] = version
    path = tmp_path / "old.json"
    path.write_text(json.dumps(data))

    with pytest.raises(tl.TimelineError) as err:
        tl.load(path)

    assert str(path) in str(err.value)
    assert str(version if version is not None else "missing") in str(err.value)


def test_beat_time_clamps(make_timeline):
    data = make_timeline(PROGRESSION)

    assert tl.beat_time(data, 3) == data["beats"][3]
    assert tl.beat_time(data, -2) == data["beats"][0]
    assert tl.beat_time(data, 8) == data["source"]["duration"]
    assert tl.beat_time(data, 99) == data["source"]["duration"]


def test_non_json_names_path(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("not json")

    with pytest.raises(tl.TimelineError, match="bad.json"):
        tl.load(path)


def test_undecodable_bytes_name_path(tmp_path):
    path = tmp_path / "song.mid"  # a MIDI file passed as the timeline
    path.write_bytes(b"MThd\x00\x00\x00\x06\x00\x01\x00\x02\x01\xe0MTrk\xff\xfe")

    with pytest.raises(tl.TimelineError, match=r"song\.mid: not valid JSON"):
        tl.load(path)
