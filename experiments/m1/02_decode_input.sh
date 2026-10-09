#!/usr/bin/env bash
# Decodes SONG_MP3 into input/song.wav (44.1 kHz stereo 16-bit) and its first 75 s into
# input/song_75s.wav. The excerpt covers an ascent, a passing bIII, a B7 -> Em and the
# first chorus descent. Needs only SONG_MP3. ffmpeg is GPL; it runs as a subprocess only.
# An existing output is kept. decode.txt is rewritten from ffprobe on every run, so it
# never holds duplicate lines.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/env.sh"

: "${SONG_MP3:?set SONG_MP3 to the original recording}"
[ -f "$SONG_MP3" ] || { echo "SONG_MP3 not found: $SONG_MP3" >&2; exit 1; }

IN="$M1/input"
mkdir -p "$IN"

# decode DEST [extra ffmpeg input-limiting args...]: write to a temp name, rename on success.
decode() {
  local dest="$1"; shift
  [ -s "$dest" ] && return 0
  local part="$dest.part.wav"
  rm -f "$part"
  if ffmpeg -nostdin -hide_banner -loglevel error -n -i "$SONG_MP3" "$@" \
      -ar 44100 -ac 2 -c:a pcm_s16le "$part"; then
    mv "$part" "$dest"
  else
    rm -f "$part"
    return 1
  fi
}

decode "$IN/song.wav"
decode "$IN/song_75s.wav" -t 75

for f in song.wav song_75s.wav; do
  printf '%s %s s\n' "$f" "$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$IN/$f")"
done > "$IN/decode.txt"
cat "$IN/decode.txt"
