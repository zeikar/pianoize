import io
import random

import mido
import pytest

from pianoize import bars, notes, steady

TICKS = 480
BAR = 4 * TICKS  # ticks of a 2/2 bar: four MIDI beats
# Seconds after the first downbeat of the melody's notes, each about half a sixteenth at 120 bpm
# off the grid.
MELODY = (2.31, 9.06, 30.44, 51.19, 77.57)
# The bent transcription's distinct attacks at its defaults: eight eighths a bar, a sixteenth in
# every second bar, and the melody; the bass and the drums strike with the eighths.
ATTACKS = 48 * 8 + 24 + len(MELODY)


def _track(
    name: str | None,
    events: list[tuple[int, int, mido.Message | mido.MetaMessage]],
    tail: int = 0,
):
    """A track from (tick, rank, message) triples, sorted by both, ending `tail` ticks after the
    last."""
    found = mido.MidiTrack()
    if name is not None:
        found.append(mido.MetaMessage("track_name", name=name))
    now = 0
    for tick, _, message in sorted(events, key=lambda e: e[:2]):
        found.append(message.copy(time=tick - now))
        now = tick
    found.append(mido.MetaMessage("end_of_track", time=tail))
    return found


def _transcription(
    tempos: list[tuple[int, int]],
    markers: list[float],
    parts: list[tuple[str, int, list[tuple[float, float, int]]]],
    signatures: tuple[tuple[int, int, int], ...] = ((0, 2, 2),),
) -> mido.MidiFile:
    """A file shaped like tsumugi's transcription: a tempo map from (tick, tempo) changes with
    (tick, numerator, denominator) signatures, by default 2/2, and a key; chord markers at
    seconds, the track ending a bar after the last; an empty unnamed track; then, per (name,
    channel, notes), a track of (onset, offset, pitch) seconds, each ending with a velocity 0
    note_on as tsumugi writes it. Every second becomes a tick on the map."""
    conductor = [(tick, 0, mido.MetaMessage("set_tempo", tempo=tempo)) for tick, tempo in tempos]
    conductor += [
        (tick, 1, mido.MetaMessage("time_signature", numerator=n, denominator=d))
        for tick, n, d in signatures
    ]
    conductor.append((0, 2, mido.MetaMessage("key_signature", key="D")))
    midi = mido.MidiFile(type=1, ticks_per_beat=TICKS)
    midi.tracks.append(_track("Predicted Tempo Map", conductor))
    segments = notes.tempo_map(midi)

    def tick(seconds: float) -> int:
        return notes.tick_in(segments, TICKS, seconds)

    midi.tracks.append(
        _track(
            "Predicted Chords",
            [(tick(s), 0, mido.MetaMessage("marker", text="D")) for s in markers],
            tail=BAR,
        )
    )
    midi.tracks.append(mido.MidiTrack([mido.MetaMessage("end_of_track")]))
    for name, channel, played in parts:
        events = []
        for on, off, pitch in played:
            # Ends before strikes on a tick, so a note ending where the next begins pairs right.
            events.append(
                (tick(on), 1, mido.Message("note_on", channel=channel, note=pitch, velocity=80))
            )
            events.append(
                (tick(off), 0, mido.Message("note_on", channel=channel, note=pitch, velocity=0))
            )
        midi.tracks.append(_track(name, events))
    return midi


