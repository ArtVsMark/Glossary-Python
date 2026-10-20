"""Хук окна исполняется интерпретатором планки (#274, правило каталога 217).

Подделки показывают, что разбор устроен верно: голый ``python3`` находится,
имя с планкой, ``uv python``, проза и комментарий — нет, стартовый хук
исключён по роли. Отдельно держатся два свойства обёртки стража: ``floor.sh``
читает ту же планку, что ``scripts/python_floor.py``, а без интерпретатора
планки обёртка закрывает толчок и heredoc. Живая половина гоняет гейт по дереву.
"""

import json
import os
import subprocess
from pathlib import Path

import pytest

import check_hook_interpreter as gate
import python_floor
from glossary.loader import project_root

ROOT = project_root()
HOOKS = ROOT / ".claude" / "hooks"


@pytest.mark.parametrize(
    "line",
    [
        '[ -x "$py" ] || py=python3',
        "exec python3 scripts/window_guard.py",
        "cd x && python scripts/a.py",
    ],
)
def test_bare_interpreter_is_found(line: str) -> None:
    assert gate.bare_calls(line)


@pytest.mark.parametrize(
    "line",
    [
        'py=$(command -v "python$floor")',
        "exec /opt/venv/bin/python guard.py",
        "/opt/uv/bin/uv python install 3.14",
        'echo "поставьте python3.14 вручную"',
        "# раньше здесь был python3",
        "exec python3.14 guard.py",
    ],
)
def test_floor_named_interpreter_passes(line: str) -> None:
    assert not gate.bare_calls(line)


def _tree(tmp_path: Path, hooks: dict[str, str], settings: dict[str, object]) -> Path:
    """Дерево-подделка: настройки и обёртки хуков."""
    (tmp_path / ".claude" / "hooks").mkdir(parents=True)
    (tmp_path / ".claude" / "settings.json").write_text(
        json.dumps(settings), encoding="utf-8"
    )
    for name, text in hooks.items():
        (tmp_path / ".claude" / "hooks" / name).write_text(text, encoding="utf-8")
    return tmp_path


def _settings(**events: str) -> dict[str, object]:
    return {
        "hooks": {
            event: [{"hooks": [{"type": "command", "command": command}]}]
            for event, command in events.items()
        }
    }


def test_start_hook_is_excluded_by_role_not_name(tmp_path: Path) -> None:
    root = _tree(
        tmp_path,
        {"boot.sh": "reader=$(command -v python3)\n", "guard.sh": "exec python3 g.py\n"},
        _settings(
            SessionStart='"$CLAUDE_PROJECT_DIR/.claude/hooks/boot.sh"',
            PreToolUse='"$CLAUDE_PROJECT_DIR/.claude/hooks/guard.sh"',
        ),
    )
    assert gate.main(["--root", str(root)]) == 1
    found = gate.findings(
        root,
        gate.hook_commands(
            json.loads((root / ".claude" / "settings.json").read_text(encoding="utf-8"))
        ),
    )
    assert [line.split(":")[0] for line in found] == [".claude/hooks/guard.sh"]


def test_interpreter_in_settings_is_found(tmp_path: Path) -> None:
    root = _tree(tmp_path, {}, _settings(PreToolUse="python3 scripts/guard.py"))
    assert gate.main(["--root", str(root)]) == 1


def test_no_hooks_is_not_run(tmp_path: Path) -> None:
    root = _tree(tmp_path, {}, {"hooks": {}})
    assert gate.main(["--root", str(root)]) == gate.NOT_RUN


def test_unreadable_settings_is_not_run(tmp_path: Path) -> None:
    assert gate.main(["--root", str(tmp_path)]) == gate.NOT_RUN


def _shell_floor(pyproject: Path) -> str:
    done = subprocess.run(  # noqa: S603 — команда собрана из констант
        [  # noqa: S607 — sh ищется в PATH
            "sh",
            "-c",
            f'. "{HOOKS / "floor.sh"}"; planka_floor "$1"',
            "sh",
            str(pyproject),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
        check=True,
    )
    return done.stdout.strip()


@pytest.mark.parametrize("spec", ['">=3.14"', '">= 3.11"', '">=3.12,<4"', '"~=3.13"'])
def test_shell_floor_agrees_with_python_floor(tmp_path: Path, spec: str) -> None:
    """Второй разбор планки — sed без Python — совпадает с первым (214)."""
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(f"[project]\nrequires-python = {spec}\n", encoding="utf-8")
    if not spec.startswith('">'):
        with pytest.raises(ValueError, match="нижняя граница"):
            python_floor.floor(pyproject.read_text(encoding="utf-8"))
        return
    major, minor = python_floor.floor(pyproject.read_text(encoding="utf-8"))
    assert _shell_floor(pyproject) == f"{major}.{minor}"


def _run_wrapper(project: Path, command: str) -> subprocess.CompletedProcess[str]:
    """Обёртка стража в дереве, где интерпретатора планки нет."""
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(project)}
    event = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})
    return subprocess.run(  # noqa: S603 — путь к обёртке наш
        ["sh", str(HOOKS / "pre_tool_use.sh")],  # noqa: S607
        input=event,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        timeout=30,
        check=False,
    )


@pytest.fixture
def floorless(tmp_path: Path) -> Path:
    """Проект с планкой, интерпретатора которой нет нигде: 3.99."""
    (tmp_path / ".claude" / "hooks").mkdir(parents=True)
    (tmp_path / ".claude" / "hooks" / "floor.sh").write_text(
        (HOOKS / "floor.sh").read_text(encoding="utf-8"), encoding="utf-8"
    )
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nrequires-python = ">=3.99"\n', encoding="utf-8"
    )
    return tmp_path


@pytest.mark.parametrize("command", ["git push origin main", "cat <<EOF\nx\nEOF"])
def test_without_floor_interpreter_guarded_forms_are_closed(
    floorless: Path, command: str
) -> None:
    done = _run_wrapper(floorless, command)
    assert done.returncode == 2, "без сторожа толчок и heredoc закрыты, а не пропущены"
    assert "python3.99" in done.stderr


def test_without_floor_interpreter_other_commands_pass(floorless: Path) -> None:
    assert _run_wrapper(floorless, "ls -la").returncode == 0


@pytest.mark.live_surface
def test_live_hooks_run_on_the_floor() -> None:
    """Живая половина: хуки дерева исполняются интерпретатором планки."""
    assert gate.main(["--root", str(ROOT)]) == 0
    assert _shell_floor(ROOT / "pyproject.toml") == "{}.{}".format(
        *python_floor.floor((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    )
