#!/usr/bin/env bash
# Lists what changed outside work/m1 since 00_fluidsynth.sh wrote $M1/.stamp, so anything an
# M1 run wrote to the user's own caches shows up. Expected entries: Homebrew's cache from the
# approved FluidSynth install, uv's cache from the project's own `uv sync`/`uv run`, and
# chordotomy's cache being read. Anything else needs an explanation in leak-check.txt.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/env.sh"

out="$M1/leak-check.txt"
{
  echo "since $(cat "$M1/.stamp")"
  for root in "$HOME/.cache" "$HOME/Library/Caches" "$HOME/.local/share/uv" "$HOME/.local/bin"; do
    [ -d "$root" ] || continue
    # macOS daemons and other apps rewrite their own caches all the time; they say nothing
    # about M1, so they are left out.
    find "$root" -maxdepth 2 -newer "$M1/.stamp" 2>/dev/null \
      | grep -Ev '/Library/Caches/(com\.apple\.|com\.google\.|CloudKit|GameKit|GeoServices)' \
      | sort || true
  done
} > "$out"
cat "$out"
