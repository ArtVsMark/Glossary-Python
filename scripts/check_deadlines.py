#!/usr/bin/env python3
"""У всякого ожидания назван срок: и у процесса, и у работы конвейера.

Правило каталога 100: у порождённого процесса есть дедлайн. Ожидание без срока
не отказывает — оно **висит**, и снаружи это неотличимо от медленной работы:
ни находки, ни отказа, ни следа. Платит за это тот, кто ждёт.

ЗАМЕР, ИЗ-ЗА КОТОРОГО ГЕЙТ ЗАВЕДЁН, И ОН НЕ ПРО КОД. Разбор дерева показал, что
порождения процесса в ``src/`` и ``scripts/`` дедлайн несут все до одного — а
вот у работ ``ci.yml`` его не было НИ У ОДНОЙ. Наружная граница отсутствовала
целиком: зависший подпроцесс в наборе сжёг бы шесть часов раннера — умолчание
площадки, — прежде чем кто-нибудь узнал бы об этом. Внутренний срок без
наружного держит только то, что уже проверено; наружный держит остальное.

ПОЭТОМУ ПОВЕРХНОСТИ ДВЕ, и обе разбираются здесь:

* **процесс** — вызов из ``SPAWNERS`` без ``timeout=`` в исходниках дерева;
* **работа** — задание конвейера без ``timeout-minutes``.

РАЗБОР НАДВОЕ (правило 182). Верен ли срок — суждение: пять минут мало для
сборки и много для чтения тега, и машине этого не решить. **Что срок назван
вообще** следует из текста целиком, и держится здесь.

ЧЕГО ГЕЙТ НЕ ЛОВИТ, названо здесь, а не подразумевается (правило 056):

* **разделение срока на старт и работу.** Правило просит их различать; у
  ``subprocess.run`` параметр один и меряет всё вместе. Различить их можно
  только своим циклом ожидания, и такого у проекта нет;
* **величину срока.** ``timeout=1`` пройдёт наравне с разумным;
* **ожидание не процессом.** Сетевой вызов, блокировка, чтение канала сюда не
  попадают: разбираются порождения процесса и задания конвейера.

Запуск::

    python scripts/check_deadlines.py            # дерево проекта
    python scripts/check_deadlines.py --root DIR # другое дерево

Исходы: 0 — чисто; 1 — есть находки; 2 — проверка не отработала.
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path
from typing import Final, NamedTuple

ROOT: Final = Path(__file__).resolve().parent.parent

SOURCES: Final = ("src/glossary/**/*.py", "scripts/*.py")
"""Исходники, которые ходят в конвейере: их ожидания и разбираются."""

WORKFLOWS: Final = ".github/workflows/*.yml"

SPAWNERS: Final = frozenset({"run", "Popen", "check_output", "check_call", "call"})
"""Чем порождают процесс. Список закрыт: новое имя добавляется явно."""

DEADLINE: Final = "timeout"
JOB_DEADLINE: Final = "timeout-minutes"

JOB: Final = re.compile(r"^  (?P<name>[A-Za-z_][\w-]*):\s*$")
"""Заголовок задания: два пробела отступа и двоеточие."""

NESTED: Final = re.compile(r"^ {4}\S")
"""Строка внутри задания: четыре пробела отступа."""

SKIP: Final = ("__pycache__",)

NOT_RUN: Final = 2
"""Проверка не отработала. Не означает «сроки названы» — их не искали."""


class Finding(NamedTuple):
    """Находка разбора.

    Attributes:
        where: Адрес в форме ``файл:строка``.
        what: Чего именно не хватает.
    """

    where: str
    what: str

    def __str__(self) -> str:
        """Находка в привычной форме ``файл:строка`` (правило 158)."""
        return f"{self.where}: {self.what}"


def _callee(node: ast.Call) -> str:
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return node.func.id if isinstance(node.func, ast.Name) else ""


def spawns_without_deadline(source: str, name: str) -> list[Finding]:
    """Порождения процесса, у которых срок не назван.

    Args:
        source: Текст модуля.
        name: Путь модуля для сообщений.

    Returns:
        Находки; пустой список — у всех порождений срок есть.
    """
    module = ast.parse(source)
    return [
        Finding(
            f"{name}:{node.lineno}",
            f"порождение процесса без {DEADLINE}= — ожидание без срока не "
            "отказывает, а висит, и снаружи это неотличимо от медленной работы "
            "(правило 100)",
        )
        for node in ast.walk(module)
        if isinstance(node, ast.Call)
        and _callee(node) in SPAWNERS
        and not any(word.arg == DEADLINE for word in node.keywords)
    ]


def jobs_without_deadline(text: str, name: str) -> list[Finding]:
    """Задания конвейера, у которых срок не назван.

    Разбор построчный, а не через YAML: у скриптов дерева зависимостей нет по
    решению проекта, и одна проверка не повод его заводить. Форма заголовка
    задания в этом дереве постоянна и держится набором.

    Args:
        text: Текст прогона.
        name: Путь прогона для сообщений.

    Returns:
        Находки; пустой список — у всех заданий срок есть.
    """
    lines = text.splitlines()
    inside_jobs = False
    findings: list[Finding] = []
    current: str | None = None
    line_of: int = 0
    has_deadline = False

    def close() -> None:
        if current is not None and not has_deadline:
            findings.append(
                Finding(
                    f"{name}:{line_of}",
                    f"работа «{current}» без {JOB_DEADLINE} — умолчание площадки "
                    "шесть часов, и зависшее задание столько и займёт (правило 100)",
                )
            )

    for number, line in enumerate(lines, start=1):
        if line.rstrip() == "jobs:":
            inside_jobs = True
            continue
        if inside_jobs and line and not line.startswith(" "):
            break
        if not inside_jobs:
            continue
        header = JOB.match(line)
        if header:
            close()
            current, line_of, has_deadline = header.group("name"), number, False
            continue
        if current and NESTED.match(line) and line.strip().startswith(f"{JOB_DEADLINE}:"):
            has_deadline = True
    close()
    return findings


def scan(root: Path) -> tuple[list[Finding], int]:
    """Находки по дереву и число разобранных мест ожидания.

    Второе число нужно само по себе: ноль находок при нуле мест означает не
    «чисто», а «нечего смотреть» (правила 039, 146).

    Args:
        root: Корень дерева.

    Returns:
        Находки и число разобранных файлов.
    """
    findings: list[Finding] = []
    seen = 0
    for pattern in SOURCES:
        for path in sorted(root.glob(pattern)):
            if any(part in SKIP for part in path.parts):
                continue
            seen += 1
            findings.extend(
                spawns_without_deadline(
                    path.read_text(encoding="utf-8"), str(path.relative_to(root))
                )
            )
    for path in sorted(root.glob(WORKFLOWS)):
        seen += 1
        findings.extend(
            jobs_without_deadline(
                path.read_text(encoding="utf-8"), str(path.relative_to(root))
            )
        )
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
            f"проверка не отработала: под {args.root} не найдено ни исходников "
            f"({', '.join(SOURCES)}), ни прогонов ({WORKFLOWS}) — проверьте, что "
            "запуск идёт из репозитория",
            file=sys.stderr,
        )
        return NOT_RUN

    if findings:
        print("ожидание без названного срока:", file=sys.stderr)
        for finding in findings:
            print(f"  • {finding}", file=sys.stderr)
        return 1

    print(f"сроки названы: разобрано файлов {seen}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
