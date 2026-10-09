#!/usr/bin/env bash
# Lists what changed outside work/m1 since 00_fluidsynth.sh wrote $M1/.stamp, so anything an
# M1 run wrote to the user's own caches shows up. Expected entries: Homebrew's cache from the
# approved FluidSynth install, uv's cache from the project's own `uv sync`/`uv run`, and
# chordotomy's cache being read. Anything else needs an explanation in leak-check.txt.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/env.sh"

out="$M1/leak-check.txt"
# A nested file changing does not touch its distant ancestors' mtimes, so the tool caches are
# searched in full. ~/Library/Caches holds many unrelated apps, so only its top level is listed.
changed() { # dir [maxdepth]
  [ -d "$1" ] || return 0
  find "$1" ${2:+-maxdepth "$2"} -newer "$M1/.stamp" | sort
}
# macOS daemons and other apps rewrite their own caches all the time; they say nothing about
# M1, so they are left out. grep exits 1 on no match, which is fine; 2 is a real error.
quiet() { grep -Ev '/Library/Caches/(com\.apple\.|com\.google\.|CloudKit|GameKit|GeoServices)' || [ $? -eq 1 ]; }
{
  echo "since $(cat "$M1/.stamp")"
  for root in "$HOME/.cache" "$HOME/Library/Caches/pip" "$HOME/Library/Caches/Homebrew" \
    "$HOME/.local/share/uv" "$HOME/.local/bin"; do
    changed "$root" | quiet
  done
  changed "$HOME/Library/Caches" 1 | quiet
} > "$out"
cat "$out"
