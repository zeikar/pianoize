#!/usr/bin/env bash
# Transcribes the sung melody with GAME v1.0.3 (openvpi; code MIT) and the GAME-1.0-medium
# weights (CC BY-NC-SA 4.0), on CPU, from the Demucs vocals stem and from the full mix:
# melody/game-vocals.{mid,csv} and melody/game-mix.{mid,csv}. melody/game.run.txt gets the
# wall times, a repeatability check and whether the default (MPS) accelerator runs.
# GAME runs from its own clone with its own env's interpreter; nothing here imports it.
# Reused on a rerun: the clone, the env, the extracted weights, existing outputs and the
# recorded checks. A mix run that failed or hit the 30-minute limit stays recorded as
# "mix: did not complete"; delete that line from game.run.txt to retry it.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/env.sh"

TAG=v1.0.3
SRC="$M1/upstream/GAME"
PY="$M1/envs/game/bin/python"
WEIGHTS_URL='https://github.com/openvpi/GAME/releases/download/v1.0.0/GAME-1.0-medium.zip'
WEIGHTS_SIZE=184550485
MODELS="$M1/models/game"
ARCHIVE="$MODELS/$(basename "$WEIGHTS_URL")"
MODEL_DIR="$MODELS/GAME-1.0-medium"
MEL="$M1/melody"
RUN_TXT="$MEL/game.run.txt"
VOCALS="$M1/stems/htdemucs_ft/song/vocals.wav"
MIX="$M1/input/song.wav"
LIMIT=1800

# Install. The clone goes to a .part dir and is renamed once complete.
if [ ! -d "$SRC" ]; then
  mkdir -p "$M1/upstream"
  rm -rf "$SRC.part"
  git -c advice.detachedHead=false clone --quiet --depth 1 --branch "$TAG" \
    https://github.com/openvpi/GAME "$SRC.part"
  mv "$SRC.part" "$SRC"
fi
commit="$(git -C "$SRC" rev-parse HEAD)"
if [ "$commit" != "$(git -C "$SRC" rev-parse "$TAG^{commit}")" ]; then
  echo "$SRC is not at $TAG; delete it to clone again" >&2
  exit 1
fi
echo "$commit" > "$M1/upstream/GAME.commit"

[ -x "$PY" ] || uv venv --python 3.12 "$M1/envs/game"
# torch 2.8.0 is the version upstream's README says it is tested with; requirements.txt pins numpy<2.
uv pip install --python "$PY" torch==2.8.0 -r "$SRC/requirements.txt"

# Weights. The PyTorch checkpoints are on the v1.0.0 release; v1.0.3 ships ONNX only.
# The model dir appears by rename once fully extracted, so it marks completion.
if [ ! -d "$MODEL_DIR" ] || [ ! -s "$MODELS/SHA256SUMS" ]; then
  fetch "$WEIGHTS_URL" "$ARCHIVE"
  size="$(stat -f %z "$ARCHIVE")"
  if [ "$size" != "$WEIGHTS_SIZE" ]; then
    echo "$ARCHIVE is $size bytes, expected $WEIGHTS_SIZE; deleting it" >&2
    rm -f "$ARCHIVE"
    exit 1
  fi

  terms="GAME-1.0-medium (pretrained GAME model by openvpi)
