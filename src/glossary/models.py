"""Доменные модели глоссария.

Форма карточки повторяет форму базы знаний ``ArtVsMark/Stepik-Python-Grader``,
откуда карточки переехали сюда (#76). Это не лень, а решение: грейдер читает
выгрузку отсюда, и совпадающая форма избавляет его импорт от отображения.

Модели неизменяемы: снимок загружается, проверяется и отдаётся наружу, но не
мутируется. Это исключает расхождение между экспортёрами.
"""

import re
from collections import Counter
from dataclasses import dataclass, field, fields
from typing import TYPE_CHECKING, Any, Final, Literal, Self, get_args

if TYPE_CHECKING:
    from collections.abc import Iterator

__all__ = [
    "ALL_OS",
    "COLOR_GROUPS",
    "KINDS",
    "LANGUAGES",
    "PLATFORMS",
    "SCHEMA_VERSION",
    "SYSTEMS",
    "ColorGroup",
    "Entry",
    "Glossary",
    "GlossaryStats",
    "Kind",
    "Language",
    "Platform",
    "Text",
    "block_since",
    "outlives_removal",
    "version_pair",
]

SCHEMA_VERSION: Final = 6
"""Версия формата ``data/glossary.json``.

Версия 1 хранила одноязычную карточку с полями ``name``/``group``/
``description``. Версия 2 приняла форму базы знаний грейдера: двуязычные
тексты, синонимы, связи и вид карточки. Версия 3 сделала двуязычными заголовок
и подкатегорию (#85): в английском режиме витрина больше не наполовину русская.
Раздел остаётся ключом — его подписи на двух языках живут в
:mod:`glossary.taxonomy`, по одной на раздел, а не по копии на карточку.
Версия 4 добавила ``platforms`` — на каких системах возможность есть (#83).
Версия 5 заменила ``version`` тремя полями жизненного цикла: ``added`` — с какой
версии возможность есть (``<3.0`` — ещё с Python 2), ``deprecated`` и
``removed`` — с какой устарела и до какой работает (#122). Версия 6 сделала
``examples`` списком самостоятельных блоков: каждый читается и исполняется
отдельно, а не сливается с соседями в одну простыню (#125).
"""

Language = Literal["ru", "en"]
LANGUAGES: Final[tuple[Language, ...]] = get_args(Language)

Kind = Literal["term", "function", "exception", "construct"]
"""Вид карточки: понятие, функция, исключение, синтаксическая конструкция."""

KINDS: Final[frozenset[str]] = frozenset(get_args(Kind))

ColorGroup = Literal[
    "builtin", "str", "seq", "mapset", "oop", "exc", "module", "iter", "op", "typing"
]
"""Цветовая группа витрины — она же файл в ``data/cards/``.

Карточки разложены по файлам (``builtin.json``, ``exc.json``, ``str.json``), и
файл несёт смысл: это верхнеуровневая рубрика. Сборка склеивает файлы в один
``data/glossary.json``, и граница между ними исчезает — поэтому рубрика
переезжает в поле карточки. Теги для этого не годятся: они
тематические (``os``, ``bytearray``, ``collections``) и группу не называют.
"""

COLOR_GROUPS: Final[frozenset[str]] = frozenset(get_args(ColorGroup))

Platform = Literal["AllOS", "Linux", "macOS", "Windows"]
"""На каких системах возможность доступна.

Три системы, а не перечень из документации CPython (``Unix, not WASI, not
Android``): учащийся спрашивает «заработает ли у меня», и ответ нужен про его
компьютер. WASI, Android и iOS в поле не попадают — это не платформы учебной
машины. «Везде» записывается явно — ``AllOS`` (решение владельца): пустой список
неотличим от «забыли заполнить».
"""

PLATFORMS: Final[tuple[Platform, ...]] = get_args(Platform)
ALL_OS: Final = "AllOS"
SYSTEMS: Final = ("Linux", "macOS", "Windows")


REQUIRES: Final = re.compile(r"^#\s*Python\s+(\d+)\.(\d+)\+")
"""Пометка блока примеров первой строкой: ``# Python 3.12+`` — работает с 3.12."""


def version_pair(text: str) -> tuple[int, int]:
    """Версия поля жизненного цикла как пара: ``<3.0`` раньше любой 3.x.

    Args:
        text: Значение ``added``, ``deprecated`` или ``removed``.

    Returns:
        ``(major, minor)``.
    """
    if text.startswith("<"):
        return (2, 7)
    major, minor = text.split(".")[:2]
    return int(major), int(minor)


def block_since(block: tuple[str, ...] | list[str]) -> tuple[int, int] | None:
    """С какой версии блок примеров обещает работать — по пометке первой строки.

    Returns:
        Версия из ``# Python 3.N+`` либо ``None``, если пометки нет.
    """
    marked = REQUIRES.match(block[0]) if block else None
    return (int(marked[1]), int(marked[2])) if marked else None