def bent_transcription(
    downbeat: float = 0.5,
    bpm: float = 120,
    bars: int = 48,
    melody: bool = True,
    map_bpm: float | None = None,
) -> mido.MidiFile:
    """A transcription of `bars` 2/2 bars at a steady `bpm` from `downbeat` seconds, on a tempo map
    bent as tsumugi bends it: a first bar fitting the seconds before the downbeat, 2 bars at
    `bpm`, 8 bars at half speed, 10 at `bpm`, 8 squeezed into 5 map bars, then `bpm` to the end,
    every change on a downbeat. With `map_bpm`, one flat tempo at that bpm from tick 0 instead,
    so the map's bar lines drift against the attacks. The piano strikes every eighth and, in
    every second bar, a sixteenth; the bass beats 1 and 3, the drums every beat, and the melody a
    few seconds off the grid."""
    bar = 240 / bpm  # seconds
    if map_bpm is not None:
        tempos = [(0, round(60e6 / map_bpm))]
    else:
        tempos, tick = [], 0
        if downbeat > 0:
            tempos, tick = [(0, round(downbeat * 1e6 / 4))], BAR
        # (song bars, map bars) of each run
        for song, grid in [(2, 2), (8, 4), (10, 10), (8, 5), (bars - 28, bars - 28)]:
            tempos.append((tick, round(song * bar * 1e6 / (4 * grid))))
            tick += grid * BAR
    downbeats = [downbeat + b * bar for b in range(bars)]
    eighth, sixteenth = bar / 8, bar / 16
    piano = [
        (start + e * eighth, start + (e + 0.8) * eighth, pitch)
        for start in downbeats
        for e in range(8)
        for pitch in (62, 66)
    ]
    piano += [(start + 3 * sixteenth, start + 3.8 * sixteenth, 69) for start in downbeats[1::2]]
    bass = [
        (start + h * bar / 2, start + (h + 0.9) * bar / 2, 38)
        for start in downbeats
        for h in (0, 1)
    ]
    drums = [
        (start + b * bar / 4, start + (b + 0.4) * bar / 4, 36 if b % 2 == 0 else 38)
        for start in downbeats
        for b in range(4)
    ]
    parts = [("piano", 0, piano), ("electric_bass", 3, bass), ("drums", 9, drums)]
    if melody:
        parts.append(("melody", 1, [(downbeat + s, downbeat + s + 0.2, 74) for s in MELODY]))
    return _transcription(tempos, downbeats, parts)


def random_transcription(count: int = 400, seconds: float = 60, bpm: float = 120) -> mido.MidiFile:
    """A transcription of `count` distinct piano attacks at random seconds on a flat map at
    `bpm`."""
    rng = random.Random(0)
    # One attack in each of `count` distinct 4 ms cells, 1 to 3 ms in: at least 2 ms apart, so no
    # two share a millisecond once on a tick.
    cells = rng.sample(range(round(seconds * 250)), count)
    onsets = [0.004 * cell + rng.uniform(0.001, 0.003) for cell in cells]
    played = [(on, on + 0.05, 48 + i % 24) for i, on in enumerate(onsets)]
    bar = 240 / bpm
    markers = [b * bar for b in range(int(seconds / bar) + 1)]
    return _transcription([(0, round(60e6 / bpm))], markers, [("piano", 0, played)])


def strikes_transcription(
    runs: list[tuple[int, float]],
    per_bar: int = 8,
    map_runs: list[tuple[int, float]] | None = None,
) -> mido.MidiFile:
    """A transcription of `per_bar` even drum strikes a 2/2 bar over runs of (bars, bpm). The tempo
    map follows the runs, or with `map_runs`, its own (map bars, bpm) runs."""
    tempos, played, start, tick = [], [], 0.0, 0
    for bars_, bpm in runs:
        tempos.append((tick, round(60e6 / bpm)))
        bar = 240 / bpm
        played += [
            (start + i * bar / per_bar, start + (i + 0.4) * bar / per_bar, 36)
            for i in range(per_bar * bars_)
        ]
        start, tick = start + bars_ * bar, tick + bars_ * BAR
    if map_runs is not None:
        tempos, tick = [], 0
        for bars_, bpm in map_runs:
            tempos.append((tick, round(60e6 / bpm)))
            tick += bars_ * BAR
    return _transcription(tempos, [0.0], [("drums", 9, played)])


@pytest.fixture(scope="module")
def bent() -> tuple[mido.MidiFile, steady.Fit]:
    """The default bent transcription and its fit; tests must not change the file."""
    midi = bent_transcription()
    return midi, steady.fit(midi)


