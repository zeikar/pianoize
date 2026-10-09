#!/usr/bin/env bash
# Generates piano covers with Etude (code MIT; checkpoints CC BY-NC-SA 4.0) from the 75 s clip
# (covers/etude-75s.mid) and from the full song (covers/etude.mid). covers/etude/run.txt gets
# each run's device and wall time; covers/etude.status.md says whether it ran.
# Etude runs from its own clone with its own env's interpreter; nothing here imports it. Its
# Demucs separation backend (etude-config.yaml) replaces Spleeter, which needs conda; upstream
# warns that it gives less accurate beats. torchaudio loads audio through torchcodec, which
# loads Homebrew's FFmpeg (--enable-gpl) inside Etude's process.
# Reused on a rerun: the clone, the env, the extracted checkpoints and existing covers.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/env.sh"

SRC="$M1/upstream/Etude"
PY="$M1/envs/etude/bin/python"
CONFIG="$REPO/experiments/m1/etude-config.yaml"
CKPT_URL='https://github.com/Xiugapurin/Etude/releases/download/latest/checkpoints.zip'
MODELS="$M1/models/etude"
ARCHIVE="$MODELS/checkpoints.zip"
COVERS="$M1/covers"
LOGS="$COVERS/etude"
RUN_TXT="$LOGS/run.txt"
STATUS="$COVERS/etude.status.md"

mkdir -p "$LOGS"

# Install. The clone goes to a .part dir and is renamed once complete.
if [ ! -d "$SRC" ]; then
  mkdir -p "$M1/upstream"
  rm -rf "$SRC.part"
  git clone --quiet https://github.com/Xiugapurin/Etude "$SRC.part"
  mv "$SRC.part" "$SRC"
fi
git -C "$SRC" rev-parse HEAD > "$M1/upstream/Etude.commit"

# Upstream requires Python <3.13.
[ -x "$PY" ] || uv venv --python 3.12 "$M1/envs/etude"
# torch is left unpinned: requirements.txt's torch 2.6.0 is too old for pyproject's
# torchcodec>=0.4, and only a recent torchcodec loads Homebrew's FFmpeg 9.
if ! uv pip install --python "$PY" -e "${SRC}[demucs]" 2>&1 | tee "$LOGS/install.log"; then
  { echo "did not run: installing Etude[demucs] failed:"; echo; tail -n 20 "$LOGS/install.log" | sed 's/^/    /'; } > "$STATUS"
  cat "$STATUS" >&2
  exit 1
fi
uv pip freeze --python "$PY" > "$LOGS/freeze.txt"

# Checkpoints. The latest tag can move, so the size is recorded, not enforced, and the
# archive's SHA-256 is the pin. checkpoints/ appears by rename once fully extracted.
if [ ! -d "$SRC/checkpoints" ] || [ ! -s "$MODELS/SHA256SUMS" ]; then
  fetch "$CKPT_URL" "$ARCHIVE"

  terms="Etude pre-trained checkpoints (beat_detector, decoder, extractor, hft_transformer)
