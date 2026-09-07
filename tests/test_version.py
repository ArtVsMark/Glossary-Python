"""Версия объявлена один раз (правило каталога 035).

Число стоит в ``pyproject.toml``; ``glossary.__version__`` выводится из
метаданных установленного дистрибутива. Гейт держит три утверждения:

* объявленное в ``pyproject.toml`` совпадает с установленным;
* ``__version__`` совпадает с установленным;
* в исходниках пакета нет присваивания ``__version__`` литералом — второго
  места, где версию правят руками.

У каждого утверждения рядом стоит подделка, показывающая, что сверка краснеет
на расхождении. Без неё гейт неотличим от пустышки: сверка величины с самой
собой проходит всегда и не проверяет ничего (правило каталога 146).
"""

from __future__ import annotations

import ast
import tomllib
from importlib.metadata import version as installed_version
from pathlib import Path

from glossary import __version__
from glossary._version import DISTRIBUTION, UNINSTALLED, package_version
from glossary.loader import project_root

PYPROJECT = project_root() / "pyproject.toml"
PACKAGE = project_root() / "src" / "glossary"

REINSTALL = "переустановите пакет: pip install -e '.[dev,schema]'"


def declared_version(pyproject: Path = PYPROJECT) -> str:
    """Версия, объявленная в ``[project]`` — единственный источник числа."""
    payload = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    declared = payload["project"]["version"]
    assert isinstance(declared, str)
    return declared


def version_literals(source: Path) -> list[str]:
    """Присваивания ``__version__`` строковым литералом в одном файле.

    Разбор синтаксисом, а не поиском по тексту: упоминание имени в ``__all__``
    или в docstring — не второй источник версии, и гейт, спотыкающийся о них,
    научил бы обходить себя кавычками.
    """
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            targets: list[ast.expr] = list(node.targets)
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
        else:
            continue
        named = any(isinstance(t, ast.Name) and t.id == "__version__" for t in targets)
        value = node.value
        if named and isinstance(value, ast.Constant) and isinstance(value.value, str):
            found.append(value.value)
    return found


def test_tests_run_against_an_installed_distribution():
    """Без метаданных сверять нечего — и это не «версия неизвестна», а отказ."""
    assert __version__ != UNINSTALLED, f"пакет не установлен, {REINSTALL}"


def test_declared_version_matches_installed_distribution():
    assert declared_version() == installed_version(DISTRIBUTION), (
        f"объявленная версия разошлась с установленной, {REINSTALL}"
    )


def test_package_version_matches_installed_distribution():
    assert __version__ == installed_version(DISTRIBUTION)


def test_package_sources_carry_no_version_literal():
    offenders = sorted(
        str(path.relative_to(project_root()))
        for path in PACKAGE.rglob("*.py")
        if version_literals(path)
    )
    assert not offenders, "версия записана руками в " + ", ".join(offenders)


def test_declaration_gate_catches_a_divergence(tmp_path):
    """Подделка: объявление с другим числом — сверка обязана его увидеть."""
    installed = installed_version(DISTRIBUTION)
    fake = tmp_path / "pyproject.toml"
    fake.write_text(
        f'[project]\nname = "glossary-python"\nversion = "{installed}.dev1"\n',
        encoding="utf-8",
    )
    assert declared_version(fake) != installed


def test_literal_scan_catches_a_handwritten_version(tmp_path):
    """Подделка: вернувшийся в исходники литерал — скан обязан его найти."""
    fake = tmp_path / "__init__.py"
    fake.write_text('__version__ = "0.1.0"\n', encoding="utf-8")
    assert version_literals(fake) == ["0.1.0"]


def test_literal_scan_passes_the_derived_assignment(tmp_path):
    """Вывод из метаданных литералом не является — иначе гейт красен всегда."""
    fake = tmp_path / "__init__.py"
    fake.write_text(
        '__all__ = ["__version__"]\n__version__ = package_version()\n', encoding="utf-8"
    )
    assert version_literals(fake) == []


def test_uninstalled_tree_says_so_instead_of_guessing():
    """Дерева без установки метаданные не несут — ответ обязан это назвать."""
    assert package_version("glossary-python-not-installed") == UNINSTALLED
