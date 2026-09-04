"""Инвентарь официального Python — чем меряется полнота глоссария.

Полноту нельзя мерить относительно самого глоссария: он полон по построению.
Эталон — сам язык, и снимается он **интроспекцией работающего интерпретатора**,
а не разбором документации. Причин две. Документация — внешний сайт: её разбор
требует сети, ломается от смены вёрстки и врёт при опечатке в HTML.
Интерпретатор же не может ошибиться в том, что в нём есть.

Цена решения названа честно: интроспекция видит **объекты**, а не текст. Из неё
не следует ни синтаксис (`match`, walrus, спецификаторы f-строк), ни удаления,
ни то, что элемент устарел. Такие пласты остаются непокрытыми, и это записано,
а не умолчано.

**Версия — ось измерения, а не настройка.** Инвентарь снимается с той версии, на
которой запущен, и говорит об этом в ``python_version``. Разность двух
инвентарей отвечает на вопрос «что появилось в 3.14» без единого обращения к
документации: то, чего в 3.13 не было, а в 3.14 есть.

Модуль — лист: он не знает ни о карточках, ни о валидаторе, ни об остальном
пакете. Сопоставлением занимается :mod:`glossary.coverage`, и эта граница
держит инвентарь пригодным к переносу — он ничей.
"""

from __future__ import annotations

import builtins
import importlib
import inspect
import sys
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, Literal, get_args

if TYPE_CHECKING:
    from collections.abc import Iterator

__all__ = [
    "BUILTIN_TYPES",
    "INVENTORY_KINDS",
    "SCHEMA_OF",
    "STDLIB_MODULES",
    "Inventory",
    "InventoryKind",
    "Item",
    "build_inventory",
    "difference",
    "python_version",
]

SCHEMA_OF: Final = "инвентарь официального Python на одной версии интерпретатора"
"""Чего именно эта версия (правило каталога 164)."""

InventoryKind = Literal["function", "class", "exception", "method"]
INVENTORY_KINDS: Final[frozenset[str]] = frozenset(get_args(InventoryKind))

BUILTIN_TYPES: Final[tuple[type, ...]] = (
    str,
    bytes,
    bytearray,
    list,
    tuple,
    dict,
    set,
    frozenset,
    int,
    float,
    complex,
)
"""Типы, чьи методы инвентаризируются.

Пласт, которого сканер ``builtins`` не видит: он собирает сами классы (``str``,
``list``), но не ``str.split`` и ``list.append`` — а именно с ними и работает
человек. В глоссарии этих карточек больше, чем любых других.
"""

STDLIB_MODULES: Final[frozenset[str]] = frozenset(
    {
        # Ядро: с этим сталкиваются раньше всего.
        "abc",
        "collections",
        "collections.abc",
        "contextlib",
        "copy",
        "dataclasses",
        "enum",
        "functools",
        "io",
        "itertools",
        "json",
        "math",
        "operator",
        "os",
        "os.path",
        "pathlib",
        "random",
        "re",
        "statistics",
        "string",
        "sys",
        "textwrap",
        "typing",
        # Разделы, которые глоссарий уже ведёт: не измерять их значило бы
        # объявить полными по умолчанию.
        "bisect",
        "concurrent.futures",
        "datetime",
        "hashlib",
        "heapq",
        "logging",
        "sqlite3",
        "subprocess",
        "threading",
        "unittest",
        # Темы, карточек по которым нет вовсе. Здесь они намеренно: пробел,
        # который не измеряют, не отличается от закрытой темы.
        "argparse",
        "csv",
        "decimal",
        "fractions",
        "shutil",
        "struct",
        "time",
        "uuid",
    }
)
"""Курируемый набор модулей.

Список конечен и меняется явным изменением, а не автоматически: иначе состав
инвентаря поехал бы вместе с версией интерпретатора, и разность двух версий
перестала бы отвечать на вопрос «что появилось», начав отвечать на «что мы
решили посмотреть».
"""


def python_version() -> str:
    """Версия работающего интерпретатора как ``major.minor``."""
    return f"{sys.version_info.major}.{sys.version_info.minor}"


@dataclass(frozen=True, slots=True, order=True)
class Item:
    """Одна сущность языка или стандартной библиотеки.

    ``qualname`` — то, как это пишут в коде: ``ValueError``, ``functools.reduce``,
    ``str.split``. Это же значение служит идентификатором карточки в глоссарии,
    поэтому сопоставление идёт точным совпадением, без эвристик.
    """

    qualname: str
    module: str
    kind: str


@dataclass(frozen=True, slots=True)
class Inventory:
    """Снимок языка на одной версии интерпретатора."""

    items: tuple[Item, ...]
    python_version: str

    def __len__(self) -> int:
        """Сколько сущностей в снимке."""
        return len(self.items)

    def __iter__(self) -> Iterator[Item]:
        """Итерация по сущностям в каноническом порядке."""
        return iter(self.items)

    @property
    def qualnames(self) -> frozenset[str]:
        """Все полные имена снимка — для сопоставления и разности версий."""
        return frozenset(item.qualname for item in self.items)

    def of_kind(self, kind: str) -> tuple[Item, ...]:
        """Сущности одного вида."""
        return tuple(item for item in self.items if item.kind == kind)


def _is_public(name: str) -> bool:
    """Имя предназначено пользователю, а не реализации."""
    return not name.startswith("_")


