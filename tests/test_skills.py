import json
import re
from pathlib import Path

import typer

from pianoize import corrections, timeline
from pianoize.cli import app

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "polish-cover"
POLISHING = ROOT / "docs" / "polishing.md"

# A command line is code; prose such as "pianoize reads" is not one.
CODE = re.compile(r"```.*?```|`[^`\n]+`", re.DOTALL)
COMMAND = re.compile(r"\bpianoize (?=[a-z])")
NAME = re.compile(r"[a-z][a-z-]*")
FLAG = re.compile(r"(?<![^\s\[])--?[A-Za-z][A-Za-z-]*")  # after a space or a [, not inside a path


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _documents() -> list[Path]:
    return [SKILL / "SKILL.md", *sorted((SKILL / "references").glob("*.md")), POLISHING]


def test_skill_is_written_for_this_schema():
    skill = _text(SKILL / "SKILL.md")
    assert re.findall(r"written for version (\d+)", skill) == [str(timeline.SCHEMA_VERSION)]


def test_skill_and_docs_name_this_spec_version():
    version = str(corrections.SPEC_VERSION)
    skill = _text(SKILL / "SKILL.md")
    assert re.findall(r"correction spec version (\d+)", skill) == [version]
    assert re.findall(r"`spec_version (\d+)`", _text(POLISHING)) == [version]
    for path in _documents():  # the JSON examples carry the number too
        assert set(re.findall(r'"spec_version": (\d+)', _text(path))) <= {version}, path.name


def _command_lines(text: str):
    """Each `pianoize <command> …` in the code of a document: the command and its flags."""
    for code in CODE.findall(text):
        for line in code.splitlines():
            for call in COMMAND.split(line)[1:]:
                yield NAME.match(call).group(), set(FLAG.findall(call))


def test_named_commands_and_their_options_exist():
    commands = typer.main.get_command(app).commands
    for path in _documents():
        lines = list(_command_lines(_text(path)))
        for name, flags in lines:
            assert name in commands, (path.name, name)
            params = commands[name].params
            options = {opt for param in params for opt in (*param.opts, *param.secondary_opts)}
            assert flags <= options | {"--help"}, (path.name, name, flags - options)
        if path.name == "SKILL.md":
            assert lines, "SKILL.md names no pianoize command"


def test_references_need_no_plugin_root():
    # Claude Code substitutes ${CLAUDE_PLUGIN_ROOT} only in SKILL.md, never in the files it names.
    for path in (SKILL / "references").glob("*.md"):
        assert "CLAUDE_PLUGIN_ROOT" not in _text(path), path.name


def test_manifests_leave_the_version_to_pyproject():
    plugin = json.loads(_text(ROOT / ".claude-plugin" / "plugin.json"))
    marketplace = json.loads(_text(ROOT / ".claude-plugin" / "marketplace.json"))
    assert "version" not in plugin
    assert [entry["source"] for entry in marketplace["plugins"]] == ["./"]
    assert not any("version" in entry for entry in marketplace["plugins"])
