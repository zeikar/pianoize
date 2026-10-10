"""Harte chord labels and their tones: the table the synthetic builder, the scorer and the melody
clash report all read."""

ROOT_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")

# Semitones above the root, in chord-tone order: the position of the bass in this tuple is the
# inversion (root, first, second, third). The added ninths are 14 so they sort after the sixth
# and seventh; use `% 12` for a pitch class.
INTERVALS = {
    "maj": (0, 4, 7),
    "min": (0, 3, 7),
    "7": (0, 4, 7, 10),
    "maj7": (0, 4, 7, 11),
    "min7": (0, 3, 7, 10),
    "min6": (0, 3, 7, 9),
    "hdim7": (0, 3, 6, 10),
    "dim7": (0, 3, 6, 9),
    "sus4": (0, 5, 7),
    "aug": (0, 4, 8),
    "dim": (0, 3, 6),
    "sus2": (0, 2, 7),
    "sus4(b7)": (0, 5, 7, 10),
    "maj(9)": (0, 4, 7, 14),
    "min(9)": (0, 3, 7, 14),
}

INVERSIONS = ("root", "first", "second", "third")


def is_label(label) -> bool:
    """Whether a value is a chord label chordotomy writes: N, or a sharp root and a quality."""
    if not isinstance(label, str):
        return False
    root, _, quality = label.partition(":")
    return label == "N" or (root in ROOT_NAMES and quality in INTERVALS)


def parse_chord(label: str) -> tuple[int, str] | None:
    """A Harte label as (root pitch class, quality); None for N."""
    if label == "N":
        return None
    root, quality = label.split(":")
    return ROOT_NAMES.index(root), quality


def chord_pitch_classes(label: str) -> tuple[int, ...]:
    """The chord's pitch classes from the root up; empty for N."""
    parsed = parse_chord(label)
    if parsed is None:
        return ()
    root, quality = parsed
    return tuple((root + i) % 12 for i in INTERVALS[quality])


def inversion(label: str, bass: str | None) -> str | None:
    """The bass's place among the chord's tones, as the timeline's `inversion` field."""
    parsed = parse_chord(label)
    if bass is None or parsed is None:
        return None
    root, quality = parsed
    pc = ROOT_NAMES.index(bass)
    for place, interval in zip(INVERSIONS, INTERVALS[quality], strict=False):
        if (root + interval) % 12 == pc:
            return place
    return "non_chord"
