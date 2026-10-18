import json
import re
from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

from pianoize import arrangement, corrections, timeline
from pianoize.cli import app

ROOT = Path(__file__).resolve().parents[1]
# Each skill's directory under skills/, and the doc of the commands it runs.
SKILLS = {
    "polish-cover": ROOT / "docs" / "polishing.md",
    "arrange-cover": ROOT / "docs" / "arranging.md",
    "arrange-transcription": ROOT / "docs" / "arranging.md",
    "prepare-song": ROOT / "docs" / "preparing.md",
    "make-video": ROOT / "docs" / "rendering.md",
}
POLISHING = SKILLS["polish-cover"]
ARRANGING = SKILLS["arrange-cover"]
ARRANGING_SKILLS = ("arrange-cover", "arrange-transcription")

# A command line is code; prose such as "pianoize reads" is not one.
CODE = re.compile(r"```.*?```|`[^`\n]+`", re.DOTALL)
COMMAND = re.compile(r"\bpianoize (?=[a-z])")
NAME = re.compile(r"[a-z][a-z-]*")
FLAG = re.compile(r"(?<![^\s\[])--?[A-Za-z][A-Za-z-]*")  # after a space or a [, not inside a path
# A file a skill names in code, from the skill's directory: a reference or a SKILL.md, its own or
# another skill's.
REFERENCE = re.compile(r"`((?:\.\./[a-z-]+/)?(?:references/[\w.-]+\.md|SKILL\.md))`")
# What arrange-transcription cites of arrange-cover's references by name, marked as it is there
# (a heading, a bold lead, a clause): arrange-cover keeps changing, and a rename must fail here.
CITED_FROM_ARRANGE_COVER = [
    ("arranging-rules.md", "## Keep the feel"),
    ("arranging-rules.md", "**The groove is the original's."),
    ("arranging-rules.md", "## Copy the cover where it renders a moment best"),
    ("arranging-rules.md", "## Where no one sings"),
    ("arranging-rules.md", "## Take from the band"),
    ("arranging-rules.md", "**The left hand still comes from the cover:**"),
    ("arranging-rules.md", "**Without a source**"),
    ("arranging-rules.md", "## Infer and fill"),
    ("arranging-rules.md", "## One velocity"),
    ("arranging-rules.md", "## Readable when falling"),
    ("arranging-rules.md", "**One pattern per section.**"),
    ("arranging-rules.md", "## The hands"),
    ("arranging-rules.md", "Write it an octave up where the cover plays it there."),
    ("arranging-rules.md", "**Jumps take time.**"),
    ("arranging-rules.md", "## Pedal"),
    ("arranging-rules.md", "## Chords and passing tones"),
    ("arranging-rules.md", "## Fixing the check"),
    ("arranging-rules.md", "## A full arrangement"),
    ("arranging-rules.md", "**One figure per layer, per section.**"),
    ("arranging-rules.md", "**What no longer applies,**"),
    ("reading-the-dump.md", "## Markers are a model's guesses"),
    ("reading-the-dump.md", "## The drums"),
    ("reading-the-dump.md", "## The melody"),
    ("reading-the-dump.md", "**Skip the strays.**"),
    ("reading-the-dump.md", "**Note the octave.**"),
    ("reading-the-dump.md", "**Where `V` is silent**"),
    ("reading-the-dump.md", "**Where `V` and the cover disagree on a pitch,**"),
]

# A fenced code block's text; under a list item its fences are indented.
FENCED = re.compile(r"^[ \t]*```[^\n]*\n(.*?)^[ \t]*```", re.DOTALL | re.MULTILINE)
# A line only a score has: its format line, a bar or a copy.
SCORE_LINE = re.compile(r"^\s*(format\s|bar\s+\d+\s*\||bars\s+\d+-\d+\s*=)", re.MULTILINE)
# The rows of docs/arranging.md's chord quality table, the one headed `| symbol |`.
QUALITY_TABLE = re.compile(r"^\| symbol \|.*\n\|[-| ]+\n((?:\|.*\n)+)", re.MULTILINE)


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _documents(skill: str) -> list[Path]:
    directory = ROOT / "skills" / skill
    return [directory / "SKILL.md", *sorted((directory / "references").glob("*.md")), SKILLS[skill]]


