from pianoize.checkpoints import Checkpoint, Excluded
from pianoize.report import markdown
from pianoize.score import score

ORIGINAL = [("C:maj", 4), ("D#:maj", 4), ("D:maj", 4)]
RESULT = [("C:maj", 4), ("C:min", 4, "D#"), ("D:maj", 4)]


def _table(make_timeline, checkpoints, excluded=()):
    original = make_timeline(ORIGINAL)
    row = score(original, checkpoints, list(excluded), make_timeline(RESULT))
    return markdown(original, [("trial", row)])


def test_summary_counts_and_marks(make_timeline):
    table = _table(
        make_timeline,
        [Checkpoint("all", 0, 12), Checkpoint("middle", 4, 8)],
        [Excluded(4, 8, "misread")],
    )

    # The middle checkpoint is all excluded, so it is out of the counts; the shared segments
    # are counted once.
    assert "| trial | 1/1 | 2/2 | 2/2 | 0.000 |" in table
    assert "| all | 0:00 | C:maj D#:maj D:maj | C:maj C:min/D# D:maj | ✓ – ✓ |" in table
    assert "| middle | 0:02 | D#:maj | C:min/D# | – |" in table


def test_a_failed_segment_is_marked_and_not_passed(make_timeline):
    table = _table(make_timeline, [Checkpoint("all", 0, 12)])

    assert "| trial | 0/1 | 2/3 | 2/3 | 0.000 |" in table
    assert "| all | 0:00 | C:maj D#:maj D:maj | C:maj C:min/D# D:maj | ✓ ✗ ✓ |" in table
