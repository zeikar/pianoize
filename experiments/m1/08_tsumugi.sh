#!/usr/bin/env bash
# Generates piano covers with tsumugi-piano-cover (code MIT; weights CC BY-NC 4.0) from a
# multi-track transcription by tsumugi (code and weights MIT): the 75 s clip (covers/tsumugi/smoke)
# and the full song (covers/tsumugi.mid), both with seed 0. The full song's vocals track, if
# tsumugi finds one, is saved with the tempo map as melody/tsumugi-vocal.mid.
# covers/tsumugi/run.txt gets each step's device and wall time; covers/tsumugi.status.md says
# whether it ran.
# Each program runs from its own clone with its own interpreter; nothing here imports them.
# tsumugi runs through tsumugi-piano-cover's cover_studio/tsumugi_worker.py (the transcription
# settings the cover model was trained on) with tsumugi's .venv. stem_splitter reads the audio
# and writes the stems through torchcodec, which loads Homebrew's FFmpeg (--enable-gpl) inside
# that process.
# Reused on a rerun: the clones, the envs, the weights and existing outputs. A step that failed
# or hit the 2-hour limit runs again.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/env.sh"

AMT="$M1/upstream/tsumugi"
AMT_PY="$AMT/.venv/bin/python"
SRC="$M1/upstream/tsumugi-piano-cover"
ENV="$M1/envs/tsumugi-cover"
PY="$ENV/bin/python"
HF_REPO=anime-song/tsumugi-piano-cover
MODELS="$M1/models/tsumugi-piano-cover"
COVERS="$M1/covers"
LOGS="$COVERS/tsumugi"
RUN_TXT="$LOGS/run.txt"
STATUS="$COVERS/tsumugi.status.md"
VOCAL="$M1/melody/tsumugi-vocal.mid"
LIMIT=7200

mkdir -p "$LOGS" "$M1/melody"

# clone URL DIR: clones into DIR.part, renamed once complete; writes the commit to DIR.commit.
clone() {
  local url="$1" dir="$2"
  if [ ! -d "$dir" ]; then
    mkdir -p "$(dirname "$dir")"
    rm -rf "$dir.part"
    git clone --quiet "$url" "$dir.part"
    mv "$dir.part" "$dir"
  fi
  git -C "$dir" rev-parse HEAD > "$dir.commit"
}

clone https://github.com/anime-song/tsumugi "$AMT"
clone https://github.com/anime-song/tsumugi-piano-cover "$SRC"

# Transcriber: upstream's own install, its .venv inside the clone. On macOS the lock takes torch
# 2.13.0 and torchaudio 2.11.0 from PyPI (its cu130 index is for Linux and Windows).
(cd "$AMT" && uv sync --locked --extra stem)
uv pip freeze --python "$AMT_PY" > "$LOGS/tsumugi.freeze.txt"

# Generator: requirements.txt pins torch==2.13.0+cu130, which has no macOS wheel. Only what
# piano_cover.generate imports is installed: wandb, soundfile and pillow serve training samples,
# fastapi, uvicorn and python-multipart serve Cover Studio. huggingface_hub provides the hf CLI.
[ -x "$PY" ] || uv venv --python 3.12 "$ENV"
uv pip install --python "$PY" torch==2.13.0 numpy symusic safetensors huggingface_hub
uv pip freeze --python "$PY" > "$LOGS/freeze.txt"

# Weights. hf download resumes an interrupted download; SHA256SUMS is written last and marks
# completion.
if [ ! -s "$MODELS/SHA256SUMS" ]; then
  terms="tsumugi-piano-cover weights (piano_cover, piano_ar) by anime-song