def _seconds(midi: mido.MidiFile, index: int, kind: str) -> list[float]:
    """The seconds of every message of a type on one track, on the file's tempo map."""
    segments = notes.tempo_map(midi)
    found, now = [], 0
    for message in midi.tracks[index]:
        now += message.time
        if message.type == kind:
            found.append(notes.seconds_at(segments, midi.ticks_per_beat, now))
    return found


def _ticks(track: mido.MidiTrack, kind: str) -> list[int]:
    found, now = [], 0
    for message in track:
        now += message.time
        if message.type == kind:
            found.append(now)
    return found


def test_the_dominant_tempo_is_the_median_by_seconds():
    # Six 2 s segments at half speed or squeezed, around one of 30 s at 170 bpm: the median of the
    # segments' tempos is 106.25 bpm; weighted by their seconds, it is 170.
    short = [mido.bpm2tempo(85), mido.bpm2tempo(106.25)] * 3
    tempos = short[:3] + [mido.bpm2tempo(170)] + short[3:]
    starts = [0.0, 2.0, 4.0, 6.0, 36.0, 38.0, 40.0]
    segments = [
        (i * BAR, start, tempo) for i, (start, tempo) in enumerate(zip(starts, tempos, strict=True))
    ]
    assert steady._dominant(segments, 42.0) == pytest.approx(170, abs=0.01)


@pytest.mark.parametrize("downbeat", [0.5, 0.59])
def test_a_bent_transcription_fits_its_steady_tempo_and_first_downbeat(downbeat):
    # At 0.59 the grid's phase is 0.09 s, not a multiple of the sixteenth: a bar line's vote
    # rounded on a grid from zero would land a sixteenth late, at 0.715 s.
    found = steady.fit(bent_transcription(downbeat))
    assert found.bpm == pytest.approx(120, abs=0.005)
    assert found.downbeat == pytest.approx(downbeat, abs=0.003)
    assert found.coverage > 0.95
    assert found.attacks == ATTACKS


def test_a_song_starting_on_a_downbeat_fits_one_at_the_start():
    found = steady.fit(bent_transcription(0.0))
    assert abs(found.downbeat) <= found.window
    assert found.downbeat == pytest.approx(0, abs=0.003)


def test_a_downbeat_just_before_a_bar_line_is_the_one_a_bar_earlier():
    # A bar is 2 s, so 1.99 s is 10 ms before the second bar line: the first downbeat is at
    # -0.01 s, within the window of the start.
    found = steady.fit(bent_transcription(1.99))
    assert -found.window <= found.downbeat < 0
    assert found.downbeat == pytest.approx(-0.01, abs=0.003)


def test_too_few_attacks_fit_nothing():
    with pytest.raises(steady.SteadyError, match="^200 distinct attacks, fewer than 300$"):
        steady.fit(random_transcription(count=200))


@pytest.mark.parametrize("bpm", [120, 300])
def test_randomly_timed_attacks_fit_no_grid(bpm):
    expected = (
        r"^best fit [\d.]+ bpm puts \d+% of 400 attacks within a quarter sixteenth, under 70%$"
    )
    with pytest.raises(steady.SteadyError, match=expected):
        steady.fit(random_transcription(bpm=bpm))


@pytest.mark.parametrize(("on_grid", "share"), [(228, 57), (279, 69)])
def test_the_rejected_share_is_floored_exactly(monkeypatch, on_grid, share):
    # 228 of 400 is 57% exactly, though 0.57 * 100 is 56.99999999999999; 279 of 400, 69.75%,
    # must not read as the 70% gate.
    monkeypatch.setattr(steady, "_search", lambda onsets, dominant: (126.45, 0.0, on_grid))
    expected = (
        f"^best fit 126.45 bpm puts {share}% of 400 attacks within a quarter sixteenth, under 70%$"
    )
    with pytest.raises(steady.SteadyError, match=expected):
        steady.fit(random_transcription())


def test_a_map_far_off_the_fit_says_nothing_of_the_downbeats():
    # 110 bpm is 8% off 120, outside the 5% that lets a bar line vote, while the search band
    # around 110 still holds 120.
    expected = "^none of tsumugi's bars run within 5% of 120.00 bpm, so the downbeats are unknown$"
    with pytest.raises(steady.SteadyError, match=expected):
        steady.fit(bent_transcription(map_bpm=110))


