#!/usr/bin/env python3
"""У проверки три исхода, и третий называет предмет отказа.

Правило каталога 039: исходов три, а не два — «чисто», «есть находки» и
«проверка не отработала». Склеив два последних, инструмент отвечает «нарушений
нет» там, где их не искали, и пустой вход становится зелёным прогоном (075).

Правило каталога 158: третий исход обязан сказать, **что именно** не
отработало, — какой источник, файл, адрес. Код и текст чужой ошибки отвечают на
вопрос «что случилось», но не на тот единственный, ради которого третий исход
заведён: чужой это отказ или наш. Адрес прикрепляется в точке обращения, а не
восстанавливается потом по трассировке.

РАЗБОР НАДВОЕ (правило 182). Различить в прозе причину и предмет разбором
нельзя — эта половина машинной не станет. **Что предмет назван вообще** —
подстановкой либо буквальным адресом — следует из исходника целиком, и держится
здесь. Гейт не судит, верен ли адрес; он требует, чтобы адрес был.

ЗАМЕР, ИЗ-ЗА КОТОРОГО ГЕЙТ ЗАВЕДЁН. Третьего исхода не было у ЧЕТЫРЁХ точек
входа: ``changelog.py`` (пропавший каталог фрагментов читался как «замечаний
нет»), ``facts.py`` (непрочитанный источник — как «числа совпадают»),
``whatsnew.py`` («дана одна выгрузка» — как «нового нет»),
``import_from_grader.py`` («снимка нет» — как «снимок разошёлся»). Все четыре
исправлены тем же заходом, и гейт заведён, чтобы пятый случай не появился молча.

ПЯТЫЙ СЛУЧАЙ НАШЁЛСЯ СРАЗУ — В САМОМ ГЕЙТЕ. Первый же его прогон покраснел на
собственном исходном файле: константа исхода называлась ``NOT_RUN_CODE``, а
словарь имён такого не знал. Гейт, не узнающий своего имени, сказал бы «третьего
исхода нет» о любом чужом модуле с другим написанием — поэтому словарь закрыт и
короток, а новое имя добавляется в него явным изменением.

ЧЕГО ГЕЙТ НЕ ЛОВИТ, названо здесь, а не подразумевается (правило 056):

* **верность адреса.** ``f"нет файла {путь}"`` пройдёт и тогда, когда напечатан
  не тот путь: гейт видит подстановку, а не смысл;
* **исход, отданный исключением.** Точка входа, падающая трассировкой вместо
  кода возврата, сюда не попадает — предмет разбора это ``return``;
* **достаточность трёх.** Четвёртый осмысленный исход правилами не запрещён, и
  гейт его не считает.

Запуск::

    python scripts/check_third_outcome.py            # гейт по дереву проекта
    python scripts/check_third_outcome.py --root DIR # то же по другому дереву

Исходы: 0 — чисто; 1 — есть находки; 2 — проверка не отработала.
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Final, NamedTuple

if TYPE_CHECKING:
    from collections.abc import Iterator

ROOT: Final = Path(__file__).resolve().parent.parent

ENTRY_POINTS: Final = ("scripts/*.py", "src/glossary/cli.py")
"""Где живут точки входа: у каждой обязан быть третий исход."""

SKIP: Final = ("__pycache__",)

THIRD_OUTCOME: Final = frozenset({"NOT_RUN", "EXIT_USAGE", "REFUSED"})
"""Имена, которыми в этом дереве называется исход «не отработало».

