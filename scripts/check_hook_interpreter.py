#!/usr/bin/env python3
"""Хук окна исполняется интерпретатором планки, а не системным ``python3`` (217).

Правило каталога 217: всё, что исполняет код проекта, исполняет его
интерпретатор планки. Хук окна — тоже. Обёртка стража ``pre_tool_use.sh``
откатывалась на системный ``python3``, который в облачном окне бывает 3.11, а
на macOS — 3.9; упавший сторож площадка считает неблокирующей ошибкой и
пропускает действие молча. Нашёл каталог, сверив семью перед постройкой своего
гейта (правило 162, Glossary-Python#274). Гейт — переделка его
``scripts/check_hook_interpreter.py``.

ЧТО ПРОВЕРЯЕТСЯ:

* ``.claude/settings.json`` — команда хука не зовёт интерпретатор сама, ни
  первым словом, ни путём: хук зовётся обёрткой, которая ищет планку;
* ``.claude/hooks/*.sh`` — слово-команда ``python``/``python3`` не встречается
  вне имени с планкой (``python$floor``) и вне подкоманды ``uv python``.
  Комментарии и команды ``echo`` не читаются: там это проза.

ИСКЛЮЧЕНИЕ ОДНО, И ОНО ПО РОЛИ, А НЕ ПО ИМЕНИ. Хук события ``SessionStart`` сам
ставит интерпретатор планки и до этого вправе звать системный. Какой хук
стартовый, гейт берёт из ``.claude/settings.json``: переименование файла дыры
не откроет.

ГРАНИЦА. Косвенный вызов (``p=python3; $p``) не виден. Разбор кавычек не
ведётся: ``;`` и ``|`` внутри кавычек ``echo`` режут строку, и проза после них
читается как команда — гейт тогда краснеет, а не пропускает.

Исходы: 0 — чисто; 1 — найдено, названы файл, строка и форма; 2 — проверять
нечего: нет ``.claude/settings.json`` или хуков в нём (правило 075).
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Final

ROOT: Final = Path(__file__).resolve().parent.parent
SETTINGS: Final = Path(".claude") / "settings.json"
HOOKS: Final = Path(".claude") / "hooks"
NOT_RUN: Final = 2
START: Final = "SessionStart"

BARE: Final = re.compile(r"(?<![\w$/{.-])(?<!uv )(?<!uv\" )(python3?)(?![\w.$/-])")
"""Слово-команда интерпретатора: не часть имени с планкой, пути или ``uv python``."""

DIRECT: Final = re.compile(r"(?:^|[\s\"'/=])python[\d.]*(?![\w$.-])")
"""Команда хука в настройках, которая сама и есть интерпретатор."""

COMMENT: Final = re.compile(r"(?:^|(?<=\s))#.*")
"""Комментарий оболочки: ``#`` в начале слова — ``$#`` и ``${x#p}`` не он."""

SEPARATORS: Final = re.compile(r"&&|\|\||[;|&]")


def hook_commands(settings: dict[str, Any]) -> list[tuple[str, str]]:
    """Пары «событие, команда» всех хуков из настроек."""
    return [
        (event, str(hook.get("command", "")))
        for event, groups in settings.get("hooks", {}).items()
        for group in groups
        for hook in group.get("hooks", [])
    ]


def start_hooks(pairs: list[tuple[str, str]]) -> set[str]:
    """Имена файлов хуков, зарегистрированных на старт окна."""
    names: set[str] = set()
    for event, command in pairs:
        match = re.search(r"hooks/([\w.-]+)", command)
        if event == START and match:
            names.add(match.group(1))
    return names


def bare_calls(text: str) -> list[tuple[int, str]]:
    """Строки оболочки, где интерпретатор зовётся не по планке."""
    found: list[tuple[int, str]] = []
    for number, line in enumerate(text.splitlines(), 1):
        code = COMMENT.sub("", line)
        commands = [
            part for part in SEPARATORS.split(code) if not re.match(r"\s*echo\b", part)
        ]
        if any(BARE.search(part) for part in commands):
            found.append((number, line.strip()))
    return found


def findings(root: Path, pairs: list[tuple[str, str]]) -> list[str]:
    """Находки по настройкам и обёрткам хуков дерева ``root``."""
    found = [
        f"{SETTINGS}: {event} зовёт интерпретатор напрямую — «{command[:80]}»"
        for event, command in pairs
        if DIRECT.search(command)
    ]
    excluded = start_hooks(pairs)
    for path in sorted((root / HOOKS).glob("*.sh")):
        if path.name in excluded:
            continue
        found.extend(
            f"{HOOKS / path.name}:{number}: «{line[:90]}» — интерпретатор не по планке"
            for number, line in bare_calls(path.read_text(encoding="utf-8"))
        )
    return found


def main(argv: list[str] | None = None) -> int:
    """Проверить настройки и обёртки хуков окна."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    path = args.root / SETTINGS
    try:
        pairs = hook_commands(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError) as refusal:
        print(f"проверка не отработала: {path} не прочитан — {refusal}", file=sys.stderr)
        return NOT_RUN
    if not pairs:
        print(f"проверять нечего: в {path} нет ни одного хука (075)", file=sys.stderr)
        return NOT_RUN
    found = findings(args.root, pairs)
    if found:
        print("хук окна исполняется не интерпретатором планки (217):", file=sys.stderr)
        for line in found:
            print(f"  • {line}", file=sys.stderr)
        return 1
    print(f"хуки окна исполняются планкой: команд {len(pairs)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