def test_a_map_a_little_off_the_fit_drifts_through_every_sixteenth():
    # 123 bpm is 2.5% off: every bar line votes, but they drift through every sixteenth of the
    # bar, so the most-voted one holds a few of them.
    expected = (
        r"^tsumugi's bars agree on no downbeat: "
        r"the most-voted sixteenth holds \d+ of \d+ bar lines$"
    )
    with pytest.raises(steady.SteadyError, match=expected):
        steady.fit(bent_transcription(map_bpm=123))


def test_a_map_split_between_octaves_takes_the_longer_one_and_reports_the_other():
    # 16 s at 120 bpm, 80 s tracked at 60, then 32 s at 120: the eighths fit 60 and 120 alike, so
    # the grid takes 60, the octave tsumugi held for 63% of the song.
    midi = strikes_transcription([(64, 120)], map_runs=[(8, 120), (20, 60), (16, 120)])
    found = steady.fit(midi)
    assert found.bpm == pytest.approx(60, abs=0.01)
    assert found.other_octave == pytest.approx(120, abs=0.01)
    assert found.other_octave_share == pytest.approx(0.375, abs=0.01)


def test_a_few_seconds_at_the_other_octave_are_still_reported():
    # 192 s at 60 bpm and 8 s at the real 120.
    midi = strikes_transcription([(100, 120)], map_runs=[(48, 60), (4, 120)])
    found = steady.fit(midi)
    assert found.bpm == pytest.approx(60, abs=0.01)
    assert 0 < found.other_octave_share < 0.05


def test_a_map_at_one_octave_reports_no_other():
    assert steady.fit(bent_transcription(map_bpm=120)).other_octave_share == 0


@pytest.mark.parametrize("per_bar", [8, 4])
@pytest.mark.parametrize("first", [40, 20])
def test_a_tempo_change_tsumugi_tracked_is_kept(per_bar, first):
    # 120 bpm for `first` bars (2 s each), then 150 for 60 bars. The 150 bpm grid fits the
    # eighths of the first run 50%, and its quarters, which land five sixteenths apart, 100% but
    # on every place in the beat alike.
    midi = strikes_transcription([(first, 120), (60, 150)], per_bar)
    with pytest.raises(steady.SteadyError, match=r"^150\.00 bpm does not hold through the song: "):
        steady.fit(midi)


def test_a_tempo_change_by_three_halves_is_kept():
    # Quarters at 120 bpm for 80 s, then 180 for 96 s: 120 is two thirds of the fit.
    midi = strikes_transcription([(40, 120), (72, 180)], 4)
    with pytest.raises(steady.SteadyError, match=r"^180\.00 bpm does not hold through the song: "):
        steady.fit(midi)


@pytest.mark.parametrize("per_bar", [8, 16])
def test_a_distorted_map_under_a_steady_tempo_is_regridded(per_bar):
    # A steady 120 bpm song of eighths or sixteenths whose map runs 30 bars at 120, 45 at 180,
    # then 40 at 120: the attacks decide, not how long the distortion lasts, and uniform
    # subdivisions fill every beat.
    midi = strikes_transcription([(100, 120)], per_bar, map_runs=[(30, 120), (45, 180), (40, 120)])
    found = steady.fit(midi)
    assert found.bpm == pytest.approx(120, abs=0.005)
    assert found.other_octave_share == 0


def test_a_tempo_change_tsumugi_missed_is_kept():
    # The same eighths on a flat map at 150 bpm: no stretch of the map is off, but the first run's
    # spans fall half off the grid.
    midi = strikes_transcription([(40, 120), (60, 150)], map_runs=[(1, 150)])
    with pytest.raises(steady.SteadyError, match=r"^150\.00 bpm does not hold through the song: "):
        steady.fit(midi)