License: CC BY-NC 4.0 (https://creativecommons.org/licenses/by-nc/4.0/)
Stated in: https://huggingface.co/$HF_REPO (model card) and https://github.com/anime-song/tsumugi-piano-cover#license
Terms: attribution, non-commercial use only.
Code: MIT, https://github.com/anime-song/tsumugi-piano-cover"
  printf '%s\n' "$terms"
  "$ENV/bin/hf" download "$HF_REPO" --local-dir "$MODELS"
  # The first line of hf's download metadata is the commit it resolved.
  rev="$(head -n 1 "$MODELS/.cache/huggingface/download/piano_cover/model.safetensors.metadata")"
  printf '%s\n' "$terms" "Downloaded from: https://huggingface.co/$HF_REPO, revision $rev" \
    "Downloaded on: $(date -u +%Y-%m-%d)" > "$MODELS/TERMS.txt"
  (cd "$MODELS" && shasum -a 256 README.md piano_ar/* piano_cover/*) > "$MODELS/SHA256SUMS.part"
  mv "$MODELS/SHA256SUMS.part" "$MODELS/SHA256SUMS"
  cat "$MODELS/SHA256SUMS"
fi

# piano_cover.generate picks CUDA, else CPU.
GEN_DEVICE="$("$PY" -I -c 'import torch; print("cuda" if torch.cuda.is_available() else "cpu")')"

# record KEY TEXT: sets KEY's line in run.txt, replacing an earlier one.
record() {
  local tmp="$TMPDIR/tsumugi.run.txt.part"
  { grep -v "^$1: " "$RUN_TXT" 2>/dev/null || true; echo "$1: $2"; } > "$tmp"
  mv "$tmp" "$RUN_TXT"
}

# reason LOG: the last Python exception line, else the last non-blank line. Progress bars
# redraw with carriage returns.
reason() {
  tr '\r' '\n' < "$1" | awk 'NF { last = $0 } /^[[:alnum:]_.]+(Error|Exception)/ { err = $0 }
    END { print substr(err != "" ? err : last, 1, 200) }'
}

# timed LOG DIR CMD...: runs CMD in DIR, its output in LOG without the worker's streamed notes,
# killed after $LIMIT s (exit 142). Sets secs to the wall time and returns CMD's status.
timed() {
  local log="$1" dir="$2" start status=0
  shift 2
  start=$(date +%s)
  (cd "$dir" && PYTHONUNBUFFERED=1 exec perl -e 'alarm shift; exec @ARGV or die "exec: $!\n"' "$LIMIT" "$@") 2>&1 \
    | grep -v '^@@notes ' > "$log" || status=$?
  secs=$(( $(date +%s) - start ))
  return "$status"
}

# failed KEY LOG STATUS: records in run.txt why KEY's step stopped.
failed() {
  if [ "$3" -eq 142 ]; then
    record "$1" "did not complete in $(( secs / 60 )) min: killed at the $LIMIT s limit"
  else
    record "$1" "failed: exit $3 after $secs s: $(reason "$2")"
  fi
}

# transcriber_sums: SHA-256 of the transcriber's checkpoints, which tsumugi downloads on first
# use into its clone and $STEM_SPLITTER_CACHE (HF anime-song/instrument_agnostic_amt and
# anime-song/stem-splitter, both MIT).
transcriber_sums() {
  local dirs=() d
  for d in upstream/tsumugi/checkpoints upstream/tsumugi/beat_chord_checkpoints cache/stem-splitter; do
    if [ -d "$M1/$d" ]; then dirs+=("$d"); fi
  done
  (cd "$M1" && find "${dirs[@]}" -type f | sort | xargs shasum -a 256) > "$AMT.SHA256SUMS.part"
  mv "$AMT.SHA256SUMS.part" "$AMT.SHA256SUMS"
}

# transcribe KEY AUDIO OUT: tsumugi through the worker, run the way Cover Studio runs it: tsumugi's
# interpreter, from the tsumugi clone (the worker imports only tsumugi's packages), stems in a
# scratch dir the worker deletes. tsumugi picks CUDA, else MPS, else CPU.
# tsumugi's locked torchcodec 0.16 has no rpath to Homebrew's FFmpeg (0.17 has), so this process
# alone gets DYLD_FALLBACK_LIBRARY_PATH. It is set by env, after perl: macOS strips DYLD_*
# variables when it starts a protected binary such as /usr/bin/perl.
transcribe() {
  local key="$1" audio="$2" out="$3" log="$LOGS/$1.log" status=0 devices note=""
  timed "$log" "$AMT" env DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib \
    "$AMT_PY" -X utf8 "$SRC/cover_studio/tsumugi_worker.py" --tsumugi-dir "$AMT" \
    --audio "$audio" --out "$out" --work "$TMPDIR/tsumugi-work" || status=$?
  if [ "$status" -ne 0 ]; then
    failed "$key" "$log" "$status"
    return "$status"
  fi
  devices="$(grep -oE '^Loading .* on [a-z]+' "$log" | awk '{ print $NF }' | sort -u | paste -sd / -)"
  if grep -qi 'download' "$log"; then note=", including checkpoint downloads"; fi
  record "$key" "${devices:-device not logged}, $secs s$note"
  # The worker only warns when velocity or beat/chord estimation failed, which leaves the source
  # unlike the transcriptions the cover model was trained on.
  if grep -q '^警告' "$log"; then record "$key warning" "$(grep -m 1 '^警告' "$log")"; fi
  transcriber_sums
}

# generate KEY SOURCE OUTDIR [SECONDS]: piano_cover.generate with seed 0 into OUTDIR.part, renamed
# to OUTDIR on success. Runs from the generator clone, whose root holds piano_cover and piano_ar.
generate() {
  local key="$1" source="$2" out="$3" seconds="${4:-}" log="$LOGS/$1.log" status=0
  rm -rf "$out.part"
  timed "$log" "$SRC" "$PY" -m piano_cover.generate --checkpoint "$MODELS" --source "$source" \
    ${seconds:+--seconds "$seconds"} --seed 0 --out-dir "$out.part" || status=$?
  if [ "$status" -ne 0 ]; then
    failed "$key" "$log" "$status"
    return "$status"
  fi
  record "$key" "$GEN_DEVICE, $secs s"
  rm -rf "$out"
  mv "$out.part" "$out"
}

# vocals: tsumugi names the vocal stem's lead line "melody" (vocal_harmony and choir are the other
# voices). That track and track 0's tempo and time signatures go to melody/tsumugi-vocal.mid,
# through the project venv's mido. run.txt lists every track of source.mid with its note count.
vocals() {
  local tracks
  tracks="$("$REPO/.venv/bin/python" -I -c 'import sys, mido
src = mido.MidiFile(sys.argv[1])
def name(track):
    return next((m.name for m in track if m.type == "track_name"), "")
print(", ".join("%s %d" % (name(t) or "(unnamed)", sum(m.type == "note_on" and m.velocity > 0 for m in t))
                for t in src.tracks))
lead = [t for t in src.tracks if name(t) == "melody"]
if lead:
    tempo, now, last = mido.MidiTrack(), 0, 0
    for m in src.tracks[0]:
        now += m.time
        if m.type in ("set_tempo", "time_signature"):
            tempo.append(m.copy(time=now - last))
            last = now
    out = mido.MidiFile(type=1, ticks_per_beat=src.ticks_per_beat)
    out.tracks += [tempo, lead[0]]
    out.save(sys.argv[2])' "$LOGS/source.mid" "$VOCAL.part")"
  record source-tracks "$tracks"
  if [ -s "$VOCAL.part" ]; then
    mv "$VOCAL.part" "$VOCAL"
  else
    record vocals "no track named melody in source.mid"
  fi
}

# did_not_run KEY: KEY's smoke step failed, so the model does not run here.
did_not_run() {
  echo "did not run: $(grep "^$1: " "$RUN_TXT")" > "$STATUS"
  cat "$STATUS" >&2
  exit 1
}

# smoke_only KEY: the full song stopped at KEY; the 75 s cover is kept as covers/tsumugi-75s.mid.
smoke_only() {
  cp "$LOGS/smoke/source-75s_ch0_0.mid" "$COVERS/tsumugi-75s.mid.part"
  mv "$COVERS/tsumugi-75s.mid.part" "$COVERS/tsumugi-75s.mid"
  echo "ran on the 75 s clip only (covers/tsumugi-75s.mid); full song $(grep "^$1: " "$RUN_TXT")" > "$STATUS"
  cat "$STATUS" >&2
  exit 1
}

if [ ! -s "$LOGS/source-75s.mid" ]; then
  transcribe worker-75s "$M1/input/song_75s.wav" "$LOGS/source-75s.mid" || did_not_run worker-75s
fi
if [ ! -d "$LOGS/smoke" ]; then
  generate generate-75s "$LOGS/source-75s.mid" "$LOGS/smoke" 75 || did_not_run generate-75s
fi

if [ ! -s "$LOGS/source.mid" ]; then
  transcribe worker-full "$M1/input/song.wav" "$LOGS/source.mid" || smoke_only worker-full
fi
[ -s "$VOCAL" ] || vocals
if [ ! -s "$COVERS/tsumugi.mid" ]; then
  [ -d "$LOGS/full" ] || generate generate-full "$LOGS/source.mid" "$LOGS/full" || smoke_only generate-full
  cp "$LOGS/full/source_ch0_0.mid" "$COVERS/tsumugi.mid.part"
  mv "$COVERS/tsumugi.mid.part" "$COVERS/tsumugi.mid"
fi

printf '%s\n' "ran: tsumugi commit $(cat "$AMT.commit"), tsumugi-piano-cover commit $(cat "$SRC.commit"), weights $(sed -n 's/^Downloaded from: //p' "$MODELS/TERMS.txt")" \
  "covers: tsumugi/smoke (75 s clip), tsumugi.mid (full song), both seed 0; devices and wall times in covers/tsumugi/run.txt" > "$STATUS"
cat "$RUN_TXT"
