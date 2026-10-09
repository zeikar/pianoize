#!/usr/bin/env bash
# Downloads the Salamander Grand Piano V3 SoundFont, records its terms and SHA-256, and
# links the extracted .sf2 as $PIANOIZE_SOUNDFONT.
# The archive is deleted once extracted; SHA256SUMS keeps pinning it. A rerun with the
# link and SHA256SUMS in place does nothing.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/env.sh"

URL='https://freepats.zenvoid.org/Piano/SalamanderGrandPiano/SalamanderGrandPiano-SF2-V3+20200602.tar.xz'
DIR="$M1/soundfonts"
ARCHIVE="$DIR/$(basename "$URL")"
LINK="$DIR/salamander.sf2"

if [ -f "$LINK" ] && [ -s "$DIR/SHA256SUMS" ]; then
  echo "already installed: $(readlink "$LINK")"
  exit 0
fi

mkdir -p "$DIR"
fetch "$URL" "$ARCHIVE"

terms="Salamander Grand Piano V3 (SF2)
License: CC BY 3.0 (https://creativecommons.org/licenses/by/3.0/)
Author: Alexander Holm
Source page: https://freepats.zenvoid.org/Piano/acoustic-grand-piano.html
Downloaded from: $URL
Downloaded on: $(date -u +%Y-%m-%d)
Required credit: Piano sound: Salamander Grand Piano V3 by Alexander Holm (CC BY 3.0), via FreePats."
printf '%s\n' "$terms" | tee "$DIR/TERMS.txt"

(cd "$DIR" && shasum -a 256 "$(basename "$ARCHIVE")") > "$DIR/SHA256SUMS"
cat "$DIR/SHA256SUMS"

rm -rf "$DIR/salamander"
mkdir "$DIR/salamander"
if ! tar -xJf "$ARCHIVE" -C "$DIR/salamander"; then
  echo "extraction failed; deleting the archive" >&2
  rm -rf "$ARCHIVE" "$DIR/salamander"
  exit 1
fi
rm -f "$ARCHIVE"

sf2="$(find "$DIR/salamander" -name '*.sf2' | head -n 1)"
[ -n "$sf2" ] || { echo "no .sf2 in the archive" >&2; exit 1; }
ln -sfn "$sf2" "$LINK"
echo "linked $LINK -> $sf2"
