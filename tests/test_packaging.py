"""Версия задаётся в одном месте и подставляется везде.

Правило каталога 035: ручная правка версии даёт расхождение, которое
обнаруживается **после публикации** — то есть тогда, когда чинить уже поздно.

РАЗБОР НАДВОЕ (правило 182). Человеческой половины у требования нет вовсе, и
прежний ответ «до него не дошли руки» это скрывал: он говорил про всё
требование сразу, а требование машинное целиком. Версия стояла дважды —
``pyproject.toml`` и ``src/glossary/__init__.py``, обе руками.

Источник теперь один: ``pyproject.toml``. Пакет читает его через метаданные
дистрибутива, а набор держит две разные вещи — что значения сходятся и что
второй записи не завелось снова. Первое ловит устаревшую установку, второе —
возврат ручного дубля; ни одна из проверок не покрывает другую.
"""

from __future__ import annotations

import ast
import tomllib

import pytest

import glossary
from glossary.loader import project_root

PYPROJECT = project_root() / "pyproject.toml"
INIT = project_root() / "src" / "glossary" / "__init__.py"
UNKNOWN = "0+unknown"


def declared_version() -> str:
    """Версия из единственного источника."""
    manifest = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    version: str = manifest["project"]["version"]
    return version


def hardcoded_versions(source: str) -> list[str]:
    """Строковые присваивания ``__version__`` в разборе модуля.

    Ищется присваивание, а не подстрока: подстрока «__version__» встречается и
    в ``__all__``, и в комментариях, и проверка на неё зеленела бы там, где
    отношения нет (правило 166 в его общей части).
    """
    found: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Assign):
            continue
        names = [t.id for t in node.targets if isinstance(t, ast.Name)]
        if "__version__" not in names:
            continue
        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            found.append(node.value.value)
    return found


def test_package_reports_a_real_version():
    """Заглушка означает «пакет не установлен», и в наборе её быть не должно."""
    assert glossary.__version__ != UNKNOWN, (
        "пакет не установлен в окружение — версия не измерена, а подставлена; "
        "запустите pip install -e ."
    )


def test_version_matches_the_single_source():
    assert glossary.__version__ == declared_version(), (
        f"версия пакета {glossary.__version__!r} разошлась с "
        f"{PYPROJECT.name} ({declared_version()!r}): установка устарела либо "
        "версия снова записана руками"
    )


def test_no_hardcoded_version_returns():
    """Ручной дубль расходится молча — поэтому его отвергают, а не сверяют."""
    literals = hardcoded_versions(INIT.read_text(encoding="utf-8"))
    assert literals == [UNKNOWN], (
        "в пакете снова записана версия строкой: "
        + ", ".join(repr(v) for v in literals)
        + ". Источник один — pyproject.toml; допустима только заглушка "
        f"{UNKNOWN!r} на случай запуска из дерева без установки"
    )


# --------------------------------------------------------------------------- #
# Гейт проверяется тем, что он обязан отвергнуть (правило 140)
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "source, expected",
    [
        ('__version__ = "1.2.3"', ["1.2.3"]),
        ('__all__ = ["__version__"]', []),
        ('# __version__ = "1.2.3"', []),
        ('__version__ = _distribution_version("glossary-python")', []),
    ],
)
def test_hardcoded_version_detection(source: str, expected: list[str]):
    assert hardcoded_versions(source) == expected
