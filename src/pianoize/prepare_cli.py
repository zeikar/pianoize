"""The preparing commands: setup installs the tsumugi tools pianoize runs, and prepare turns a
song's recording into the files arranging starts from. They register on the same Typer app as the
rest of the CLI."""

from __future__ import annotations

import shutil
import tempfile
import time
from pathlib import Path
from typing import Annotated

import mido
import soundfile
import typer

from . import files, grid, steady, tsumugi
from .cli import _fail, _read_midi, _refuse_input, _stop_on_signals, app

DEFAULT_MELODY_TRACK = "melody"


@app.command()
def setup() -> None:
    """Install tsumugi and tsumugi-piano-cover into the pianoize home, pinned, once."""
    try:
        tsumugi.setup(tsumugi.Install.from_env(), typer.echo)
    except (tsumugi.TsumugiError, OSError) as exc:
        raise _fail(str(exc)) from exc


def _reusing(path: Path) -> bool:
    if path.exists():
        typer.echo(f"reusing {path}")
        return True
    return False


def _reason(exc: soundfile.LibsndfileError | OSError) -> object:
    """The error without the path libsndfile's message starts with."""
    if isinstance(exc, soundfile.LibsndfileError):
        return exc.error_string.rstrip(".")
    return exc.strerror or exc


def _decode(audio: Path, wav: Path) -> None:
    """Write `audio` as a 16-bit WAV at its own rate and channels: stem_splitter resamples
    whatever it reads to 44.1 kHz itself."""
    try:
        data, rate = soundfile.read(audio, dtype="float32")
    except (soundfile.LibsndfileError, OSError) as exc:
        raise _fail(
            f"decode: cannot read {audio}: {_reason(exc)}; the decoder reads wav, flac, ogg and mp3"
        ) from exc
    try:
        files.write_all({wav: lambda path: soundfile.write(path, data, rate, subtype="PCM_16")})
    except soundfile.LibsndfileError as exc:
        raise _fail(f"decode: cannot write {wav}: {_reason(exc)}") from exc


def _transcribe(install: tsumugi.Install, wav: Path, transcription: Path, scratch: Path) -> None:
    log = transcription.with_name("transcribe.log")
    typer.echo(
        "transcribing with tsumugi, about twice the song's length on an Apple-silicon Mac; "
        f"log: {log}"
    )
    start = time.monotonic()
    tsumugi.transcribe(install, wav, scratch / "transcription.mid", log)
    (scratch / "transcription.mid").replace(transcription)
    typer.echo(f"transcribe: {time.monotonic() - start:.0f} s")


def _grid(transcription: Path, source: Path) -> None:
    """The transcription on its steady tempo grid, or as it is when the fit finds none."""
    midi = _read_midi(transcription)
    try:
        found = steady.fit(midi)
    except steady.SteadyError as exc:
        typer.echo(f"tempo grid: keeping tsumugi's tempo map: {exc}")
        # A byte copy, not a save through mido, so source.mid is tsumugi's file as it wrote it.
        files.write_all({source: lambda path: shutil.copyfile(transcription, path)})
        return
    typer.echo(
        f"tempo grid: {found.bpm:.2f} bpm, first downbeat at {found.downbeat:.3f} s, "
        f"{found.coverage:.0%} of {found.attacks} attacks within a quarter sixteenth "
        f"({found.window * 1000:.0f} ms)"
    )
    if found.other_octave_share:
        typer.echo(
            f"tempo grid: tsumugi also ran {found.other_octave_share:.0%} of its seconds at "
            f"{found.other_octave:.2f} bpm; the grid takes {found.bpm:.2f}, the octave it held "
            "longer; check the bars by ear"
        )
    files.write_all({source: steady.apply(midi, found).save})


def _check_melody_track(source: Path, name: str) -> None:
    """Refuse a --melody-track the transcription doesn't have, before any melody.mid is reused,
    so a wrong name never passes quietly."""
    tracks = _read_midi(source).tracks
    if not any(track.name == name for track in tracks):
        named = ", ".join(repr(track.name) for track in tracks if track.name)
        raise typer.BadParameter(
            f"no track named {name!r}; tracks named: {named or 'none'}", param_hint="--melody-track"
        )


def _melody(source: Path, melody: Path, name: str) -> None:
    """The transcription's lead line, the track named `name` (tsumugi's `melody` is its lead
    vocal), on the transcription's tempo map and time signatures, without its chord markers. An
    instrumental has no `melody` track, and then there is no melody.mid."""
    midi = _read_midi(source)
    if name == DEFAULT_MELODY_TRACK and not any(track.name == name for track in midi.tracks):
        return
    try:
        built = grid.build(midi, [name], conductor=("set_tempo", "time_signature"))
    except grid.GridError as exc:
        raise _fail(f"melody: {exc}") from exc
    files.write_all({melody: built.save})


