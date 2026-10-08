import json

import pytest

from pianoize import checkpoints

PROGRESSION = [("C:maj", 4), ("F:maj", 4), ("G:7", 4)]


def _write(tmp_path, checkpoints_, excluded=()):
    path = tmp_path / "checkpoints.json"
    path.write_text(json.dumps({"checkpoints": checkpoints_, "excluded": list(excluded)}))
    return path


@pytest.fixture
def data(make_timeline):
    return make_timeline(PROGRESSION)


def test_valid_file_loads(tmp_path, data):
    path = _write(
        tmp_path,
        [{"name": "verse", "start_beat": 0, "end_beat": 8, "note": "first half"}],
        [{"start_beat": 8, "end_beat": 12, "reason": "spoken intro"}],
    )

    found, excluded = checkpoints.load(path, data)

    assert [(c.name, c.start_beat, c.end_beat, c.note) for c in found] == [
        ("verse", 0, 8, "first half")
    ]
    assert [(e.start_beat, e.end_beat, e.reason) for e in excluded] == [(8, 12, "spoken intro")]


def test_range_cutting_a_segment_fails(tmp_path, data):
    path = _write(tmp_path, [{"name": "cut", "start_beat": 0, "end_beat": 6}])

    with pytest.raises(checkpoints.CheckpointError, match="cut"):
        checkpoints.load(path, data)


def test_range_past_the_end_fails(tmp_path, data):
    path = _write(tmp_path, [{"name": "long", "start_beat": 4, "end_beat": 16}])

    with pytest.raises(checkpoints.CheckpointError, match="long"):
        checkpoints.load(path, data)


def test_missing_field_fails_naming_file_and_key(tmp_path, data):
    path = _write(
        tmp_path, [{"name": "a", "start_beat": 0, "end_beat": 4}, {"name": "b", "start_beat": 4}]
    )

    with pytest.raises(
        checkpoints.CheckpointError, match=r"checkpoints\.json.*checkpoint 1.*end_beat"
    ):
        checkpoints.load(path, data)


def test_missing_checkpoints_key_and_bad_json_fail(tmp_path, data):
    path = tmp_path / "checkpoints.json"
    path.write_text("{}")
    with pytest.raises(checkpoints.CheckpointError, match="is missing 'checkpoints'"):
        checkpoints.load(path, data)

    path.write_text("nope")
    with pytest.raises(checkpoints.CheckpointError, match="checkpoints.json"):
        checkpoints.load(path, data)


@pytest.mark.parametrize("start, end", [(4, 4), (8, 4)])
def test_empty_or_reversed_range_fails(tmp_path, data, start, end):
    path = _write(tmp_path, [{"name": "flat", "start_beat": start, "end_beat": end}])

    with pytest.raises(checkpoints.CheckpointError, match="flat"):
        checkpoints.load(path, data)


def test_invalid_excluded_range_names_its_reason(tmp_path, data):
    path = _write(
        tmp_path,
        [{"name": "ok", "start_beat": 0, "end_beat": 4}],
        [{"start_beat": 2, "end_beat": 4, "reason": "drum solo"}],
    )

    with pytest.raises(checkpoints.CheckpointError, match="drum solo"):
        checkpoints.load(path, data)


def test_excluded_key_is_optional(tmp_path, data):
    path = tmp_path / "checkpoints.json"
    path.write_text(json.dumps({"checkpoints": [{"name": "a", "start_beat": 0, "end_beat": 4}]}))

    found, excluded = checkpoints.load(path, data)

    assert len(found) == 1
    assert excluded == []
