"""Сторож окна: толчок в чужую ветку и heredoc с экранированием (012, 013).

Подделки показывают, что разбор устроен верно: какие формы команды он узнаёт и
какие пропускает. Живая половина — что хук окна действительно зовёт сторожа:
без регистрации в ``.claude/settings.json`` верный разбор не защищает ничего.
"""

import ast
import json
from pathlib import Path

import pytest

import window_guard as guard
from glossary.loader import project_root

ROOT: Path = project_root()


@pytest.mark.parametrize(
    ("command", "targets"),
    [
        ("git push", []),
        ("git push -u origin claude/x", ["claude/x"]),
        ("git push origin HEAD:claude/y", []),
        ("git push origin +claude/x:claude/z", ["claude/z"]),
        ("git push origin :claude/old", []),
        ("git push --delete origin claude/old", []),
        ("git -C /tmp/r push origin feature", ["feature"]),
        ("cd /r && git push -q origin main 2>&1 | tail -1", ["main"]),
        ("for i in 1 2; do git push origin claude/x && break; done", ["claude/x"]),
        ("git push origin refs/heads/claude/x", ["claude/x"]),
        ("echo git push origin main", []),
    ],
)
def test_push_targets_are_read_from_the_command(command: str, targets: list[str]):
    assert guard.push_targets(command) == targets


def test_push_inside_a_heredoc_body_is_data_not_an_action():
    command = "cat > notes.md <<'EOF'\ngit push origin main\nEOF"
    assert guard.push_targets(command) == []


def test_foreign_branch_is_refused():
    reason = guard.verdict("git push -u origin claude/other", "claude/mine")
    assert reason is not None and "012" in reason


def test_own_branch_passes():
    assert guard.verdict("git push -u origin claude/mine", "claude/mine") is None


def test_detached_head_does_not_refuse():
    """Голова не названа — сравнивать не с чем, ложный отказ дороже пропуска."""
    assert guard.verdict("git push origin claude/x", None) is None


def test_unquoted_heredoc_with_backslash_is_refused():
    command = "cat > a.py <<EOF\nprint('a\\nb')\nEOF"
    reason = guard.verdict(command, None)
    assert reason is not None and "013" in reason


def test_quoted_heredoc_with_backslash_passes():
    command = "cat > a.py <<'EOF'\nprint('a\\nb')\nEOF"
    assert guard.verdict(command, None) is None


def test_unquoted_heredoc_without_backslash_passes():
    assert guard.verdict("cat > a.txt <<EOF\nhello $USER\nEOF", None) is None


def test_unreadable_event_is_let_through():
    assert guard.main("не json") == guard.NOT_RUN
    assert guard.main(json.dumps({"tool_input": {}})) == guard.NOT_RUN


def test_refusal_exits_with_the_blocking_code(capsys: pytest.CaptureFixture[str]):
    event = json.dumps({"tool_input": {"command": "cat > a <<EOF\n\\n\nEOF"}})
    assert guard.main(event) == guard.REJECTED
    assert "013" in capsys.readouterr().err


@pytest.mark.live_surface
def test_window_hook_calls_the_guard():
    """Хук PreToolUse на Bash зарегистрирован и ведёт к существующему сторожу."""
    settings = json.loads((ROOT / ".claude" / "settings.json").read_text("utf-8"))
    entries = settings["hooks"]["PreToolUse"]
    commands = [
        hook["command"]
        for entry in entries
        if entry.get("matcher") == "Bash"
        for hook in entry["hooks"]
    ]
    assert any("pre_tool_use.sh" in command for command in commands)
    script = (ROOT / ".claude" / "hooks" / "pre_tool_use.sh").read_text("utf-8")
    assert "scripts/window_guard.py" in script
    assert (ROOT / "scripts" / "window_guard.py").exists()


def test_guard_parses_on_the_oldest_window_python():
    """Хук стартует системным python3 окна, а он бывает ниже планки проекта."""
    source = (ROOT / "scripts" / "window_guard.py").read_text("utf-8")
    ast.parse(source, feature_version=(3, 11))


def test_hook_protocol_blocks_only_on_rejection():
    """Протокол хука: 2 отвергает, 1 — неблокирующая ошибка, 0 — пропуск."""
    assert guard.HOOK_CODE[guard.REJECTED] == 2
    assert guard.HOOK_CODE[guard.NOT_RUN] not in {0, 2}
    assert guard.HOOK_CODE[guard.PASSED] == 0


def test_own_branch_push_passes_through_main():
    branch = guard.current_branch()
    if branch is None:
        pytest.skip("голова отделена — сравнивать не с чем")
    event = json.dumps({"tool_input": {"command": f"git push origin {branch}"}})
    assert guard.main(event) == guard.PASSED