def _generate(install: tsumugi.Install, source: Path, cover: Path, scratch: Path) -> None:
    log = cover.with_name("generate.log")
    typer.echo(
        "generating the cover with tsumugi-piano-cover, about a third of the song's length on an "
        f"Apple-silicon Mac; log: {log}"
    )
    start = time.monotonic()
    tsumugi.generate(install, source, scratch / "cover", log).replace(cover)
    typer.echo(f"generate: {time.monotonic() - start:.0f} s")


def _notes(track: mido.MidiTrack) -> int:
    return sum(m.type == "note_on" and m.velocity > 0 for m in track)


def _summary(wav: Path, source: Path, melody: Path, cover: Path) -> None:
    try:
        duration = soundfile.info(wav).duration
    except (soundfile.LibsndfileError, OSError) as exc:
        raise _fail(f"{wav}: cannot read audio: {_reason(exc)}") from exc
    typer.echo(f"song.wav: {duration:.1f} s")
    tracks = _read_midi(source).tracks
    counts = ", ".join(f"{track.name or '(unnamed)'} {_notes(track)}" for track in tracks)
    typer.echo(f"source.mid: {len(tracks)} tracks: {counts}")
    if melody.exists():
        typer.echo(f"melody.mid: {sum(map(_notes, _read_midi(melody).tracks))} notes")
    else:
        typer.echo(
            f"melody.mid: none: no track named {DEFAULT_MELODY_TRACK!r}; "
            "--melody-track NAME takes a track as the melody"
        )
    played = _read_midi(cover)
    typer.echo(f"cover.mid: {sum(map(_notes, played.tracks))} notes, {played.length:.1f} s")


@app.command()
def prepare(
    audio: Annotated[
        Path,
        typer.Argument(
            metavar="AUDIO",
            help="The song's recording: wav, flac, ogg or mp3.",
            exists=True,
            dir_okay=False,
        ),
    ],
    out_dir: Annotated[
        Path,
        typer.Option(
            "-o",
            "--out-dir",
            help="Where song.wav, transcription.mid, source.mid, melody.mid and cover.mid go.",
        ),
    ],
    melody_track: Annotated[
        str | None,
        typer.Option(
            "--melody-track",
            metavar="NAME",
            help="A track of the transcription to take as melody.mid instead of `melody`, for an "
            "instrumental's lead.",
        ),
    ] = None,
) -> None:
    """Decode a song, transcribe it with tsumugi, fit its steady tempo grid, take its melody and
    generate its cover.

    A file already in OUT_DIR is reused, so a stopped run picks up where it stopped.
    """
    _stop_on_signals()
    # Resolved first, so the "reusing" and "log:" lines name absolute paths; transcribe and
    # generate resolve their own.
    audio, out_dir = audio.resolve(), out_dir.resolve()
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise _fail(str(exc)) from exc
    wav, transcription, source, melody, cover = (
        out_dir / name
        for name in ("song.wav", "transcription.mid", "source.mid", "melody.mid", "cover.mid")
    )
    _refuse_input(wav, [audio], "--out-dir")
    install = tsumugi.Install.from_env()
    missing = install.missing()
    if missing:
        raise _fail(
            f"not installed under {install.home}: {', '.join(missing)}; run `pianoize setup`"
        )
    try:
        # The tools write here, and a failed or stopped step leaves nothing behind.
        with tempfile.TemporaryDirectory(dir=out_dir, prefix=".prepare-") as tmp:
            scratch = Path(tmp)
            if not _reusing(wav):
                _decode(audio, wav)
            # A source.mid already made never looks for its transcription, so a directory from
            # before the grid, with no transcription.mid, runs no tool.
            if not _reusing(source):
                if not _reusing(transcription):
                    _transcribe(install, wav, transcription, scratch)
                _grid(transcription, source)
            if melody_track is not None:
                _check_melody_track(source, melody_track)
            if not _reusing(melody):
                _melody(
                    source, melody, DEFAULT_MELODY_TRACK if melody_track is None else melody_track
                )
            if not _reusing(cover):
                _generate(install, source, cover, scratch)
    except (tsumugi.TsumugiError, OSError) as exc:
        raise _fail(str(exc)) from exc
    _summary(wav, source, melody, cover)
