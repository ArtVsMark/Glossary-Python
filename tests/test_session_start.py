"""Хук старта облачного окна объявлен и вне облака не делает ничего.

Сам хук ходит в сеть и ставит интерпретатор — в наборе это не воспроизводится.
Набор держит то, что следует из дерева: хук объявлен в настройках, исполним,
вне облака молчит и читает планку тем же разбором, что и все.
"""

from __future__ import annotations

import json
import os
import subprocess

import pytest

from glossary.loader import project_root

ROOT = project_root()
HOOK = ROOT / ".claude" / "hooks" / "session-start.sh"
SETTINGS = ROOT / ".claude" / "settings.json"


@pytest.mark.live_surface
def test_hook_is_declared_and_executable():
    """Хук, которого нет в настройках, не запустится ни в одном окне."""
    settings = json.loads(SETTINGS.read_text(encoding="utf-8"))
    commands = [
        hook["command"]
        for group in settings["hooks"]["SessionStart"]
        for hook in group["hooks"]
    ]
    assert any(".claude/hooks/session-start.sh" in c for c in commands)
    assert os.access(HOOK, os.X_OK), "хук не исполним — окно его не запустит"


def test_hook_does_nothing_outside_the_cloud():
    """На машине владельца окружение его: хук выходит, ничего не тронув."""
    env = {k: v for k, v in os.environ.items() if k != "CLAUDE_CODE_REMOTE"}
    done = subprocess.run(  # noqa: S603 — наш хук, не чужой ввод
        [str(HOOK)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        check=False,
        timeout=30,
    )
    assert (done.returncode, done.stdout, done.stderr) == (0, "", "")


def test_hook_reads_the_floor_through_the_shared_reader():
    """Второй разбор requires-python разошёлся бы с первым молча (214)."""
    text = HOOK.read_text(encoding="utf-8")
    assert "scripts/python_floor.py" in text
    body = text.split("set -uo pipefail", 1)[1]
    parsing = [
        line
        for line in body.splitlines()
        if "requires-python" in line and "warn" not in line
    ]
    assert not parsing, f"хук разбирает планку сам: {parsing}"
