import pytest

from pianoize import synthetic
from pianoize.checkpoints import Checkpoint, Excluded
from pianoize.score import exact, passes, score, triad

# The result's C:maj lies in the C:7's window too, but it has stopped by the C:7's start.
REUSE_ORIGINAL = [("C:maj", 1), ("C:7", 1), ("F:maj", 2)]
REUSE_RESULT = [("C:maj", 1), ("F:maj", 3)]

# The result's one C:maj, a beat late for the first and a beat early for the second, skips the
# G:maj between them.
SKIP_ORIGINAL = [("C:maj", 1), ("G:maj", 1), ("C:maj", 2)]
SKIP_RESULT = [("F:maj", 1), ("C:maj", 3)]


def _segment(chord, bass=None):
    entry = (chord, 4) if bass is None else (chord, 4, bass)
    return synthetic.timeline([entry])["segments"][0]


def _segments(original, result, start=0, end=None):
    end = len(original["beats"]) if end is None else end
    return score(original, [Checkpoint("cp", start, end)], [], result).checkpoints[0].segments


def _passed(segments):
    return [s.passed for s in segments]


@pytest.mark.parametrize(
    "quality, expected",
    [
        ("maj", "maj"),
        ("maj7", "maj"),
        ("7", "maj"),
        ("maj(9)", "maj"),
        ("min", "min"),
        ("min7", "min"),
        ("min6", "min"),
        ("min(9)", "min"),
        ("dim", "dim"),
        ("dim7", "dim"),
        ("hdim7", "dim"),
        ("aug", "aug"),
        ("sus2", "sus2"),
        ("sus4", "sus4"),
        ("sus4(b7)", "sus4"),
    ],
)
def test_triad_class(quality, expected):
    assert triad(f"D:{quality}") == (2, expected)


def test_triad_of_n_and_of_an_unknown_quality():
    assert triad("N") == (None, "N")
    with pytest.raises(ValueError, match="C:maj13"):
        triad("C:maj13")


def test_a_suspension_matches_only_the_same_suspension():
    assert not passes(_segment("C:sus2"), _segment("C:sus4"))
    assert not passes(_segment("C:sus4"), _segment("C:maj"))
    assert passes(_segment("C:sus4(b7)"), _segment("C:sus4"))


def test_n_matches_only_n():
    assert not passes(_segment("C:maj"), _segment("N"))
    assert not passes(_segment("N"), _segment("C:maj"))
    assert passes(_segment("N"), _segment("N"))


def test_an_inverted_original_needs_its_bass():
    original = _segment("C:maj", "E")

    assert not passes(original, _segment("C:maj"))
    assert not passes(original, _segment("C:maj", "G"))
    assert passes(original, _segment("C:maj7", "E"))


def test_a_root_position_original_takes_any_bass():
    original = _segment("C:maj")

    assert passes(original, _segment("C:maj", "E"))
    assert passes(original, _segment("C:maj", "F"))


def test_exact_needs_the_same_chord_and_bass():
    assert exact(_segment("C:maj", "E"), _segment("C:maj", "E"))
    assert not exact(_segment("C:maj"), _segment("C:7"))
    assert not exact(_segment("C:maj"), _segment("C:maj", "E"))


@pytest.mark.parametrize(
    "result, offset",
    [
        ([("C:maj", 5), ("G:maj", 3)], 0.05),
        ([("C:maj", 3), ("G:maj", 5)], 0.05),
        # A millisecond further, within the timelines' rounding.
        ([("C:maj", 5), ("G:maj", 3)], 0.051),
        ([("C:maj", 3), ("G:maj", 5)], 0.049),
    ],
)
def test_a_transition_one_beat_off_passes(make_timeline, result, offset):
    original = make_timeline([("C:maj", 4), ("G:maj", 4)])

    assert _passed(_segments(original, make_timeline(result, offset=offset))) == [True, True]


def test_a_transition_two_beats_late_fails_showing_the_chord_sounding(make_timeline):
    original = make_timeline([("C:maj", 4), ("G:maj", 4)])

    segments = _segments(original, make_timeline([("C:maj", 6), ("G:maj", 2)]))

    assert _passed(segments) == [True, False]
    assert segments[1].shown == "C:maj"


