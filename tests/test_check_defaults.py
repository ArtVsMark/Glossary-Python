"""Гейт на умолчания окружения: правило каталога 176.

Набор держит устройство разбора на подделках и отдельно — утверждение о живом
дереве. Зелёный гейт подтверждает себя, а не дерево (правило 146), поэтому
второе проверяется своим тестом и своими словами.

Главный предмет здесь — **тот вызов, который гейт обязан отвергнуть**
(правило 140). Он не выдуман: ровно в такой форме ``subprocess.run`` стоял в
``tests/test_data_integrity.py`` до того, как разбор ответа каталогу его нашёл.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import check_defaults
from glossary.loader import project_root

# Вызов, стоявший в дереве до правки: text=True берёт кодировку локали, и на
# ячейке матрицы с cp1252 разбор кириллицы в выводе развалился бы.
LIVE_DEFECT = """
import subprocess
result = subprocess.run(
    [sys.executable, "-m", "glossary", "completeness", "--format", "json"],
    capture_output=True,
    text=True,
    check=True,
)
"""


def whats_wrong(source: str) -> list[str]:
    """Что гейт скажет об этом исходнике."""
    return [finding.what for finding in check_defaults.inspect(source, "проба.py")]


# --------------------------------------------------------------------------- #
# Предметы, которые гейт обязан отвергнуть
# --------------------------------------------------------------------------- #


def test_the_live_defect_is_rejected():
    """Тот самый вызов, найденный разбором ответа каталогу, а не гейтом."""
    assert whats_wrong(LIVE_DEFECT) == ["run(text=…) без encoding="]


@pytest.mark.parametrize(
    "source, expected",
    [
        ('open("a.txt")', "open() без encoding="),
        ('open("a.txt", "w")', "open() без encoding="),
        ('Path("a").read_text()', "read_text() без encoding="),
        ('Path("a").write_text(text)', "write_text() без encoding="),
        ("datetime.now()", "datetime.now() без часового пояса"),
        ("dt.datetime.now()", "datetime.now() без часового пояса"),
        (
            "subprocess.check_output(cmd, universal_newlines=True)",
            "check_output(text=…) без encoding=",
        ),
    ],
)
def test_implicit_defaults_are_rejected(source: str, expected: str):
    assert whats_wrong(source) == [expected]


# --------------------------------------------------------------------------- #
# Предметы, которые гейт обязан пропустить: красное на верном коде приучает
# читать красное как фон (правило 051)
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "source",
    [
        'open("a.txt", encoding="utf-8")',
        'open("a.bin", "rb")',
        'open("a.bin", mode="wb")',
        'open("a.txt", "r", -1, "utf-8")',
        'Path("a").read_text(encoding="utf-8")',
        'Path("a").read_text("utf-8")',
        'Path("a").write_text(text, "utf-8")',
        "datetime.now(dt.UTC)",
        "datetime.now(tz=timezone.utc)",
        'subprocess.run(cmd, text=True, encoding="utf-8")',
        "subprocess.run(cmd, capture_output=True)",
    ],
)
def test_explicit_or_irrelevant_calls_pass(source: str):
    assert whats_wrong(source) == []


def test_a_helper_named_now_is_not_datetime_now():
    """Проверка по одному имени ловила бы собственный contracts.now().

    Это тот же промах, что и проверка отношения по подстроке: условие
    выполняется, а предмет другой (правило 166 в его общей части).
    """
    assert whats_wrong('{"generated_at": now()}') == []


# --------------------------------------------------------------------------- #
# Исходы команды и утверждение о живом дереве
# --------------------------------------------------------------------------- #


def test_empty_tree_is_the_third_outcome(tmp_path: Path, capsys):
    """Ноль модулей — «нечего смотреть», а не «чисто» (правила 075, 039)."""
    assert check_defaults.main(["--root", str(tmp_path)]) == 2
    error = capsys.readouterr().err
    assert "проверка не отработала" in error
    assert str(tmp_path) in error, "третий исход обязан назвать предмет (158)"


def test_findings_return_one(tmp_path: Path, capsys):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "m.py").write_text(LIVE_DEFECT, encoding="utf-8")
    assert check_defaults.main(["--root", str(tmp_path)]) == 1
    assert "без encoding=" in capsys.readouterr().err


@pytest.mark.live_surface
def test_repository_names_every_environment_default():
    """Утверждение о живом дереве, отдельно от проверки устройства."""
    findings, seen = check_defaults.scan(project_root())
    assert seen, "не разобрано ни одного модуля — гейт смотрел бы в пустоту"
    assert not findings, "\n".join(str(finding) for finding in findings)
