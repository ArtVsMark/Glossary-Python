"""Что появилось и исчезло между версиями Python.

Вопрос «что нового в 3.14» обычно решают разбором раздела What's New —
внешнего документа, который надо скачать, разобрать и надеяться, что вёрстка
не поменялась. Здесь он решается вычитанием: то, чего в инвентаре 3.13 нет, а
в инвентаре 3.14 есть, и появилось в 3.14. Ни сети, ни разбора HTML.

Инвентарь снимается на каждой версии матрицы (``glossary inventory``), а этот
скрипт сводит выгрузки вместе. Отсюда и его место в ``scripts/``: пакет считает
по одной версии — по той, на которой запущен, — а сравнение нескольких сразу
возможно только там, где собраны их результаты.

Главная ценность не в списке нового, а в его пересечении с глоссарием:
**появилось в языке и не описано** — это очередь на завтра, а не справка.

Граница честности. Разность отвечает не на «появилось в языке», а на **«появилось
в инвентаре»**, и это не одно и то же. ``typing.Union`` существует с 3.5, но в
3.14 стал полноценным классом — и классификация увидела его впервые, отчего он
попал в список нового. Находка при этом верна: карточки на него нет. Неверна
была бы формулировка «появилось в 3.14», если читать её буквально. Точный смысл:
«впервые видно инвентарём на этой версии» — новая сущность, изменившая природу
старая, или расширенный набор курируемых модулей.

Запуск::

    python scripts/whatsnew.py inventory-*.json -o whatsnew.json
"""

from __future__ import annotations

import argparse
import json
import sys
from itertools import pairwise
from pathlib import Path
from typing import Any, Final

from glossary.contracts import envelope
from glossary.coverage import known_names
from glossary.loader import default_data_path, load_glossary

SCHEMA_OF: Final = "что появилось и исчезло между версиями Python"

MIN_VERSIONS: Final = 2
"""Меньше двух выгрузок вычитать не из чего."""


def version_key(version: str) -> tuple[int, ...]:
    """Ключ сортировки версий: ``3.9`` идёт перед ``3.10``, а не после.

    Лексикографический порядок здесь врёт, и врёт молча: разность посчиталась
    бы между не теми версиями, а результат выглядел бы правдоподобно.
    """
    return tuple(int(part) for part in version.split(".") if part.isdigit())


def read_dump(path: Path) -> dict[str, Any]:
    """Прочитать одну выгрузку инвентаря.

    Raises:
        SystemExit: файл не разобран или не похож на инвентарь. Молчаливый
            пропуск испорченной выгрузки дал бы разность с соседней версией
            вместо разности с пропущенной — то есть неверный ответ вместо отказа.
    """
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"{path}: выгрузка не прочитана: {exc}") from exc
    if not isinstance(payload, dict) or "python_version" not in payload:
        raise SystemExit(f"{path}: это не выгрузка инвентаря")
    return payload


def build(dumps: list[dict[str, Any]], known: frozenset[str]) -> dict[str, Any]:
    """Свести выгрузки в контракт: что добавилось и что исчезло по версиям."""
    ordered = sorted(dumps, key=lambda d: version_key(str(d["python_version"])))
    releases: list[dict[str, Any]] = []
    for before, after in pairwise(ordered):
        old = {str(item["qualname"]) for item in before["items"]}
        new = {str(item["qualname"]): item for item in after["items"]}
        added = sorted(name for name in new if name not in old)
        removed = sorted(name for name in old if name not in new)
        # Пересечение с глоссарием и есть смысл всей затеи: новое, о котором
        # у нас нет карточки, — очередь на завтра, а не справка.
        undocumented = [name for name in added if name.lower() not in known]
        releases.append(
            {
                "version": after["python_version"],
                "since": before["python_version"],
                "added": [
                    {
                        "qualname": name,
                        "module": new[name]["module"],
                        "kind": new[name]["kind"],
                        "documented": name.lower() in known,
                    }
                    for name in added
                ],
                "removed": removed,
                "totals": {
                    "added": len(added),
                    "removed": len(removed),
                    "undocumented": len(undocumented),
                },
            }
        )
    return {
        **envelope(SCHEMA_OF),
        "versions": [d["python_version"] for d in ordered],
        "releases": releases,
    }


def main(argv: list[str] | None = None) -> int:
    """Точка входа: свести выгрузки инвентаря в ``whatsnew.json``."""
    parser = argparse.ArgumentParser(description="Разность инвентарей по версиям")
    parser.add_argument(
        "dumps", nargs="+", type=Path, metavar="FILE", help="выгрузки инвентаря"
    )
    parser.add_argument(
        "-o", "--output", type=Path, default=None, metavar="PATH", help="файл результата"
    )
    parser.add_argument(
        "--data", type=Path, default=None, metavar="PATH", help="путь к снимку карточек"
    )
    args = parser.parse_args(argv)

    if len(args.dumps) < MIN_VERSIONS:
        print(
            f"нужно хотя бы {MIN_VERSIONS} выгрузки: разность считается между "
            "версиями, а не внутри одной",
            file=sys.stderr,
        )
        return 1

    known = known_names(load_glossary(args.data or default_data_path()))
    payload = build([read_dump(path) for path in args.dumps], known)
    rendered = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"

    if args.output is None:
        print(rendered, end="")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8")
    for release in payload["releases"]:
        totals = release["totals"]
        print(
            f"{release['since']} → {release['version']}: "
            f"добавлено {totals['added']}, из них без карточки "
            f"{totals['undocumented']}; удалено {totals['removed']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
