"""Выгрузка карточек для потребителей — контракт ``delivery.json``.

С #76 хозяин содержания — этот репозиторий, а Stepik-Python-Grader получает
итоговые карточки выгрузкой и читает её сам: издатель считает, потребитель
читает обычным HTTP, без клона и без токена (правило каталога 174). В дерево
потребителя отсюда не пишут: когда и как забирать данные, решает он.

Форма выбрана так, чтобы импорт у потребителя был скачиванием, а не
преобразованием. ``groups`` повторяет раскладку ``data/cards/``: ключ — имя
файла группы, значение — массив карточек в той же форме и в том же порядке,
что в файле. Поля ``color_group`` в карточке нет: группу задаёт ключ, как в
источнике имя файла.

В выгрузку идут только опубликованные карточки (``status == "ready"``) —
черновик не должен оказаться у учащегося раньше, чем его допишут.

``snapshot.digest`` — отпечаток той же сборки, что лежит в
``data/glossary.json``: потребитель сверяет, о каком состоянии речь, без
сравнения тысячи карточек.
"""

import json
from typing import TYPE_CHECKING, Any, Final

from glossary.cards import PUBLISHED, assemble, read_cards
from glossary.contracts import envelope
from glossary.loader import digest
from glossary.models import SCHEMA_VERSION

if TYPE_CHECKING:
    from pathlib import Path

    from glossary.models import Entry

__all__ = ["SCHEMA_OF", "as_json", "collect", "groups_of"]

SCHEMA_OF: Final = "карточки глоссария по группам, в форме data/cards/"
"""Чего именно эта версия (правило каталога 164)."""


def groups_of(entries: list[Entry]) -> dict[str, list[dict[str, Any]]]:
    """Разложить опубликованные карточки по группам в форме файлов источника.

    Порядок групп — по имени, как ``sorted`` файлов в :func:`read_cards`;
    порядок карточек внутри группы — порядок файла.
    """
    grouped: dict[str, list[dict[str, Any]]] = {}
    for entry in entries:
        if entry.status != PUBLISHED:
            continue
        card = entry.to_dict()
        del card["color_group"]
        grouped.setdefault(entry.color_group, []).append(card)
    return dict(sorted(grouped.items()))


def collect(directory: Path | None = None) -> dict[str, Any]:
    """Собрать выгрузку из карточек ``data/cards/``.

    Raises:
        DataFormatError: каталога карточек нет или файл в нём повреждён.
    """
    entries = read_cards(directory)
    glossary = assemble(entries)
    groups = groups_of(entries)
    return {
        **envelope(SCHEMA_OF),
        "snapshot": {
            "cards": len(glossary),
            "schema_version": SCHEMA_VERSION,
            "digest": digest(glossary),
        },
        "groups": groups,
    }


def as_json(directory: Path | None = None) -> str:
    """Выгрузка как публикуемый JSON — полная, без усечения."""
    return json.dumps(collect(directory), ensure_ascii=False, indent=2) + "\n"
