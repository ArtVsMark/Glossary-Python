"""Импорт карточек из базы знаний Stepik-Python-Grader.

У данных один хозяин. Содержание глоссария ведётся в
``ArtVsMark/Stepik-Python-Grader``; здесь оно превращается в страницу, которую
скачивают и открывают. Обратного потока нет: правка карточки в двух местах
разъезжается на первой же выгрузке, а спор о том, чья версия верна, решать
некому.

Импорт **идемпотентен**: один и тот же вход даёт побайтово одинаковый снимок.
Порядок детерминирован — по разделу и идентификатору, а не по порядку файлов
на диске, который зависит от файловой системы.

Форма карточки принимается как есть: своя третья форма означала бы отображение
в обе стороны и разъезд на первом же новом поле источника. Единственное
добавление — ``color_group``: в источнике верхнеуровневая рубрика выражена
именем файла, а склейка 11 файлов в один снимок эту границу стирает.

Запуск::

    python scripts/import_from_grader.py --source /путь/к/Stepik-Python-Grader
    python scripts/import_from_grader.py --source ... --check   # сверить, не писать
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Final

from glossary.loader import default_data_path, dump_glossary
from glossary.models import SCHEMA_VERSION, Entry, Glossary

ROOT: Final = Path(__file__).resolve().parent.parent
DATA_SUBPATH: Final = Path("src") / "stepik_grader" / "glossary" / "data"
PUBLISHED: Final = "ready"
"""Статус карточки, которая доезжает до витрины. Черновики остаются в источнике."""


def read_source(source: Path) -> list[dict[str, Any]]:
    """Прочитать карточки из всех файлов базы знаний.

    Имя файла становится ``color_group`` карточки: рубрика источника выражена
    раскладкой по файлам, и при склейке её больше неоткуда взять.

    Raises:
        SystemExit: каталога нет или в нём нет ни одного файла — это ошибка
            входа, а не пустой глоссарий.
    """
    data_dir = source / DATA_SUBPATH
    if not data_dir.is_dir():
        raise SystemExit(f"каталог карточек не найден: {data_dir}")

    files = sorted(data_dir.glob("*.json"))
    if not files:
        raise SystemExit(f"в {data_dir} нет ни одного файла — импортировать нечего")

    cards: list[dict[str, Any]] = []
    for path in files:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise SystemExit(f"{path.name}: ожидался массив карточек")
        group = path.stem
        cards.extend(
            {**item, "color_group": group} for item in payload if isinstance(item, dict)
        )
    return cards


def build(cards: list[dict[str, Any]]) -> Glossary:
    """Собрать снимок: только опубликованные карточки, порядок детерминирован."""
    published = [c for c in cards if c.get("status") == PUBLISHED]
    entries = sorted(
        (Entry.from_dict(card) for card in published),
        key=lambda e: (e.section, e.id),
    )
    # Дубликат id пережил бы импорт молча и сломал якоря витрины.
    seen: dict[str, Entry] = {}
    unique: list[Entry] = []
    for entry in entries:
        if entry.id in seen:
            continue
        seen[entry.id] = entry
        unique.append(entry)
    return Glossary(entries=tuple(unique), schema_version=SCHEMA_VERSION)


def main(argv: list[str] | None = None) -> int:
    """Точка входа. Возвращает 1, если снимок разошёлся с источником."""
    parser = argparse.ArgumentParser(description="Импорт карточек из грейдера")
    parser.add_argument(
        "--source",
        type=Path,
        required=True,
        metavar="DIR",
        help="каталог клона ArtVsMark/Stepik-Python-Grader",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="сверить снимок с источником, ничего не записывая",
    )
    args = parser.parse_args(argv)

    cards = read_source(args.source)
    glossary = build(cards)
    skipped = len(cards) - len(glossary)
    target = default_data_path()

    if args.check:
        if not target.exists():
            print(f"снимок отсутствует: {target}", file=sys.stderr)
            return 1
        expected = dump_glossary(glossary, ROOT / ".import-check.json")
        same = expected.read_text("utf-8") == target.read_text("utf-8")
        expected.unlink()
        if same:
            print(f"снимок совпадает с источником: {len(glossary)} карточек")
            return 0
        print(
            f"снимок разошёлся с источником. Пересоберите: "
            f"python scripts/import_from_grader.py --source {args.source}",
            file=sys.stderr,
        )
        return 1

    dump_glossary(glossary, target)
    print(f"импортировано карточек: {len(glossary)} → {target}")
    if skipped:
        print(f"пропущено неопубликованных: {skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
