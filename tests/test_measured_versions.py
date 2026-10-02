"""Замер языка исполняется ниже планки, и граница проведена импортами.

Планка проекта — 3.14: на ней идут тесты и витрина, и код пишется в её стиле.
Но инвентарь языка меряет и младшие версии (матрица ``inventory`` в
``badges.yml``) запуском из дерева, без установки. Поэтому ниже планки обязана
работать **цепочка замера** — ``glossary.measure`` и то, что он грузит, — и
только она. Остальной пакет свободен от грамматики младших версий.

Набор держит обе стороны границы:

* цепочка разбирается грамматикой младшей версии замера, а число берётся из
  матрицы, а не пишется здесь вторым местом (правило 214);
* запуск замера грузит ровно цепочку — ленивый ``__init__`` не тянет остальное;
* прогоны замера зовут ``glossary.measure``, а не CLI всего пакета;
* ``from __future__ import annotations`` есть в цепочке и нет больше нигде.

Граница названа: ``ast.parse(feature_version=…)`` ловит синтаксис, а не вызов
API, появившегося позже. Вызов ловит живой путь — сам прогон инвентаря на
младшей версии.
"""

import ast
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

from glossary.loader import project_root

ROOT = project_root()
BADGES = ROOT / ".github" / "workflows" / "badges.yml"
PACKAGE = ROOT / "src" / "glossary"

ENTRY = "glossary.measure"
"""Точка входа замера."""

MEASUREMENT = frozenset(
    {"glossary", "glossary._version", "glossary.contracts", "glossary.inventory", ENTRY}
)
"""Цепочка замера: модули, которые исполняются ниже планки."""

FUTURE = "from __future__ import annotations"

TREE = ("src", "scripts", "tests")
"""Где живёт код проекта."""

TIMEOUT = 60
"""Дедлайн на запуск интерпретатора (правило 100)."""


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


def loaded(entry: str, package: str, path: Path) -> set[str]:
    """Модули пакета, которые грузит импорт точки входа в чистом интерпретаторе."""
    probe = (
        f"import sys, {entry}; "
        f"print('\\n'.join(m for m in sys.modules if m.split('.')[0] == {package!r}))"
    )
    done = subprocess.run(  # noqa: S603 — интерпретатор свой, аргументы наши
        [sys.executable, "-c", probe],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
        timeout=TIMEOUT,
        env={**os.environ, "PYTHONPATH": str(path)},
    )
    return set(done.stdout.split())


def module_name(path: Path) -> str:
    """Имя модуля пакета по пути файла."""
    parts = path.relative_to(PACKAGE.parent).with_suffix("").parts
    return ".".join(parts[:-1] if parts[-1] == "__init__" else parts)


def has_future(path: Path) -> bool:
    """Есть ли в модуле импорт отложенных аннотаций."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return any(
        isinstance(node, ast.ImportFrom)
        and node.module == "__future__"
        and any(alias.name == "annotations" for alias in node.names)
        for node in tree.body
    )


# --------------------------------------------------------------------------- #
# Подделки: разбор устроен верно
# --------------------------------------------------------------------------- #


def test_newer_syntax_is_caught_on_a_fake():
    """Подделка: обобщение PEP 695 грамматикой 3.11 не разбирается."""
    assert unparsable("def first[T](xs: list[T]) -> T: ...\n", (3, 11)) is not None
    assert unparsable("def first(xs: list) -> object: ...\n", (3, 11)) is None


def test_eager_import_is_caught_on_a_fake(tmp_path: Path):
    """Подделка: жадный ``__init__`` тянет лишнее, ленивый — нет."""
    package = tmp_path / "fake"
    package.mkdir()
    (package / "leaf.py").write_text("VALUE = 1\n", encoding="utf-8")
    (package / "heavy.py").write_text("VALUE = 2\n", encoding="utf-8")

    (package / "__init__.py").write_text("from fake import heavy\n", encoding="utf-8")
    assert loaded("fake.leaf", "fake", tmp_path) == {"fake", "fake.leaf", "fake.heavy"}

    (package / "__init__.py").write_text("", encoding="utf-8")
    assert loaded("fake.leaf", "fake", tmp_path) == {"fake", "fake.leaf"}


def test_future_import_is_found_on_a_fake(tmp_path: Path):
    """Подделка: импорт находится в теле модуля, а не подстрокой в тексте."""
    with_future = tmp_path / "a.py"
    with_future.write_text(f'"""Док."""\n\n{FUTURE}\n', encoding="utf-8")
    in_text = tmp_path / "b.py"
    in_text.write_text(f'"""Пишется {FUTURE}."""\n', encoding="utf-8")
    assert has_future(with_future)
    assert not has_future(in_text)


# --------------------------------------------------------------------------- #
# Живая половина: что в дереве
# --------------------------------------------------------------------------- #


@pytest.mark.live_surface
def test_measurement_loads_exactly_its_chain():
    """Запуск замера грузит цепочку и ничего больше из пакета."""
    got = loaded(ENTRY, "glossary", ROOT / "src")
    assert got == MEASUREMENT, (
        f"лишнее: {sorted(got - MEASUREMENT)}; не хватает: {sorted(MEASUREMENT - got)}"
    )


@pytest.mark.live_surface
def test_chain_parses_on_the_oldest_measured_version():
    """Каждый модуль цепочки разбирается младшей версией замера."""
    version = oldest_measured()
    broken = {
        name: problem
        for path in sorted(PACKAGE.rglob("*.py"))
        if (name := module_name(path)) in MEASUREMENT
        and (problem := unparsable(path.read_text(encoding="utf-8"), version))
    }
    assert not broken, f"не разбирается на {version}: {broken}"


@pytest.mark.live_surface
def test_measurement_jobs_call_the_entry():
    """Прогоны замера зовут точку входа цепочки, а не CLI всего пакета."""
    workflow: dict[str, Any] = yaml.safe_load(BADGES.read_text(encoding="utf-8"))
    for job in ("inventory", "preview"):
        runs = [step.get("run", "") for step in workflow["jobs"][job]["steps"]]
        assert any(f"python -m {ENTRY}" in run for run in runs), job
        assert not any("python -m glossary " in run for run in runs), job


@pytest.mark.live_surface
def test_future_import_lives_only_in_the_chain():
    """Отложенные аннотации — стиль младших версий: в цепочке есть, вне её нет."""
    chain = {path for path in PACKAGE.rglob("*.py") if module_name(path) in MEASUREMENT}
    missing = sorted(str(p.relative_to(ROOT)) for p in chain if not has_future(p))
    extra = sorted(
        str(path.relative_to(ROOT))
        for top in TREE
        for path in (ROOT / top).rglob("*.py")
        if path not in chain and has_future(path)
    )
    assert not missing, f"цепочке замера нужен {FUTURE}: {missing}"
    assert not extra, f"на планке 3.14 {FUTURE} не нужен: {extra}"
