"""The falling-notes video's timing, cards and padded audio."""

import json
import math
from dataclasses import dataclass
from pathlib import Path

import mido
import numpy as np
import soundfile

from . import render, roll

FPS = 60
INTRO_SECONDS = 6.0  # where the music starts
CREDITS_SECONDS = 6.0
# The viewer is page assets, not Python, so it stays at the checkout's top level rather than
# inside the package; pianoize runs from a checkout.
VIEWER = Path(__file__).resolve().parents[2] / "viewer"


class VideoError(Exception):
    pass


def cards(text: str) -> dict[str, list[str]]:
    """Split a cards file at its first `---` line into the title and credits cards' lines."""
    lines = text.splitlines()
    if "---" not in (line.strip() for line in lines):
        raise VideoError("the cards file has no '---' line between the title and the credits")
    at = next(i for i, line in enumerate(lines) if line.strip() == "---")
    found = {"title": _trim(lines[:at]), "credits": _trim(lines[at + 1 :])}
    for name, card in found.items():
        if not card:
            raise VideoError(f"the {name} card is empty")
    return found


def _trim(lines: list[str]) -> list[str]:
    lines = [line.rstrip() for line in lines]
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    return lines


@dataclass(frozen=True)
class Timeline:
    music_start: float
    music_end: float
    end: float
    frames: int


def timeline(audio_seconds: float, midi_seconds: float) -> Timeline:
    """The video's seconds. The music runs to the later of the audio and the MIDI, rounded up
    to a whole frame."""
    # The epsilon keeps an exact frame (1.3 s is 78 frames) from tipping to the next on
    # floating-point noise in the product.
    frames = math.ceil(max(audio_seconds, midi_seconds) * FPS - 1e-9)
    music_end = INTRO_SECONDS + frames / FPS
    end = music_end + CREDITS_SECONDS
    return Timeline(INTRO_SECONDS, music_end, end, round(end * FPS))


def pad(wav_in: Path, wav_out: Path, timeline: Timeline) -> None:
    """Write `wav_in` with silence in front and after, so its clock is the video's clock."""
    info = soundfile.info(wav_in)
    audio, rate = soundfile.read(wav_in, dtype="float32", always_2d=True)
    total = round(timeline.end * rate)
    front = round(timeline.music_start * rate)
    out = np.zeros((total, audio.shape[1]), dtype=np.float32)
    kept = audio[: total - front]
    out[front : front + len(kept)] = kept
    soundfile.write(wav_out, out, rate, subtype=info.subtype)


def manifest(card_lines: dict[str, list[str]], timeline: Timeline) -> dict:
    """What the page reads from /run/manifest.json: the names of the run's files, the cards'
    lines and the timeline's seconds."""
    return {
        "arrangement": "arrangement.json",
        "audio": "audio.wav",
        "cards": card_lines,
        "timeline": {
            "music_start": timeline.music_start,
            "music_end": timeline.music_end,
            "end": timeline.end,
        },
    }


def prepare(
    midi: mido.MidiFile,
    cards_text: str,
    soundfont: Path,
    run_dir: Path,
    gain: float,
) -> tuple[Timeline, float]:
    """Fill `run_dir` with what the page needs; return the timeline and the render's peak."""
    card_lines = cards(cards_text)
    data = roll.export(midi)
    (run_dir / "arrangement.json").write_text(roll.dump(data), encoding="utf-8")
    rendered = run_dir / "render.wav"
    peak = render.render(midi, rendered, soundfont, gain=gain)
    info = soundfile.info(rendered)
    moments = timeline(info.frames / info.samplerate, roll.length(midi))
    pad(rendered, run_dir / "audio.wav", moments)
    rendered.unlink()
    (run_dir / "manifest.json").write_text(
        json.dumps(manifest(card_lines, moments), indent=2) + "\n", encoding="utf-8"
    )
    return moments, peak
