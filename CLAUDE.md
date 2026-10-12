# CLAUDE.md

Project-specific instructions for pianoize. The global ~/.claude/CLAUDE.md still applies; this only adds project rules.

## Documentation map

- [README.md](README.md): direction, the rules, layout, dev commands
- [docs/decisions.md](docs/decisions.md): design decisions and their reasons
- [docs/evaluation.md](docs/evaluation.md): the evaluation tooling and the checkpoint file format
- [docs/polishing.md](docs/polishing.md): the polishing commands, the candidate and correction-spec formats, the refined-timeline rules
- [docs/arranging.md](docs/arranging.md): the score format, the arranging commands and the check's limits
- [docs/rendering.md](docs/rendering.md): the arrangement JSON, the viewer and the video commands
- chordotomy's [timeline-json.md](https://github.com/zeikar/chordotomy/blob/main/docs/timeline-json.md): the chord timeline pianoize reads (schema 11)
- CLAUDE.md (this file): rules to follow while working

## Rules

The [rules in the README](README.md#rules) apply. The reasons for those and for the rules below are in [docs/decisions.md](docs/decisions.md).

- **Don't change chordotomy.** pianoize reads its timeline JSON, checks `schema_version`, and runs its CLI as a separately installed tool. It doesn't import chordotomy or share its environment.
- **No analysis is the answer key.** chordotomy's timeline, web chord charts and tsumugi's transcription are evidence to weigh, not truth. Where they disagree, check the notes before calling anything a mistake.
- **No GPL/AGPL code in the repo or its dependencies.** That covers vendored code and anything imported or bundled, Python or npm; Neothesia and YourMT3+ are out. LGPL is allowed. A tool the user installs separately and pianoize runs as a subprocess is allowed whatever its license.
- **Check the license before adding a dependency, model or sample library.** Weights included. Record the date and the source in docs/decisions.md. Weights with non-commercial terms are allowed, and are downloaded into `work/`.
- **The CLI never calls an LLM.** An agent session writes the correction spec or the score into `work/`. Code validates it and applies it to the cover, or builds it into MIDI, deterministically: the same inputs give byte-identical output.
- **Arrangements are playable.** From M3 the arrangement is written for two hands, and `pianoize check-arrangement` verifies notes per hand, hand span, jumps and no crossed hands; a score or a correction must keep it passing.
- **Models with conflicting dependencies run in their own environments**, not in the core package.
- Tests synthesize their audio. The default suite runs no model and downloads nothing.
- The version lives only in `pyproject.toml`; code reads it through `importlib.metadata`.
- The arrangement JSON's schema is in docs/rendering.md; changes to it are breaking.
- **The viewer is plain HTML, CSS and ES modules, with no bundler.** Its only npm dependency is playwright-core. npm keeps its default cache (`~/.npm`).
- **Commit to `main` and push.** Work done on a separate branch is merged into `main` and pushed once it's finished. Commit messages are conventional commits (`feat(scope): …`, `chore: …`).