def test_a_chord_held_over_from_a_different_chord_fails(make_timeline):
    # The result's C:maj is right for beats 4-8, but it already sounded under the A:min before.
    original = make_timeline([("A:min", 4), ("C:maj", 4)])
    result = make_timeline([("C:maj", 8)])

    [segment] = _segments(original, result, start=4)

    assert not segment.passed
    assert segment.shown == "C:maj"
    # The chord shown has the original's label, but nothing was chosen.
    assert not segment.exact


@pytest.mark.parametrize(
    "original, held",
    [
        ([("C:maj", 4), ("C:7", 4)], ("C:maj", 8)),
        ([("G:maj", 4, "B"), ("G:maj", 4)], ("G:maj", 8, "B")),
    ],
)
def test_one_sustained_result_chord_passes_a_boundary_the_rule_does_not_see(
    make_timeline, original, held
):
    original, result = make_timeline(original), make_timeline([held])

    segments = _segments(original, result)

    assert _passed(segments) == [True, True]
    assert [s.exact for s in segments] == [True, False]
    # The same holds when the boundary is a checkpoint's start.
    assert _passed(_segments(original, result, start=4)) == [True]


def test_the_ascent_with_two_chords_swapped_fails_on_both(make_timeline):
    original = make_timeline([("A:min", 4), ("B:min", 4), ("C:min", 4), ("D:maj", 4)])
    result = make_timeline([("A:min", 4), ("C:min", 4), ("B:min", 4), ("D:maj", 4)])

    assert _passed(_segments(original, result)) == [True, False, False, True]


def test_a_result_chord_is_not_taken_out_of_order(make_timeline):
    # On one-beat chords the swap lies inside the window: B:min a beat late passes, and the C:min
    # the result played before it can't then be taken for the next segment.
    original = make_timeline([("A:min", 1), ("B:min", 1), ("C:min", 1), ("D:maj", 1)])
    result = make_timeline([("A:min", 1), ("C:min", 1), ("B:min", 1), ("D:maj", 1)])

    assert _passed(_segments(original, result)) == [True, True, False, True]


def test_a_result_chord_is_taken_again_only_when_held(make_timeline):
    original, result = make_timeline(REUSE_ORIGINAL), make_timeline(REUSE_RESULT)

    assert _passed(_segments(original, result)) == [True, False, True]


def test_an_excluded_segment_still_takes_its_chord(make_timeline):
    original, result = make_timeline(REUSE_ORIGINAL), make_timeline(REUSE_RESULT)

    row = score(original, [Checkpoint("cp", 0, 4)], [Excluded(0, 1, "unsure")], result)

    assert [(s.passed, s.excluded) for s in row.checkpoints[0].segments] == [
        (True, True),
        (False, False),
        (True, False),
    ]


FIRST, WHOLE, REST = Checkpoint("first", 0, 1), Checkpoint("whole", 0, 4), Checkpoint("rest", 1, 4)


@pytest.mark.parametrize(
    "checkpoints",
    [
        [FIRST, REST],
        [REST, FIRST],
        [FIRST, WHOLE, REST],
        [REST, WHOLE, FIRST],
        [WHOLE, REST, FIRST],
    ],
)
def test_splitting_or_overlapping_checkpoints_changes_nothing(make_timeline, checkpoints):
    original, result = make_timeline(REUSE_ORIGINAL), make_timeline(REUSE_RESULT)
    song = score(original, [Checkpoint("song", 0, 4)], [], result).checkpoints[0].segments

    row = score(original, checkpoints, [], result)

    assert [c.checkpoint for c in row.checkpoints] == checkpoints
    for scored in row.checkpoints:
        span = scored.checkpoint
        assert scored.segments == [
            s for s in song if span.start_beat <= s.start_beat < span.end_beat
        ]


def test_an_unscored_segment_starts_the_order_again(make_timeline):
    # Scored whole this gives pass, fail, fail (the C:maj taken for beat 0 can't be taken again).
    # With the G:maj left out, the C:maj a beat early for beat 2 is free.
    original, result = make_timeline(SKIP_ORIGINAL), make_timeline(SKIP_RESULT)

    row = score(original, [Checkpoint("first", 0, 1), Checkpoint("last", 2, 4)], [], result)

    assert [_passed(c.segments) for c in row.checkpoints] == [[True], [True]]


