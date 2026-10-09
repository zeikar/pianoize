#!/usr/bin/env bash
# Splits the input into vocals / no_vocals with Demucs 4.1.0 (htdemucs_ft, CPU) and records
# the downloaded weights. Skips the run when both stems exist; a failed run removes its
# partial output so a rerun starts clean. env.sh keeps its caches under work/m1;
# 11_leak_check.sh checks that nothing was written elsewhere.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/env.sh"

OUT="$M1/stems/htdemucs_ft/song"

if [ ! -s "$OUT/vocals.wav" ] || [ ! -s "$OUT/no_vocals.wav" ]; then
  rm -rf "$OUT"
  mkdir -p "$M1/stems"
  start=$(date +%s)
  # demucs 4.1.0 imports numpy without declaring it, so it is added here.
  if ! uvx --python 3.12 --from "demucs==4.1.0" --with numpy demucs --two-stems=vocals -n htdemucs_ft -d cpu \
      -o "$M1/stems" "$M1/input/song.wav"; then
    echo "demucs failed; removing partial output" >&2
    rm -rf "$OUT"
    exit 1
  fi
  echo "demucs htdemucs_ft wall time: $(( $(date +%s) - start )) s" | tee "$M1/stems/run.txt"
fi

# Weights: whatever Demucs fetched into the HF or torch caches under work/m1.
mkdir -p "$M1/cache/huggingface" "$M1/cache/torch"
{
  echo "Weight files recorded $(date -u +%Y-%m-%d)"
  find "$M1/cache/huggingface" "$M1/cache/torch" \( -type f -o -type l \) \( -name "*.th" -o -name "*.pt" -o -name "*.safetensors" -o -name "*.yaml" -o -name "*.bin" \)| sort |
    while read -r f; do
      echo "$(du -L -k "$f" | cut -f1) KiB  $(shasum -a 256 "$f" | cut -d" " -f1)  ${f#"$M1/"}"
    done
  for r in "$M1"/cache/huggingface/hub/models--*/refs/main; do
    [ -f "$r" ] && echo "revision ${r#"$M1/"}: $(cat "$r")"
  done
} > "$M1/stems/WEIGHTS.txt"
cat "$M1/stems/WEIGHTS.txt"

printf "%s\n" "Demucs htdemucs_ft weights (HF adefossez/HTDemucs-ft)" \
  "License of the weights: none stated. The model card carries no license statement." \
  "Card: https://huggingface.co/adefossez/HTDemucs-ft" \
  "Checked: 2026-10-09" \
  "Code: MIT, https://github.com/adefossez/demucs" \
  "Use: stems stay under work/ and never enter a video." > "$M1/stems/TERMS.txt"
