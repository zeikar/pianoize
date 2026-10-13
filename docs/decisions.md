# Design decisions

## The arrangement first, the video last

The goal is falling-notes videos of piano arrangements for a personal, non-monetized YouTube channel. What makes one worth watching is the arrangement, so the renderer comes last and is started only once the arrangements sound right as MIDI. The work runs in five steps:

1. **M0**: these rules and the package skeleton.
2. **M1**: run the existing audio-to-piano-cover models that run on a Mac, and the melody extractors, and score them together with a human piano cover.
3. **M2**: polishing the M1 model's arrangement: its harmony, slips, voice leading and timing. Built ([M2 decisions](#m2-decisions-2026-10-10)), but since 2026-10-11 no longer the main path.
4. **M3**: the arrangement, written by an agent as a two-hand score from the cover and the melody, and built and checked by pianoize. Added 2026-10-11; until then M3 was the renderer. Built, and its first full-song arrangement approved on 2026-10-12 ([M3](#m3-an-agent-writes-the-arrangement-2026-10-11)).
5. **M4**: the renderer. Built 2026-10-12, and its first full-song video approved on 2026-10-13 ([M4](#m4-the-falling-notes-renderer-2026-10-12)).

If a model in M1 keeps the harmony, pianoize wraps it. If it simplifies the harmony the way the human cover does, M2 is the reason pianoize exists. The user makes that call from the M1 table; there is no fixed threshold.

**Decision (2026-10-09): pianoize wraps tsumugi-piano-cover.** It scored the most checkpoints in M1 (11 of 20), and to the user's ear its render kept the harmony. Two of its misses are the analyzer reading Cm over E♭ as E♭ major, the same misreading the synthetic check found; the rest are a few passages (the bridge, the augmented passing chords, one passing chord, parts of two choruses). So M2 polishes tsumugi's cover instead of arranging from scratch: where it departs from the original's harmony, and where a note slips, a voice jumps or the timing stumbles. Etude scored 10 of 20 but sounded less clear, and its ShareAlike weights complicate the videos; Pop2Piano has no license. The numbers are in [M1 results](#m1-results-2026-10-09).

Superseded in part on 2026-10-11: tsumugi's cover is still what the arrangement starts from, but an agent now writes the arrangement from the cover and the melody instead of polishing the cover note by note ([M3](#m3-an-agent-writes-the-arrangement-2026-10-11)).

## Harmony from several sources; chordotomy stays as it is

[chordotomy](https://github.com/zeikar/chordotomy) already gives chords, the bass and inversions, beats, key regions and Roman numerals. It deliberately stops there: melody → MIDI is outside it, so pianoize doesn't add it there. pianoize reads the timeline JSON and checks its `schema_version` (11 for now). To analyze audio it runs the `chordotomy` CLI as a separately installed tool. chordotomy's model extra pins torch, lv-chordia and beat-this, and the pianoize models in M1 bring their own pins, so the two don't share an environment.

chordotomy's timeline is one reading, not the answer key. M1 showed it: scoring tsumugi's cover against it counted the analyzer's own misreadings as the model's mistakes. It read Cm over E♭ as E♭ major, an augmented chord as major, and a melody note on top of the piano as the chord. Reading the cover's notes found only two passages that really depart from the song. Web chord charts are transcribed by people and often get the harmony right, but they carry no timing and may be transposed or simplified; tsumugi's transcription brings its own chord, bass and melody tracks. So an LLM skill gathers these readings, weighs each disagreement against the others and against the notes, and writes one refined harmony timeline. That timeline, not chordotomy's, is what the cover's chords are checked against. Charts copied from websites stay in `work/`, like recordings.

M2 leaves web charts out (2026-10-10). U-FRET draws its chords with JavaScript, and its terms forbid use outside the service, analysis and heavy load; ChordWiki refuses automated requests. Charts can come back later as a chord sequence the user pastes.

## Downbeats from Beat This!, on chordotomy's beats

The timeline has beats but no downbeats. Beat This! (MIT) predicts both, so pianoize calls it directly. Each predicted downbeat is moved to the nearest beat in chordotomy's list, so chords, melody and bars all count the same beats instead of two grids that drift apart.

## Licenses

Nothing is monetized, so weights with non-commercial terms are usable. They are never committed. They are installed once into the user's cache through `pianoize setup`, with their terms shown ([Song preparation](#song-preparation-the-models-move-out-of-work-2026-10-13)); M1 downloaded them into `work/`. Each model's code and weight licenses are checked again before it is used, because these change. The date and the source are recorded here.

A weight license binds the use of the model, and the repository holds none of its code or weights, so the repository's own license is unaffected. Whether a model's output counts as material adapted from its weights is unsettled, so output of a non-commercial model is treated as non-commercial too: the video stays non-monetized and credits the model. That is why tsumugi-piano-cover (CC BY-NC 4.0), whose cover is the arrangement's base, is credited, while tsumugi's transcriber (MIT code and weights), used as evidence for the harmony and, since M3, for instrument lines the arrangement takes up, carries no such terms. The [transcription-only arrangement](#the-transcription-only-arrangement-an-experiment-2026-10-13) is the path that owes the cover nothing.

The code is published under MIT (2026-10-12), so no GPL or AGPL code goes into the repository or its dependencies, Python or npm, vendored, imported or bundled. Neothesia and YourMT3+ are out for this reason. LGPL is allowed, as in chordotomy. A tool the user installs separately and pianoize runs as a subprocess, such as a MIDI synthesizer, is not part of what is published, so its license doesn't matter.

## What goes into a video

A video carries only the piano pianoize renders, never the original audio or vocals separated from it. Its description credits the song, the artist and the composer, and the arrangement model, tsumugi-piano-cover (anime-song, CC BY-NC 4.0), whose license asks for attribution. Songs under a creator's fan-work guidelines follow them. For モモノネ that is hololive's music guidelines ([hololivepro.com/terms](https://hololivepro.com/terms/), read 2026-10-13): the credit is required, and registering the video with Content ID or any other automatic identification is not allowed. Corporate use, and for-profit use beyond the sharing site's own monetization, is refused; an individual may use the site's partner program, YouTube's ad revenue included. Before uploading, check that the song is not on the guidelines' exclusion list, and its registration with JASRAC or NexTone, whose databases the guidelines point to.

What the video shows on screen is in [M4](#m4-the-falling-notes-renderer-2026-10-12).

## Scoring whether the harmony survived

A piano result is rendered from MIDI to audio and analyzed with chordotomy. The result is then compared with the original's timeline at the same times. A checkpoint is a run of segments in the original timeline: a borrowed iv, a V7/vi, a chromatic bass line under the chorus, passing chords. The result's chords are looked up at the same time, within one beat either way.

A chord passes when its root, triad class and, for inverted originals, bass match; the full rule is in [docs/evaluation.md](evaluation.md#the-pass-rule). Sevenths and tensions are ignored, because chordotomy's sevenths come and go between repeats of the same passage. The bass has to match because in a passage like C/E – Cm/E♭ – G/D – A/C♯ – D the descending bass is the point.

A human cover is scored the same way. That checks the scoring itself: the cover's simplifications have to come out as failures.

M1 scored against chordotomy's timeline, so its numbers include the analyzer's misreadings (see [Harmony from several sources](#harmony-from-several-sources-chordotomy-stays-as-it-is)). From M2 on, a result's notes are checked against the refined harmony timeline directly: `pianoize harmony-evidence` gives each segment's coverage and missing tones, with no render or chordotomy reanalysis in between ([docs/polishing.md](polishing.md#harmony-evidence)). The render-and-analyze scoring above is what M1 used, and stays in `pianoize evaluate`.

The checkpoints for a particular song are made from its recording, so they stay in `work/`. The repository keeps only their format and synthetic examples.

## Playable arrangements

A falling-notes video reads as a piece someone could play. So arrangements are pitched at an intermediate-to-advanced player. tsumugi's cover is one piano part with no hands assigned. From M3 the arrangement is written for two hands by an agent ([M3](#m3-an-agent-writes-the-arrangement-2026-10-11)), rather than pianoize splitting the cover as first planned, and `pianoize check-arrangement` verifies that each hand can play it. Every arrangement, and every correction, must keep that check passing.

The limits as built (2026-10-12) are the ones the M3 spike's check used:

- at most 5 keys held in one hand at its attack;
- a hand's held keys spanning at most 16 semitones, a major tenth. A span of 15 or 16, wider than a ninth, is listed but not flagged, so it can stay where the music needs it;
- no jump of a hand's centre by 15 semitones or more in under 0.2 s, by 22 or more in under 0.36 s, or by more than 26 at any speed;
- no crossed hands: the left hand's top below the right hand's bottom;
- the melody on top of the right hand;
- no pitch struck twice in one hand at one tick: one key can't be struck twice at once.

The same command checks the harmony too: an accompaniment note outside the score's chord at its onset is flagged unless marked as a passing tone. The rules and the report are in [docs/arranging.md](arranging.md#checking).

Every note of an arrangement gets the same velocity (2026-10-11). Most piano covers barely vary their dynamics, so pianoize writes none.

## An agent writes the correction spec, code applies it

tsumugi's cover is kept; M2 polishes it rather than generating a new one. Four kinds of problem are worth fixing: a chord that doesn't match the song, a note that sounds like a slip, a voice that jumps or a bass line that breaks off, and timing that stumbles. An LLM can't listen, so code reads the cover's notes and lists candidates of each kind with the notes around them. The LLM judges each candidate against the refined harmony and the music around it, and writes a correction spec for those worth fixing, with a reason for each one it keeps. Code applies the spec to a copy of the cover. The LLM is an agent session, such as Claude Code; it writes the spec as a file in `work/`.

The pianoize CLI never calls an LLM. That way there is no API key and no cost, and the spec can be read and edited by hand. The same cover and spec give byte-identical output. A CLI that calls an API could later write the same file format.

## The melody comes with the cover

tsumugi's cover already carries the melody, so no separate melody extractor feeds pianoize; GAME, Basic Pitch and torchcrepe were compared in M1 only for an arrangement built from scratch. tsumugi's transcription also writes a `melody` track, which can mark the cover's melody notes so a correction leaves them alone. Since M3 (2026-10-11) the arrangement takes its melody from that track rather than from the cover's top line, still with no separate extractor ([M3](#m3-an-agent-writes-the-arrangement-2026-10-11)).

Corrections live in the spec, not in hand edits to the cover's MIDI: the cover stays untouched, and each change can be read and undone.

## M1 license check (2026-10-08)

Upstream programs run as separately installed subprocess tools, each in its own environment under `work/m1/` (the tsumugi install moved to the pianoize home on 2026-10-13). Homebrew's FFmpeg (built `--enable-gpl`) is loaded only inside the processes of tsumugi and Etude, through torchcodec. That is accepted because those run as separately installed subprocess tools and nothing committed imports or links FFmpeg. Rows are added as each candidate is tried. PiCoGen2, Sheet Sage and sfizz were judged on 2026-10-08 from their documentation and were never downloaded. Every other row was checked on 2026-10-09, when its weights were downloaded or recorded (`TERMS.txt` and `SHA256SUMS` under `work/m1/models/`, `WEIGHTS.txt` under `work/m1/stems/`).

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

## M2 decisions (2026-10-10)

M2 built four commands, `harmony-evidence`, `refine-timeline`, `find-candidates` and `apply-corrections`, and the `polish-cover` Claude Code skill that runs them. [docs/polishing.md](polishing.md) documents them.

- **The agent writes two small JSON files; code writes the rest.** The agent writes the chord edits (`harmony-edits.json`, chords over beat ranges) and the correction spec (a verdict per candidate, an edit per fix). Code validates both and writes the refined timeline and the polished MIDI. The agent never writes a timeline or a MIDI file itself, so what it decided stays small enough to read and edit, every change carries a reason, and the same files give the same bytes.
- **The refined timeline is chordotomy's with edited spans.** It lives at `<stem>.refined.chords.json`, so a save in chordotomy's viewer, which writes `<stem>.edited.chords.json`, never overwrites it. It keeps chordotomy's `generator` and `candidates`, and sets `numeral`, `role`, `function` and `target` to `null` on edited segments: pianoize does not port chordotomy's harmonic analysis, and the viewer recomputes them at its first edit. An edit is a beat range, so a chord change between two beats goes to a beat.
- **Melody protection is pitch only.** A cover note that carries the melody never changes pitch; deleting or retiming it stays allowed. A note carries the melody when it is the top of its 30 ms onset cluster and a note of tsumugi's melody track starts within 60 ms of it on the same pitch class, at or below it: the cover mostly plays the melody an octave up.
- **`add` is allowed, and the pedal is ignored.** A missing chord tone may need a new note. The checks count a note from its note-on to its note-off, so a tone only the pedal holds counts as missing; the spec has no pedal edit.
- **Thresholds** started at the values proposed while planning M2 and were tuned once on the test cover, where a kind giving more than about 60 candidates floods the judging. Only `off_grid_ms` changed, from 45 to 50 ms, which cut the off-grid candidates from 73 to 45. At the tuned values the finder listed 181 candidates; the count per kind is in [docs/polishing.md](polishing.md#thresholds).
- **The harmony check reads the notes.** The render → chordotomy scoring gives way to `harmony-evidence` run on the polished cover and the refined timeline (see [Scoring whether the harmony survived](#scoring-whether-the-harmony-survived)).

**The real run.** On the test song, phase 1 edited 27 of 145 segments of chordotomy's timeline. One was a passing chord over its third that chordotomy read as the major chord on that bass; the transcription's piano and strings showed the real chord. In phase 2 the agent judged the 181 candidates and one more that an edit had created: 20 fixed and 162 kept, with 26 edits (7 deletes, 18 modifies, 1 add). The `--spec` run exited 0 on its second iteration.

**Listening.** The original and the polished cover were rendered for the A/B gate. Instead of approving or naming places to revert, the user compared them with arrangements built other ways, and chose another direction for M3 ([below](#m3-an-agent-writes-the-arrangement-2026-10-11)). The polished cover was never approved as the final arrangement, and nothing was reverted.

**Known gaps in the `polish-cover` skill**, reported by the two agent sessions that ran it, recorded and not fixed:

- The evidence table shows only the transcription's bass track; three decisions needed its other instruments, read outside the table.
- The transcribed bass's share is measured over the bass track's own sounding time in the segment, so a bass that plays for a moment of it can still show a full share.
- Where there is no vocal, the cover's lead line is not matched to the melody and counts as accompaniment, which skews the `velocity` medians and the coverage.
- Nothing tells texture from error on `harmony:missing`.
- A candidate's `context` lines carry no beat or segment marks.
- `off_grid_ms` also sets the passing-tone, segment-bass and `bass-late` tolerances, so tuning it for `off-grid` moves those too.
- SKILL.md's step 6 asks for coverage of at least 0.6 where a chord was fixed, and leaves unclear what applies to a coverage candidate that was kept.
- `references/reconcile-harmony.md` says a reading already in chordotomy's `candidates` is the likeliest answer; that misled where every candidate shared a wrong root.

## M3: an agent writes the arrangement (2026-10-11)

At M2's listening gate the user compared renders of one excerpt, from the start of the song to the end of the first chorus:

- **A**, a rule-based arrangement built from scratch (the melody, the refined chords, left-hand patterns): clearly cleaner.
- **B**, tsumugi's cover, and **C**, the polished cover.
- **D**, C with a clean melody layer on top: too ornate, and things don't fit, because the cover's right-hand lines were written around the cover's own melody.
- **E**, A's right hand over the cover's left hand: better.
- **F1** and **F2**, E with the left hand's pitches regenerated from the chords on the cover's rhythm, bar by bar or from one template per section.
- **G**, an agent (Claude) arranging for a falling-notes video from only tsumugi's cover and tsumugi's vocal transcription. It wrote a per-bar text score, which a script turned into a two-hand MIDI on the cover's tempo grid and checked for playability. The user rated it best, and hard to improve on. A revision brought back the original's signature rhythmic hits, its stop-time and band hits, using the cover's own notes.

Two rules came out of it. Every note gets one velocity, because most piano covers barely vary their dynamics (see [Playable arrangements](#playable-arrangements)). And copying the cover's notes is fine where they render a moment best, once their strays are cleaned.

**Decision (2026-10-11): an agent writes the arrangement as a score; pianoize renders and checks it.** An agent session following a new `arrange-cover` skill reads the cover and the melody, and writes a per-bar score into `work/`. The score is song-specific and stays in `work/`, like a correction spec. pianoize commits only generic, tested tooling:

- a documented score format;
- a command that turns a score into a two-hand MIDI on the cover's tempo grid, with one velocity and the pedal;
- a check of playability and harmony;
- a per-bar dump of the cover and the melody for the agent to read.

The reasons: G sounded cleaner than the polished cover, it is written for two hands and checked as playable, and it keeps the song's own feel, its rhythmic hits included. Committed tooling makes the next song reproducible, where the spike's one-off scripts were written for one song. The CLI still never calls an LLM: the agent writes the score, and code renders it deterministically.

The score is the natural seed for the arrangement JSON the README plans, since it already names the hands and the chords. M2's tooling stays: the refined timeline and the evidence table remain evidence for the agent, and the polish path still runs. The arrangement still copies tsumugi-piano-cover's notes in places, so the video credit and the non-commercial terms in [What goes into a video](#what-goes-into-a-video) and [Licenses](#licenses) stay as they are. The spike's outputs are in `work/m3-spike/` and `work/m3-claude/`, not committed.

### Built (2026-10-12)

M3 built four commands, `regrid`, `dump-bars`, `build-arrangement` and `check-arrangement`, and the `arrange-cover` skill that runs them, in the same Claude Code plugin as `polish-cover`. [docs/arranging.md](arranging.md) documents them. The spike's scripts were rewritten as tested package code, with nothing song-specific carried over.

- **A text score, a bar at a time, on the sixteenth grid.** The agent writes each bar's chords, its pedal and up to three hand lines: the melody and the rest of the right hand, and the left hand. Positions and durations count sixteenths on the cover's meter and tempo map, so bar N of the score sounds where bar N of the cover does. The grammar is the one the spike wrote G in.
- **Pop chord symbols with their own table, not Harte labels.** The agent writes the symbols by hand, as a chord chart spells them: flats, tensions in parentheses, slash basses, `N.C.`. `chords.py`'s Harte labels have no flats and no tensions. A quality the table lacks is written as the nearest one and recorded as a gap; the table can gain it.
- **The version is a header line**, `format 1`, the score's first line that isn't blank or a comment. `tests/test_skills.py` ties it to `arrangement.FORMAT_VERSION` in the skill and the docs, as it ties the spec version to `corrections.SPEC_VERSION`.
- **Repeats are copies with whole-bar overrides.** `bars A-B = C-D` takes its source as it stands at the copy line, so a later change to a source bar never reaches a copy already taken. A `bar N` block for a copied bar replaces it whole, and keeps its section and pedal unless it sets its own. One rule, and a bar can be changed without touching the rest. Overrides per hand line were the alternative; the run showed their cost (gaps below).
- **One velocity, 88**, the spike's loudness-matched value. Loudness is `render --gain`'s.
- **The pedal comes from the score**: per chord by default, a list of positions or none per bar. The build lifts and presses again where an attack would ring a semitone or a minor ninth against a note the pedal holds. A pitch struck again in one hand cuts its earlier note short, so a falling-notes view draws two notes, and the last notes ring a beat past the last note-off.
- **The check builds in memory.** It takes the score and the cover, not a MIDI, so it checks exactly what the build plays. Its limits are under [Playable arrangements](#playable-arrangements).

**The real run.** A fresh agent session, not the one that wrote the format and the skill, followed the skill on the test song, so that the gaps it met were real ones. It ported the 68 bars of the spike the user had approved; the build and the check accepted them unchanged. Then it arranged the rest of the song: 178 bars, 8 bar-range copies covering 83 of them, and 27 of those overridden. On the way the check flagged one jump and listed one span, both fixed, and then printed `clean`. The run's files are in `work/m3/`, not committed.

**The first listening.** The user found the accompaniment better than expected, and the parts without vocals weaker than the sung ones. They asked whether the right hand could carry all of the melody, and whether the tempo hiccup was worth fixing. The tempo hiccup was the cover's: its beat tracking squeezed some of the song's bars into fewer grid bars, and the run had worked around it inside the format with decimal positions a scratch script computed, which no copy could reach. Three additions were proposed, and the user approved them, adding tsumugi's transcription as an input: "tsumugi 채보 파일도 넣자. 진행해줘" (2026-10-12).

- **`regrid`, because the bars must fall on the grid.** Every command counts bars from the cover's tempo map. Where the beat tracker miscounts a few bars, the song's downbeats fall mid-bar there and every later bar is numbered off. `pianoize regrid` writes a copy of the cover in which each hiccup's tempo changes become one, and every event moves to the tick its time lands on: the tempo map and the ticks change, never a note's time. A hiccup is a run of at most 4 bars on bar lines, whose tempo as a whole is more than 15% off the tempos either side of it, which agree within 5%, and whose seconds fit a whole number of bars within 10 ms. The rule can't tell a hiccup from a tempo change that returns to tempo, so each span is checked by ear. On the test cover it found one span, five bars of the song in four grid bars.
- **The transcription, because the cover blends the band.** Where no one sings, the cover mixes the band into one piano part, and its top note is often an accompaniment voice. tsumugi's transcription keeps a track per instrument. `dump-bars --source` prints each instrument's top line, an `I` line, in the bars without vocal, and the skill has the right hand take the line that carries the tune. `--every-bar`, added later at the user's request, prints them in every bar, for fills and riffs under the voice that the plain dump hides; before it, the agent had read the transcription with a scratch script. The transcription is optional: without it, the sections without vocal are written from the cover.
- **`check-arrangement --melody`, listed, never flagged.** It lists the vocal notes of 80 ms or more that no top right-hand note of their pitch class starts within 70 ms of. A note may stay out on purpose, a stray of the transcription or a run too fast to read as it falls, so the agent adds each one or records why it stays out, and the exit code is unchanged.

**The second pass.** The score was renumbered onto the regridded cover, so the song now has 179 bars, and the hiccup's bars became a copy. The intro, the interlude, the instrumental and the ending were rewritten from the instrument lines. The vocal notes the right hand left out went from 9 to 4, and the 4 left are recorded with their reasons.

**The second listening.** The user: "엄청 나아졌음" (much better). They named two places. One was a short descending figure the arrangement missed: the transcription's strings and brass carried it, the cover only in part. The other was an awkward drop from the end of the first chorus into the interlude. Both were fixed, and the same figure was then added where it first occurs, at the user's request. The score now holds 9 bar-range copies covering 88 bars, 28 of those overridden; the check prints `clean`, with the 4 vocal notes listed.

**Approval.** The user approved the arrangement on 2026-10-12: "ㅇㅋ 이정도로 하자 ㅋㅋ 엄청 좋아졌음. 승인."

**Known gaps in the `arrange-cover` skill, the format and the commands**, reported by the sessions that arranged the song, recorded and not fixed:

- An override replaces a whole bar; there is no override per hand line. So an override that changes only the accompaniment restates the melody, as more than half of the run's overrides do, and a later change to the source bar no longer reaches it.
- `regrid` reports its spans in the cover's old numbering, and nothing helps carry a score written before the regrid onto the new numbering. The agent renumbered with a scratch script.
- `--melody` keeps the higher of two vocal notes sung together, so where the lead is the lower of a harmony pair, the higher note is listed as missing.
- A note sung in only one statement of a repeat can't be added to the source bar without reaching every copy of it; it needs an override.
- Reading the `I` lines needs judgment the skill doesn't fully give: no single instrument carries a whole instrumental, transcribed lines jump octaves inside a phrase, and nothing says when to take a sustained line or the stabs above it.
- Whole runs of onsets at the half-sixteenth rounding tie, notes played a little early, read loosely; `reading-the-dump.md` covers a lone `.5`, not bars of them.
- Nothing tells the band changing between repeats apart from the cover model varying its own.
- There is no guidance for two vocal notes at one onset.
- The dump runs past the song's last bar while the cover's last chord rings, so where the score ends is a judgment call.
- Drums never appear in the dump. (`dump-bars --drums` closed this on 2026-10-13; see [the transcription-only arrangement](#the-transcription-only-arrangement-an-experiment-2026-10-13).)
- A figure played slightly early prints its first note at the end of the previous bar.

## M4: the falling-notes renderer (2026-10-12)

M4 built `export-arrangement`, `preview-video` and `render-video`, and the page in `viewer/` they share. [docs/rendering.md](rendering.md) documents them. These were decided in the M4 interview on 2026-10-12.

**Decision (2026-10-12): one web page draws every frame; it is previewed in a browser and captured for the MP4.** The user wanted a web viewer to preview and an MP4 to upload. The alternatives were Python drawing the MP4 beside a separate web preview, which is two drawing codes to keep the same, and a web viewer screen-recorded by hand, whose sync and quality drift. One page drawn at a time `t` has one drawing code, and the preview and the video can't disagree.

- **Capture.** The user asked whether the Playwright plugin and the installed Chrome could be used. The capture uses playwright-core with `channel: "chrome"`, so no browser is downloaded. The Playwright MCP plugin is an agent tool for checking the page while developing; the CLI can't call it. The PNG frames are piped into ffmpeg. pianoize serves the page on 127.0.0.1 because Chrome refuses ES modules from `file://`. The speed was about 47 to 50 frames/s on the roll and about 33 on text cards; a 20 s synthetic render took about 31 s.
- **The look.** Clean and flat, in the Synthesia style: a dark plain background, flat rounded notes, no glow or particles. Green is the right hand and blue the left, Synthesia's convention. Effects can come later, which is why every colour and size is in `viewer/style.js`. Velocity is not exported, since every note has one ([Playable arrangements](#playable-arrangements)).
- **On screen.** The 88 keys, the notes falling coloured by hand, pressed keys lit, and the two cards. The user did not choose chord names, melody highlighting or a pedal display, so they are out. The README's planned "chord names to overlay" is dropped, and the JSON carries the notes and their hands only.
- **The timeline.** 1920×1080 at 60 fps, H.264 with AAC in MP4, and a fixed fall time of 3 s, all accepted with the spec. The music starts at 6 s, after the title card and an empty keyboard, so the first notes have a full fall time to arrive; the credits card follows for 6 s. The audio is padded in Python so that the WAV's clock is the video's clock: the preview plays it through the native `<audio>` element, and ffmpeg muxes it with no offset. ffmpeg converts RGB to YUV with the BT.709 matrix and tags the video BT.709; without that it would use BT.601 untagged, and players would shift the colours.
- **Scratch files.** The preview's and the render's scratch directories sit beside the MIDI and the output, so the song's JSON and audio never leave `work/`. npm keeps its default cache, `~/.npm`, which npm manages itself and the user's other projects share (2026-10-13); a cache under `work/` needed a relative path in `.npmrc`, which npm resolves against its working directory, not the file's.
- **Sync.** The page lights a key on its note-on's frame. The Salamander C4 attack passes 0.01 about 20 ms later, so the sync test finds the key one frame before the sound's threshold, within its ±1-frame tolerance.
- **Repeatability.** Two renders of the same inputs gave identical frames and byte-identical MP4s, on the same Chrome 154 and ffmpeg. That is all it promises: Chrome updates itself, so frames can change between Chrome versions.
- **Licenses (checked 2026-10-12).** playwright-core 1.64.0 is Apache-2.0 and has no dependencies; it is the viewer's only one. ffmpeg's GPL build runs only as a subprocess, like FluidSynth, and Chrome is the installed browser, driven but not bundled.

**The real run.** `render-video` rendered the approved M3 arrangement of the test song with the Salamander SoundFont: 15,895 frames, 264.9 s, 27.8 MB, in 8 min 42 s end to end, at a peak of 0.341. The preview was checked first at the title card, a dense passage and the credits card. The cards file was a draft written from the source file's title, singer and producer, with the credits from [What goes into a video](#what-goes-into-a-video). The run's files are in `work/m4/`, not committed.

**Approval.** The user approved the video on 2026-10-13 with no changes: "ㅇㅋ 이정도면 훌륭함 승인".

## The transcription-only arrangement, an experiment (2026-10-13)

**Why.** The default path's cover comes from tsumugi-piano-cover, whose weights are CC BY-NC 4.0, so its output is treated as non-commercial and the video stays non-monetized ([Licenses](#licenses)). tsumugi's transcriber has MIT code and weights, and hololive's guidelines allow an individual's ad revenue ([What goes into a video](#what-goes-into-a-video)). So an arrangement made from the transcription alone would be monetizable. This tested whether one is good enough.

**The clean-room test** covered bars 1 to 67 of the test song and read no cover. Its three inputs:

- a tempo-grid MIDI that a scratch script built from `source.mid`'s tempo map, time signature and chord markers, with its `piano` and `electric_bass` tracks, run through `regrid`;
- tsumugi's melody MIDI;
- `source.mid`, through `dump-bars --source --every-bar`.

A second scratch script printed the drums per bar.

**The verdicts**, by the user:

- v1, the left hand mostly following the bass as single notes: "왼손 반주쪽을 편곡을 좀더 해야할듯함".
- The two inputs need different instructions: "둘이 프롬프트가 다르게 들어가야 해. 그거 고려해줘." A cover has a pianistic accompaniment to keep the feel of; a band transcription has none, so the band has to be arranged for piano.
- v2, the left hand re-arranged per section from the kick, snare, hi-hat and strums: "이번엔 너무 뭔가 많은데".
- v3, thinned to the bass on the main kicks, with chords on the backbeat left to ring: "아직 애매함."

**Decision (2026-10-13): keep it as an experiment; the cover stays the default.** The user: "별도 스킬? 별도 에이전트 같은걸로 킵은 해두되 … tsumugi-piano-cover 이게 더 좋네. 나중에 claude 모델 업데이트 되거나 프롬프트 더 튜닝해서 쓰면 될거 같긴해." They then chose an experimental skill plus the scratch steps as commands.

- **Built.** `pianoize build-grid`, which builds the tempo-grid MIDI from a tsumugi transcription; `dump-bars --drums`, which prints the drum lines; and the `arrange-transcription` skill, with its clean-room rule (no cover is read) and its guidance on arranging a band for piano.
- **`arrange-cover` stays the default and is unchanged.**
- **The video's credit and non-commercial terms stay as they are** ([What goes into a video](#what-goes-into-a-video)).
- The run's files are in `work/tsumugi-only/`, not committed.

## Song preparation: the models move out of `work/` (2026-10-13)

**Why.** Preparing a song had been one script per song, run from the M1 environments under `work/m1/`. That does not scale to a second song, and a plugin user has no `work/` at all, so the models live user-wide. The second test song was the first real test: starting it from a YouTube link, the user asked about downloading the way chordotomy does, and said: "돌릴때는 레포 캐시말고 전역 사용하면 chordotomy랑 캐시 공유해서 그게 더 좋을듯" (use the global caches, shared with chordotomy). Asked when to build the tooling, they chose "지금 바로 도구화" (now, with the second song as its first real test).

**The user's choices.**

- **Shape:** pianoize commands plus a skill: `pianoize setup`, `pianoize prepare` and the `prepare-song` skill ([docs/preparing.md](preparing.md)).
- **Location.** "플러그인 사용자 입장에서 보면 거긴 work 디렉토리 없을수 있으니까... 전역에 받아야 하려나". They chose `~/.cache/pianoize`, with the weights in the Hugging Face cache and uv's cache global. npm had already moved to its default cache the same day ([M4](#m4-the-falling-notes-renderer-2026-10-12)).

**Decisions.**

- **The home.** `$PIANOIZE_HOME`, else `$XDG_CACHE_HOME/pianoize`, else `~/.cache/pianoize`. It holds the two clones, their environments, tsumugi's checkpoints and the stem splitter's weights. The cover's weights go in the Hugging Face hub cache (`~/.cache/huggingface/hub` by default), so they are shared with whatever else uses that model.
- **uv's cache stays global**, shared with chordotomy and every other uv project, instead of the `work/m1/cache` that M1 used.
- **yt-dlp runs through `uvx … @latest`, not as a dependency.** An old yt-dlp stops working when YouTube changes, so every run takes the newest, as chordotomy's skill does. It stays out of pyproject.toml and out of the repository's dependencies.
- **The pins** are the tsumugi and tsumugi-piano-cover rows of the [M1 license check](#m1-license-check-2026-10-08): commits for the clones, a revision for the cover's weights, torch 2.13.0 for the generator. tsumugi's checkpoints are fetched from `main`, so they are pinned by content: setup checks each against its recorded SHA-256.
- **Setup fetches tsumugi's own checkpoints too**, and verifies them by hash. The approved spec says setup installs both models, pinned; otherwise the first `prepare` would download 850 MB unpinned. Setup streams uv's and huggingface_hub's progress to the terminal.
- **The download call.** One video's audio as mp3, since pianoize's decoder reads wav, flac, ogg and mp3 but not m4a or webm; `--no-playlist -I 1`, so a link to a video in a playlist, or to a playlist, takes a single video; the `deno` extra, for the JavaScript runtime YouTube needs.
- **The 2-hour limit on the recording was dropped.**
- **The logs are filtered.** The tools' logs keep their output in order, one line at a time, but leave out the `@@` lines the worker streams to Cover Studio's page.
- **The melody goes through `grid.build`**, keeping only `source.mid`'s `melody` track and its tempo changes and time signatures, so there are no chord markers and the file reads on the tempo map the cover is built from.
- **A stopped `prepare` exits 130** and removes its scratch directory.

**Determinism.** Each transcription is one draw ([M1 results](#m1-results-2026-10-09)), so `source.mid` is kept and reused. The cover is generated with seed 0, and on this machine the same `source.mid` gives the same `cover.mid`: generated again from the second song's first transcription, it matched the first cover byte for byte (CPU, 2026-10-13).

**The real run.** The M1 install moved instead of downloading again: the two clones with their commit files, the generator's environment and the stem splitter's weights went into `~/.cache/pianoize`, and the cover's weights into the Hugging Face snapshot of the pinned revision, where their SHA-256 sums matched `work/m1/models/tsumugi-piano-cover/SHA256SUMS`. The two environments' interpreter links pointed into M1's `work/m1/cache/uv-python`; `uv venv --python 3.12 --allow-existing` re-linked them to uv's own Python 3.12.14 and kept their packages. `pianoize setup` then found everything in place: both clones at their pins, uv's checks of both environments, the checkpoints and the weights present, nothing downloaded and the sizes unchanged, in under a second. `pianoize prepare` on the second song, from its YouTube mp3, wrote the four files: the transcription took 558 s on MPS for the 307 s song and the cover 58 s on the CPU. A second run reused all four. The runs' files are in `work/beacon-of-light/prepared/` and `redo/`, not committed.

**What the second test song showed.** tsumugi-piano-cover builds its beat tokens from `source.mid`'s tempo map (`piano_cover/source.py`), so where tsumugi's beat tracking is wrong, the cover's rhythm bends with it. On the second test song the tracking ran at half speed in long stretches and squeezed bars elsewhere. The user heard the cover's tempo as strange and suggested arranging from the transcription alone: "이건 source.mid 만 보는게 나을수도 있겠다는 생각이 들었음. cover.mid 자체가 템포가 이상함." The `prepare-song` skill's hand-off cites this when it offers the [transcription-only path](#the-transcription-only-arrangement-an-experiment-2026-10-13); the cover stays the default.