def outlives_removal(removed: str, block: tuple[str, ...] | list[str]) -> bool:
    """Описывает ли блок жизнь после удаления возможности (#164, #167).

    Блок с пометкой не раньше ``removed`` показывает замену или ошибку импорта
    на версии, где возможности уже нет; граница ``removed`` его не отсекает.
    Одна реализация на двоих: гейт примеров решает по ней, исполнять ли блок, а
    правило валидации — есть ли у удалённой карточки что показать (#247).
    """
    since = block_since(block)
    return bool(removed) and since is not None and since >= version_pair(removed)


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


def _blocks(raw: object) -> tuple[tuple[str, ...], ...]:
    """Блоки примеров из сырого значения.

    Плоский список строк — прежняя форма карточек, в которой их приносил
    выведенный из работы импорт из грейдера, — читается одним блоком. Пустые
    блоки отбрасываются, как и пустые строки внутри.
    """
    if not isinstance(raw, list | tuple):
        return ()
    if all(isinstance(item, str) for item in raw):
        flat = _tuple(raw)
        return (flat,) if flat else ()
    return tuple(block for item in raw if (block := _tuple(item)))


@dataclass(frozen=True, slots=True)
class Entry:
    """Одна карточка глоссария.

    Порядок полей значим: он определяет порядок ключей в снимке, а значит —
    воспроизводимость импорта и читаемость diff.
    """

    id: str
    title: Text
    kind: str
    summary: Text
    body: Text
    syntax: str = ""
    status: str = "ready"
    docs_url: str = ""
    added: str = ""
    deprecated: str = ""
    removed: str = ""
    platforms: tuple[str, ...] = (ALL_OS,)
    section: str = ""
    subcat: Text = field(default_factory=Text)
    color_group: str = "op"
    aliases: tuple[str, ...] = ()
    keywords: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    examples: tuple[tuple[str, ...], ...] = ()
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
            title=Text.from_any(raw.get("title")),
            kind=str(raw.get("kind", "")),
            summary=Text.from_any(raw.get("summary")),
            body=Text.from_any(raw.get("body")),
            syntax=str(raw.get("syntax", "")),
            status=str(raw.get("status", "")),
            docs_url=str(raw.get("docs_url", "")),
            added=str(raw.get("added", "")),
            deprecated=str(raw.get("deprecated", "")),
            removed=str(raw.get("removed", "")),
            platforms=_tuple(raw.get("platforms")),
            section=str(raw.get("section", "")),
            subcat=Text.from_any(raw.get("subcat")),
            color_group=str(raw.get("color_group", "") or "op"),
            aliases=_tuple(raw.get("aliases")),
            keywords=_tuple(raw.get("keywords")),
            tags=_tuple(raw.get("tags")),
            examples=_blocks(raw.get("examples")),
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
                payload[spec.name] = [
                    list(item) if isinstance(item, tuple) else item for item in value
                ]
            else:
                payload[spec.name] = value
        return payload

    def searchable(self, language: str = "ru") -> str:
        """Всё, по чему карточку ищут: имя, синонимы, ключевые слова, сводка."""
        parts = [
            self.title.get(language),
            self.summary.get(language),
            *self.aliases,
            *self.keywords,
        ]
        return " ".join(part for part in parts if part)


@dataclass(frozen=True, slots=True)
class Glossary:
    """Снимок глоссария вместе с версией формата."""

    entries: tuple[Entry, ...]
    schema_version: int = SCHEMA_VERSION
    _by_id: dict[str, Entry] = field(init=False, repr=False, compare=False)
    _by_lower: dict[str, Entry] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        """Построить индекс по идентификатору."""
        # Дубликаты id — находка валидатора, а не отказ загрузки: индекс
        # строится по первому вхождению, чтобы отчёт вышел полным.
        index: dict[str, Entry] = {}
        lowered: dict[str, Entry] = {}
        for entry in self.entries:
            index.setdefault(entry.id, entry)
            lowered.setdefault(entry.id.lower(), entry)
        object.__setattr__(self, "_by_id", index)
        object.__setattr__(self, "_by_lower", lowered)

    def __len__(self) -> int:
        """Количество карточек."""
        return len(self.entries)

    def __iter__(self) -> Iterator[Entry]:
        """Итерация по карточкам в исходном порядке."""
        return iter(self.entries)

    def get(self, entry_id: str) -> Entry | None:
        """Найти карточку по идентификатору."""
        return self._by_id.get(entry_id)

    def resolve(self, reference: str) -> Entry | None:
        """Найти карточку по ссылке из другой карточки.

        Точное совпадение, затем совпадение без учёта регистра. Второй проход
        нужен из-за конвенции источника: ``related_errors`` хранит имена
        исключений (``IndexError``), а идентификаторы карточек-исключений
        приведены к нижнему регистру. Конвенция нигде не записана, поэтому
        разрешение общее для всех видов ссылок — иначе оно разъедется по
        экспортёрам и витрине.
        """
        found = self._by_id.get(reference)
        if found is not None:
            return found
        return self._by_lower.get(reference.lower())

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
            versioned=sum(1 for e in self.entries if e.added),
            translated=sum(1 for e in self.entries if e.summary.en and e.body.en),
            with_related=sum(1 for e in self.entries if e.related),
            with_errors=sum(1 for e in self.entries if e.related_errors),
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
    with_errors: int
    avg_summary: float
