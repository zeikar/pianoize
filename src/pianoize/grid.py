"""The tempo grid of a transcription-only arrangement: the transcription's tempo map, time
signature and chord markers on one conductor track, plus the band's chord and bass tracks, so the
arranging commands can take it as their cover. The copied tracks keep everything else they carry,
as the transcription wrote it."""

import mido

CONDUCTOR = ("set_tempo", "time_signature", "marker")
DEFAULT_TRACKS = ("piano", "electric_bass")


class GridError(ValueError):
    pass


def _ticks(track: mido.MidiTrack):
    now = 0
    for message in track:
        now += message.time
        yield now, message


def _final_tick(track: mido.MidiTrack) -> int:
    return sum(message.time for message in track)


def _retimed(events: list[tuple[int, mido.Message | mido.MetaMessage]], end: int) -> mido.MidiTrack:
    """The events, sorted as given, with delta times from their ticks, closed at tick `end`."""
    track = mido.MidiTrack()
    now = 0
    for tick, message in events:
        track.append(message.copy(time=tick - now))
        now = tick
    track.append(mido.MetaMessage("end_of_track", time=end - now))
    return track


def build(
    source: mido.MidiFile, names: list[str], *, conductor: tuple[str, ...] = CONDUCTOR
) -> mido.MidiFile:
    """A type 1 file of a conductor track with every message of `source` whose type is in
    `conductor`, by default every tempo, time signature and marker, then each track of `source`
    named in `names`, in the source's order, without those messages. Each track ends where its
    source track did: a note only the track's end closes keeps its length, and the grid is as
    long as the transcription."""
    if source.type == 2:
        raise GridError("a type 2 MIDI file's tracks share no timeline to build a grid on")
    if not any(m.type == "set_tempo" for track in source.tracks for m in track):
        raise GridError("no tempo map: no set_tempo message on any track")
    for name in names:
        if not any(track.name == name for track in source.tracks):
            named = ", ".join(repr(track.name) for track in source.tracks if track.name)
            raise GridError(f"no track named {name!r}; tracks named: {named or 'none'}")

    merged = sorted(
        (
            ((tick, index, k), message)
            for index, track in enumerate(source.tracks)
            for k, (tick, message) in enumerate(_ticks(track))
            if message.type in conductor
        ),
        key=lambda event: event[0],
    )
    grid = mido.MidiFile(type=1, ticks_per_beat=source.ticks_per_beat, charset=source.charset)
    grid.tracks.append(
        _retimed(
            [(key[0], message) for key, message in merged],
            max(_final_tick(track) for track in source.tracks),
        )
    )
    for track in source.tracks:
        if track.name in names:
            kept = [
                (tick, message)
                for tick, message in _ticks(track)
                if message.type not in conductor and message.type != "end_of_track"
            ]
            grid.tracks.append(_retimed(kept, _final_tick(track)))
    return grid
