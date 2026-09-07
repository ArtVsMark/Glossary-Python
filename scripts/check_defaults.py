#!/usr/bin/env python3
"""Умолчание, взятое из окружения, задаётся явно.

Правило каталога 176: умолчание, вычисляемое из **окружения**, — скрытая
зависимость от платформы, и матрица прогонов её не доказывает. Кодировка локали
у ``text=True``, часовой пояс у naive-времени, регистр имён файловой системы:
такой код зелен на одних ячейках матрицы и красен на других, но краснеет он ещё
и **только на подходящих данных**. Два условия должны совпасть, чтобы дефект
проявился, — значит зелёная матрица говорит «совпадения не случилось на этих
данных», а не «умолчание задано верно».

ПОЭТОМУ РАЗБОР ИСХОДНИКА, А НЕ ПРОГОН. Правило говорит это прямо, и
человеческой половины у требования нет вовсе: «encoding назван» и «пояс назван»
следуют из текста программы целиком.

ЧТО ГЕЙТ ОХРАНЯЕТ. Не долг, а достигнутое: на момент заведения дерево правилу
соответствовало. Пустым он от этого не становится — предмет у него был живым в
тот же день. ``subprocess.run`` в ``tests/test_data_integrity.py`` стоял с
``text=True`` без ``encoding=``: на ячейке матрицы с локалью cp1252 разбор
вывода развалился бы на кириллице, а на linux оставался зелёным. Нашёл это
разбор ответа каталогу, а не гейт, — гейт заведён, чтобы второй раз не искали
руками, и прогнан по тому самому вызову (``tests/test_check_defaults.py``).

ЧЕГО ГЕЙТ НЕ ЛОВИТ, названо здесь, а не подразумевается (правило 056):

* **умолчание за вызовом.** ``functools.partial(open)`` и обёртка вокруг
  ``subprocess`` разбором не видны: гейт судит о вызове, а не о том, во что он
  превратится;
* **регистр имён файловой системы.** Третий пример из правила: он не выражается
  ни одним аргументом вызова, и проверять его тут нечем;
* **верность значения.** ``encoding="cp1251"`` пройдёт: правило требует, чтобы
  умолчание было НАЗВАНО, а не чтобы оно было верным.

Запуск::

    python scripts/check_defaults.py            # гейт по дереву проекта
    python scripts/check_defaults.py --root DIR # то же по другому дереву

Исходы: 0 — чисто; 1 — есть находки; 2 — проверка не отработала.
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Final, NamedTuple

if TYPE_CHECKING:
    from collections.abc import Iterator

ROOT: Final = Path(__file__).resolve().parent.parent

TREES: Final = ("src", "scripts", "tests")
"""Где разбирается код. Тесты входят: платформа не делает им скидки."""

SKIP: Final = ("__pycache__", ".venv", "build", "dist")

READERS: Final = {
    # имя вызова: индекс позиционного аргумента, которым можно передать encoding
    "open": 3,
    "read_text": 0,
    "write_text": 1,
}
"""Текстовые обращения к файлам и место encoding среди позиционных аргументов.