Список закрытый и короткий намеренно: имя, не попавшее сюда, гейт не узнает и
скажет, что третьего исхода нет, — а это лучше молчаливого пропуска. Новое имя
добавляется сюда явным изменением.
"""

NOT_RUN: Final = 2
"""Исход «не отработало». Не означает «нарушений нет» — их не искали."""

ADDRESS: Final = re.compile(
    r"(?:[\w.\-]+/)+[\w.\-*]+"  # путь с разделителем
    r"|\.[a-z][\w.\-]+"  # корневой dotfile
    r"|[A-Z][A-Za-z_]*\.(?:md|json|toml|yml)"  # документ по имени
    r"|[A-Z_]{4,}"  # имя переменной окружения
)
"""Признак буквального адреса в сообщении: путь, dotfile, документ, переменная."""


class Finding(NamedTuple):
    """Находка разбора.

    Attributes:
        path: Путь модуля от корня дерева.
        line: Строка точки входа.
        what: Чего именно не хватает.
    """

    path: str
    line: int
    what: str

    def __str__(self) -> str:
        """Находка в привычной форме ``файл:строка`` (правило 158)."""
        return f"{self.path}:{self.line}: {self.what}"


def _declared_outcomes(module: ast.Module) -> set[str]:
    """Имена констант модуля, равных коду «не отработало»."""
    found: set[str] = set()
    for node in module.body:
        if not isinstance(node, ast.AnnAssign | ast.Assign):
            continue
        targets = [node.target] if isinstance(node, ast.AnnAssign) else list(node.targets)
        value = node.value
        if not isinstance(value, ast.Constant) or value.value != NOT_RUN:
            continue
        found.update(
            target.id
            for target in targets
            if isinstance(target, ast.Name) and target.id in THIRD_OUTCOME
        )
    return found


def _returns_not_run(function: ast.FunctionDef, names: set[str]) -> bool:
    """Отдаёт ли функция исход «не отработало»."""
    for node in ast.walk(function):
        if not isinstance(node, ast.Return) or node.value is None:
            continue
        value = node.value
        if isinstance(value, ast.Constant) and value.value == NOT_RUN:
            return True
        if isinstance(value, ast.Name) and value.id in names:
            return True
    return False


def _names_a_subject(function: ast.FunctionDef) -> bool:
    """Названо ли в сообщениях функции ЧТО именно не отработало.

    Подстановка считается названным предметом: в неё подставляют путь, номер
    или имя. Буквальный адрес — тоже. Проза без того и другого отвечает на
    вопрос «что случилось» и молчит о том, чей это отказ (правило 158).
    """
    for node in ast.walk(function):
        if isinstance(node, ast.JoinedStr) and any(
            isinstance(part, ast.FormattedValue) for part in node.values
        ):
            return True
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and ADDRESS.search(node.value)
        ):
            return True
    return False


def inspect(source: str, name: str) -> list[Finding]:
    """Разобрать модуль и проверить его точку входа.

    Args:
        source: Текст модуля.
        name: Имя файла для сообщений.

    Returns:
        Находки; пустой список — у модуля есть третий исход и он назван.
    """
    module = ast.parse(source)
    entries = [
        node
        for node in module.body
        if isinstance(node, ast.FunctionDef) and node.name == "main"
    ]
    if not entries:
        return []

    names = _declared_outcomes(module)
    findings: list[Finding] = []
    for entry in entries:
        helpers = [
            node
            for node in module.body
            if isinstance(node, ast.FunctionDef)
            and _returns_not_run(node, names)
            and node is not entry
        ]
        if not _returns_not_run(entry, names) and not helpers:
            findings.append(
                Finding(
                    name,
                    entry.lineno,
                    "у точки входа два исхода вместо трёх: «не отработало» "
                    "неотличимо от «нарушений нет» (правила 039, 075)",
                )
            )
            continue
        findings.extend(
            Finding(
                name,
                holder.lineno,
                f"третий исход в {holder.name}() называет причину, но не "
                "предмет: скажите ЧТО именно не отработало — подстановкой "
                "либо адресом (правило 158)",
            )
            for holder in [entry, *helpers]
            if not _names_a_subject(holder)
        )
    return findings


def _modules(root: Path) -> Iterator[tuple[Path, str]]:
    for pattern in ENTRY_POINTS:
        for path in sorted(root.glob(pattern)):
            if any(part in SKIP for part in path.parts):
                continue
            yield path, str(path.relative_to(root))


def scan(root: Path) -> tuple[list[Finding], int]:
    """Находки по дереву и число разобранных точек входа.

    Второе число нужно само по себе: ноль находок при нуле модулей означает не
    «чисто», а «нечего смотреть» — та самая склейка, против которой гейт.
    """
    findings: list[Finding] = []
    seen = 0
    for path, name in _modules(root):
        source = path.read_text(encoding="utf-8")
        if "def main(" not in source:
            continue
        seen += 1
        findings.extend(inspect(source, name))
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
            f"проверка не отработала: под {args.root} не найдено ни одной точки "
            f"входа. Ожидались {', '.join(ENTRY_POINTS)} — проверьте, что запуск "
            "идёт из репозитория",
            file=sys.stderr,
        )
        return NOT_RUN

    if findings:
        print("третий исход отсутствует или не называет предмет:", file=sys.stderr)
        for finding in findings:
            print(f"  • {finding}", file=sys.stderr)
        return 1

    print(f"третий исход есть и назван: разобрано точек входа {seen}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
