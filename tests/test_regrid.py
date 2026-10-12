import mido
import pytest
from typer.testing import CliRunner

from pianoize import bars, notes, regrid
from pianoize.cli import app

BAR = 1920  # ticks of a 4/4 bar at tick_midi's 480 per beat
METER = bars.Meter(480, 4, 4)
# Tempo changes as (bar, bpm), bars counted from 0, so a shape plays at any resolution.
# Bars 2 to 5 hold five bars at 175 BPM, 1.92 + 3.017 + 1.92 s: the middle tempo is only 9% off
# 175, the run as a whole 20%.
HICCUP = [(0, 175), (2, 125), (3, 159.09), (5, 125), (6, 175)]
# tsumugi's own tempos around its hiccup, in microseconds a beat: five bars within about 1 ms.
REAL = [(bar, mido.tempo2bpm(tempo)) for bar, tempo in
        [(0, 342848), (2, 480726), (3, 373529), (5, 486281), (6, 342883)]]  # fmt: skip
TWICE = HICCUP + [(bar + 6, bpm) for bar, bpm in HICCUP[1:]]
# Tempo restatements a little off 175: their bars hold as many of the song's.
DRIFT = [(0, 175), (2, 173), (3, 177), (4, 175)]


def on_every_beat(bar_count: int, ticks_per_beat: int = 480) -> list[tuple[int, int, int, int]]:
    ticks = range(0, bar_count * 4 * ticks_per_beat, ticks_per_beat)
    return [(tick, tick + ticks_per_beat // 2, 60, 80) for tick in ticks]


def make_cover(tick_midi, tempos, bar_count=10, ticks_per_beat=480) -> mido.MidiFile:
    bar = 4 * ticks_per_beat
    changes = [(round(at * bar), bpm) for at, bpm in tempos]
    return tick_midi(
        on_every_beat(bar_count, ticks_per_beat), changes, ticks_per_beat=ticks_per_beat
    )


@pytest.mark.parametrize(
    ("tempos", "ticks_per_beat"), [(HICCUP, 480), (REAL, 960)], ids=["hiccup", "real at 960"]
)
def test_a_run_holding_five_bars_in_four_is_a_hiccup(tick_midi, tempos, ticks_per_beat):
    midi = make_cover(tick_midi, tempos, ticks_per_beat=ticks_per_beat)
    (span,) = regrid.hiccups(midi, bars.meter(midi))
    bar = 4 * ticks_per_beat
    assert (span.start, span.end, span.bars) == (2 * bar, 6 * bar, 5)
    assert span.tempos == tuple(mido.bpm2tempo(bpm) for _, bpm in tempos[1:4])
    assert mido.tempo2bpm(span.tempo) == pytest.approx(175, abs=0.03)


@pytest.mark.parametrize(
    "tempos",
    [
        # The run fits three bars at its neighbours' mean, 150, but the song settles at 125.
        [(0, 175), (4, 100), (6, 125)],
        # Five grid bars holding six bars at 175: too long for a hiccup.
        [(0, 175), (2, 175 * 5 / 6), (7, 175)],
        # Five bars in four, a beat off the bar lines.
        [(at + 0.25 if at else 0, bpm) for at, bpm in HICCUP],
        # Four grid bars holding 5.4 bars at 175: no whole number.
        [(0, 175), (2, 130), (6, 175)],
        # A two-bar ritardando back to tempo, 47 ms off three bars at 175.
        [(0, 175), (4, 140), (5, 102), (6, 175)],
        # Three bars at 130, 53 ms off four bars at 175.
        [(0, 175), (2, 130), (5, 175)],
        # Bars a little off the tempo, holding as many of the song's.
        DRIFT,
    ],
    ids=[
        "lasting change",
        "five bars",
        "off the bar lines",
        "no whole bars",
        "ritardando",
        "three bars at 130",
        "drift",
    ],
)
def test_not_a_hiccup(tick_midi, tempos):
    assert regrid.hiccups(make_cover(tick_midi, tempos), METER) == []


@pytest.mark.parametrize(
    ("tempos", "bar_count", "ticks_per_beat", "midi_type", "tempo_bars"),
    [
        (HICCUP, 10, 480, 1, [0, 2, 7]),
        (REAL, 10, 960, 1, [0, 2, 7]),
        (HICCUP, 10, 480, 0, [0, 2, 7]),
        (TWICE, 14, 480, 1, [0, 2, 7, 9, 14]),
    ],
    ids=["hiccup", "real at 960", "type 0", "two spans"],
)
def test_the_repair_adds_the_bars_and_keeps_every_notes_time(
    tick_midi, tempos, bar_count, ticks_per_beat, midi_type, tempo_bars
):
    midi = make_cover(tick_midi, tempos, bar_count, ticks_per_beat)
    midi.type = midi_type
    meter = bars.meter(midi)
    spans = regrid.hiccups(midi, meter)
    gained = (len(tempo_bars) - 1) // 2
    fixed = regrid.repair(midi, spans)
    assert (fixed.type, fixed.ticks_per_beat) == (midi_type, ticks_per_beat)
    assert bars.bar_count(fixed, meter) == bars.bar_count(midi, meter) + gained
    tick = mido.tick2second(1, ticks_per_beat, mido.bpm2tempo(175))
    before, after = notes.read(midi), notes.read(fixed)
    assert len(after) == len(before)
    for old, new in zip(before, after, strict=True):
        assert new.onset == pytest.approx(old.onset, abs=tick)
        assert new.offset == pytest.approx(old.offset, abs=tick)
        if old.on_tick >= spans[-1].end:
            assert new.on_tick == old.on_tick + gained * meter.bar_ticks
    found = [
        (at / meter.bar_ticks, round(mido.tempo2bpm(tempo)))
        for at, _, tempo in notes.tempo_map(fixed)
    ]
    assert found == [(at, 175) for at in tempo_bars]


def _ticks(track: mido.MidiTrack, kind: str) -> list[int]:
    found, now = [], 0
    for message in track:
        now += message.time
        if message.type == kind:
            found.append(now)
    return found


def test_the_repair_keeps_the_files_layout(tick_midi):
    # The hiccup's tempo changes are split over both tracks, as a file may have them.
    name = mido.MetaMessage("track_name", name="Tempo")
    marker = mido.MetaMessage("marker", text="G")
    first = [(0, 175), (2 * BAR, 125), (3 * BAR, 159.09)]
    midi = tick_midi([], first, meta=[(0, name), (4 * BAR, marker), (8 * BAR, marker)])
    piano = mido.MetaMessage("track_name", name="Piano")
    second = tick_midi(on_every_beat(10), [(5 * BAR, 125), (6 * BAR, 175)], meta=[(0, piano)])
    midi.tracks.append(second.tracks[0])
    fixed = regrid.repair(midi, regrid.hiccups(midi, METER))
    assert (fixed.type, fixed.ticks_per_beat) == (1, 480)

    def untimed(file):
        return [[m.copy(time=0) for m in track if m.type != "set_tempo"] for track in file.tracks]

    assert untimed(fixed) == untimed(midi)
    # The tempo inside the span is dropped from the track it sat on; the others stay on theirs.
    assert [_ticks(track, "set_tempo") for track in fixed.tracks] == [[0, 2 * BAR], [7 * BAR]]
    # 3.43 s into the span is 4.5 bars at 175; after the span, a bar later.
    assert _ticks(fixed.tracks[0], "marker") == [4 * BAR + BAR // 2, 9 * BAR]


def test_a_cover_without_hiccups_comes_back_the_same(tick_midi):
    midi = make_cover(tick_midi, DRIFT, 6)
    fixed = regrid.repair(midi, regrid.hiccups(midi, METER))
    assert notes.read(fixed) == notes.read(midi)
    assert notes.tempo_map(fixed) == notes.tempo_map(midi)


def _regrid_cli(cover, out):
    return CliRunner().invoke(app, ["regrid", str(cover), "-o", str(out)])


def test_cli_prints_the_span_and_writes_the_copy(tmp_path, tick_midi):
    cover, out, expected = tmp_path / "cover.mid", tmp_path / "out.mid", tmp_path / "expected.mid"
    make_cover(tick_midi, HICCUP).save(cover)
    result = _regrid_cli(cover, out)
    assert result.exit_code == 0, result.output
    assert result.stdout == "bars 3-6: 125.00, 159.09, 125.00 BPM -> 5 bars at 175.00\n"
    midi = mido.MidiFile(cover)
    regrid.repair(midi, regrid.hiccups(midi, METER)).save(expected)
    assert out.read_bytes() == expected.read_bytes()


def test_cli_writes_a_cover_without_hiccups_as_it_was(tmp_path, tick_midi):
    cover, out = tmp_path / "cover.mid", tmp_path / "out.mid"
    make_cover(tick_midi, DRIFT, 6).save(cover)
    result = _regrid_cli(cover, out)
    assert result.exit_code == 0, result.output
    assert result.stdout == "no tempo hiccups\n"
    assert out.read_bytes() == cover.read_bytes()


def test_cli_refuses_to_overwrite_its_input(tmp_path, tick_midi):
    cover = tmp_path / "cover.mid"
    make_cover(tick_midi, HICCUP).save(cover)
    before = cover.read_bytes()
    (tmp_path / "sub").mkdir()
    result = _regrid_cli(cover, tmp_path / "sub" / ".." / "cover.mid")
    assert result.exit_code == 2
    assert "would overwrite an input" in " ".join(result.output.split())
    assert cover.read_bytes() == before


@pytest.mark.parametrize(
    ("kind", "message"),
    [
        ("unreadable", "cannot read MIDI"),
        ("type 2", "a type 2 MIDI file's tracks share no timeline"),
        ("meter change", "the cover changes meter at tick 1920, 4/4 to 3/4"),
    ],
)
def test_cli_reports_a_cover_it_cannot_regrid(tmp_path, tick_midi, kind, message):
    cover, out = tmp_path / "cover.mid", tmp_path / "out.mid"
    if kind == "unreadable":
        cover.write_bytes(b"not a MIDI file")
    else:
        three_four = mido.MetaMessage("time_signature", numerator=3, denominator=4)
        meta = [(BAR, three_four)] if kind == "meter change" else []
        midi = tick_midi(on_every_beat(2), meta=meta)
        midi.type = 2 if kind == "type 2" else 1
        midi.save(cover)
    result = _regrid_cli(cover, out)
    assert result.exit_code == 1
    assert f"error: {cover}: {message}" in result.output
    assert "Traceback" not in result.output
    assert not out.exists()
