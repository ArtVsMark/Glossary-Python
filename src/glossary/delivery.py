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

``moved`` — куда переехали карточки, которых больше нет: «старый id → новый»
(форма 4.1, #79). Карточку сливают с дублем, и её ``id`` исчезает, а у
потребителя на него остались ссылки. Без списка такая ссылка молча ведёт в
пустоту; со списком потребитель перенаправляет её сам. Источник — файл
``data/moved.json`` рядом с каталогом карточек.
"""

import copy
import json
from typing import TYPE_CHECKING, Any, Final

from glossary.cards import PUBLISHED, assemble, default_cards_dir, read_cards
from glossary.contracts import envelope
from glossary.errors import DataFormatError
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
    "moved",
    "schema",
]

SCHEMA_OF: Final = "карточки глоссария по группам, в форме data/cards/"
"""Чего именно эта версия (правило каталога 164)."""

FORM_MINOR: Final = 1
"""Минор формы: растёт на новом необязательном поле, сбрасывается с мажором."""

FORM: Final = f"{SCHEMA_VERSION}.{FORM_MINOR}"
"""Версия формы карточки в выгрузке; мажор — ``schema_version``."""

CARD_SCHEMA: Final = "data/glossary.schema.json"

MOVED_FILE: Final = "moved.json"
"""Файл переездов — рядом с каталогом карточек: ``data/moved.json``."""


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


def moved(
    directory: Path | None = None, ids: frozenset[str] = frozenset()
) -> dict[str, str]:
    """Прочитать переезды «старый id → новый» и сверить их с карточками.

    Файла нет — переездов нет. Если переданы ``ids`` опубликованных карточек,
    каждый новый ``id`` обязан среди них быть, а старый — нет: ссылка, которую
    перенаправили в пустоту, хуже ссылки, которую не перенаправили вовсе.

    Raises:
        DataFormatError: файл повреждён или переезд ведёт не туда.
    """
    path = (directory or default_cards_dir()).parent / MOVED_FILE
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise DataFormatError(f"{path}: не JSON — {exc}") from exc
    mapping = {k: v for k, v in raw.items() if not k.startswith("_")}
    if not all(isinstance(v, str) for v in mapping.values()):
        raise DataFormatError(f"{path}: новый id должен быть строкой")
    if ids:
        alive = sorted(old for old in mapping if old in ids)
        if alive:
            raise DataFormatError(f"{path}: карточки ещё существуют: {alive}")
        lost = sorted(f"{old} → {new}" for old, new in mapping.items() if new not in ids)
        if lost:
            raise DataFormatError(f"{path}: переезд в несуществующую карточку: {lost}")
    return dict(sorted(mapping.items()))


def collect(directory: Path | None = None) -> dict[str, Any]:
    """Собрать выгрузку из карточек ``data/cards/``.

    Raises:
        DataFormatError: каталога карточек нет или файл в нём повреждён.
    """
    entries = read_cards(directory)
    glossary = assemble(entries)
    groups = groups_of(entries)
    published = frozenset(card["id"] for cards in groups.values() for card in cards)
    return {
        **envelope(SCHEMA_OF),
        "form": FORM,
        "snapshot": {
            "cards": len(glossary),
            "schema_version": SCHEMA_VERSION,
            "digest": digest(glossary),
        },
        "groups": groups,
        "moved": moved(directory, published),
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
            "moved": {
                "type": "object",
                "description": "Куда переехали слитые карточки: старый id → новый.",
                "additionalProperties": {"type": "string", "minLength": 1},
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
