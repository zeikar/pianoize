#!/usr/bin/env bash
# Builds the M1 results from whatever has finished, so it can run again as models finish:
# 1. results/first-note.txt: each cover's first note onset next to the original's first chord
#    onset. Diagnostic only: a model may omit the opening, or start on time and drift later.
# 2. results/table.md: the human cover, the decoded original and each cover MIDI present
#    (pop2piano, tsumugi, etude), scored against the original's timeline. Rendered and analyzed
#    rows are reused, so a rerun only analyzes a new row.
# 3. results/melody-NAME.{txt,wav}: for each melody/NAME.mid, its chord clashes against the
#    original's timeline (Basic Pitch reduced to one voice) and a render for listening; an
#    existing render is reused.
# Reads the .chords.json next to SONG_MP3 and COVER_MP3. melody.md and not-run.md are written by hand.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/env.sh"

: "${SONG_MP3:?set SONG_MP3 to the original recording}"
: "${COVER_MP3:?set COVER_MP3 to the human piano cover}"

RESULTS="$M1/results"
ORIGINAL="${SONG_MP3%.mp3}.chords.json"
PY="$REPO/.venv/bin/python"

mkdir -p "$RESULTS"

covers=""
for name in pop2piano tsumugi etude; do
  if [ -s "$M1/covers/$name.mid" ]; then covers="$covers $name"; fi
done

{
  "$PY" -c 'import json, sys
first = next(s for s in json.load(open(sys.argv[1]))["segments"] if s["chord"] != "N")
print("original: first chord {chord} at {start_time:.3f} s (beats[{start_beat}])".format(**first))' "$ORIGINAL"
  for name in $covers; do
    "$PY" -c 'import mido, sys
now = 0.0
for message in mido.MidiFile(sys.argv[2]):
    now += message.time
    if message.type == "note_on" and message.velocity > 0:
        print("%s: first note at %.3f s" % (sys.argv[1], now))
        break' "$name" "$M1/covers/$name.mid"
  done
} > "$RESULTS/first-note.txt"
cat "$RESULTS/first-note.txt"

rows=("human=${COVER_MP3%.mp3}.chords.json" "original-wav=$M1/input/song.wav")
for name in $covers; do
  rows+=("$name=$M1/covers/$name.mid")
done
XDG_CACHE_HOME="$CHORDOTOMY_XDG_CACHE_HOME" "$PIANOIZE" evaluate \
  --original "$ORIGINAL" \
  --checkpoints "$M1/momonone.checkpoints.json" \
  --out-dir "$RESULTS" \
  "${rows[@]}"

for midi in "$M1"/melody/*.mid; do
  name="$(basename "$midi" .mid)"
  # Basic Pitch is polyphonic. GAME is monophonic by design, so it is scored as extracted.
  mono=""
  case "$name" in basic-pitch*) mono=--mono ;; esac
  "$PIANOIZE" melody-clashes ${mono:+"$mono"} "$midi" "$ORIGINAL" > "$RESULTS/melody-$name.txt"
  echo "melody-$name:"
  head -n 4 "$RESULTS/melody-$name.txt"
  [ -s "$RESULTS/melody-$name.wav" ] || "$PIANOIZE" render "$midi" -o "$RESULTS/melody-$name.wav"
done
