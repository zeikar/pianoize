def test_midi_strikes_every_beat_on_time(make_midi):
    # An N segment in the middle must still advance time by its beats.
    mid = make_midi([("C:maj", 2), ("N", 2), ("G:maj", 1)])

    tick = 0
    onsets = {}
    for msg in mid.tracks[0]:
        tick += msg.time
        if msg.type == "note_on":
            onsets.setdefault(tick, set()).add(msg.note)

    assert sorted(onsets) == [b * mid.ticks_per_beat for b in (0, 1, 4)]
    assert onsets[0] == {36, 60, 64, 67}
    assert onsets[4 * mid.ticks_per_beat] == {43, 67, 71, 74}