def test_skill_is_written_for_this_schema():
    skill = _text(ROOT / "skills" / "polish-cover" / "SKILL.md")
    assert re.findall(r"written for version (\d+)", skill) == [str(timeline.SCHEMA_VERSION)]


def test_skill_and_docs_name_this_spec_version():
    version = str(corrections.SPEC_VERSION)
    skill = _text(ROOT / "skills" / "polish-cover" / "SKILL.md")
    assert re.findall(r"correction spec version (\d+)", skill) == [version]
    assert re.findall(r"`spec_version (\d+)`", _text(POLISHING)) == [version]
    for path in _documents("polish-cover"):  # the JSON examples carry the number too
        assert set(re.findall(r'"spec_version": (\d+)', _text(path))) <= {version}, path.name


def _scores(skill: str) -> list[tuple[str, str]]:
    """(file name, text) of each score in a code block of an arranging skill, its references and
    its doc."""
    return [
        (path.name, block)
        for path in _documents(skill)
        for block in FENCED.findall(_text(path))
        if SCORE_LINE.search(block)
    ]


@pytest.mark.parametrize("skill", ARRANGING_SKILLS)
def test_arrange_skill_and_docs_name_this_format_version(skill):
    version = str(arrangement.FORMAT_VERSION)
    text = _text(ROOT / "skills" / skill / "SKILL.md")
    assert re.findall(r"score format version (\d+)", text) == [version]
    assert re.findall(r"`format (\d+)`", _text(SKILLS[skill])) == [version]
    for name, score in _scores(skill):  # every score opens with its format line
        assert score.split("\n", 1)[0].strip() == f"format {version}", name


@pytest.mark.parametrize("skill", ARRANGING_SKILLS)
def test_the_scores_in_the_arrange_skill_and_docs_parse(skill):
    scores = _scores(skill)
    assert ARRANGING.name in {name for name, _ in scores}, "the doc's example is no score"
    for name, score in scores:
        try:
            arrangement.parse(score, 16)
        except arrangement.ArrangementError as exc:
            pytest.fail(f"{name}: {exc}")


def test_the_docs_example_builds_and_checks_as_the_doc_says(tmp_path, tick_midi):
    [example] = [score for name, score in _scores("arrange-cover") if name == ARRANGING.name]
    [printed] = [block for block in FENCED.findall(_text(ARRANGING)) if block.startswith("notes: ")]
    score, cover, out = tmp_path / "score.txt", tmp_path / "cover.mid", tmp_path / "out.mid"
    score.write_text(example, encoding="utf-8")
    tick_midi([(0, 1920 * 4, 48, 80)], tempos=[(0, 120)]).save(cover)  # four 4/4 bars, 120 bpm
    runner = CliRunner()
    built = runner.invoke(
        app, ["build-arrangement", str(score), "--cover", str(cover), "-o", str(out)]
    )
    assert (built.exit_code, built.stdout) == (0, printed)
    checked = runner.invoke(app, ["check-arrangement", str(score), "--cover", str(cover)])
    assert (checked.exit_code, checked.stdout) == (0, "clean\n")


def test_the_docs_chord_table_lists_every_quality_with_its_intervals():
    rows = QUALITY_TABLE.search(_text(ARRANGING))[1].splitlines()
    table = {}
    for row in rows:
        symbol, _, intervals, *_ = (cell.strip() for cell in row.strip("|").split("|"))
        table[symbol.strip("`").removeprefix("C")] = tuple(map(int, intervals.split()))
    assert len(table) == len(rows)  # no quality twice
    assert table == arrangement.QUALITIES


def _command_lines(text: str):
    """Each `pianoize <command> …` in the code of a document: the command and its flags."""
    for code in CODE.findall(text):
        for line in code.splitlines():
            for call in COMMAND.split(line)[1:]:
                yield NAME.match(call).group(), set(FLAG.findall(call))


@pytest.mark.parametrize("skill", SKILLS)
def test_named_commands_and_their_options_exist(skill):
    commands = typer.main.get_command(app).commands
    for path in _documents(skill):
        lines = list(_command_lines(_text(path)))
        for name, flags in lines:
            assert name in commands, (path.name, name)
            params = commands[name].params
            options = {opt for param in params for opt in (*param.opts, *param.secondary_opts)}
            assert flags <= options | {"--help"}, (path.name, name, flags - options)
        if path.name == "SKILL.md":
            assert lines, "SKILL.md names no pianoize command"


