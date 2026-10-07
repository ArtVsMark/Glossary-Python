"""Навигация витрины: семейства разделов и подписи на двух языках.

Читатель ищет не по ``color_group`` — это цвет полосы карточки, а не смысл, — а
по тому, о чём карточка: тип, синтаксис, модуль. Поэтому фильтр витрины
двухуровневый: семейство, внутри него раздел. Схема повторяет навигацию
глоссария грейдера (его ``glossary/taxonomy.py``), чтобы человек, перешедший из
одного инструмента в другой, видел те же группы под теми же именами.

Классификация живёт здесь, а не в шаблоне: страница получает готовую таблицу
сборкой и правила у себя не повторяет (правило 214). Семейство вычисляется из
``section``, нового поля карточке не нужно.

Страховка от дрейфа: раздел, которого нет в :data:`SECTION_GROUPS`, падает в
``other`` («Прочее»), а ``tests/test_taxonomy.py`` требует, чтобы в снимке
данных ``other`` было пустым. Новый раздел обязан быть классифицирован явно.
"""

from typing import Final

__all__ = [
    "GROUPS",
    "GROUP_LABELS",
    "MODULE_PREFIX",
    "OTHER",
    "SECTION_GROUPS",
    "SECTION_LABELS_EN",
    "group_of",
    "section_label",
    "table",
]

MODULE_PREFIX: Final = "Модуль "
"""Разделы модулей стандартной библиотеки — одно семейство по префиксу."""

OTHER: Final = "other"

GROUPS: Final[tuple[str, ...]] = (
    "types",
    "syntax",
    "builtins",
    "io",
    "modules",
    "algorithms",
    OTHER,
)
"""Порядок семейств в фильтре: от основ языка к библиотеке."""

GROUP_LABELS: Final[dict[str, dict[str, str]]] = {
    "types": {"ru": "Типы данных", "en": "Data types"},
    "syntax": {"ru": "Синтаксис", "en": "Syntax"},
    "builtins": {"ru": "Встроенные и исключения", "en": "Built-ins & exceptions"},
    "io": {"ru": "Ввод-вывод и файлы", "en": "I/O & files"},
    "modules": {"ru": "Модули", "en": "Modules"},
    "algorithms": {"ru": "Алгоритмы", "en": "Algorithms"},
    OTHER: {"ru": "Прочее", "en": "Other"},
}

SECTION_GROUPS: Final[dict[str, str]] = {
    "Строки (str)": "types",
    "Списки (list)": "types",
    "Кортежи (tuple)": "types",
    "Словари (dict)": "types",
    "Множества (set)": "types",
    "Байтовые последовательности": "types",
    "Числа и математика": "types",
    "Типы данных": "types",
    "Встроенные типы": "types",
    "Функции": "syntax",
    "ООП": "syntax",
    "Циклы": "syntax",
    "Условный оператор": "syntax",
    "Итераторы и генераторы": "syntax",
    "Асинхронное программирование": "syntax",
    "Арифметика и операторы": "syntax",
    "Аннотации и typing": "syntax",
    "Модули и импорт": "syntax",
    "Встроенные функции": "builtins",
    "Исключения": "builtins",
    "Ввод и вывод": "io",
    "Файлы и I/O": "io",
    "Алгоритмы и структуры данных": "algorithms",
    # Как глава «Removed Modules» справочника библиотеки (library/removed.rst):
    # модули, которых в стандартной библиотеке больше нет, — всё равно модули,
    # а не синтаксис импорта (#164).
    "Удалённые модули": "modules",
}
"""Раздел → семейство. Разделы модулей сюда не входят: их узнаёт префикс."""

SECTION_LABELS_EN: Final[dict[str, str]] = {
    "Строки (str)": "Strings (str)",
    "Списки (list)": "Lists (list)",
    "Кортежи (tuple)": "Tuples (tuple)",
    "Словари (dict)": "Dictionaries (dict)",
    "Множества (set)": "Sets (set)",
    "Байтовые последовательности": "Byte sequences",
    "Числа и математика": "Numbers & math",
    "Типы данных": "Data types",
    "Встроенные типы": "Built-in types",
    "Функции": "Functions",
    "ООП": "OOP",
    "Циклы": "Loops",
    "Условный оператор": "Conditionals",
    "Итераторы и генераторы": "Iterators & generators",
    "Асинхронное программирование": "Async programming",
    "Арифметика и операторы": "Arithmetic & operators",
    "Аннотации и typing": "Annotations & typing",
    "Модули и импорт": "Modules & imports",
    "Встроенные функции": "Built-in functions",
    "Исключения": "Exceptions",
    "Ввод и вывод": "Input & output",
    "Файлы и I/O": "Files & I/O",
    "Алгоритмы и структуры данных": "Algorithms & data structures",
    "Удалённые модули": "Removed modules",
}
"""Английские подписи разделов. Имя раздела остаётся значением фильтра."""


def group_of(section: str) -> str:
    """Семейство раздела; неизвестный раздел — ``other``."""
    if section.startswith(MODULE_PREFIX):
        return "modules"
    return SECTION_GROUPS.get(section, OTHER)


def section_label(section: str, lang: str) -> str:
    """Подпись раздела в фильтре.

    Внутри семейства «Модули» префикс избыточен: читатель видит ``os``, а не
    «Модуль os». Имя модуля — идентификатор, переводу не подлежит.

    Args:
        section: Раздел карточки.
        lang: ``ru`` или ``en``.

    Returns:
        Подпись; незнакомый раздел показывается как есть.
    """
    if section.startswith(MODULE_PREFIX):
        return section.removeprefix(MODULE_PREFIX)
    if lang == "en":
        return SECTION_LABELS_EN.get(section, section)
    return section


def table(sections: list[str]) -> dict[str, object]:
    """Таблица навигации для страницы: порядок, подписи, принадлежность.

    Args:
        sections: Разделы, встречающиеся в данных.

    Returns:
        ``groups`` — порядок семейств, ``labels`` — их подписи по языкам,
        ``sections`` — раздел → семейство и подписи по языкам.
    """
    return {
        "groups": list(GROUPS),
        "labels": GROUP_LABELS,
        "sections": {
            section: {
                "group": group_of(section),
                "ru": section_label(section, "ru"),
                "en": section_label(section, "en"),
            }
            for section in sections
        },
    }
