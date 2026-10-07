#!/usr/bin/env python3
"""Поле ``added`` карточки сходится с тем, где имя впервые видно в языке (#86).

Версию появления карточке ставит автор — по документации, по памяти, по
соседней карточке. Ошибиться легко и незаметно: «3.12» вместо «3.11» читается
так же убедительно. Исходный замер эпика #79 нашёл таких расхождений 13.

Здесь версия не читается, а **меряется**: матрица ``inventory`` в
``badges.yml`` снимает инвентарь на каждой версии Python, и имя, которого в
снимке 3.12 нет, а в 3.13 есть, появилось в 3.13. Сверяется это с полем.

ЧТО ПРОВЕРЯЕТСЯ, по каждой карточке, чьё имя (``id`` или заголовок) есть хоть в
одном снимке:

* **поле раньше младшего снимка** (``<3.0`` … ``3.11``) — имя обязано быть уже
  в младшем снимке, иначе оно появилось позже, чем сказано;
* **поле внутри диапазона** — имя впервые видно ровно в этой версии.

ЧЕГО ГЕЙТ НЕ ВИДИТ, названо здесь (правило 056):

* **версии раньше младшего снимка.** ``2.7`` против ``3.5`` неразличимы: обе
  раньше 3.11, и в снимке имя есть в обоих случаях;
* **имена вне инвентаря** — синтаксис, понятия, модули вне ``STDLIB_MODULES``;
* **«появилось в инвентаре» ≠ «появилось в языке».** Класс, переехавший в
  подмодуль, или функция, доступная на этой ОС позже, чем на другой, видны
  инвентарю позже срока. Такие случаи перечислены в ``SEEN_LATER`` с причиной.

Исходы: 0 — чисто; 1 — находки; 2 — сверять не с чем (снимков меньше двух).
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Final, NamedTuple

import whatsnew
from glossary.loader import default_data_path

NOT_RUN: Final = 2
MIN_SNAPSHOTS: Final = 2

SEEN_LATER: Final[dict[str, str]] = {
    "os.path.isdevdrive": "в 3.12 только на Windows (ntpath), на Linux — с 3.13",
    "pathlib.UnsupportedOperation": "в 3.13 класс жил в pathlib._abc, "
    "инвентарь видит его с переезда в 3.14",
}
"""Имена, которые инвентарь видит позже, чем они появились в языке.

Список закрытый: каждая строка — разобранный случай с причиной, а не способ
заглушить находку.
"""


class Finding(NamedTuple):
    """Расхождение поля ``added`` с замером."""

    card: str
    added: str
    first_seen: str


def _key(version: str) -> tuple[int, ...]:
    """Ключ версии поля: ``<3.0`` раньше любой 3.x, в том числе самой 3.0."""
    return (-1,) if version.startswith("<") else whatsnew.version_key(version)


def first_seen(dumps: list[dict[str, Any]]) -> tuple[str, dict[str, str]]:
    """Младшая версия снимков и версия, в которой каждое имя видно впервые."""
    ordered = sorted(dumps, key=lambda dump: whatsnew.version_key(dump["python_version"]))
    seen: dict[str, str] = {}
    for dump in ordered:
        for item in dump["items"]:
            seen.setdefault(item["qualname"], dump["python_version"])
    return ordered[0]["python_version"], seen


def names(card: dict[str, Any]) -> set[str]:
    """Под какими именами карточка видна инвентарю."""
    title = card["title"]["en"].removeprefix("@").removesuffix("()")
    return {card["id"], title}


def findings(cards: list[dict[str, Any]], dumps: list[dict[str, Any]]) -> list[Finding]:
    """Карточки, чьё поле ``added`` спорит с замером."""
    oldest, seen = first_seen(dumps)
    found: list[Finding] = []
    for card in cards:
        hits = sorted(
            (
                seen[name]
                for name in names(card)
                if name in seen and name not in SEEN_LATER
            ),
            key=whatsnew.version_key,
        )
        if not hits:
            continue
        measured = hits[0]
        added = card["added"]
        expected = oldest if _key(added) <= whatsnew.version_key(oldest) else added
        if measured != expected:
            found.append(Finding(card["id"], added, measured))
    return found


def main(argv: list[str] | None = None) -> int:
    """Точка входа: сверить ``added`` карточек со снимками инвентаря."""
    parser = argparse.ArgumentParser(description="Сверка added с замером языка")
    parser.add_argument(
        "dumps", nargs="+", type=Path, metavar="FILE", help="выгрузки инвентаря"
    )
    parser.add_argument(
        "--data", type=Path, default=None, metavar="PATH", help="путь к снимку карточек"
    )
    args = parser.parse_args(argv)

    if len(args.dumps) < MIN_SNAPSHOTS:
        # Третий исход: с одним снимком «впервые видно» не отличить от «было всегда».
        print(
            f"не отработало: снимков {len(args.dumps)}, нужно хотя бы {MIN_SNAPSHOTS}",
            file=sys.stderr,
        )
        return NOT_RUN

    data = args.data or default_data_path()
    raw = json.loads(data.read_text(encoding="utf-8"))
    cards = raw["entries"] if isinstance(raw, dict) else raw
    found = findings(cards, [whatsnew.read_dump(path) for path in args.dumps])
    for finding in found:
        print(
            f"{finding.card}: added {finding.added}, а впервые видно в "
            f"{finding.first_seen}"
        )
    print(f"расхождений с замером: {len(found)}")
    return 1 if found else 0


if __name__ == "__main__":
    raise SystemExit(main())
