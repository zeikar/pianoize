"""MIDI to audio through the FluidSynth CLI, which pianoize runs as a separately installed tool."""

import shutil
import subprocess
import tempfile
from pathlib import Path

import mido
import soundfile

DRUM_CHANNEL = 9


class RenderError(Exception):
    pass


def normalize(midi: mido.MidiFile) -> mido.MidiFile:
    """Make a one-preset SoundFont play every note as its piano.

    Such a font is silent on other programs and plays drums on channel 10, so programs and
    banks are zeroed and the drum channel is moved. Channels are kept apart: overlapping
    same-pitch notes and each channel's sustain pedal only work if they stay on their own.
    """
    out = mido.MidiFile(type=midi.type, ticks_per_beat=midi.ticks_per_beat)
    used = {m.channel for track in midi.tracks for m in track if hasattr(m, "channel")}
    free = None
    if DRUM_CHANNEL in used:
        free = next((c for c in range(16) if c not in used), None)
        if free is None:
            raise RenderError("every MIDI channel is in use, so the drum channel cannot move")
    noted = set()
    for track in midi.tracks:
        copy = mido.MidiTrack()
        for message in track:
            message = message.copy()
            if hasattr(message, "channel"):
                if message.channel == DRUM_CHANNEL:
                    message.channel = free
                if message.type == "program_change":
                    message.program = 0
                elif message.type == "control_change" and message.control in (0, 32):
                    message.value = 0
                elif message.type == "note_on":
                    noted.add(message.channel)
            copy.append(message)
        out.tracks.append(copy)
    if out.tracks:
        for channel in sorted(noted, reverse=True):
            out.tracks[0].insert(0, mido.Message("program_change", channel=channel, program=0))
    return out


def render(
    midi: mido.MidiFile,
    wav: Path,
    soundfont: Path,
    fluidsynth: str = "fluidsynth",
    gain: float = 0.5,
    sample_rate: int = 44100,
) -> float:
    """Render `midi` to `wav` and return the peak amplitude."""
    binary = shutil.which(fluidsynth)
    if binary is None:
        raise RenderError(f"{fluidsynth} not found on PATH; install FluidSynth")
    # A stale file from an earlier run must not pass for this run's output.
    wav.unlink(missing_ok=True)
    try:
        with tempfile.TemporaryDirectory() as tmp:
            mid = Path(tmp) / "normalized.mid"
            normalize(midi).save(mid)
            command = [
                binary, "-ni", "-q", "-R", "0", "-C", "0", "-g", str(gain), "-r", str(sample_rate),
                "-T", "wav", "-F", str(wav), str(soundfont), str(mid),
            ]  # fmt: skip
            try:
                subprocess.run(command, check=True, capture_output=True, text=True)
            except subprocess.CalledProcessError as exc:
                raise RenderError(
                    f"{fluidsynth} failed ({exc.returncode}): {exc.stderr.strip()}"
                ) from exc
            except OSError as exc:
                raise RenderError(f"cannot run {fluidsynth}: {exc}") from exc
        return _peak(wav, fluidsynth)
    except RenderError:
        wav.unlink(missing_ok=True)  # a failed render leaves no file behind
        raise


def _peak(wav: Path, fluidsynth: str) -> float:
    try:
        audio, _ = soundfile.read(wav, dtype="float32")
    except (OSError, RuntimeError) as exc:  # soundfile raises LibsndfileError, a RuntimeError
        raise RenderError(f"{fluidsynth} wrote no readable audio to {wav}: {exc}") from exc
    if audio.size == 0:
        raise RenderError(f"{fluidsynth} wrote no audio to {wav}")
    peak = float(abs(audio).max())
    if peak == 0:
        raise RenderError(f"the render is silent; check the soundfont and its program: {wav}")
    return peak
