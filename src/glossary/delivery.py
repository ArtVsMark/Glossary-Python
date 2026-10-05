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

``form`` — версия формы карточки строкой ``"мажор.минор"`` (#105). Мажор равен
``schema_version``: новое обязательное поле, смена смысла или удаление поля.
Минор — новое необязательное поле, о котором потребитель вправе не знать.
Журнал версий формы — ``docs/contracts.md``; потребитель закрепляет выпуск и по
журналу узнаёт, что изменилось, когда закрепление отстало. Форму выгрузки
описывает ``delivery.schema.json`` — она собирается из
``data/glossary.schema.json``, а не пишется второй раз руками.
"""

import copy
import json
from typing import TYPE_CHECKING, Any, Final

from glossary.cards import PUBLISHED, assemble, read_cards
from glossary.contracts import envelope
from glossary.loader import digest, project_root
from glossary.models import COLOR_GROUPS, SCHEMA_VERSION

if TYPE_CHECKING:
    from pathlib import Path

    from glossary.models import Entry

__all__ = [
    "FORM",
    "SCHEMA_OF",
    "as_json",
    "as_schema_json",
    "collect",
    "groups_of",
    "schema",
]

SCHEMA_OF: Final = "карточки глоссария по группам, в форме data/cards/"
"""Чего именно эта версия (правило каталога 164)."""

FORM_MINOR: Final = 0
"""Минор формы: растёт на новом необязательном поле, сбрасывается с мажором."""

FORM: Final = f"{SCHEMA_VERSION}.{FORM_MINOR}"
"""Версия формы карточки в выгрузке; мажор — ``schema_version``."""

CARD_SCHEMA: Final = "data/glossary.schema.json"


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
        "form": FORM,
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


def schema() -> dict[str, Any]:
    """JSON Schema выгрузки, собранная из схемы карточки ``data/glossary.schema.json``.

    Карточка в выгрузке — та же, что в схеме данных, без ``color_group``: группу
    задаёт ключ ``groups``. Вторую схему руками не пишут — она разошлась бы с
    первой на первом же новом поле (правило каталога 214).
    """
    cards = json.loads((project_root() / CARD_SCHEMA).read_text(encoding="utf-8"))
    defs = copy.deepcopy(cards["$defs"])
    entry = defs["entry"]
    entry["required"] = [name for name in entry["required"] if name != "color_group"]
    entry["properties"].pop("color_group", None)
    text = {"type": "string", "minLength": 1}
    return {
        "$schema": cards["$schema"],
        "title": "Glossary-Python delivery",
        "description": (
            f"Выгрузка карточек для потребителей, форма {FORM}. "
            "Собрана из data/glossary.schema.json."
        ),
        "type": "object",
        "required": [
            "schema",
            "schema_of",
            "producer",
            "source",
            "generated_at",
            "form",
            "snapshot",
            "groups",
        ],
        "properties": {
            "schema": text,
            "schema_of": text,
            "producer": text,
            "source": text,
            "generated_at": text,
            "form": {"const": FORM},
            "snapshot": {
                "type": "object",
                "required": ["cards", "schema_version", "digest"],
                "properties": {
                    "cards": {"type": "integer", "minimum": 0},
                    "schema_version": {"const": SCHEMA_VERSION},
                    "digest": text,
                },
            },
            "groups": {
                "type": "object",
                "propertyNames": {"enum": sorted(COLOR_GROUPS)},
                "additionalProperties": {
                    "type": "array",
                    "items": {"$ref": "#/$defs/entry"},
                },
            },
        },
        "$defs": defs,
    }


def as_schema_json() -> str:
    """JSON Schema выгрузки как публикуемый файл."""
    return json.dumps(schema(), ensure_ascii=False, indent=2) + "\n"