``open(file, mode, buffering, encoding)``, ``Path.read_text(encoding)``,
``Path.write_text(data, encoding)`` — позиционная форма законна и встречается
в этом дереве, поэтому проверять только ключевое слово нельзя.
"""

MODE_POSITION: Final = {"open": 1}
"""Где искать режим: ``open(file, mode)``. У read_text/write_text режима нет."""

SPAWNERS: Final = {"run", "Popen", "check_output", "check_call", "call"}
TEXT_FLAGS: Final = ("text", "universal_newlines")


class Finding(NamedTuple):
    """Находка разбора.

    Attributes:
        path: Путь файла от корня дерева.
        line: Номер строки вызова.
        what: Что именно не названо.
    """

    path: str
    line: int
    what: str

    def __str__(self) -> str:
        """Находка в привычной форме ``файл:строка`` (правило 158)."""
        return f"{self.path}:{self.line}: {self.what}"


def _callee(node: ast.Call) -> str:
    """Имя вызываемого: последний сегмент, без разбора цепочки."""
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    if isinstance(node.func, ast.Name):
        return node.func.id
    return ""


def _keywords(node: ast.Call) -> set[str]:
    return {word.arg for word in node.keywords if word.arg}


def _literal(node: ast.expr | None) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _is_binary(node: ast.Call, callee: str) -> bool:
    """Двоичный режим кодировки не имеет — и требовать её было бы неверно."""
    position = MODE_POSITION.get(callee)
    mode = None
    if position is not None and len(node.args) > position:
        mode = _literal(node.args[position])
    for word in node.keywords:
        if word.arg == "mode":
            mode = _literal(word.value)
    return bool(mode and "b" in mode)


def _is_datetime_now(node: ast.Call) -> bool:
    """Именно ``datetime.now``, а не любой помощник с таким именем.

    Проверка на одно имя ловила бы собственный ``contracts.now()`` — обёртку,
    которая пояс как раз передаёт. Это тот же промах, что и проверка отношения
    по подстроке (правило 166): условие выполняется не на том предмете.
    """
    func = node.func
    if not isinstance(func, ast.Attribute) or func.attr != "now":
        return False
    owner = func.value
    if isinstance(owner, ast.Name):
        return owner.id == "datetime"
    return isinstance(owner, ast.Attribute) and owner.attr == "datetime"


def inspect(source: str, name: str) -> list[Finding]:
    """Разобрать модуль и собрать умолчания, взятые из окружения.

    Args:
        source: Текст модуля.
        name: Имя файла для сообщений.

    Returns:
        Находки в порядке появления.
    """
    findings: list[Finding] = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call):
            continue
        callee = _callee(node)
        words = _keywords(node)

        if callee in READERS and not _is_binary(node, callee):
            positional = READERS[callee]
            named = "encoding" in words or len(node.args) > positional
            if not named:
                findings.append(Finding(name, node.lineno, f"{callee}() без encoding="))

        spawns_text = callee in SPAWNERS and any(f in words for f in TEXT_FLAGS)
        if spawns_text and "encoding" not in words:
            findings.append(Finding(name, node.lineno, f"{callee}(text=…) без encoding="))

        if _is_datetime_now(node) and not node.args and "tz" not in words:
            findings.append(
                Finding(name, node.lineno, "datetime.now() без часового пояса")
            )

    return sorted(findings)


def _modules(root: Path) -> Iterator[tuple[Path, str]]:
    for tree in TREES:
        for path in sorted((root / tree).rglob("*.py")):
            if any(part in SKIP for part in path.parts):
                continue
            yield path, str(path.relative_to(root))


def scan(root: Path) -> tuple[list[Finding], int]:
    """Находки по дереву и число разобранных модулей.

    Второе число нужно само по себе: ноль находок при нуле модулей означает не
    «чисто», а «нечего смотреть» (правила 039, 075).
    """
    findings: list[Finding] = []
    seen = 0
    for path, name in _modules(root):
        seen += 1
        findings.extend(inspect(path.read_text(encoding="utf-8"), name))
    return findings, seen


def main(argv: list[str] | None = None) -> int:
    """Точка входа.

    Args:
        argv: Аргументы командной строки; ``None`` — взять из ``sys.argv``.

    Returns:
        Код возврата процесса.
    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args(argv)

    findings, seen = scan(args.root)
    if not seen:
        print(
            "проверка не отработала: под "
            f"{args.root} не разобрано ни одного модуля. Ожидались деревья "
            f"{', '.join(TREES)} — проверьте, что запуск идёт из репозитория",
            file=sys.stderr,
        )
        return 2

    if findings:
        print("умолчание взято из окружения, а не задано явно:", file=sys.stderr)
        for finding in findings:
            print(f"  • {finding}", file=sys.stderr)
        print(
            "\n  Такой код зелен на одних ячейках матрицы и красен на других,\n"
            "  и только на подходящих данных: зелёная матрица говорит\n"
            "  «совпадения не случилось», а не «умолчание задано верно»\n"
            "  (правило 176).",
            file=sys.stderr,
        )
        return 1

    print(f"умолчания заданы явно: разобрано модулей {seen}, находок нет")
    return 0


if __name__ == "__main__":
    sys.exit(main())
