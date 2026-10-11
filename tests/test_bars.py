import mido
import pytest

from pianoize.bars import Meter, MeterError, bar_count, meter, position, where


def signature(numerator: int, denominator: int) -> mido.MetaMessage:
    return mido.MetaMessage("time_signature", numerator=numerator, denominator=denominator)


def track_with(tick: int, message: mido.MetaMessage) -> mido.MidiTrack:
    return mido.MidiTrack([message.copy(time=tick)])


@pytest.mark.parametrize(
    ("ticks_per_beat", "numerator", "denominator", "bar_ticks", "sixteenth_ticks", "sixteenths"),
    [
        (480, 4, 4, 1920, 120, 16),
        (480, 3, 4, 1440, 120, 12),
        (480, 6, 8, 1440, 120, 12),
        (220, 4, 4, 880, 55, 16),
    ],
)
def test_the_meter_sizes_the_bar(
    tick_midi, ticks_per_beat, numerator, denominator, bar_ticks, sixteenth_ticks, sixteenths
):
    midi = tick_midi(
        [(0, 240, 60, 80)],
        meta=[(0, signature(numerator, denominator))],
        ticks_per_beat=ticks_per_beat,
    )
    found = meter(midi)
    assert found == Meter(ticks_per_beat, numerator, denominator)
    assert (found.bar_ticks, found.sixteenth_ticks, found.sixteenths_per_bar) == (
        bar_ticks,
        sixteenth_ticks,
        sixteenths,
    )


@pytest.mark.parametrize(
    ("ticks_per_beat", "numerator", "denominator", "message"),
    [(90, 4, 4, "whole sixteenths; 90 ticks per beat"), (480, 3, 32, "whole sixteenths; a 3/32")],
)
def test_a_fractional_sixteenth_raises(tick_midi, ticks_per_beat, numerator, denominator, message):
    midi = tick_midi(
        [(0, 45, 60, 80)],
        meta=[(0, signature(numerator, denominator))],
        ticks_per_beat=ticks_per_beat,
    )
    with pytest.raises(MeterError, match=message):
        meter(midi)


def test_no_time_signature_reads_four_four(tick_midi):
    assert meter(tick_midi([(0, 240, 60, 80)])) == Meter(480, 4, 4)


def test_equal_signatures_pass(tick_midi):
    midi = tick_midi([(0, 240, 60, 80)], meta=[(0, signature(3, 4))])
    midi.tracks.append(track_with(1440, signature(3, 4)))
    assert meter(midi) == Meter(480, 3, 4)


def test_a_change_of_meter_on_any_track_raises(tick_midi):
    midi = tick_midi([(0, 240, 60, 80)], meta=[(0, signature(4, 4))])
    midi.tracks.append(track_with(7680, signature(3, 4)))
    with pytest.raises(MeterError, match="at tick 7680, 4/4 to 3/4"):
        meter(midi)


def test_same_tick_signatures_keep_track_order(tick_midi):
    midi = tick_midi([(0, 240, 60, 80)], meta=[(0, signature(4, 4))])
    midi.tracks.append(track_with(0, signature(3, 4)))
    with pytest.raises(MeterError, match="at tick 0, 4/4 to 3/4"):
        meter(midi)


def test_a_late_first_signature_must_be_four_four(tick_midi):
    late = tick_midi([(0, 240, 60, 80)], meta=[(1920, signature(3, 4))])
    with pytest.raises(MeterError, match="at tick 1920, 4/4 to 3/4"):
        meter(late)
    assert meter(tick_midi([(0, 240, 60, 80)], meta=[(1920, signature(4, 4))])) == Meter(480, 4, 4)


def test_bar_count_rounds_the_longest_track_up(tick_midi):
    midi = tick_midi([(0, 1920, 60, 80)])
    four_four = meter(midi)
    assert bar_count(midi, four_four) == 1
    midi.tracks.append(track_with(1921, mido.MetaMessage("end_of_track")))
    assert bar_count(midi, four_four) == 2
    assert bar_count(midi, Meter(480, 3, 4)) == 2


def test_position_and_where_across_a_bar_boundary():
    four_four = Meter(480, 4, 4)
    assert position(four_four, 0) == (1, 0.0)
    assert position(four_four, 1800) == (1, 15.0)
    assert position(four_four, 1920) == (2, 0.0)
    assert position(four_four, 1980) == (2, 0.5)  # half a sixteenth into bar 2
    assert where(four_four, 1920) == "bar 2 pos 0"
    assert where(four_four, 1980) == "bar 2 pos 0.5"
    assert where(Meter(480, 3, 4), 1500) == "bar 2 pos 0.5"
