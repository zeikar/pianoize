#!/usr/bin/env bash
# Installs FluidSynth with Homebrew, the one approved global install, and records which
# formulas it added so they can be removed later.
# brew-before.txt and .stamp are written once, so the baseline survives reruns.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/env.sh"

mkdir -p "$M1"
# Written through a temp file: a failed `brew list` must not leave an empty baseline that every
# later run would then keep.
if [ ! -e "$M1/brew-before.txt" ]; then
  brew list --formula | sort > "$M1/brew-before.txt.tmp"
  mv "$M1/brew-before.txt.tmp" "$M1/brew-before.txt"
fi
[ -e "$M1/.stamp" ] || date -u +%Y-%m-%dT%H:%M:%SZ > "$M1/.stamp"

# Auto-update and cleanup are off to keep the install narrow. brew may still upgrade a formula
# that was already installed when it is a dependency; that upgrade is not in the removal list.
status=0
HOMEBREW_NO_AUTO_UPDATE=1 HOMEBREW_NO_INSTALL_CLEANUP=1 brew install fluid-synth || status=$?

brew list --formula | sort > "$M1/brew-after.txt"
comm -13 "$M1/brew-before.txt" "$M1/brew-after.txt" > "$M1/brew-new-formulas.txt"

if [ "$status" -ne 0 ]; then
  echo "brew install fluid-synth failed with status $status" >&2
  exit "$status"
fi

line="$(fluidsynth --version | sed -n 1p)"
touch "$M1/tools.txt"
grep -qxF "$line" "$M1/tools.txt" || echo "$line" >> "$M1/tools.txt"
