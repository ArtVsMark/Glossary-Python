"""Планка Python проекта — из ``requires-python``, одним разбором на всех.

Планку читают хук старта облачного окна (``.claude/hooks/session-start.sh``,
он собирает ``.venv`` на ней) и наборы, сверяющие с ней прогоны. Второй разбор
той же строки разошёлся бы с первым молча (правило каталога 214), поэтому он
здесь один.

Запуск::

    python scripts/python_floor.py   # 3.11

Исходы: 0 — планка напечатана; 2 — ``requires-python`` не прочитан.
"""

from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path
from typing import Final

ROOT: Final = Path(__file__).resolve().parent.parent
PYPROJECT: Final = ROOT / "pyproject.toml"

NOT_RUN: Final = 2
"""Планка не прочитана: печатать нечего, и это не «планки нет»."""

FLOOR_RE: Final = re.compile(r">=\s*(\d+)\.(\d+)")
"""Нижняя граница в ``requires-python``. Верхнюю проект не объявляет."""


def floor(pyproject_text: str) -> tuple[int, int]:
    """Планка ``(major, minor)`` из текста ``pyproject.toml``.

    Raises:
        ValueError: Поля нет или нижняя граница не названа.
    """
    project = tomllib.loads(pyproject_text).get("project", {})
    spec = project.get("requires-python")
    if not isinstance(spec, str):
        raise ValueError("в [project] нет requires-python")
    match = FLOOR_RE.search(spec)
    if match is None:
        raise ValueError(f"в requires-python {spec!r} не названа нижняя граница >=X.Y")
    return int(match.group(1)), int(match.group(2))


def main(path: Path = PYPROJECT) -> int:
    """Напечатать планку ``X.Y``."""
    try:
        major, minor = floor(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as refusal:
        print(f"планка не прочитана из {path}: {refusal}", file=sys.stderr)
        return NOT_RUN
    print(f"{major}.{minor}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
