#!/usr/bin/env bash
# Transcribes the vocals stem to MIDI with Basic Pitch 0.4.0 (ONNX backend, CPU) and records
# the backend and wall time. Skips when the MIDI already exists; a failed run removes its
# partial output so a rerun starts clean.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/env.sh"

ENV="$M1/envs/basic-pitch"
OUT="$M1/melody/basic-pitch-vocals"
MIDI="$M1/melody/basic-pitch-vocals.mid"

if [ ! -x "$ENV/bin/python" ]; then
  # 3.12 is broken for Basic Pitch on macOS.
  uv venv --python 3.11 "$ENV"
fi
# basic-pitch 0.4.0 imports pkg_resources through resampy, and setuptools 81+ no longer ships it.
uv pip install --python "$ENV/bin/python" "basic-pitch[onnx]==0.4.0" "setuptools<81"

if [ ! -s "$MIDI" ]; then
  # Basic Pitch refuses to overwrite and refuses a missing output directory.
  rm -rf "$OUT" "$MIDI"
  mkdir -p "$OUT"
  start=$(date +%s)
  if ! "$ENV/bin/basic-pitch" "$OUT" "$M1/stems/htdemucs_ft/song/vocals.wav" \
      --save-midi --model-serialization onnx --minimum-frequency 80 --maximum-frequency 1100; then
    echo "basic-pitch failed; removing partial output" >&2
    rm -rf "$OUT" "$MIDI"
    exit 1
  fi
  secs=$(( $(date +%s) - start ))
  cp "$OUT"/*.mid "$MIDI"
  {
    echo "basic-pitch 0.4.0, backend: onnx (--model-serialization onnx), CPU"
    echo "wall time: $secs s for a 251 s vocals stem"
  } > "$M1/melody/basic-pitch.run.txt"
fi
cat "$M1/melody/basic-pitch.run.txt"
