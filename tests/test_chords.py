from pianoize import chords


def test_inversion_non_chord_and_pitch_classes():
    assert chords.inversion("C:maj", "D") == "non_chord"
    assert chords.inversion("C:min6", "A") == "third"
    assert chords.inversion("C:maj", None) is None
    assert chords.chord_pitch_classes("A:min") == (9, 0, 4)
