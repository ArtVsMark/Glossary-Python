#!/usr/bin/env python3
"""Какие карточки изменение добавило или поправило — список для ревизора.

Ревизор карточек (``.github/workflows/card-review.yml``) проводит изменённые
карточки через навык ``card-audit``. Выбирать их по диффу строк ему нечем:
карточка в ``data/cards/<группа>.json`` занимает десятки строк, и строка
изменённого примера не называет, чей это пример. Поэтому сравниваются карточки
целиком, по ``id``, между основой изменения и его головой.

Удалённые карточки в список не входят: выверять у них нечего, а исчезновение
``id`` держит другой гейт (#172).

Список урезается до ``--limit`` с названным обрывом (``glossary.reporting``):
волна в сотню карточек иначе отдала бы ревизору работу, на которую не хватит
ни срока прогона, ни выдачи.

Исходы: 0 — список собран (возможно, пустой); 2 — основу прочитать нечем.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

from glossary.reporting import truncate

if TYPE_CHECKING:
    from collections.abc import Mapping

ROOT: Final = Path(__file__).resolve().parent.parent
CARDS: Final = "data/cards"
NOT_RUN: Final = 2
DEFAULT_LIMIT: Final = 20
GIT_TIMEOUT: Final = 60

type Cards = dict[str, tuple[str, dict[str, Any]]]
"""Карточки по ``id``: файл группы и сама карточка."""


def index(groups: Mapping[str, str]) -> Cards:
    """Разложить файлы групп в карточки по ``id``.

    Args:
        groups: Текст файла группы по его пути от корня.

    Returns:
        Карточки по ``id`` вместе с файлом, где они лежат.
    """
    cards: Cards = {}
    for path, text in sorted(groups.items()):
        data = json.loads(text)
        entries = data["entries"] if isinstance(data, dict) else data
        for entry in entries:
            cards[entry["id"]] = (path, entry)
    return cards


def changed(before: Cards, after: Cards) -> list[tuple[str, str, str]]:
    """Карточки, которые изменение добавило или поправило.

    Args:
        before: Карточки основы.
        after: Карточки головы.

    Returns:
        Тройки «``id``, что случилось, файл группы» в порядке файлов головы.
    """
    found: list[tuple[str, str, str]] = []
    for cid, (path, entry) in after.items():
        old = before.get(cid)
        if old is None:
            found.append((cid, "новая", path))
        elif old[1] != entry:
            found.append((cid, "изменена", path))
    return sorted(found, key=lambda item: (item[2], item[0]))


def render(items: list[tuple[str, str, str]], limit: int) -> str:
    """Markdown-список для ревизора с названным обрывом."""
    shown, tail = truncate(items, limit)
    lines = [f"- `{cid}` ({what}) — `{path}`" for cid, what, path in shown]
    return "\n".join([*lines, *tail]) + "\n"


def read_head(root: Path) -> dict[str, str]:
    """Файлы групп в рабочем дереве."""
    return {
        f"{CARDS}/{path.name}": path.read_text(encoding="utf-8")
        for path in sorted((root / CARDS).glob("*.json"))
    }


def read_base(root: Path, ref: str, paths: list[str]) -> dict[str, str]:
    """Те же файлы групп на основе изменения; новой группы там нет — пропуск.

    Raises:
        RuntimeError: ``ref`` в клоне не разрешается — сравнивать не с чем.
    """
    # git зовётся по имени из PATH, аргументы собраны из констант и ссылки CI.
    probe = subprocess.run(  # noqa: S603
        ["git", "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"],  # noqa: S607
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=GIT_TIMEOUT,
        check=False,
    )
    if probe.returncode != 0:
        raise RuntimeError(f"основа {ref} в клоне не найдена: нужен fetch-depth 0")
    groups: dict[str, str] = {}
    for path in paths:
        shown = subprocess.run(  # noqa: S603
            ["git", "show", f"{ref}:{path}"],  # noqa: S607
            cwd=root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=GIT_TIMEOUT,
            check=False,
        )
        if shown.returncode == 0:
            groups[path] = shown.stdout
    return groups


def main(argv: list[str] | None = None) -> int:
    """Точка входа: напечатать число карточек, список — в файл."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base", required=True, help="основа изменения: коммит")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    parser.add_argument("-o", "--output", type=Path, required=True)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args(argv)

    head = read_head(args.root)
    try:
        base = read_base(args.root, args.base, list(head))
    except RuntimeError as error:
        print(f"review_cards: {error}", file=sys.stderr)
        return NOT_RUN
    items = changed(index(base), index(head))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render(items, args.limit), encoding="utf-8")
    print(len(items))
    return 0


if __name__ == "__main__":
    sys.exit(main())
