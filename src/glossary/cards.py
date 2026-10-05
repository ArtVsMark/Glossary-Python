"""Источник содержания: карточки в ``data/cards/<группа>.json``.

Карточки ведутся здесь, по файлу на цветовую группу — так же, как в базе знаний
грейдера, откуда они переехали. Раскладка по файлам выбрана не ради привычки:
правка карточки трогает один файл из десяти, и параллельные изменения в разных
группах не конфликтуют, а diff читается без прокрутки тысячи соседей.

``data/glossary.json`` собирается отсюда и вручную не правится. Сборка
**идемпотентна**: один и тот же вход даёт побайтово одинаковый файл. Порядок
задан разделом и идентификатором, а не порядком файлов на диске, который
зависит от файловой системы.
"""

import json
from typing import TYPE_CHECKING, Any, Final

from glossary.errors import DataFormatError
from glossary.loader import project_root
from glossary.models import SCHEMA_VERSION, Entry, Glossary

if TYPE_CHECKING:
    from pathlib import Path

__all__ = [
    "CARDS_DIRNAME",
    "PUBLISHED",
    "assemble",
    "default_cards_dir",
    "read_cards",
]

CARDS_DIRNAME: Final = "cards"
PUBLISHED: Final = "ready"
"""Статус карточки, которая доезжает до сборки. Черновики остаются в источнике."""


def default_cards_dir() -> Path:
    """Каталог источника по умолчанию — ``<корень>/data/cards``."""
    return project_root() / "data" / CARDS_DIRNAME


def read_cards(directory: Path | None = None) -> list[Entry]:
    """Прочитать карточки всех файлов источника.

    Имя файла становится ``color_group`` карточки: рубрика выражена
    раскладкой по файлам, и в самой карточке её не пишут — иначе у одного
    факта было бы два места и они разъехались бы на первом переносе.

    Raises:
        DataFormatError: каталога нет, в нём нет ни одного файла, файл не
            читается как JSON или не является массивом. Это ошибка входа, а не
            пустой глоссарий.
    """
    source = directory or default_cards_dir()
    if not source.is_dir():
        raise DataFormatError(f"каталог карточек не найден: {source}")

    files = sorted(source.glob("*.json"))
    if not files:
        raise DataFormatError(f"в {source} нет ни одного файла карточек")

    entries: list[Entry] = []
    for path in files:
        try:
            payload: Any = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise DataFormatError(f"{path}: некорректный JSON ({exc})") from exc
        if not isinstance(payload, list):
            raise DataFormatError(f"{path}: ожидался массив карточек")
        for position, item in enumerate(payload):
            if not isinstance(item, dict):
                raise DataFormatError(f"{path}: [{position}] должен быть объектом")
            entries.append(Entry.from_dict({**item, "color_group": path.stem}))
    return entries


def assemble(entries: list[Entry]) -> Glossary:
    """Собрать глоссарий: только опубликованные карточки, порядок детерминирован.

    Дубликат идентификатора не отбрасывается молча: источник теперь здесь, и
    выбрать за автора, какая из двух карточек верна, сборке не по чину. Его
    назовёт правило ``unique-id`` валидатора.
    """
    published = [entry for entry in entries if entry.status == PUBLISHED]
    ordered = sorted(published, key=lambda entry: (entry.section, entry.id))
    return Glossary(entries=tuple(ordered), schema_version=SCHEMA_VERSION)