License: CC BY-NC-SA 4.0 (https://creativecommons.org/licenses/by-nc-sa/4.0/)
Stated in: https://github.com/openvpi/GAME/releases/tag/v1.0.0 (\"The model files apply CC BY-NC-SA 4.0 license.\")
Terms: attribution, non-commercial use only, adaptations under the same license.
Code: MIT, https://github.com/openvpi/GAME
Downloaded from: $WEIGHTS_URL
Downloaded on: $(date -u +%Y-%m-%d)"
  printf '%s\n' "$terms" | tee "$MODELS/TERMS.txt"

  (cd "$MODELS" && shasum -a 256 "$(basename "$ARCHIVE")") > "$MODELS/SHA256SUMS"
  cat "$MODELS/SHA256SUMS"

  rm -rf "$MODELS/unzip.part"
  if ! unzip -q "$ARCHIVE" -d "$MODELS/unzip.part"; then
    echo "unzip failed; deleting the archive" >&2
    rm -rf "$ARCHIVE" "$MODELS/unzip.part"
    exit 1
  fi
  rm -rf "$MODEL_DIR"
  mv "$MODELS/unzip.part/GAME-1.0-medium" "$MODEL_DIR"
  rmdir "$MODELS/unzip.part"
  rm -f "$ARCHIVE"
fi
MODEL="$(find "$MODEL_DIR" -name '*.pt' | head -n 1)"
[ -n "$MODEL" ] || { echo "no .pt in $MODEL_DIR" >&2; exit 1; }

mkdir -p "$MEL"

# record KEY TEXT: sets KEY's line in game.run.txt, replacing an earlier one.
record() {
  local tmp="$TMPDIR/game.run.txt.part"
  { grep -v "^$1: " "$RUN_TXT" 2>/dev/null || true; echo "$1: $2"; } > "$tmp"
  mv "$tmp" "$RUN_TXT"
}

# game AUDIO OUTDIR [ACCELERATOR]: one GAME extraction into a fresh OUTDIR, logged to
# OUTDIR/game.log, killed after $LIMIT s (exit 142). Without ACCELERATOR, Lightning picks one.
# Runs from the clone because infer.py imports its sibling lib.
game() {
  local audio="$1" out="$2" accel="${3:-}"
  rm -rf "$out"
  mkdir -p "$out"
  (
    cd "$SRC"
    if [ -n "$accel" ]; then export PL_TRAINER_ACCELERATOR="$accel"; else unset PL_TRAINER_ACCELERATOR; fi
    exec perl -e 'alarm shift; exec @ARGV or die "exec: $!\n"' "$LIMIT" \
      "$PY" infer.py extract "$audio" -m "$MODEL" -l ja --output-formats mid,csv --output-dir "$out"
  ) 2>&1 | tee "$out/game.log"
}

# reason LOG: the last Python exception line, else the last non-blank line. The progress
# bar redraws with carriage returns and keeps printing after a traceback.
reason() {
  tr '\r' '\n' < "$1" | awk 'NF { last = $0 } /^[[:alnum:]_.]+(Error|Exception)/ { err = $0 }
    END { print substr(err != "" ? err : last, 1, 200) }'
}

if [ ! -s "$MEL/game-vocals.mid" ] || [ ! -s "$MEL/game-vocals.csv" ]; then
  start=$(date +%s)
  game "$VOCALS" "$MEL/game-vocals" cpu
  record vocals "CPU, $(( $(date +%s) - start )) s"
  cp "$MEL/game-vocals/vocals.csv" "$MEL/game-vocals.csv"
  cp "$MEL/game-vocals/vocals.mid" "$MEL/game-vocals.mid"
fi

# The mix may reach GAME as one 251 s item when the silence slicer finds no gaps.
if { [ ! -s "$MEL/game-mix.mid" ] || [ ! -s "$MEL/game-mix.csv" ]; } \
    && ! grep -q '^mix: did not complete' "$RUN_TXT" 2>/dev/null; then
  rm -f "$MEL/game-mix.mid" "$MEL/game-mix.csv"
  start=$(date +%s)
  status=0
  game "$MIX" "$MEL/game-mix" cpu || status=$?
  secs=$(( $(date +%s) - start ))
  if [ "$status" -eq 0 ] && [ -s "$MEL/game-mix/song.mid" ] && [ -s "$MEL/game-mix/song.csv" ]; then
    record mix "CPU, $secs s"
    cp "$MEL/game-mix/song.csv" "$MEL/game-mix.csv"
    cp "$MEL/game-mix/song.mid" "$MEL/game-mix.mid"
  elif [ "$status" -eq 142 ]; then
    record mix "did not complete: killed at the $LIMIT s limit"
  else
    record mix "did not complete: exit $status after $secs s: $(reason "$MEL/game-mix/game.log")"
  fi
fi

if ! grep -q '^repeatability: ' "$RUN_TXT" 2>/dev/null; then
  scratch="$TMPDIR/game-repeat"
  game "$VOCALS" "$scratch" cpu
  status=0
  diff "$MEL/game-vocals.csv" "$scratch/vocals.csv" > "$scratch/csv.diff" || status=$?
  case "$status" in
    0) record repeatability "second CPU extraction of the vocals: CSV identical" ;;
    1) record repeatability "second CPU extraction of the vocals: CSV differs: $(grep -c '^[<>]' "$scratch/csv.diff") lines" ;;
    *) exit 1 ;;
  esac
  rm -rf "$scratch"
fi

# Diagnostic only: its failure is recorded, not fatal.
if ! grep -q '^mps: ' "$RUN_TXT" 2>/dev/null; then
  start=$(date +%s)
  status=0
  game "$VOCALS" "$MEL/game-vocals-mps" || status=$?
  secs=$(( $(date +%s) - start ))
  device="$(grep -m 1 'GPU available' "$MEL/game-vocals-mps/game.log" || true)"
  if [ "$status" -eq 0 ] && [ -s "$MEL/game-vocals-mps/vocals.csv" ]; then
    # Note counts: one CSV row per note after the header.
    mps_notes=$(( $(wc -l < "$MEL/game-vocals-mps/vocals.csv") - 1 ))
    cpu_notes=$(( $(wc -l < "$MEL/game-vocals.csv") - 1 ))
    record mps "vocals with PL_TRAINER_ACCELERATOR unset ran, $secs s ($device), $mps_notes notes vs $cpu_notes on CPU"
  else
    record mps "vocals with PL_TRAINER_ACCELERATOR unset failed: exit $status after $secs s: $(reason "$MEL/game-vocals-mps/game.log")"
  fi
fi

cat "$RUN_TXT"