def _workflow(skill: str) -> str:
    return _text(ROOT / "skills" / skill / "references" / "workflow.md")


def test_the_transcription_skill_builds_the_grid_and_dumps_the_drums():
    lines = list(_command_lines(_workflow("arrange-transcription")))
    assert "build-grid" in {name for name, _ in lines}
    assert any(name == "dump-bars" and "--drums" in flags for name, flags in lines)


def test_the_cover_workflow_steps_the_transcription_workflow_cites():
    # arrange-transcription cites the score example in step 4 and the copies in step 5.
    cited = _workflow("arrange-transcription")
    assert "the example in step 4 of `../arrange-cover/references/workflow.md`" in cited
    assert "as step 5 of `../arrange-cover/references/workflow.md` says" in cited
    steps = _workflow("arrange-cover")
    assert "\n4. **Write `<out>/score.txt`" in steps and "```\n   format 1\n" in steps
    assert "\n5. **Repeats:** write a section that repeats an earlier one as" in steps


def test_the_cover_skill_dumps_the_band_in_every_bar():
    lines = list(_command_lines(_workflow("arrange-cover")))
    assert any(name == "dump-bars" and {"--every-bar", "--drums"} <= flags for name, flags in lines)


def _frontmatter(path: Path) -> dict[str, str]:
    head = _text(path).split("---\n")[1]
    return dict(line.split(": ", 1) for line in head.strip().splitlines())


def test_the_arranging_skills_dispatch_the_arranger():
    agent = ROOT / "agents" / "arranger.md"
    front = _frontmatter(agent)
    assert front["name"] == "arranger"
    # The shell and the files only: no web tools, so audio and song content stay on the machine.
    tools = {tool.strip() for tool in front["tools"].split(",")}
    assert tools == {"Bash", "Read", "Write", "Edit", "Glob", "Grep"}
    for skill in ARRANGING_SKILLS:
        text = _text(ROOT / "skills" / skill / "SKILL.md")
        assert "`pianoize:arranger`" in text, skill
        assert f"<root>/skills/{skill}/references/workflow.md" in text, skill
        assert "<root>/agents/arranger.md" in text, skill  # the fallback without the type


def test_the_prepare_skill_sets_up_and_prepares_into_a_directory():
    lines = list(_command_lines(_text(ROOT / "skills" / "prepare-song" / "SKILL.md")))
    assert "setup" in {name for name, _ in lines}
    assert any(name == "prepare" and "-o" in flags for name, flags in lines)
    assert any(name == "prepare" and "--melody-track" in flags for name, flags in lines)


@pytest.mark.parametrize("skill", SKILLS)
def test_named_references_exist(skill):
    directory = ROOT / "skills" / skill
    documents = [directory / "SKILL.md", *sorted((directory / "references").glob("*.md"))]
    named = [(path.name, name) for path in documents for name in REFERENCE.findall(_text(path))]
    assert named, "the skill names no reference"
    for document, name in named:
        assert (directory / name).is_file(), (document, name)


def test_what_arrange_transcription_cites_of_arrange_cover_exists():
    # SKILL.md and its references; the last document is docs/arranging.md.
    citing = "".join(_text(path) for path in _documents("arrange-transcription")[:-1])
    cited = ROOT / "skills" / "arrange-cover" / "references"
    for reference, name in CITED_FROM_ARRANGE_COVER:
        assert name in _text(cited / reference), (reference, name)
        assert f'"{name.strip("#*.,: ")}"' in citing, name  # the list follows what the skill cites


@pytest.mark.parametrize("skill", SKILLS)
def test_references_need_no_plugin_root(skill):
    # Claude Code substitutes ${CLAUDE_PLUGIN_ROOT} only in SKILL.md, never in the files it names.
    references = sorted((ROOT / "skills" / skill / "references").glob("*.md"))
    assert references
    for path in references:
        assert "CLAUDE_PLUGIN_ROOT" not in _text(path), path.name


def test_manifests_leave_the_version_to_pyproject():
    plugin = json.loads(_text(ROOT / ".claude-plugin" / "plugin.json"))
    marketplace = json.loads(_text(ROOT / ".claude-plugin" / "marketplace.json"))
    assert "version" not in plugin
    assert [entry["source"] for entry in marketplace["plugins"]] == ["./"]
    assert not any("version" in entry for entry in marketplace["plugins"])
