"""Версия пакета: объявлена один раз, дальше только читается.

Число живёт в ``pyproject.toml`` — поле ``version`` секции ``[project]`` — и
больше нигде. Второй экземпляр расходится с первым молча: собранный
дистрибутив несёт одну версию, а ``glossary --version`` печатает другую, и
обнаруживается это после публикации, когда исправлять уже поздно.

Ответ берётся из метаданных **установленного** дистрибутива: сборка кладёт
туда ровно объявленное, поэтому источник остаётся один. ``importlib.metadata``
входит в стандартную библиотеку — ноль runtime-зависимостей сохраняется.

Дерево без установки метаданных не несёт вовсе. Там ответ —
:data:`UNINSTALLED`, а не правдоподобное число: правдоподобное стало бы вторым
ответом, сверить который не с чем, а ``0+unknown`` (форма PEP 440 с локальным
сегментом) ни с каким выпуском не спутать.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from typing import Final

__all__ = ["DISTRIBUTION", "UNINSTALLED", "package_version"]

DISTRIBUTION: Final = "glossary-python"
"""Имя дистрибутива — дословно поле ``name`` секции ``[project]``.

Имя импортируемого пакета (``glossary``) и имя дистрибутива
(``glossary-python``) различаются; метаданные ищутся по второму.
"""

UNINSTALLED: Final = "0+unknown"
"""Ответ, когда метаданных нет: пакет запущен из дерева без установки."""


def package_version(distribution: str = DISTRIBUTION) -> str:
    """Прочитать версию дистрибутива из метаданных окружения.

    Args:
        distribution: Имя дистрибутива, под которым он установлен.

    Returns:
        Версию из метаданных, а если дистрибутив не установлен —
        :data:`UNINSTALLED`.
    """
    try:
        return version(distribution)
    except PackageNotFoundError:
        return UNINSTALLED