License: CC BY-NC-SA 4.0 (https://creativecommons.org/licenses/by-nc-sa/4.0/)
Stated in: https://github.com/Xiugapurin/Etude/blob/main/LICENSE (Part 2)
Terms: attribution, non-commercial use only, adaptations under the same license.
Code: MIT, https://github.com/Xiugapurin/Etude
Downloaded from: $CKPT_URL
Downloaded on: $(date -u +%Y-%m-%d)
Size: $(stat -f %z "$ARCHIVE") bytes (170665865 at research time)"
  printf '%s\n' "$terms" | tee "$MODELS/TERMS.txt"

  (cd "$MODELS" && shasum -a 256 "$(basename "$ARCHIVE")") > "$MODELS/SHA256SUMS"
  cat "$MODELS/SHA256SUMS"

  # The archive holds a top-level checkpoints/, which goes where the config's relative paths look.
  rm -rf "$MODELS/unzip.part"
  if ! unzip -q "$ARCHIVE" -d "$MODELS/unzip.part"; then
    echo "unzip failed; deleting the archive" >&2
    rm -rf "$ARCHIVE" "$MODELS/unzip.part"
    exit 1
  fi
  rm -rf "$SRC/checkpoints"
  mv "$MODELS/unzip.part/checkpoints" "$SRC/checkpoints"
  rmdir "$MODELS/unzip.part"
  rm -f "$ARCHIVE"
fi

# record KEY TEXT: sets KEY's line in run.txt, replacing an earlier one.
record() {
  local tmp="$TMPDIR/etude.run.txt.part"
  { grep -v "^$1: " "$RUN_TXT" 2>/dev/null || true; echo "$1: $2"; } > "$tmp"
  mv "$tmp" "$RUN_TXT"
}

# last_line LOG: the last non-blank line, progress-bar carriage returns split into lines.
last_line() {
  tr '\r' '\n' < "$1" | grep -v '^[[:space:]]*$' | tail -n 1 | cut -c 1-200
}

# etude NAME AUDIO DEVICE: one Etude run, logged to covers/etude/NAME.DEVICE.log. It runs from
# the clone: the config's checkpoint and output paths are relative, and infer.py starts
# scripts/run_separation.py by a relative path. NAME's earlier MIDI and Etude's intermediates
# (shared by all runs) are removed first, so nothing from an earlier run can pass for this one.
etude() {
  local name="$1" audio="$2" device="$3"
  rm -f "$SRC/outputs/infer/$name.mid"
  rm -rf "$SRC/outputs/infer/temp"
  (
    cd "$SRC"
    # Unbuffered, so the log holds the last stage even when the run is killed.
    export PYTHONUNBUFFERED=1
    exec "$PY" infer.py --config "$CONFIG" --input "$audio" --device "$device" --output_name "$name"
  ) 2>&1 | tee "$LOGS/$name.$device.log"
}

# cover NAME AUDIO DEST: runs Etude on MPS, and again on CPU if that fails, each run recorded
# in run.txt. Copies the MIDI to DEST through a temp name, so a killed copy leaves no DEST.
cover() {
  local name="$1" audio="$2" dest="$3" device start secs status
  for device in mps cpu; do
    start=$(date +%s)
    status=0
    etude "$name" "$audio" "$device" || status=$?
    secs=$(( $(date +%s) - start ))
    if [ "$status" -ne 0 ]; then
      record "$name $device" "failed: exit $status after $secs s: $(last_line "$LOGS/$name.$device.log")"
      continue
    fi
    # Etude only warns when the decoder generates an empty sequence, and writes no MIDI.
    if [ ! -s "$SRC/outputs/infer/$name.mid" ]; then
      record "$name $device" "exit 0 after $secs s but no MIDI: empty sequence"
      echo "did not run: empty sequence ($name on $device; see covers/etude/$name.$device.log)" > "$STATUS"
      exit 1
    fi
    record "$name $device" "$secs s"
    cp "$SRC/outputs/infer/$name.mid" "$dest.part"
    mv "$dest.part" "$dest"
    return 0
  done
  echo "did not run: $name failed on MPS and on CPU (see covers/etude/run.txt)" > "$STATUS"
  exit 1
}

[ -s "$COVERS/etude-75s.mid" ] || cover etude-75s "$M1/input/song_75s.wav" "$COVERS/etude-75s.mid"
[ -s "$COVERS/etude.mid" ] || cover etude-full "$M1/input/song.wav" "$COVERS/etude.mid"

printf '%s\n' "ran: commit $(cat "$M1/upstream/Etude.commit"), Demucs separation backend (upstream: less accurate beats)" \
  "covers: etude-75s.mid (75 s clip), etude.mid (full song); devices and wall times in covers/etude/run.txt" > "$STATUS"
cat "$RUN_TXT"
