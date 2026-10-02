"""Пакет разбирается на каждой версии, которую меряет инвентарь языка.

Планка проекта — 3.14: на ней идут тесты и витрина. Но инвентарь языка меряет
и старшие, и младшие версии (матрица ``inventory`` в ``badges.yml``), и делает
это запуском пакета из дерева — без установки, потому что ``requires-python``
установку ниже планки запрещает. Поэтому код пакета обязан разбираться
грамматикой самой младшей измеряемой версии. Число берётся из матрицы, а не
пишется здесь вторым местом (правило 214).

Граница названа: ``ast.parse(feature_version=…)`` ловит синтаксис, а не вызов
API, появившегося позже. Вызов ловит живой путь — сам прогон инвентаря на
младшей версии.
"""

from __future__ import annotations

import ast
from typing import Any

import pytest
import yaml

from glossary.loader import project_root

ROOT = project_root()
BADGES = ROOT / ".github" / "workflows" / "badges.yml"
PACKAGE = ROOT / "src" / "glossary"


def oldest_measured() -> tuple[int, int]:
    """Младшая версия матрицы инвентаря."""
    workflow: dict[str, Any] = yaml.safe_load(BADGES.read_text(encoding="utf-8"))
    versions = workflow["jobs"]["inventory"]["strategy"]["matrix"]["python-version"]
    parsed = [tuple(int(part) for part in str(v).split(".")) for v in versions]
    return min(parsed)  # type: ignore[return-value]


def unparsable(source: str, version: tuple[int, int]) -> str | None:
    """Почему текст не разбирается грамматикой версии; ``None`` — разбирается."""
    try:
        ast.parse(source, feature_version=version)
    except SyntaxError as refusal:
        return f"{refusal.msg} (строка {refusal.lineno})"
    return None


def test_newer_syntax_is_caught_on_a_fake():
    """Подделка: обобщение PEP 695 грамматикой 3.11 не разбирается."""
    assert unparsable("def first[T](xs: list[T]) -> T: ...\n", (3, 11)) is not None
    assert unparsable("def first(xs: list) -> object: ...\n", (3, 11)) is None


@pytest.mark.live_surface
def test_package_parses_on_the_oldest_measured_version():
    """Живая половина: каждый модуль пакета разбирается младшей версией замера."""
    version = oldest_measured()
    broken = {
        path.name: problem
        for path in sorted(PACKAGE.rglob("*.py"))
        if (problem := unparsable(path.read_text(encoding="utf-8"), version))
    }
    assert not broken, f"не разбирается на {version}: {broken}"
