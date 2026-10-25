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
    "arrange-vocal": ROOT / "docs" / "arranging.md",
    "prepare-song": ROOT / "docs" / "preparing.md",
    "make-video": ROOT / "docs" / "rendering.md",
}
POLISHING = SKILLS["polish-cover"]
ARRANGING = SKILLS["arrange-cover"]
ARRANGING_SKILLS = ("arrange-cover", "arrange-transcription", "arrange-vocal")

# A command line is code; prose such as "pianoize reads" is not one.
CODE = re.compile(r"```.*?```|`[^`\n]+`", re.DOTALL)
COMMAND = re.compile(r"\bpianoize (?=[a-z])")
NAME = re.compile(r"[a-z][a-z-]*")
FLAG = re.compile(r"(?<![^\s\[])--?[A-Za-z][A-Za-z-]*")  # after a space or a [, not inside a path
# A file a skill names in code, from the skill's directory: one of its references, its own SKILL.md
# or another skill's, or a rule file the arranging skills share.
REFERENCE = re.compile(
    r"`(references/[\w.-]+\.md|(?:\.\./[a-z-]+/)?SKILL\.md|\.\./\.\./arranging/[\w-]+\.md)`"
)
# A relative path in code: each must be one REFERENCE matches, or it would go unchecked.
RELATIVE = re.compile(r"`(\.\./[^`\s]+\.md)`")
# The rule files the arranging skills share, which their dispatch prompts name by path, and the
# names the shared files use for each other.
SHARED = ROOT / "arranging"
PROMPT_FILE = re.compile(r"<root>/arranging/([\w-]+\.md)")
BARE = re.compile(r"`([a-z-]+\.md)`")
# Each arranging skill's front end, and its modes' right- and left-hand files, the default first.
# A skill without modes has one combination, under None, whose hands its prompt names.
COMBINATIONS = {
    "arrange-cover": (
        "front-end-cover.md",
        {
            "playable": ("right-hand-playable.md", "left-hand-cover.md"),
            "full": ("right-hand-full.md", "left-hand-band-layers.md"),
        },
    ),
    "arrange-transcription": (
        "front-end-transcription.md",
        {
            "full": ("right-hand-full.md", "left-hand-band-layers.md"),
            "playable": ("right-hand-playable.md", "left-hand-accompaniment.md"),
        },
    ),
    "arrange-vocal": (
        "front-end-transcription.md",
        {None: ("right-hand-full.md", "left-hand-accompaniment.md")},
    ),
}
# A front end or a hand file, wherever a skill names it.
RULE_FILE = re.compile(r"\b(?:front-end|right-hand|left-hand)-[a-z-]+\.md")
# The skills that read no cover, and the rule each states.
CLEAN_ROOM_SKILLS = ("arrange-vocal", "arrange-transcription")
CLEAN_ROOM_RULE = re.compile(r"^- \*\*Clean room\.\*\* .*$", re.MULTILINE)
# A row of an arranging skill's "Modes" table: the mode, whether it is the default, and its hands.
MODE_ROW = re.compile(
    r"^\| `(\w+)`(, the default)? \| `<root>/arranging/([\w-]+\.md)` "
    r"\| `<root>/arranging/([\w-]+\.md)` \|$",
    re.MULTILINE,
)

# A fenced code block's text; under a list item its fences are indented.
FENCED = re.compile(r"^[ \t]*```[^\n]*\n(.*?)^[ \t]*```", re.DOTALL | re.MULTILINE)
# A line only a score has: its format line, a bar or a copy.
SCORE_LINE = re.compile(r"^\s*(format\s|bar\s+\d+\s*\||bars\s+\d+-\d+\s*=)", re.MULTILINE)
# The rows of docs/arranging.md's chord quality table, the one headed `| symbol |`.
QUALITY_TABLE = re.compile(r"^\| symbol \|.*\n\|[-| ]+\n((?:\|.*\n)+)", re.MULTILINE)


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _documents(skill: str) -> list[Path]:
    """A skill's SKILL.md, its references, the shared rule files for an arranging skill, and its
    doc."""
    directory = ROOT / "skills" / skill
    shared = sorted(SHARED.glob("*.md")) if skill in ARRANGING_SKILLS else []
    references = sorted((directory / "references").glob("*.md"))
    return [directory / "SKILL.md", *references, *shared, SKILLS[skill]]


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
    """(file name, text) of each score in a code block of an arranging skill's documents."""
    return [
        (path.name, block)
        for path in _documents(skill)
        for block in FENCED.findall(_text(path))
        if SCORE_LINE.search(block)
    ]


def test_arrange_skill_and_docs_name_this_format_version():
    version = str(arrangement.FORMAT_VERSION)
    session = _text(SHARED / "main-session.md")
    assert re.findall(r"score format version (\d+)", session) == [version]
    for skill in ARRANGING_SKILLS:
        assert re.findall(r"`format (\d+)`", _text(SKILLS[skill])) == [version], skill
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
        if path == SHARED / "workflow.md":
            assert {"build-arrangement", "check-arrangement"} <= {name for name, _ in lines}


def test_the_transcription_front_end_builds_the_grid():
    lines = list(_command_lines(_text(SHARED / "front-end-transcription.md")))
    assert "build-grid" in {name for name, _ in lines}


def test_the_workflow_dumps_the_band_in_every_bar():
    dumps = [
        flags
        for name, flags in _command_lines(_text(SHARED / "workflow.md"))
        if name == "dump-bars"
    ]
    assert any({"--every-bar", "--drums"} <= flags for flags in dumps)
    assert any("--every-note" in flags for flags in dumps)


