"""Measures a song's separated stems into pianoize's stem table, `stems.npz`, which
`pianoize.stems.load` reads: `python stem_worker.py --stems DIR --out FILE`, DIR holding the stem
splitter's `<name>_<stem>.wav` at 44.1 kHz.

tsumugi's interpreter runs it, after tsumugi's stem splitter, so it imports only what that
environment holds (numpy, soundfile, librosa) and nothing of pianoize, which is not installed
there. It sits alone in its directory because the interpreter puts a script's directory first on
sys.path, where pianoize's module names (`notes`, `files`, `cli`) would shadow the libraries'."""

import argparse
import sys
from pathlib import Path

import librosa
import numpy as np
import soundfile

VERSION = 1
SAMPLE_RATE = 44100  # the splitter's
HOP = 512
LOW_PITCH = 36  # C2, the levels' first row
SEMITONES = 72  # C2 to B7
BINS_PER_SEMITONE = 3
LEVEL_STEMS = ("guitar", "other", "piano")
# pyin's rate and hop, a frame of the same length as HOP at SAMPLE_RATE.
VOCALS_RATE = 22050
VOCALS_HOP = 256
VOCALS_FRAME = 2048
VOCALS_LOW, VOCALS_HIGH = 45, 84  # A2 to C6, the range pyin tracks


def find(directory: Path, stem: str) -> Path:
    found = sorted(directory.glob(f"*_{stem}.wav"))
    if len(found) != 1:
        sys.exit(f"stem worker: expected one *_{stem}.wav in {directory}, found {len(found)}")
    return found[0]


def read(path: Path) -> np.ndarray:
    """The WAV at `path`, its channels averaged."""
    signal, rate = soundfile.read(path, dtype="float32", always_2d=True)
    if rate != SAMPLE_RATE:
        sys.exit(f"stem worker: {path} is at {rate} Hz, not the splitter's {SAMPLE_RATE}")
    return signal.mean(axis=1)


def semitones(signal: np.ndarray) -> np.ndarray:
    """Each semitone's amplitude per frame, the loudest of its three constant-Q bins, the first
    bin a third of a semitone under C2 so each semitone's middle bin is centred on it."""
    bins = librosa.cqt(
        signal,
        sr=SAMPLE_RATE,
        hop_length=HOP,
        fmin=librosa.midi_to_hz(LOW_PITCH - 1 / BINS_PER_SEMITONE),
        n_bins=SEMITONES * BINS_PER_SEMITONE,
        bins_per_octave=12 * BINS_PER_SEMITONE,
    )
    return np.abs(bins).reshape(SEMITONES, BINS_PER_SEMITONE, -1).max(axis=1)


def vocals(signal: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """The vocals' pitch per frame as a fractional MIDI number, NaN where unvoiced, and their
    RMS."""
    signal = librosa.resample(signal, orig_sr=SAMPLE_RATE, target_sr=VOCALS_RATE)
    f0, _, _ = librosa.pyin(
        signal,
        fmin=librosa.midi_to_hz(VOCALS_LOW),
        fmax=librosa.midi_to_hz(VOCALS_HIGH),
        sr=VOCALS_RATE,
        frame_length=VOCALS_FRAME,
        hop_length=VOCALS_HOP,
    )
    rms = librosa.feature.rms(y=signal, frame_length=VOCALS_FRAME, hop_length=VOCALS_HOP)[0]
    return librosa.hz_to_midi(f0).astype(np.float32), rms


def scaled(amplitude: np.ndarray) -> np.ndarray:
    """Amplitudes as the table's bytes, half-dB steps under the loudest: 255 is 0 dB, 0 is
    -127.5 dB or less. A silent stem is all zeros."""
    loudest = amplitude.max()
    if loudest == 0:
        return np.zeros(amplitude.shape, np.uint8)
    with np.errstate(divide="ignore"):  # a silent cell is -inf dB, clipped to 0
        decibels = 20 * np.log10(amplitude / loudest)
    return np.clip(np.round(255 + 2 * decibels), 0, 255).astype(np.uint8)


def main() -> None:
    parser = argparse.ArgumentParser(description="Measure separated stems into stems.npz.")
    parser.add_argument("--stems", type=Path, required=True, metavar="DIR")
    parser.add_argument("--out", type=Path, required=True, metavar="FILE")
    args = parser.parse_args()
    # Found first, so a missing stem fails before the minutes of measuring.
    paths = {stem: find(args.stems, stem) for stem in (*LEVEL_STEMS, "vocals")}
    levels = {stem: semitones(read(paths[stem])) for stem in LEVEL_STEMS}
    pitch, rms = vocals(read(paths["vocals"]))
    # The readings' frame counts differ by the last frame or so; cut before scaling, so each
    # stem's loudest is in the table.
    frames = min(len(pitch), len(rms), *(rows.shape[1] for rows in levels.values()))
    # Written to the file object, as savez_compressed adds `.npz` to a name without it.
    with args.out.open("wb") as out:
        np.savez_compressed(
            out,
            version=VERSION,
            frame_seconds=HOP / SAMPLE_RATE,
            low_pitch=LOW_PITCH,
            **{stem: scaled(rows[:, :frames]) for stem, rows in levels.items()},
            vocals_pitch=pitch[:frames],
            vocals_low=VOCALS_LOW,
            vocals_high=VOCALS_HIGH,
            vocals_level=scaled(rms[:frames]),
        )
    print(f"{args.out}: {frames} frames")


if __name__ == "__main__":
    main()
