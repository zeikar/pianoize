# pianoize

Turn a song recording into a piano arrangement, rendered as falling notes.

Status: planning. Nothing runs yet.

## Direction so far

- **Harmony from chordotomy.** Chords, bass line, beats and key come from a [chordotomy](https://github.com/zeikar/chordotomy) chord timeline. pianoize reads that JSON; chordotomy itself stays an analyzer.
- **Melody from a pretrained model.** The first candidate is openvpi's GAME (singing to notes); the fallback is Demucs vocal separation followed by Spotify's Basic Pitch. They are compared on one song before either is chosen.
- **An LLM writes the arrangement, code plays it.** An agent reads the timeline and picks a texture per passage. A deterministic renderer turns that into notes.
- **Falling-notes output.** A piano roll drawn over time needs no bar lines or time signature.

## Rules

- Audio never leaves the machine.
- Recordings, and the MIDI or video made from them, are never committed. They stay in the gitignored `work/`.
- Model weights with non-commercial terms are never committed. They are downloaded on first use, with their terms shown.