def test_a_song_tracked_at_the_wrong_octave_for_most_of_its_length_grids_there():
    # The limit: 160 of 200 s at 60 bpm, 40 s at the real 120. Eighths fit 60 and 120 alike, so
    # the grid takes the octave held longer, reports the other, and the note seconds stay.
    midi = strikes_transcription([(100, 120)], map_runs=[(40, 60), (20, 120)])
    found = steady.fit(midi)
    assert found.bpm == pytest.approx(60, abs=0.01)
    assert found.coverage == 1.0
    assert found.other_octave == pytest.approx(120, abs=0.01)
    assert found.other_octave_share == pytest.approx(0.2, abs=0.01)
    fixed = steady.apply(midi, found)
    half_tick = mido.tick2second(0.5, TICKS, 1000000) + 1e-9
    before = steady._attacks(midi, notes.tempo_map(midi))
    after = steady._attacks(fixed, notes.tempo_map(fixed))
    assert len(after) == len(before) == 800
    assert after == pytest.approx(before, abs=half_tick)


def _signed(numerator: int, denominator: int) -> tuple[mido.MidiFile, int]:
    """The bent transcription with a second signature at the end of its tempo track, and its
    tick."""
    midi = bent_transcription()
    tempo_track = midi.tracks[0]
    tempo_track.insert(
        -1, mido.MetaMessage("time_signature", numerator=numerator, denominator=denominator)
    )
    return midi, sum(message.time for message in tempo_track)


def test_a_change_of_meter_grids_on_the_first_and_is_reported():
    midi, at = _signed(3, 4)
    found = steady.fit(midi)
    assert found.meter_change == (at, "2/2", "3/4")
    fixed = steady.apply(midi, found)
    signatures = [m for m in fixed.tracks[0] if m.type == "time_signature"]
    assert [(m.numerator, m.denominator) for m in signatures] == [(2, 2)]
    assert bars.meter(fixed) == bars.Meter(TICKS, 2, 2)


def test_a_signature_with_the_same_bar_stays_and_is_no_change():
    midi, _ = _signed(4, 4)
    found = steady.fit(midi)
    assert found.meter_change is None
    fixed = steady.apply(midi, found)
    signatures = [m for m in fixed.tracks[0] if m.type == "time_signature"]
    assert [(m.numerator, m.denominator) for m in signatures] == [(2, 2), (4, 4)]


def test_bars_tsumugi_wrote_on_a_sixteenth_beat_are_read_as_quarters():
    # tsumugi writes stretches of a 4/4 song at 120 bpm 4/16 at 30 bpm, its beat on the sixteenth:
    # the same 2 s bars, but the map's sixteenths are the song's quarters, and the 30 bpm stretches
    # hold most of the seconds. Read as 4/4, the song grids at 120 in one meter.
    short, bar = TICKS, 4 * TICKS  # a 4/16 bar and a 4/4 one
    tempos = [(0, 2000000), (20 * short, 500000), (20 * short + 10 * bar, 2000000)]
    signatures = ((0, 4, 16), (20 * short, 4, 4), (20 * short + 10 * bar, 4, 16))
    eighths = [(i / 4, (i + 0.4) / 4, 36) for i in range(8 * 50)]
    midi = _transcription(tempos, [0.0], [("drums", 9, eighths)], signatures)
    found = steady.fit(midi)
    assert found.bpm == pytest.approx(120, abs=0.005)
    assert found.coverage == 1.0
    assert found.meter_change is None
    fixed = steady.apply(midi, found)
    assert bars.meter(fixed) == bars.Meter(TICKS, 4, 4)
    half_tick = mido.tick2second(0.5, TICKS, 500000) + 1e-9
    assert _seconds(fixed, 3, "note_on") == pytest.approx(
        _seconds(midi, 3, "note_on"), abs=half_tick
    )