def _public_names(module: object) -> list[str]:
    """Публичные имена модуля: ``__all__``, если объявлен, иначе ``dir()``.

    ``__all__`` — заявление автора модуля о том, что здесь публично. Оно точнее
    ``dir()``, который приносит ещё и импортированные модулем чужие имена.
    """
    declared = getattr(module, "__all__", None)
    if isinstance(declared, list | tuple):
        return [str(name) for name in declared if _is_public(str(name))]
    return [name for name in dir(module) if _is_public(name)]


def _classify(obj: object) -> str | None:
    """Определить вид объекта; ``None`` — не то, что инвентаризируется.

    Исключения сюда не попадают: их собирает обход иерархии ``BaseException``,
    иначе одна и та же сущность оказалась бы в снимке дважды.
    """
    if isinstance(obj, type):
        if issubclass(obj, BaseException):
            return None
        return "class"
    if inspect.isroutine(obj):
        return "function"
    return None


def _builtin_items() -> list[Item]:
    """Публичные функции и классы модуля ``builtins``, кроме исключений."""
    items: list[Item] = []
    for name in dir(builtins):
        if not _is_public(name):
            continue
        kind = _classify(getattr(builtins, name))
        if kind is not None:
            items.append(Item(qualname=name, module="builtins", kind=kind))
    return items


def _module_items(names: frozenset[str]) -> list[Item]:
    """Публичные функции и классы курируемых модулей.

    Модуль, которого в этой версии Python нет, пропускается молча: набор общий
    для всех версий матрицы, и его отсутствие — свойство версии, а не ошибка.
    """
    items: list[Item] = []
    for module_name in sorted(names):
        try:
            module = importlib.import_module(module_name)
        except ImportError:
            continue
        for name in _public_names(module):
            member = getattr(module, name, None)
            if member is None:
                continue
            kind = _classify(member)
            if kind is not None:
                items.append(
                    Item(
                        qualname=f"{module_name}.{name}",
                        module=module_name,
                        kind=kind,
                    )
                )
    return items


def _method_items(types: tuple[type, ...]) -> list[Item]:
    """Публичные методы встроенных типов.

    Дескрипторы данных (``int.numerator``, ``float.real``) отбрасываются: это
    свойства значения, а не операции над ним, и карточка им не полагается.
    """
    items: list[Item] = []
    for type_ in types:
        for name in dir(type_):
            if not _is_public(name):
                continue
            member = inspect.getattr_static(type_, name, None)
            if member is None or not callable(member):
                continue
            items.append(
                Item(
                    qualname=f"{type_.__name__}.{name}",
                    module="builtins",
                    kind="method",
                )
            )
    return items


def _exception_items(names: frozenset[str]) -> list[Item]:
    """Исключения, достижимые обходом иерархии ``BaseException``.

    Обход рекурсивный, а не список из ``builtins``: так в снимок попадают и
    исключения курируемых модулей (``json.JSONDecodeError``), которые плоский
    список не увидел бы.

    Отбор жёсткий — только ``builtins`` и курируемые модули. Обход добирается
    и до внутренностей реализации (``_csv.Error``, ``_pickle.PicklingError``,
    исключений сторонних пакетов, оказавшихся в окружении). Публично они
    называются иначе или не называются вовсе, и требовать на них карточку
    значило бы требовать описания того, чего в языке нет.
    """
    allowed = names | {"builtins"}
    seen: dict[str, Item] = {}
    queue: list[type[BaseException]] = [BaseException]
    visited: set[type[BaseException]] = set()
    while queue:
        current = queue.pop()
        if current in visited:
            continue
        visited.add(current)
        module = getattr(current, "__module__", "builtins")
        if module in allowed and _is_public(current.__name__):
            qualname = (
                current.__name__
                if module == "builtins"
                else f"{module}.{current.__name__}"
            )
            seen.setdefault(
                qualname, Item(qualname=qualname, module=module, kind="exception")
            )
        # Обход продолжается и через отвергнутый класс: приватный предок может
        # иметь публичных потомков, и остановка здесь их бы потеряла.
        queue.extend(current.__subclasses__())
    return list(seen.values())


def build_inventory(modules: frozenset[str] | None = None) -> Inventory:
    """Снять инвентарь с работающего интерпретатора.

    Порядок детерминирован (по ``qualname``), дубликаты сняты по полному имени:
    один и тот же снимок на одной версии Python даёт побайтово один результат,
    иначе разность версий показывала бы шум вместо изменений языка.
    """
    names = STDLIB_MODULES if modules is None else modules
    collected: list[Item] = [
        *_builtin_items(),
        *_module_items(names),
        *_method_items(BUILTIN_TYPES),
        # Исключения последними: модули к этому моменту импортированы, и обход
        # иерархии видит те, что объявлены ими.
        *_exception_items(names),
    ]
    unique: dict[str, Item] = {}
    for item in collected:
        unique.setdefault(item.qualname, item)
    return Inventory(
        items=tuple(sorted(unique.values())),
        python_version=python_version(),
    )


def difference(before: Inventory, after: Inventory) -> tuple[Item, ...]:
    """Что есть в ``after`` и чего не было в ``before``.

    Это и есть ответ на «что появилось в 3.14»: разность двух снимков языка,
    без единого обращения к документации. Обратный порядок аргументов даёт
    удалённое — та же операция, другой вопрос.

    Сравнение идёт по полному имени, а не по объекту: между версиями объекты
    разные, а имя — то, что человек ищет в глоссарии.

    Warning:
        Разность честна только при **одинаковом наборе курируемых модулей**.
        Расширив :data:`STDLIB_MODULES`, вы получите «новое» там, где на самом
        деле «раньше не смотрели», — поэтому набор и меняется явным изменением.
    """
    known = before.qualnames
    return tuple(item for item in after if item.qualname not in known)