def _prompt(text: str, skill: str) -> str:
    """An arranging skill's dispatch prompt: the code block that opens with its `Skill:` line."""
    [prompt] = [block for block in FENCED.findall(text) if block.startswith(f"Skill: {skill}\n")]
    return prompt


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
    session = _text(SHARED / "main-session.md")
    assert "`pianoize:arranger`" in session
    assert "<root>/agents/arranger.md" in session  # the fallback without the type
    for skill in ARRANGING_SKILLS:
        text = _text(ROOT / "skills" / skill / "SKILL.md")
        assert "Workflow: <root>/arranging/workflow.md" in text, skill
        assert "`../../arranging/main-session.md`" in text, skill  # its only route to the steps
        assert skill in _text(agent), skill


@pytest.mark.parametrize("skill", ARRANGING_SKILLS)
def test_each_arranging_skill_names_its_combination(skill):
    text = _text(ROOT / "skills" / skill / "SKILL.md")
    front_end, modes = COMBINATIONS[skill]
    rows = MODE_ROW.findall(text)
    lines = _prompt(text, skill).splitlines()
    keys = [line.split(":", 1)[0] for line in lines]
    files = ["Workflow", "Front end", "Right hand", "Left hand"]
    assert [key for key in keys if key in files] == files, keys  # each once, in this order
    assert lines[keys.index("Workflow")] == "Workflow: <root>/arranging/workflow.md"
    assert lines[keys.index("Front end")] == f"Front end: <root>/arranging/{front_end}"
    if None in modes:  # one combination: no "Modes" table, and the prompt names the hands
        [(right, left)] = modes.values()
        assert rows == []
        assert lines[keys.index("Right hand")] == f"Right hand: <root>/arranging/{right}"
        assert lines[keys.index("Left hand")] == f"Left hand: <root>/arranging/{left}"
    else:
        assert [(mode, right, left) for mode, _, right, left in rows] == [
            (mode, *hands) for mode, hands in modes.items()
        ]
        assert [bool(default) for _, default, _, _ in rows] == [True] + [False] * (len(modes) - 1)
    # Nowhere does it name a front end or a hand file outside its combinations.
    combined = {front_end, *(name for hands in modes.values() for name in hands)}
    assert set(RULE_FILE.findall(text)) == combined
    for name in PROMPT_FILE.findall(text):
        assert (SHARED / name).is_file(), name


@pytest.mark.parametrize("skill", CLEAN_ROOM_SKILLS)
def test_the_clean_room_skills_read_no_cover(skill):
    # It asks for no cover and gives the arranger none, under the rule both skills state alike.
    text = _text(ROOT / "skills" / skill / "SKILL.md")
    assert "Cover:" not in _prompt(text, skill)
    assert "<cover>" not in text and "`cover.mid`" not in text
    [rule] = CLEAN_ROOM_RULE.findall(text)
    for other in CLEAN_ROOM_SKILLS:
        assert CLEAN_ROOM_RULE.findall(_text(ROOT / "skills" / other / "SKILL.md")) == [rule], other


def test_the_notes_record_the_dispatch_for_a_later_session():
    # A revision in a new conversation dispatches what wrote the score, whichever skill loaded.
    blocks = FENCED.findall(_text(SHARED / "workflow.md"))
    [outline] = [block for block in blocks if block.startswith("# <song>: arranging notes\n")]
    first = re.split(r"^## ", outline, flags=re.MULTILINE)[1].splitlines()
    assert first[0] == "Dispatch"
    lines = dict(line.removeprefix("- ").split(": ", 1) for line in first[1:])
    assert list(lines) == ["Skill", "Front end", "Right hand", "Left hand"]
    front_end, modes = COMBINATIONS[lines["Skill"]]  # the example is a real combination
    files = [PROMPT_FILE.fullmatch(path)[1] for path in list(lines.values())[1:]]
    assert files[0] == front_end and tuple(files[1:]) in modes.values()
    assert '"Dispatch"' in _text(SHARED / "main-session.md")


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
    for path in documents:  # a wrong depth, `../arranging/…`, matches no REFERENCE
        for name in RELATIVE.findall(_text(path)):
            assert REFERENCE.fullmatch(f"`{name}`"), (path.name, name)


def test_what_the_shared_files_name_exists():
    shared = sorted(SHARED.glob("*.md"))
    assert shared
    for path in shared:
        for name in BARE.findall(_text(path)):
            if name != "notes.md":  # the arranger's own output
                found = (SHARED / name).is_file() or (ROOT / "docs" / name).is_file()
                assert found, (path.name, name)


def test_no_skill_cites_another_skills_references():
    # What two skills share is in arranging/, not in one skill's references.
    documents = [
        *sorted((ROOT / "skills").glob("*/SKILL.md")),
        *sorted((ROOT / "skills").glob("*/references/*.md")),
        *sorted(SHARED.glob("*.md")),
    ]
    assert documents
    for path in documents:
        assert not re.search(r"\.\./[a-z-]+/references/", _text(path)), path


def test_references_need_no_plugin_root():
    # Claude Code substitutes ${CLAUDE_PLUGIN_ROOT} only in SKILL.md, never in the files it names.
    references = [
        *sorted(SHARED.glob("*.md")),
        *sorted((ROOT / "skills").glob("*/references/*.md")),
    ]
    assert references
    for path in references:
        assert "CLAUDE_PLUGIN_ROOT" not in _text(path), path


def test_manifests_leave_the_version_to_pyproject():
    plugin = json.loads(_text(ROOT / ".claude-plugin" / "plugin.json"))
    marketplace = json.loads(_text(ROOT / ".claude-plugin" / "marketplace.json"))
    assert "version" not in plugin
    assert [entry["source"] for entry in marketplace["plugins"]] == ["./"]
    assert not any("version" in entry for entry in marketplace["plugins"])
