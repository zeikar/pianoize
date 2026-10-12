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
}
POLISHING = SKILLS["polish-cover"]
ARRANGING = SKILLS["arrange-cover"]

# A command line is code; prose such as "pianoize reads" is not one.
CODE = re.compile(r"```.*?```|`[^`\n]+`", re.DOTALL)
COMMAND = re.compile(r"\bpianoize (?=[a-z])")
NAME = re.compile(r"[a-z][a-z-]*")
FLAG = re.compile(r"(?<![^\s\[])--?[A-Za-z][A-Za-z-]*")  # after a space or a [, not inside a path

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


def _scores() -> list[tuple[str, str]]:
    """(file name, text) of each score in a code block of the arrange skill, its references and
    its doc."""
    return [
        (path.name, block)
        for path in _documents("arrange-cover")
        for block in FENCED.findall(_text(path))
        if SCORE_LINE.search(block)
    ]


def test_arrange_skill_and_docs_name_this_format_version():
    version = str(arrangement.FORMAT_VERSION)
    skill = _text(ROOT / "skills" / "arrange-cover" / "SKILL.md")
    assert re.findall(r"score format version (\d+)", skill) == [version]
    assert re.findall(r"`format (\d+)`", _text(ARRANGING)) == [version]
    for name, score in _scores():  # every score opens with its format line
        assert score.split("\n", 1)[0].strip() == f"format {version}", name


def test_the_scores_in_the_arrange_skill_and_docs_parse():
    scores = _scores()
    assert ARRANGING.name in {name for name, _ in scores}, "the doc's example is no score"
    for name, score in scores:
        try:
            arrangement.parse(score, 16)
        except arrangement.ArrangementError as exc:
            pytest.fail(f"{name}: {exc}")


def test_the_docs_example_builds_and_checks_as_the_doc_says(tmp_path, tick_midi):
    [example] = [score for name, score in _scores() if name == ARRANGING.name]
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
