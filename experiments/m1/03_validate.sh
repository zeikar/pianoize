#!/usr/bin/env bash
# Checks the renderer and the scorer before any model runs.
# 1. validate/: a synthetic progression with known chords (make_synthetic.py), rendered with
#    FluidSynth, analyzed by chordotomy and scored against its own timeline.
# 2. results/: the human cover's timeline and the decoded original (input/song.wav, analyzed by
#    chordotomy's model engine, a few minutes) scored against the original's timeline. The
#    analysis's wall time goes to results/run.txt when it runs; a reused one leaves it alone.
# Reads the .chords.json next to SONG_MP3 and COVER_MP3. Exits non-zero only when an evaluate
# fails, never on the scores: reading the tables is the check.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/env.sh"

: "${SONG_MP3:?set SONG_MP3 to the original recording}"
: "${COVER_MP3:?set COVER_MP3 to the human piano cover}"

VALIDATE="$M1/validate"
RESULTS="$M1/results"

"$REPO/.venv/bin/python" "$REPO/experiments/m1/make_synthetic.py" "$VALIDATE"
# The row is not named synthetic: its analysis, NAME.chords.json in the out dir, would be the
# ground truth itself, reused instead of rendered and analyzed.
XDG_CACHE_HOME="$CHORDOTOMY_XDG_CACHE_HOME" "$PIANOIZE" evaluate \
  --original "$VALIDATE/synthetic.chords.json" \
  --checkpoints "$VALIDATE/synthetic.checkpoints.json" \
  --out-dir "$VALIDATE" \
  rendered="$VALIDATE/synthetic.mid"

analyzed=1
[ -e "$RESULTS/original-wav.chords.json" ] && analyzed=0
start=$SECONDS
XDG_CACHE_HOME="$CHORDOTOMY_XDG_CACHE_HOME" "$PIANOIZE" evaluate \
  --original "${SONG_MP3%.mp3}.chords.json" \
  --checkpoints "$M1/momonone.checkpoints.json" \
  --out-dir "$RESULTS" \
  "human=${COVER_MP3%.mp3}.chords.json" \
  "original-wav=$M1/input/song.wav"
if [ "$analyzed" = 1 ]; then
  printf 'original-wav: chordotomy --engine model on input/song.wav, %d s wall, %s\n' \
    "$((SECONDS - start))" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$RESULTS/run.txt"
fi
