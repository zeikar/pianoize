# Design decisions

## The arrangement first, the video last

The goal is falling-notes videos of piano arrangements for a personal, non-monetized YouTube channel. What makes one worth watching is the arrangement, so the renderer comes last and is started only once the arrangements sound right as MIDI. The work runs in four steps:

1. **M0**: these rules and the package skeleton.
2. **M1**: run the existing audio-to-piano-cover models that run on a Mac, and the melody extractors, and score them together with a human piano cover.
3. **M2**: polishing the M1 model's arrangement: its harmony, slips, voice leading and timing.
4. **M3**: the renderer.

If a model in M1 keeps the harmony, pianoize wraps it. If it simplifies the harmony the way the human cover does, M2 is the reason pianoize exists. The user makes that call from the M1 table; there is no fixed threshold.

**Decision (2026-10-09): pianoize wraps tsumugi-piano-cover.** It scored the most checkpoints in M1 (11 of 20), and to the user's ear its render kept the harmony. Two of its misses are the analyzer reading Cm over E♭ as E♭ major, the same misreading the synthetic check found; the rest are a few passages (the bridge, the augmented passing chords, one passing chord, parts of two choruses). So M2 polishes tsumugi's cover instead of arranging from scratch: where it departs from the original's harmony, and where a note slips, a voice jumps or the timing stumbles. Etude scored 10 of 20 but sounded less clear, and its ShareAlike weights complicate the videos; Pop2Piano has no license. The numbers are in [M1 results](#m1-results-2026-10-09).

## Harmony from several sources; chordotomy stays as it is

