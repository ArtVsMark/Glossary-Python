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

import pytest

import version as version_module
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


def _numbers(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.removeprefix("v").split("."))


def release_mismatch(declared: str, tag: str) -> str | None:
    """Расхождение поля version с тегом выпуска; ``None`` — совпадают.

    Поле в ``pyproject.toml`` — начало отсчёта схемы семьи: тег ``vX.Y.0``
    называет выпуск, и поле обязано называть тот же ``X.Y.0`` — либо
    следующий выпуск, который готовится (см. :func:`release_pending`).
    """
    if _numbers(declared) >= _numbers(tag):
        return None
    return f"pyproject.toml объявляет {declared}, а последний тег выпуска — {tag}"


def release_pending(declared: str, tag: str) -> bool:
    """Выпуск подготовлен, а тег ещё не поставлен.

    Тег ставится на коммит, который уже несёт новую версию, — то есть после
    слияния изменения, поднявшего её. Между ними поле законно новее тега, и
    сверка это называет, а не краснеет: красное на законном приучало бы читать
    красное как фон (правило каталога 051).
    """
    return _numbers(declared) > _numbers(tag)


def test_release_mismatch_is_caught_on_a_fake():
    """Подделка: сверка краснеет на отставании, а не сравнивает число с собой."""
    assert release_mismatch("0.1.0", "v0.1.0") is None
    assert release_mismatch("0.1.0", "v0.2.0") is not None
    assert release_mismatch("1.0.0", "v0.1.0") is None
    assert release_pending("1.0.0", "v0.1.0")
    assert not release_pending("0.1.0", "v0.1.0")


@pytest.mark.live_surface
def test_declared_version_names_the_latest_release_tag():
    """Живая половина: поле version совпадает с последним тегом выпуска.

    Без тегов в клоне сверять не с чем — это пропуск с названной причиной, а
    не зелёное: неглубокий клон без тегов неотличим от проекта до выпуска.
    Подготовленный выпуск без тега — тоже пропуск, и он называет, какой тег
    ждёт постановки.
    """
    tag = version_module.latest_tag()
    if tag is None:
        pytest.skip("тега выпуска в клоне не видно: git fetch --tags")
    declared = declared_version()
    problem = release_mismatch(declared, tag)
    assert problem is None, problem
    if release_pending(declared, tag):
        pytest.skip(f"выпуск {declared} подготовлен, тег v{declared} ещё не поставлен")