def test_a_sixteenth_beat_bar_with_no_tempo_of_its_own_keeps_its_seconds():
    # A 4/16 signature after a bar of 4/4 at 120 bpm, with no tempo on its tick: the tempo in force
    # is set again there, at four times the bpm.
    eighths = [(i / 4, (i + 0.4) / 4, 36) for i in range(16)]
    midi = _transcription([(0, 500000)], [0.0], [("drums", 9, eighths)], ((0, 4, 4), (BAR, 4, 16)))
    quartered = steady._quartered(midi)
    assert [(tick, tempo) for tick, _, tempo in notes.tempo_map(quartered)] == [
        (0, 500000),
        (BAR, 125000),
    ]
    assert bars.meter(quartered) == bars.Meter(TICKS, 4, 4)
    assert _seconds(quartered, 3, "note_on") == pytest.approx(_seconds(midi, 3, "note_on"))


def test_the_steady_map_is_a_pickup_bar_then_the_fitted_tempo(bent):
    midi, found = bent
    segments = notes.tempo_map(steady.apply(midi, found))
    assert [(tick, tempo) for tick, _, tempo in segments] == [(0, 125000), (BAR, 500000)]
    assert segments[1][1] == pytest.approx(0.5)
    tick = mido.tick2second(1, TICKS, 500000)
    for k in (1, 2, 11, 40):
        assert notes.seconds_at(segments, TICKS, k * BAR) == pytest.approx(
            0.5 + 2 * (k - 1), abs=tick
        )


def test_every_event_keeps_its_seconds(bent):
    midi, found = bent
    fixed = steady.apply(midi, found)
    half_tick = mido.tick2second(0.5, TICKS, 500000) + 1e-9
    for index in range(len(midi.tracks)):
        before, after = notes.read(midi, [index]), notes.read(fixed, [index])
        assert len(after) == len(before)
        for old, new in zip(before, after, strict=True):
            assert new.onset == pytest.approx(old.onset, abs=half_tick)
            assert new.offset == pytest.approx(old.offset, abs=half_tick)
        # notes.read leaves out the drums; their raw messages, with every other track's, count.
        for kind in ("note_on", "marker", "end_of_track"):
            assert _seconds(fixed, index, kind) == pytest.approx(
                _seconds(midi, index, kind), abs=half_tick
            )
    assert _seconds(midi, 5, "note_on")  # the drums
    assert _seconds(midi, 1, "marker")
    assert _seconds(midi, 1, "end_of_track")[0] > _seconds(midi, 1, "marker")[-1]


def test_the_copy_keeps_the_files_layout(bent):
    midi, found = bent
    fixed = steady.apply(midi, found)
    assert (fixed.type, fixed.ticks_per_beat, fixed.charset) == (1, TICKS, midi.charset)
    assert [track.name for track in fixed.tracks] == [track.name for track in midi.tracks]

    def kinds(track):
        return [message.type for message in track if message.type != "set_tempo"]

    for old, new in zip(midi.tracks, fixed.tracks, strict=True):
        assert kinds(new) == kinds(old)
    signatures = [m for m in fixed.tracks[0] if m.type == "time_signature"]
    assert signatures == [m for m in midi.tracks[0] if m.type == "time_signature"]
    assert _ticks(fixed.tracks[0], "time_signature") == [0]
    assert [_ticks(track, "set_tempo") for track in fixed.tracks] == [[0, BAR]] + [[]] * 6


def test_a_song_starting_on_a_downbeat_gets_no_pickup_bar():
    midi = bent_transcription(0.0)
    assert notes.tempo_map(steady.apply(midi, steady.fit(midi))) == [(0, 0.0, 500000)]


def test_a_tempo_track_ending_before_bar_2_ends_with_its_tempo():
    # A flat map's tempo track ends at tick 0, as tsumugi ends it at its last tempo.
    midi = random_transcription()
    fixed = steady.apply(midi, steady.Fit(120.0, 0.5, 1.0, 400))
    assert _ticks(fixed.tracks[0], "set_tempo") == [0, BAR]
    assert fixed.tracks[0][-1].type == "end_of_track"
    assert sum(message.time for message in fixed.tracks[0]) == BAR


def test_applying_twice_gives_the_same_bytes(bent):
    midi, found = bent

    def saved() -> bytes:
        buffer = io.BytesIO()
        steady.apply(midi, found).save(file=buffer)
        return buffer.getvalue()

    assert saved() == saved()
