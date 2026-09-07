"""У сигнала пишут и то, чего он не означает: правило каталога 056.

Описание кода возврата состоит из двух половин, и **вторая нужнее первой**.
Первая говорит, когда сигнал появляется, — её пишут все. Вторая говорит, какой
вывод из него делать нельзя, и без неё «нечего проверять» читается как
«проверено, чисто».

РАЗБОР НАДВОЕ (правило 182). Верна ли вторая половина — суждение о предмете, и
машинной она не станет. **Что она написана** — следует из исходника целиком, и
держится это здесь.

ЗАМЕР, ИЗ-ЗА КОТОРОГО НАБОР ЗАВЕДЁН: у трёх кодов возврата CLI была описана
одна половина — что каждый означает. Чего они не означают, не было сказано ни
у одного, и ответ проекта по правилу 056 честно стоял «не дошли руки».
"""

from __future__ import annotations

import ast
from typing import Final

from glossary.loader import project_root

CLI = project_root() / "src" / "glossary" / "cli.py"
PREFIX: Final = "EXIT_"
NEGATIVE: Final = "не означает"
"""Оборот, которым пишется вторая половина.

Проверяется присутствие оборота, а не смысл: машина держит то, что вопрос
задан, — судить об ответе она не может (правило 182).
"""


def documented_signals(source: str) -> dict[str, str]:
    """Коды возврата и их описания, взятые разбором.

    Docstring у константы не доступен во время исполнения — он остаётся в
    разборе модуля и нигде больше. Поэтому читается именно дерево, а не
    импортированный объект.

    Args:
        source: Текст модуля.

    Returns:
        Отображение «имя константы → её описание»; пустая строка — описания нет.
    """
    module = ast.parse(source)
    found: dict[str, str] = {}
    previous: str | None = None
    for node in module.body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            name = node.target.id
            if name.startswith(PREFIX):
                found[name] = ""
                previous = name
                continue
            previous = None
            continue
        if (
            previous is not None
            and isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            found[previous] = node.value.value
        previous = None
    return found


def test_signals_exist():
    """У гейта должен быть предмет: сигналов нет — это не гейт (правило 075)."""
    signals = documented_signals(CLI.read_text(encoding="utf-8"))
    assert signals, f"в {CLI.name} не найдено ни одной константы {PREFIX}*"


def test_every_signal_says_what_it_does_not_mean():
    """Вторая половина нужнее первой — её отсутствие и есть предмет правила."""
    silent = [
        name
        for name, text in documented_signals(CLI.read_text(encoding="utf-8")).items()
        if NEGATIVE not in text.lower()
    ]
    assert not silent, (
        "у кода возврата описана только первая половина — что он означает. "
        f"Скажите и чего он НЕ означает: {', '.join(silent)} (правило 056)"
    )


def test_every_signal_says_what_it_does_mean():
    """Одной второй половины тоже мало: описание состоит из двух."""
    thin = [
        name
        for name, text in documented_signals(CLI.read_text(encoding="utf-8")).items()
        if len(text.strip()) < len(NEGATIVE) * 2
    ]
    assert not thin, "описание кода возврата пусто или почти пусто: " + ", ".join(thin)


# --------------------------------------------------------------------------- #
# Гейт проверяется тем, что он обязан отвергнуть (правило 140)
# --------------------------------------------------------------------------- #

FORGERY: Final = '''
"""Модуль."""

EXIT_OK: Final = 0
"""Успех."""

EXIT_FAILED: Final = 1
"""Проверка не пройдена. Не означает поломки инструмента."""

EXIT_SILENT: Final = 2

OTHER: Final = 3
"""Не код возврата, и спрашивать с него нечего."""
'''


def test_forged_module_is_read_correctly():
    signals = documented_signals(FORGERY)
    assert set(signals) == {"EXIT_OK", "EXIT_FAILED", "EXIT_SILENT"}
    assert signals["EXIT_SILENT"] == "", "константа без описания читается пустой"
    assert "OTHER" not in signals, "гейт спрашивает с кодов возврата, а не со всего"


def test_one_sided_description_is_rejected():
    silent = [
        name
        for name, text in documented_signals(FORGERY).items()
        if NEGATIVE not in text.lower()
    ]
    assert silent == ["EXIT_OK", "EXIT_SILENT"], silent
