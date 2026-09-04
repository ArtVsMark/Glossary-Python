"""Доменные модели глоссария.

Форма карточки повторяет форму источника — базы знаний
``ArtVsMark/Stepik-Python-Grader``. Это не лень, а решение: у данных один
хозяин, и своя третья форма означала бы отображение в обе стороны и спор о
том, чья версия верна, у которого нет арбитра.

Модели неизменяемы: снимок загружается, проверяется и отдаётся наружу, но не
мутируется. Это исключает расхождение между экспортёрами.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field, fields
from typing import TYPE_CHECKING, Any, Final, Literal, Self, get_args

if TYPE_CHECKING:
    from collections.abc import Iterator

__all__ = [
    "COLOR_GROUPS",
    "KINDS",
    "LANGUAGES",
    "SCHEMA_VERSION",
    "ColorGroup",
    "Entry",
    "Glossary",
    "GlossaryStats",
    "Kind",
    "Language",
    "Text",
]

SCHEMA_VERSION: Final = 2
"""Версия формата ``data/glossary.json``.

Версия 1 хранила одноязычную карточку с полями ``name``/``group``/
``description``. Версия 2 приняла форму источника: двуязычные тексты,
синонимы, связи и вид карточки.
"""

Language = Literal["ru", "en"]
LANGUAGES: Final[tuple[Language, ...]] = get_args(Language)

Kind = Literal["term", "function", "exception", "construct"]
"""Вид карточки: понятие, функция, исключение, синтаксическая конструкция."""

KINDS: Final[frozenset[str]] = frozenset(get_args(Kind))

ColorGroup = Literal[
    "builtin", "str", "seq", "mapset", "oop", "exc", "module", "iter", "op", "typing"
]
"""Цветовая группа витрины — она же файл-источник в базе знаний.