[chordotomy](https://github.com/zeikar/chordotomy) already gives chords, the bass and inversions, beats, key regions and Roman numerals. It deliberately stops there: melody → MIDI is outside it, so pianoize doesn't add it there. pianoize reads the timeline JSON and checks its `schema_version` (11 for now). To analyze audio it runs the `chordotomy` CLI as a separately installed tool. chordotomy's model extra pins torch, lv-chordia and beat-this, and the pianoize models in M1 bring their own pins, so the two don't share an environment.

chordotomy's timeline is one reading, not the answer key. M1 showed it: scoring tsumugi's cover against it counted the analyzer's own misreadings as the model's mistakes. It read Cm over E♭ as E♭ major, an augmented chord as major, and a melody note on top of the piano as the chord. Reading the cover's notes found only two passages that really depart from the song. Web chord charts are transcribed by people and often get the harmony right, but they carry no timing and may be transposed or simplified; tsumugi's transcription brings its own chord, bass and melody tracks. So an LLM skill gathers these readings, weighs each disagreement against the others and against the notes, and writes one refined harmony timeline. That timeline, not chordotomy's, is what the cover's chords are checked against. Charts copied from websites stay in `work/`, like recordings.

M2 leaves web charts out (2026-10-10). U-FRET draws its chords with JavaScript, and its terms forbid use outside the service, analysis and heavy load; ChordWiki refuses automated requests. Charts can come back later as a chord sequence the user pastes.

## Downbeats from Beat This!, on chordotomy's beats

The timeline has beats but no downbeats. Beat This! (MIT) predicts both, so pianoize calls it directly. Each predicted downbeat is moved to the nearest beat in chordotomy's list, so chords, melody and bars all count the same beats instead of two grids that drift apart.

## Licenses

Nothing is monetized, so weights with non-commercial terms are usable. They are never committed. They are downloaded into `work/` on first use, with their terms shown. Each model's code and weight licenses are checked again before it is used, because these change. The date and the source are recorded here.

A weight license binds the use of the model, and the repository holds none of its code or weights, so the repository's own license is unaffected. Whether a model's output counts as material adapted from its weights is unsettled, so output of a non-commercial model is treated as non-commercial too: the video stays non-monetized and credits the model. That is why tsumugi-piano-cover (CC BY-NC 4.0), whose cover is the arrangement's base, is credited, while tsumugi's transcriber (MIT code and weights), used only as evidence for the harmony, carries no such terms.

The code license is undecided and the repository is private. It may later be published under MIT, so no GPL or AGPL code goes into the repository or its dependencies, Python or npm, vendored, imported or bundled. Neothesia and YourMT3+ are out for this reason. LGPL is allowed, as in chordotomy. A tool the user installs separately and pianoize runs as a subprocess, such as a MIDI synthesizer, is not part of what is published, so its license doesn't matter.

## What goes into a video

A video carries only the piano pianoize renders, never the original audio or vocals separated from it. Its description credits the song, the artist and the composer, and the arrangement model, tsumugi-piano-cover (anime-song, CC BY-NC 4.0), whose license asks for attribution. Songs under a creator's fan-work guidelines follow them. For モモノネ that is hololive's music guidelines: the credit is required, no Content ID registration, no commercial or corporate use. Before uploading, check that the song is not on the guidelines' exclusion list.

## Scoring whether the harmony survived

A piano result is rendered from MIDI to audio and analyzed with chordotomy. The result is then compared with the original's timeline at the same times. A checkpoint is a run of segments in the original timeline: a borrowed iv, a V7/vi, a chromatic bass line under the chorus, passing chords. The result's chords are looked up at the same time, within one beat either way.

A chord passes when its root, triad class and, for inverted originals, bass match; the full rule is in [docs/evaluation.md](evaluation.md#the-pass-rule). Sevenths and tensions are ignored, because chordotomy's sevenths come and go between repeats of the same passage. The bass has to match because in a passage like C/E – Cm/E♭ – G/D – A/C♯ – D the descending bass is the point.

A human cover is scored the same way. That checks the scoring itself: the cover's simplifications have to come out as failures.

M1 scored against chordotomy's timeline, so its numbers include the analyzer's misreadings (see [Harmony from several sources](#harmony-from-several-sources-chordotomy-stays-as-it-is)). From M2 on, results are compared with the refined harmony timeline.

The checkpoints for a particular song are made from its recording, so they stay in `work/`. The repository keeps only their format and synthetic examples.

## Playable arrangements

A falling-notes video reads as a piece someone could play. So arrangements are pitched at an intermediate-to-advanced player. tsumugi's cover is one piano part with no hands assigned; from M3, pianoize splits it into hands, and a check verifies a limit on notes per hand, a hand span (about a ninth) and no crossed hands. A correction must keep that check passing.

## An agent writes the correction spec, code applies it

tsumugi's cover is kept; M2 polishes it rather than generating a new one. Four kinds of problem are worth fixing: a chord that doesn't match the song, a note that sounds like a slip, a voice that jumps or a bass line that breaks off, and timing that stumbles. An LLM can't listen, so code reads the cover's notes and lists candidates of each kind with the notes around them. The LLM judges each candidate against the refined harmony and the music around it, and writes a correction spec for those worth fixing, with a reason for each one it keeps. Code applies the spec to a copy of the cover. The LLM is an agent session, such as Claude Code; it writes the spec as a file in `work/`.

The pianoize CLI never calls an LLM. That way there is no API key and no cost, and the spec can be read and edited by hand. The same cover and spec give byte-identical output. A CLI that calls an API could later write the same file format.

## The melody comes with the cover

tsumugi's cover already carries the melody, so no separate melody extractor feeds pianoize; GAME, Basic Pitch and torchcrepe were compared in M1 only for an arrangement built from scratch. tsumugi's transcription also writes a `melody` track, which can mark the cover's melody notes so a correction leaves them alone.

Corrections live in the spec, not in hand edits to the cover's MIDI: the cover stays untouched, and each change can be read and undone.

## M1 license check (2026-10-08)

Upstream programs run as separately installed subprocess tools, each in its own environment under `work/m1/`. Homebrew's FFmpeg (built `--enable-gpl`) is loaded only inside the processes of tsumugi and Etude, through torchcodec. That is accepted because those run as separately installed subprocess tools and nothing committed imports or links FFmpeg. Rows are added as each candidate is tried. PiCoGen2, Sheet Sage and sfizz were judged on 2026-10-08 from their documentation and were never downloaded. Every other row was checked on 2026-10-09, when its weights were downloaded or recorded (`TERMS.txt` and `SHA256SUMS` under `work/m1/models/`, `WEIGHTS.txt` under `work/m1/stems/`).

| candidate | code license | weight license | revision | SHA-256 | runs on this Mac? | runtime notes |
| --- | --- | --- | --- | --- | --- | --- |
| PiCoGen2 | MIT, [LICENSE](https://github.com/tanchihpin0517/PiCoGen/blob/v2/LICENSE) ([repo](https://github.com/tanchihpin0517/PiCoGen/tree/v2)) | CC BY-NC-SA 3.0 | not downloaded | not downloaded | no: excluded | documents Linux with a GPU of more than 16 GB |
| Sheet Sage | MIT, [repo](https://github.com/chrisdonahue/sheetsage) | transcription weights CC BY-NC-SA 3.0 | not downloaded | not downloaded | no: excluded | Linux/Docker path; Jukebox features need CUDA |
| sfizz | BSD-2, [repo](https://github.com/sfztools/sfizz) | none | 1.2.3 (last release) | not downloaded | no: rejected | archived March 2025; the macOS `sfizz_render` binary is x86-64 only |
| Demucs 4.1.0 (`htdemucs_ft`) | MIT, [repo](https://github.com/adefossez/demucs) | none stated: the [model card](https://huggingface.co/adefossez/HTDemucs-ft) carries no license statement | HF `adefossez/HTDemucs-ft` d74ac89c3a1e874fc78f152555cf4d8533f06cd4 | `04573f0d.safetensors` 68854b0d7c2b3274723b5761f6fd9f5aec5f1bcd3f0de7c1669546fdb7871b7c; `92cfc3b6.safetensors` a241863551f30d01c42bd7b97da40839922ead3acb0f1fcab25682f55b4eeb59; `d12395a8.safetensors` 5b01a97567ae9a3178a6236fb520251045c03eb8834bc8c24a4eec11d6c8fb56; `f7e0c4bc.safetensors` 2c85ab3c62dd6edd8e0b965e38b16fd1cdde357cc25de6b6bc9ce7c83f60925f; `htdemucs_ft.yaml` 69470b8c1bbd674437b51bc9fb491327a10ab0396b702c93389b9cf750016346 | yes: CPU, 396 s for a 251 s song | stems never leave `work/` and never enter a video; needs `--with numpy` (not declared by demucs 4.1.0); see `work/m1/stems/WEIGHTS.txt` |
| Basic Pitch 0.4.0 | Apache-2.0, [repo](https://github.com/spotify/basic-pitch) | Apache-2.0, bundled in the wheel | 0.4.0 (PyPI) | wheel file: not recorded (uv's cache keeps only the unpacked wheel); `icassp_2022/nmp.onnx` 2c3c1d144bfa61ad236e92e169c13535c880469a12a047d4e73451f2c059a0ec | yes: ONNX backend (`--model-serialization onnx`), CPU, 9 s for the 251 s vocals stem | Python 3.11 (3.12 is broken on macOS); needs `setuptools<81` (resampy imports `pkg_resources`); its env also holds soxr (LGPL-2.1-or-later), installed only, not imported by committed code; no GPL found |
| Pop2Piano (reference only) | none stated, [repo](https://github.com/sweetcocoa/pop2piano) (GitHub `license: null`); HF transformers port Apache-2.0 | none stated: the [model card](https://huggingface.co/sweetcocoa/pop2piano) has no license field | HF `sweetcocoa/pop2piano` 142e8ed35614bcf77a3515b979e48ed528342349 (refs/main) | `pytorch_model.bin` 4ebff90f182961d1dc7c8cf481289b5c926610fe89993b5b02f1a61fb29dfa45 | yes: CPU, transformers 5.19.0, 7 s for the 75 s clip, 14.5 s for the 251 s song (weights cached) | AGPL Essentia in its env (`essentia==2.1b6.dev1389`); runner kept in `work/` and never committed; never in a video |
| GAME v1.0.3 (`GAME-1.0-medium`) | MIT, [repo](https://github.com/openvpi/GAME) | CC BY-NC-SA 4.0, stated in the [v1.0.0 release notes](https://github.com/openvpi/GAME/releases/tag/v1.0.0) | code: tag v1.0.3, commit 475a8ee781fe8cca980b3b12fbe6c80c768a813a; weights: `GAME-1.0-medium.zip` (184,550,485 bytes) from release v1.0.0, since v1.0.3 ships ONNX only | `GAME-1.0-medium.zip` 8c5b3e531e2905b935e664e2f533921cd637243770fab5282413bdb5051ca60c (matches GitHub's asset digest) | yes: CPU, 138 s for the 251 s vocals stem, 190 s for the 251 s mix; MPS not usable: the vocals run ran out of MPS memory (`work/m1/melody/game.run.txt`), and an earlier MPS run that finished dropped whole sections | audio read by `librosa.load` through soundfile, no FFmpeg (librosa falls back to audioread only when soundfile fails, which did not happen); torch 2.8.0 (upstream's tested version) and lightning live only in its env; that env also holds soxr (LGPL-2.1-or-later), installed only, not imported by committed code; no GPL found; not deterministic: D3PM sampling draws from an unseeded `torch.rand_like` and `infer.py` has no seed option, so a second CPU run on the vocals gives a different CSV (366 lines differ; `game.run.txt`) |
| Etude | MIT, [LICENSE](https://github.com/Xiugapurin/Etude/blob/main/LICENSE) Part 1 ([repo](https://github.com/Xiugapurin/Etude)) | CC BY-NC-SA 4.0, [LICENSE](https://github.com/Xiugapurin/Etude/blob/main/LICENSE) Part 2; its Demucs separation uses `htdemucs_6s`, none stated: the [model card](https://huggingface.co/adefossez/HTDemucs-6s) carries no license statement | code: commit eb661ca1e280cb70bf15bf500b6e686772550e2d; checkpoints: `checkpoints.zip` (170,665,865 bytes) from release `latest`, a tag that can move; HF `adefossez/HTDemucs-6s` 3c5ee475be622df764938de97e4281a7b07ffa58 | `checkpoints.zip` 2788ca56e431b1636d60be27b574c8c85ce271c3a2c851330c2807e34a247f8a; `5c90dfd2.safetensors` d2a1745f0744721f6b8ca5bf469b67c651ea5ed1b52998cab033b2158609d411; `htdemucs_6s.yaml` 207405151270af8fd81c2373c25d27950916682ac91dca7884a11ce13dad6f58 (both in `work/m1/cache/huggingface/hub/models--adefossez--HTDemucs-6s/snapshots/3c5ee475…`) | yes: MPS (Etude runs its Demucs separation on CPU when there is no CUDA); 69 s for the 75 s clip, 246 s for the 251 s song (`work/m1/covers/etude/run.txt`); the first clip run, which also downloaded the Demucs weights, was slower and its time was not kept | Demucs separation backend (`experiments/m1/etude-config.yaml`) instead of Spleeter, which needs conda; upstream warns it gives less accurate beats; torch 2.14.1, torchaudio 2.11.0, torchcodec 0.17.0, transformers 5.19.0 (requirements.txt's torch 2.6.0 and transformers 4.51.3 pins not used); loads Homebrew's FFmpeg 9.0.1 (`--enable-gpl`) through torchcodec inside its own process, found through torchcodec's own rpath, no `DYLD_FALLBACK_LIBRARY_PATH`; its env also holds lameenc (LGPL-3.0-or-later) and soxr (LGPL-2.1-or-later), installed only, not imported by committed code; no GPL found; madmom's bundled models (CC BY-NC-SA 4.0) are not loaded, only its DBN trackers; not deterministic: two runs on the 75 s clip gave different note counts (the first run's MIDI was not kept), likely from the unseeded random shift Demucs' `apply_model` applies by default (not isolated) |
| tsumugi (transcriber for tsumugi-piano-cover) | MIT, [LICENSE](https://github.com/anime-song/tsumugi/blob/main/LICENSE) ([repo](https://github.com/anime-song/tsumugi)) | MIT, the license field of the HF model cards [anime-song/instrument_agnostic_amt](https://huggingface.co/anime-song/instrument_agnostic_amt) and [anime-song/stem-splitter](https://huggingface.co/anime-song/stem-splitter) | code: commit a700b8cde582cd95a3d20f460b3648f45734d06d; checkpoints: downloaded by tsumugi on first use from each HF repo's `main`, not pinned | `stem_splitter.pt` 46e65bdd7cc404580b63676cfbb15049dc31aa4cb69e7cb7f3ddd6d414cfd8d7; `best_model.pth` ef752daf323314b9c36d8f7a41089661734627d3437aefbee211e7d130c3c80d; `best_model_bass_v2.pth` 807eedb409c77a710357d57c9e47d17821c4518db3b09c78d8dabd205a2b604a; `best_model_drums_v1_5.pth` 65138ad1dd919f33fb0ce56e54c0c23c87deaad6511132d69137cf4901ee9319; `best_model_guitar_v1_5.pth` 59c8335517d1faf7d735fef29e061181d87b96385f2e9a08332791e2b64affd4; `best_model_other_v1_5.pth` e836d5b30a29ad2301726aedb9ae348db927fbb4813359cdfb2e304ba3084501; `best_model_vocal_harmony_v1_5.pth` 9f068d21313039810c82ede5f01e30bf8bc25fe2ba42f2cad16f57a2095b5e97; `best_instrument_refinement.pth` 75b2846c492fbb7e6e36336c4eb0fa6ac48a9ec8f6de1c6a85f1c57b8e9639b9; `best_velocity_model.pth` df8b0877c8b71cb5c3c224d69d386d67520417ecbc03728f02a2951abc4d2ae1; `best_beat_chord_key.pth` 7a7e138d65bc574dfaa76a8c9a80b59ce867ce9b7fbba0fb4959728a1bdad105 (`work/m1/upstream/tsumugi.SHA256SUMS`) | yes: MPS (tsumugi picks CUDA, else MPS, else CPU); 496 s for the 251 s song; 241 s for the 75 s clip, a run that also downloaded the checkpoints (`work/m1/covers/tsumugi/run.txt`) | runs through tsumugi-piano-cover's `cover_studio/tsumugi_worker.py` (stem separation, per-stem transcription, instrument refinement, velocity, beat/chord/key: the settings the cover model was trained on) with tsumugi's interpreter, from its clone; its `.venv` is upstream's `uv sync --locked --extra stem`: torch 2.13.0, torchaudio 2.11.0, torchcodec 0.16.0, stem-splitter 0.0.9; loads Homebrew's FFmpeg 9.0.1 (`--enable-gpl`) through torchcodec inside its own process; torchcodec 0.16 has no rpath to Homebrew's FFmpeg (0.17 has), so the worker alone runs with `DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib`; its env also holds soxr (LGPL-2.1-or-later), installed only, not imported by committed code; no GPL found; its lead-vocal track (`melody`) is kept as `work/m1/melody/tsumugi-vocal.mid` |
| tsumugi-piano-cover | MIT, [LICENSE](https://github.com/anime-song/tsumugi-piano-cover/blob/main/LICENSE) ([repo](https://github.com/anime-song/tsumugi-piano-cover)) | CC BY-NC 4.0, the license field of the [model card](https://huggingface.co/anime-song/tsumugi-piano-cover) and the README's License section | code: commit 4f5c4351c8d8ec31f35279343ec8349332160787; weights: HF `anime-song/tsumugi-piano-cover` 12c81996ec0c7c5cb77d9d8c0a2a25234a7620fe | `piano_cover/model.safetensors` c3644e84787bba8bd4a2aac94d764a2943cfaa71f5b7a3c03ba2f96f26bf7d56; `piano_cover/config.json` bce83e6561f814201f618b593c3321a150f0cddc1140d9241edce82eb4b7b525; `piano_ar/model.safetensors` bc3e615c2cc74073a002a5e010de34fb0ac7149ac66a9a6f036088acd10b95dc; `piano_ar/config.json` 41763c3c760497f78af27b817084a87f55622ac9fdb47e7c472cc0e494f942c6; `README.md` (the model card) e89909f6e983acec55b800518acab1b0a1169c0ac780991862bee365feb25a20 (`work/m1/models/tsumugi-piano-cover/SHA256SUMS`) | yes: CPU (the generator picks CUDA, else CPU); 26 s for the 75 s clip, 75 s for the 251 s song, both seed 0 (`work/m1/covers/tsumugi/run.txt`) | conditioned on tsumugi's transcription (row above); upstream's default generation settings; loads only `piano_cover/`, `piano_ar/` (the base model) comes with the repo download; torch 2.13.0 from PyPI, since requirements.txt's `torch==2.13.0+cu130` has no macOS wheel; its env holds only what `piano_cover.generate` imports (torch, numpy, symusic, safetensors, huggingface_hub), not requirements.txt's wandb, soundfile and pillow (training samples) or fastapi, uvicorn and python-multipart (Cover Studio); no GPL or LGPL found |

## MIDI is rendered with FluidSynth

[FluidSynth](https://github.com/FluidSynth/fluidsynth) (LGPL-2.1) renders MIDI to audio. pianoize runs its CLI as a subprocess. It is installed with Homebrew, the one approved global install; the formulas it adds are recorded so they can be removed later. The flags are fixed, `-R 0 -C 0 -g 0.5 -r 44100` (no reverb, no chorus, gain 0.5, 44.1 kHz), so the same MIDI renders the same way. The FluidSynth version is recorded with the results. Installed 2026-10-09: FluidSynth 2.6.1 (Homebrew `fluid-synth`).

The SoundFont is Salamander Grand Piano V3 (SF2; CC BY 3.0, Alexander Holm; [FreePats](https://freepats.zenvoid.org/Piano/acoustic-grand-piano.html)). It is used for evaluation and for video audio. Every video description carries the credit line: "Piano sound: Salamander Grand Piano V3 by Alexander Holm (CC BY 3.0), via FreePats." Upright Piano KW (CC0 1.0, same page) is the fallback if the sound disappoints. Downloaded 2026-10-09: `SalamanderGrandPiano-SF2-V3+20200602.tar.xz`, SHA-256 `15edb061d7ba60d58332f72dba8f8ce40988048cc703f935e6320f37d650e213`; the extracted `SalamanderGrandPiano-V3+20200602.sf2` is 1.27 GB.

## M1 results (2026-10-09)

The runs were on 2026-10-09, one day after the license check above. The song is one recording, scored on 20 checkpoints (68 segments) taken from it; how a row is scored is in [docs/evaluation.md](evaluation.md), including the beat-grid distance. The checkpoint times and chords stay in `work/m1/momonone.checkpoints.json`. Everything below is from `work/m1/results/table.md`, `melody.md`, `not-run.md` and `first-note.txt`, unless another file is named.

GAME, Etude and tsumugi's transcriber are not deterministic (GAME and Etude were seen to give different output on a second run), so their rows are one draw. tsumugi-piano-cover's generator is seeded (seed 0).

### Does the harmony survive

| row | checkpoints passed | segments passed | exact labels | beat-grid distance (s) |
| --- | --- | --- | --- | --- |
| human | 3/20 | 23/68 | 3/68 | 0.000 |
| original-wav | 20/20 | 68/68 | 68/68 | 0.000 |
| pop2piano (reference) | 6/20 | 40/68 | 30/68 | 0.000 |
| tsumugi | 11/20 | 55/68 | 45/68 | 0.023 |
| etude | 10/20 | 45/68 | 35/68 | 0.024 |

Checkpoints passed by kind, from the detail tables in `table.md` (a checkpoint passes when none of its segments fails):

| kind | n | human | original-wav | pop2piano | tsumugi | etude |
| --- | --- | --- | --- | --- | --- | --- |
| ascent | 3 | 3 | 3 | 3 | 3 | 3 |
| B7→Em | 4 | 0 | 4 | 2 | 4 | 4 |
| chorus descent | 6 | 0 | 6 | 0 | 2 | 0 |
| passing bIII | 2 | 0 | 2 | 0 | 1 | 2 |
| aug passing | 2 | 0 | 2 | 0 | 0 | 0 |
| borrowed iv | 2 | 0 | 2 | 1 | 1 | 0 |
| bridge | 1 | 0 | 1 | 0 | 0 | 1 |

- **Human cover.** It passes 3 of 20, all of them the ascent. Its simplifications come out as failures, as the scoring is meant to show.
- **original-wav.** The original recording decoded to WAV and analyzed again scores 20/20. That shows only that decoding changes nothing. It does not test the analyzer.
- **Synthetic check.** The render, analysis and scoring path was first run on a synthetic progression (`work/m1/validate/table.md`): 3/4 checkpoints, 14/15 segments. The one miss is the analyzer reading a minor chord over its own E♭ bass as E♭ major (`work/m1/validate/notes.md`). The same reading is excluded at one place in the song's checkpoints.
- **Chorus descents.** In Etude's six chorus descents, three have found labels that hold the descending-bass chords one segment later than the original. tsumugi's chorus descents keep that bass at the right segment in three of six, but the triad class differs from the original's (major where it is minor), a miss in class rather than a shift. Whether these are real displacements or a different reading of the same music is for the ear to settle.
- **Pop2Piano.** Reference only. Its weights have no stated license and its environment holds AGPL code; it is never in a video.

### First-note diagnostic

`first-note.txt` holds the time of the first note of each result against the original's first chord (1.416 s, `beats[2]`): pop2piano 0.871 s, tsumugi 1.060 s, Etude 1.089 s. All three start earlier than the first chord. Pop2Piano trims at its first Essentia beat. Whether any result is displaced in time is to be settled by ear.

### Models that did not run

Only torchcrepe, the fallback melody extractor. It was not needed because Basic Pitch on the vocals stem produced notes (`work/m1/melody/torchcrepe.run.txt`, checked 2026-10-09). GAME did not run on MPS (out of memory, `game.run.txt`) and ran on CPU.

### Melody candidates

Each melody is scored with `pianoize melody-clashes` against the original's timeline.

| candidate | notes scored | clash ratio by notes | clash ratio by duration | runtime | device |
| --- | --- | --- | --- | --- | --- |
| game-vocals | 381 | 41.5% | 30.8% | 138 s | CPU |
| game-mix | 594 | 37.9% | 34.6% | 190 s | CPU |
| basic-pitch-vocals (`--mono`) | 638 | 31.3% | 31.9% | 9 s | CPU, ONNX |
| tsumugi-vocal (`--mono`) | 366 | 43.4% | 30.6% | by-product of the tsumugi cover (worker 496 s) | MPS |

The vocals rows also need the Demucs separation (CPU, 396 s). `work/m1/results/melody.md` lists the inputs, the per-candidate notes and the coverage caveats. game-vocals has no notes in three stretches where Basic Pitch does; whether GAME dropped sung passages is to be checked by ear with `melody-game-vocals.wav`.

### Listening

The user listened to the renders in `work/m1/results/` on 2026-10-09. tsumugi's sounded good, its harmony included; Etude's and Pop2Piano's were less clear. The decision that followed is under [The arrangement first, the video last](#the-arrangement-first-the-video-last).
