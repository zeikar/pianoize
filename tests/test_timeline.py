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


def _with_key(data: dict, regions: list[tuple[int, int, str]], label: str = "C:maj") -> dict:
    data["global_key"] = {"label": label, "source": "estimated", "candidates": [label]}
    data["key_regions"] = [{"start_beat": s, "end_beat": e, "label": k} for s, e, k in regions]
    return data


def test_problem_accepts_what_the_viewer_opens(make_timeline):
    data = make_timeline(PROGRESSION)

    assert tl.problem(data) is None
    assert tl.problem(_with_key(data, [(0, 4, "C:maj"), (4, 8, "G:maj")])) is None


def _put(*path, value):
    """A change setting the field at the path to the value."""

    def change(data: dict) -> None:
        *parents, last = path
        for key in parents:
            data = data[key]
        data[last] = value

    return change


def _nudge(*path):
    """A change moving the time at the path 1 ms later."""

    def change(data: dict) -> None:
        *parents, last = path
        for key in parents:
            data = data[key]
        data[last] += 0.001

    return change


def _huge_duration(data: dict) -> None:
    # JSON.parse reads an integer past the largest double as Infinity; the last segment ends on
    # it, so the times still match.
    data["source"]["duration"] = data["segments"][-1]["end_time"] = 10**400


ONE_REGION = [(0, 8, "C:maj")]
TWO_REGIONS = [(0, 4, "C:maj"), (4, 8, "G:maj")]


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (_put("segments", 1, "chord", value="Bb:7"), "chord chordotomy doesn't write: chord Bb:7"),
        (_put("segments", 1, "chord", value="G:9"), "chord chordotomy doesn't write: chord G:9"),
        (_put("segments", 1, "bass", value="Bb"), "note chordotomy doesn't write: bass Bb"),
        (_put("segments", 1, "numeral", value=5), "segment 2 has a missing or invalid numeral"),
        (_put("segments", 2, "edited", value=None), "segment 3 has a missing or invalid edited"),
        (_nudge("segments", 1, "start_time"), "segment 2 has times that don't match its beats"),
        (_nudge("segments", 1, "end_time"), "segment 2 has times that don't match its beats"),
        (_nudge("segments", 2, "end_time"), "segment 3 has times that don't match its beats"),
        (_nudge("source", "duration"), "segment 3 has times that don't match its beats"),
        (
            _put("segments", 2, "start_beat", value=7),
            "segment 3 doesn't start where the one before it ends",
        ),
        (lambda data: data["segments"].pop(), "segment 2 stops short of the last beat"),
        (_put("segments", 2, "end_beat", value=9), "segment 3 lies outside its beats"),
        (
            lambda data: data["beats"].insert(1, data["beats"][0]),
            "beats aren't in ascending order",
        ),
        (lambda data: data["source"].pop("url"), "source has a missing or invalid url"),
        (_put("source", "url", value=5), "source has a missing or invalid url"),
        (_put("source", "duration", value=float("inf")), "has no source duration"),
        (_huge_duration, "has no source duration"),
        (
            lambda data: data["generator"].pop("engine"),
            "generator has a missing or invalid engine",
        ),
        (
            lambda data: _with_key(data, [(0, 8, "Bb:maj")], label="Bb:maj"),
            "key chordotomy doesn't write: global_key Bb:maj",
        ),
        (
            lambda data: _with_key(data, ONE_REGION)["global_key"].update(source="guessed"),
            "key has a missing or invalid source or candidates",
        ),
        (
            lambda data: _with_key(data, ONE_REGION)["global_key"].update(candidates=["Db:maj"]),
            "key has a missing or invalid source or candidates",
        ),
        (
            lambda data: _with_key(data, TWO_REGIONS)["global_key"].update(source="given"),
            "given key must be one region, not 2",
        ),
        (
            lambda data: _with_key(data, ONE_REGION).update(global_key=None),
            "key regions but no key",
        ),
        (lambda data: _with_key(data, []), "key but no key regions"),
        (
            lambda data: _with_key(data, [(0, 2, "C:maj"), (2, 8, "G:maj")]),
            "key region 2 starts inside a segment",
        ),
        (
            lambda data: _with_key(data, [(0, 8, "G:maj")]),
            "key region is labelled G:maj, but its key is C:maj",
        ),
        (lambda data: data.pop("schema_version"), "schema_version is missing"),
    ],
)
def test_problem_names_the_broken_rule(make_timeline, change, message):
    data = make_timeline(PROGRESSION)
    change(data)

    assert message in tl.problem(data)


@pytest.mark.parametrize("constant", ["NaN", "Infinity", "-Infinity"])
def test_load_refuses_what_json_parse_refuses(tmp_path, make_timeline, constant):
    data = make_timeline(PROGRESSION)
    data["source"]["confidence"] = float(constant)
    path = tmp_path / "timeline.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    assert constant in path.read_text(encoding="utf-8")

    with pytest.raises(tl.TimelineError, match=f"timeline.json: not valid JSON .*{constant}"):
        tl.load(path)
