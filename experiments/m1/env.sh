# Sourced by every M1 script, never by an interactive shell.
# Never exits: it sets variables, creates $M1/cache/tmp and defines fetch, so it is
# safe under `set -euo pipefail`.
# Points every cache and temp dir under work/m1 so it can be removed in one step.
# 11_leak_check.sh is what verifies that nothing escaped.

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
M1="$REPO/work/m1"
export REPO M1

# chordotomy's Beat This! weights live in the user's real cache. Scripts that run chordotomy
# (`pianoize evaluate` with .wav or .mid rows) prefix the call with
# XDG_CACHE_HOME="$CHORDOTOMY_XDG_CACHE_HOME" so they are not downloaded again.
export CHORDOTOMY_XDG_CACHE_HOME="${XDG_CACHE_HOME:-$HOME/.cache}"

mkdir -p "$M1/cache/tmp"

export UV_CACHE_DIR="$M1/cache/uv"
export UV_PYTHON_INSTALL_DIR="$M1/cache/uv-python"
export UV_PYTHON_CACHE_DIR="$M1/cache/uv-python-cache"
export UV_PYTHON_INSTALL_BIN=0
export UV_MANAGED_PYTHON=1
export UV_TOOL_DIR="$M1/cache/uv-tools"
export UV_TOOL_BIN_DIR="$M1/cache/uv-tools-bin"
export PIP_CACHE_DIR="$M1/cache/pip"
export HF_HOME="$M1/cache/huggingface"
export HF_HUB_DISABLE_TELEMETRY=1
export DO_NOT_TRACK=1
export TORCH_HOME="$M1/cache/torch"
export STEM_SPLITTER_CACHE="$M1/cache/stem-splitter"
export XDG_CACHE_HOME="$M1/cache/xdg"
export NUMBA_CACHE_DIR="$M1/cache/numba"
export MPLCONFIGDIR="$M1/cache/matplotlib"
export TMPDIR="$M1/cache/tmp"

export PIANOIZE_SOUNDFONT="$M1/soundfonts/salamander.sf2"
_chordotomy="$REPO/../chordotomy/.venv/bin/chordotomy"
if [ -z "${PIANOIZE_CHORDOTOMY:-}" ] && [ -x "$_chordotomy" ]; then
  export PIANOIZE_CHORDOTOMY="$_chordotomy"
fi
unset _chordotomy
export PIANOIZE="$REPO/.venv/bin/pianoize"

# fetch URL DEST: download to DEST.part, rename on success.
# A completed DEST is reused. A .part is never reused: a failed download deletes it,
# and one left by a killed run is overwritten, so the next run starts over.
fetch() {
  local url="$1" dest="$2"
  [ -s "$dest" ] && return 0
  mkdir -p "$(dirname "$dest")"
  if curl -fL -o "$dest.part" "$url"; then
    mv "$dest.part" "$dest"
  else
    rm -f "$dest.part"
    return 1
  fi
}
