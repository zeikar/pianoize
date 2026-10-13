"""The preparing commands: setup installs the tsumugi tools pianoize runs, and prepare turns a
song's recording into the files arranging starts from. They register on the same Typer app as the
rest of the CLI."""

from __future__ import annotations

import tempfile
import time
from pathlib import Path
from typing import Annotated

import mido
import soundfile
import typer

from . import files, grid, tsumugi
from .cli import _fail, _read_midi, _refuse_input, _stop_on_signals, app


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


def _transcribe(install: tsumugi.Install, wav: Path, source: Path, scratch: Path) -> None:
    log = source.with_name("transcribe.log")
    typer.echo(
        "transcribing with tsumugi, about twice the song's length on an Apple-silicon Mac; "
        f"log: {log}"
    )
    start = time.monotonic()
    tsumugi.transcribe(install, wav, scratch / "source.mid", log)
    (scratch / "source.mid").replace(source)
    typer.echo(f"transcribe: {time.monotonic() - start:.0f} s")


def _melody(source: Path, melody: Path) -> None:
    """tsumugi's lead vocal line, the track it names `melody`, on the transcription's tempo map
    and time signatures, without its chord markers."""
    try:
        built = grid.build(
            _read_midi(source), ["melody"], conductor=("set_tempo", "time_signature")
        )
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
    typer.echo(f"melody.mid: {sum(map(_notes, _read_midi(melody).tracks))} notes")
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
            "-o", "--out-dir", help="Where song.wav, source.mid, melody.mid and cover.mid go."
        ),
    ],
) -> None:
    """Decode a song, transcribe it with tsumugi, take its melody and generate its cover.

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
    wav, source, melody, cover = (
        out_dir / name for name in ("song.wav", "source.mid", "melody.mid", "cover.mid")
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
            if not _reusing(source):
                _transcribe(install, wav, source, scratch)
            if not _reusing(melody):
                _melody(source, melody)
            if not _reusing(cover):
                _generate(install, source, cover, scratch)
    except (tsumugi.TsumugiError, OSError) as exc:
        raise _fail(str(exc)) from exc
    _summary(wav, source, melody, cover)