@pytest.mark.parametrize(
    "original, result, expected",
    [
        # The C:maj taken a beat late for beat 0 can't be taken again once the G:maj has failed.
        (SKIP_ORIGINAL, SKIP_RESULT, [True, False, False]),
        # The D:maj sounding when the G:maj fails is still free for the D:maj after it.
        (
            [("C:maj", 1), ("G:maj", 1), ("D:maj", 2)],
            [("C:maj", 1), ("D:maj", 3)],
            [True, False, True],
        ),
    ],
)
def test_a_failed_segment_leaves_the_order_where_it_was(make_timeline, original, result, expected):
    segments = _segments(make_timeline(original), make_timeline(result))

    assert _passed(segments) == expected


def test_an_excluded_segment_is_reported_but_not_counted(make_timeline):
    original = make_timeline([("C:maj", 4), ("D#:maj", 4), ("D:maj", 4)])
    result = make_timeline([("C:maj", 4), ("C:min", 4, "D#"), ("D:maj", 4)])

    row = score(original, [Checkpoint("cp", 0, 12)], [Excluded(4, 8, "misread Cm/Eb")], result)

    [checkpoint] = row.checkpoints
    assert [(s.passed, s.excluded) for s in checkpoint.segments] == [
        (True, False),
        (False, True),
        (True, False),
    ]
    assert checkpoint.segments[1].shown == "C:min/D#"
    assert checkpoint.passed


def test_grid_distance_is_the_shift_between_the_beat_grids(make_timeline):
    progression = [("C:maj", 4), ("G:maj", 4)]
    original = make_timeline(progression)
    checkpoints = [Checkpoint("cp", 0, 8)]

    shifted = score(original, checkpoints, [], make_timeline(progression, offset=0.07))

    assert shifted.grid_distance == pytest.approx(0.02)
    assert shifted.checkpoints[0].passed
    assert score(original, checkpoints, [], original).grid_distance == 0


def test_a_human_cover_fails_where_it_simplifies(make_timeline):
    original = make_timeline(
        [
            ("G:maj", 4),
            ("B:7", 4),
            ("E:min", 4),
            ("C:maj", 4, "E"),
            ("C:min", 4, "D#"),
            ("G:maj", 4, "D"),
            ("A:maj", 4, "C#"),
            ("D:maj", 4),
            ("G:maj", 3),
            ("A#:maj", 1),
            ("A:min7", 4),
            ("B:min7", 4),
            ("C:min7", 4),
            ("D:maj", 4),
            ("G:maj", 4),
        ]
    )
    cover = make_timeline(
        [
            ("G:maj", 4),
            ("B:min", 4),
            ("E:min", 4),
            ("G:maj", 4),
            ("A:min", 4),
            ("B:min", 4),
            ("C:maj", 4),
            ("D:maj", 4),
            ("G:maj", 3),
            ("A:min", 5),  # its neighbour in place of the passing A#:maj
            ("B:min", 4),
            ("C:min", 3),
            ("D:maj", 5, "A"),  # a beat early
            ("G:maj", 4),
        ]
    )
    checkpoints = [
        Checkpoint("B7-Em", 4, 12),
        Checkpoint("descent", 12, 32),
        Checkpoint("passing", 35, 36),
        Checkpoint("ascent", 36, 52),
    ]

    row = score(original, checkpoints, [], cover)

    assert [c.passed for c in row.checkpoints] == [False, False, False, True]
    descent = row.checkpoints[1].segments
    assert [s.original for s in descent] == ["C:maj/E", "C:min/D#", "G:maj/D", "A:maj/C#", "D:maj"]
    assert [s.shown for s in descent] == ["G:maj", "A:min", "B:min", "C:maj", "D:maj"]
    ascent = row.checkpoints[3].segments
    assert [s.shown for s in ascent] == ["A:min", "B:min", "C:min", "D:maj/A"]
    assert [s.exact for s in ascent] == [False, False, False, False]
