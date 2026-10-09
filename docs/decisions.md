# Design decisions

## The arrangement first, the video last

The goal is falling-notes videos of piano arrangements for a personal, non-monetized YouTube channel. What makes one worth watching is the arrangement, so the renderer comes last and is started only once the arrangements sound right as MIDI. The work runs in four steps:

1. **M0**: these rules and the package skeleton.
2. **M1**: run the existing audio-to-piano-cover models that run on a Mac, and the melody extractors, and score them together with a human piano cover.
3. **M2**: pianoize's own arrangement engine.
4. **M3**: the renderer.

If a model in M1 keeps the harmony, pianoize wraps it. If it simplifies the harmony the way the human cover does, M2 is the reason pianoize exists. The user makes that call from the M1 table; there is no fixed threshold.

## Harmony from chordotomy, which stays as it is

[chordotomy](https://github.com/zeikar/chordotomy) already gives chords, the bass and inversions, beats, key regions and Roman numerals. It deliberately stops there: melody → MIDI is outside it, so pianoize doesn't add it there. pianoize reads the timeline JSON and checks its `schema_version` (11 for now). To analyze audio it runs the `chordotomy` CLI as a separately installed tool. chordotomy's model extra pins torch, lv-chordia and beat-this, and the pianoize models in M1 bring their own pins, so the two don't share an environment.

## Downbeats from Beat This!, on chordotomy's beats

The timeline has beats but no downbeats. Beat This! (MIT) predicts both, so pianoize calls it directly. Each predicted downbeat is moved to the nearest beat in chordotomy's list, so chords, melody and bars all count the same beats instead of two grids that drift apart.

## Licenses

Nothing is monetized, so weights with non-commercial terms are usable. They are never committed. They are downloaded into `work/` on first use, with their terms shown. Each model's code and weight licenses are checked again before it is used, because these change. The date and the source are recorded here.

The code license is undecided and the repository is private. It may later be published under MIT, so no GPL or AGPL code goes into the repository or its dependencies, Python or npm, vendored, imported or bundled. Neothesia and YourMT3+ are out for this reason. LGPL is allowed, as in chordotomy. A tool the user installs separately and pianoize runs as a subprocess, such as a MIDI synthesizer, is not part of what is published, so its license doesn't matter.

## What goes into a video

A video carries only the piano pianoize renders, never the original audio or vocals separated from it. Its description credits the song, the artist and the composer. Songs under a creator's fan-work guidelines follow them. For モモノネ that is hololive's music guidelines: the credit is required, no Content ID registration, no commercial or corporate use. Before uploading, check that the song is not on the guidelines' exclusion list.

## Scoring whether the harmony survived

A piano result is rendered from MIDI to audio and analyzed with chordotomy. The result is then compared with the original's timeline at the same times. A checkpoint is a run of segments in the original timeline: a borrowed iv, a V7/vi, a chromatic bass line under the chorus, passing chords. The result's chords are looked up at the same time, within one beat either way.

A chord passes when its root, triad class and, for inverted originals, bass match; the full rule is in [docs/evaluation.md](evaluation.md#the-pass-rule). Sevenths and tensions are ignored, because chordotomy's sevenths come and go between repeats of the same passage. The bass has to match because in a passage like C/E – Cm/E♭ – G/D – A/C♯ – D the descending bass is the point.

A human cover is scored the same way. That checks the scoring itself: the cover's simplifications have to come out as failures.

The checkpoints for a particular song are made from its recording, so they stay in `work/`. The repository keeps only their format and synthetic examples.

## Playable arrangements

A falling-notes video reads as a piece someone could play. So arrangements are pitched at an intermediate-to-advanced player. The generator enforces, and a check verifies, a limit on notes per hand, a hand span (about a ninth) and no crossed hands.

## An agent writes the arrangement spec, code plays it

For each passage, an LLM chooses the texture, the register and the voicing style. Code turns those choices into notes. The LLM is an agent session, such as Claude Code. It reads the timeline, the melody and the downbeats, and writes the spec as a file in `work/`.

The pianoize CLI never calls an LLM. That way there is no API key and no cost, and the spec can be read and edited by hand. A song can also be generated again from the same file with byte-identical output. A CLI that calls an API could later write the same file format.

## A hand-corrected melody can replace the extracted one

Melody has no ground truth, and an extraction error would otherwise go straight into the video. So the extracted melody is exported as MIDI. A MIDI corrected by hand in a DAW can be fed back in its place. A report lists the notes that clash with the chord, to show where to look.

Editing the generated arrangement itself is out of scope. Generating the song again would overwrite the edits.

## M1 license check (2026-10-08)

Upstream programs run as separately installed subprocess tools, each in its own environment under `work/m1/`. Homebrew's FFmpeg (built `--enable-gpl`) is loaded only inside the processes of tsumugi and Etude, through torchcodec. That is accepted because those run as separately installed subprocess tools and nothing committed imports or links FFmpeg. Rows are added as each candidate is tried.

| candidate | code license | weight license | revision | SHA-256 | runs on this Mac? | runtime notes |
| --- | --- | --- | --- | --- | --- | --- |
| PiCoGen2 | MIT, [LICENSE](https://github.com/tanchihpin0517/PiCoGen/blob/v2/LICENSE) ([repo](https://github.com/tanchihpin0517/PiCoGen/tree/v2)) | CC BY-NC-SA 3.0 | not downloaded | not downloaded | no: excluded | documents Linux with a GPU of more than 16 GB |
| Sheet Sage | MIT, [repo](https://github.com/chrisdonahue/sheetsage) | transcription weights CC BY-NC-SA 3.0 | not downloaded | not downloaded | no: excluded | Linux/Docker path; Jukebox features need CUDA |
| sfizz | BSD-2, [repo](https://github.com/sfztools/sfizz) | none | 1.2.3 (last release) | not downloaded | no: rejected | archived March 2025; the macOS `sfizz_render` binary is x86-64 only |
| Demucs 4.1.0 (`htdemucs_ft`) | MIT, [repo](https://github.com/adefossez/demucs) | none stated: the [model card](https://huggingface.co/adefossez/HTDemucs-ft) carries no license statement | HF `adefossez/HTDemucs-ft` d74ac89c3a1e874fc78f152555cf4d8533f06cd4 | `04573f0d.safetensors` 68854b0d7c2b3274723b5761f6fd9f5aec5f1bcd3f0de7c1669546fdb7871b7c; `92cfc3b6.safetensors` a241863551f30d01c42bd7b97da40839922ead3acb0f1fcab25682f55b4eeb59; `d12395a8.safetensors` 5b01a97567ae9a3178a6236fb520251045c03eb8834bc8c24a4eec11d6c8fb56; `f7e0c4bc.safetensors` 2c85ab3c62dd6edd8e0b965e38b16fd1cdde357cc25de6b6bc9ce7c83f60925f; `htdemucs_ft.yaml` 69470b8c1bbd674437b51bc9fb491327a10ab0396b702c93389b9cf750016346 | yes: CPU, 396 s for a 251 s song | stems never leave `work/` and never enter a video; needs `--with numpy` (not declared by demucs 4.1.0); see `work/m1/stems/WEIGHTS.txt` |
| Basic Pitch 0.4.0 | Apache-2.0, [repo](https://github.com/spotify/basic-pitch) | Apache-2.0, bundled in the wheel | 0.4.0 (PyPI) | wheel: bundled, see the wheel; `icassp_2022/nmp.onnx` 2c3c1d144bfa61ad236e92e169c13535c880469a12a047d4e73451f2c059a0ec | yes: ONNX backend (`--model-serialization onnx`), CPU, 9 s for the 251 s vocals stem | Python 3.11 (3.12 is broken on macOS); needs `setuptools<81` (resampy imports `pkg_resources`); its env also holds soxr (LGPL-2.1-or-later), installed only, not imported by committed code; no GPL found |

## MIDI is rendered with FluidSynth

[FluidSynth](https://github.com/FluidSynth/fluidsynth) (LGPL-2.1) renders MIDI to audio. pianoize runs its CLI as a subprocess. It is installed with Homebrew, the one approved global install; the formulas it adds are recorded so they can be removed later. The flags are fixed, `-R 0 -C 0 -g 0.5 -r 44100` (no reverb, no chorus, gain 0.5, 44.1 kHz), so the same MIDI renders the same way. The FluidSynth version is recorded with the results. Installed 2026-10-09: FluidSynth 2.6.1 (Homebrew `fluid-synth`).

The SoundFont is Salamander Grand Piano V3 (SF2; CC BY 3.0, Alexander Holm; [FreePats](https://freepats.zenvoid.org/Piano/acoustic-grand-piano.html)). It is used for evaluation and for video audio. Every video description carries the credit line: "Piano sound: Salamander Grand Piano V3 by Alexander Holm (CC BY 3.0), via FreePats." Upright Piano KW (CC0 1.0, same page) is the fallback if the sound disappoints. Downloaded 2026-10-09: `SalamanderGrandPiano-SF2-V3+20200602.tar.xz`, SHA-256 `15edb061d7ba60d58332f72dba8f8ce40988048cc703f935e6320f37d650e213`; the extracted `SalamanderGrandPiano-V3+20200602.sf2` is 1.27 GB.