В источнике карточки разложены по файлам (``builtin.json``, ``exc.json``,
``str.json``), и файл несёт смысл: это верхнеуровневая рубрика. Импорт
склеивает 11 файлов в один снимок, и граница между ними исчезает — поэтому
рубрика переезжает в поле карточки. Теги для этого не годятся: они
тематические (``os``, ``bytearray``, ``collections``) и группу не называют.
"""

COLOR_GROUPS: Final[frozenset[str]] = frozenset(get_args(ColorGroup))


@dataclass(frozen=True, slots=True)
class Text:
    """Текст на двух языках.

    Оба языка обязательны: пустой перевод — это не «нет перевода», а карточка,
    которая на одном из языков выглядит сломанной.
    """

    ru: str = ""
    en: str = ""

    def get(self, language: str) -> str:
        """Текст на указанном языке; при неизвестном языке — русский."""
        return self.en if language == "en" else self.ru

    def to_dict(self) -> dict[str, str]:
        """Представление, совпадающее с формой источника."""
        return {"ru": self.ru, "en": self.en}

    @classmethod
    def from_any(cls, raw: object) -> Self:
        """Собрать текст из словаря источника или из голой строки."""
        if isinstance(raw, dict):
            return cls(ru=str(raw.get("ru", "")), en=str(raw.get("en", "")))
        return cls(ru=str(raw or ""))


def _tuple(raw: object) -> tuple[str, ...]:
    """Список строк из сырого значения; всё лишнее отбрасывается."""
    if isinstance(raw, list | tuple):
        return tuple(str(item) for item in raw if str(item).strip())
    return ()


@dataclass(frozen=True, slots=True)
class Entry:
    """Одна карточка глоссария.

    Порядок полей значим: он определяет порядок ключей в снимке, а значит —
    воспроизводимость импорта и читаемость diff.
    """

    id: str
    title: str
    kind: str
    summary: Text
    body: Text
    syntax: str = ""
    status: str = "ready"
    docs_url: str = ""
    version: str = ""
    section: str = ""
    subcat: str = ""
    color_group: str = "op"
    aliases: tuple[str, ...] = ()
    keywords: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    examples: tuple[str, ...] = ()
    related: tuple[str, ...] = ()
    related_errors: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> Self:
        """Собрать карточку из формы источника, отбрасывая неизвестные ключи.

        Отсутствующие поля заменяются пустыми: за их наличие отвечает валидатор,
        который сообщит о каждом пропуске отдельной находкой.
        """
        return cls(
            id=str(raw.get("id", "")),
            title=str(raw.get("title", "")),
            kind=str(raw.get("kind", "")),
            summary=Text.from_any(raw.get("summary")),
            body=Text.from_any(raw.get("body")),
            syntax=str(raw.get("syntax", "")),
            status=str(raw.get("status", "")),
            docs_url=str(raw.get("docs_url", "")),
            version=str(raw.get("version", "")),
            section=str(raw.get("section", "")),
            subcat=str(raw.get("subcat", "")),
            color_group=str(raw.get("color_group", "") or "op"),
            aliases=_tuple(raw.get("aliases")),
            keywords=_tuple(raw.get("keywords")),
            tags=_tuple(raw.get("tags")),
            examples=_tuple(raw.get("examples")),
            related=_tuple(raw.get("related")),
            related_errors=_tuple(raw.get("related_errors")),
        )

    def to_dict(self) -> dict[str, Any]:
        """Представить карточку в каноническом порядке полей."""
        payload: dict[str, Any] = {}
        for spec in fields(self):
            value = getattr(self, spec.name)
            if isinstance(value, Text):
                payload[spec.name] = value.to_dict()
            elif isinstance(value, tuple):
                payload[spec.name] = list(value)
            else:
                payload[spec.name] = value
        return payload

    def searchable(self, language: str = "ru") -> str:
        """Всё, по чему карточку ищут: имя, синонимы, ключевые слова, сводка."""
        parts = [self.title, self.summary.get(language), *self.aliases, *self.keywords]
        return " ".join(part for part in parts if part)


@dataclass(frozen=True, slots=True)
class Glossary:
    """Снимок глоссария вместе с версией формата."""

    entries: tuple[Entry, ...]
    schema_version: int = SCHEMA_VERSION
    _by_id: dict[str, Entry] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        """Построить индекс по идентификатору."""
        # Дубликаты id — находка валидатора, а не отказ загрузки: индекс
        # строится по первому вхождению, чтобы отчёт вышел полным.
        index: dict[str, Entry] = {}
        for entry in self.entries:
            index.setdefault(entry.id, entry)
        object.__setattr__(self, "_by_id", index)

    def __len__(self) -> int:
        """Количество карточек."""
        return len(self.entries)

    def __iter__(self) -> Iterator[Entry]:
        """Итерация по карточкам в исходном порядке."""
        return iter(self.entries)

    def get(self, entry_id: str) -> Entry | None:
        """Найти карточку по идентификатору."""
        return self._by_id.get(entry_id)

    @property
    def sections(self) -> tuple[str, ...]:
        """Разделы в порядке первого появления — он же порядок в витрине."""
        return tuple(dict.fromkeys(e.section for e in self.entries))

    def in_section(self, section: str) -> tuple[Entry, ...]:
        """Карточки одного раздела с сохранением исходного порядка."""
        return tuple(e for e in self.entries if e.section == section)

    def stats(self) -> GlossaryStats:
        """Сводная статистика по снимку."""
        total = len(self.entries)
        return GlossaryStats(
            total=total,
            sections=Counter(e.section for e in self.entries),
            kinds=Counter(e.kind for e in self.entries),
            color_groups=Counter(e.color_group for e in self.entries),
            versioned=sum(1 for e in self.entries if e.version),
            translated=sum(1 for e in self.entries if e.summary.en and e.body.en),
            with_related=sum(1 for e in self.entries if e.related),
            avg_summary=(
                sum(len(e.summary.ru) for e in self.entries) / total if total else 0.0
            ),
        )


@dataclass(frozen=True, slots=True)
class GlossaryStats:
    """Агрегаты, которые показывает команда ``glossary stats``."""

    total: int
    sections: Counter[str]
    kinds: Counter[str]
    color_groups: Counter[str]
    versioned: int
    translated: int
    with_related: int
    avg_summary: float
