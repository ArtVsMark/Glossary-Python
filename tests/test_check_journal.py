"""Запись журнала и чтение списка путей: правила каталога 138 и 165.

Набор держит две разные вещи. **Решение о записи** — чистая функция от списка
путей, и её проверяют предметом, который она обязана отвергнуть: изменение кода
без фрагмента. **Чтение списка из git** проверяется на настоящем дереве, и
предмет отказа не выдуман: файл с кириллическим именем — тот самый инцидент,
на котором родилось правило 165.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

import check_journal as journal
from glossary.loader import project_root

CYRILLIC = "changelog.d/сброс-настроек.added.md"
"""Имя из инцидента правила 165: без -z git отдал бы его экранированным."""


# --------------------------------------------------------------------------- #
# Решение о записи (правило 138)
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "path",
    ["scripts/facts.py", "src/glossary/cli.py", ".github/workflows/ci.yml"],
    ids=["скрипт", "пакет", "прогон"],
)
def test_code_change_without_a_fragment_is_a_finding(path: str):
    problems = journal.findings([path])
    assert len(problems) == 1
    assert path in problems[0], "находка обязана назвать файл (правило 158)"


def test_code_change_with_a_fragment_is_silent():
    assert journal.findings(["scripts/facts.py", "changelog.d/факт.fixed.md"]) == []


def test_change_outside_the_watched_paths_needs_nothing():
    """Правка карточки или README записи журнала не требует."""
    assert journal.findings(["README.md", "data/glossary.json"]) == []


def test_empty_change_needs_nothing():
    assert journal.findings([]) == []


def test_many_files_are_listed_briefly():
    """Находка называет предмет, а не вываливает весь состав изменения.

    Считаются перечисленные ПУТИ, а не запятые: запятые есть и в самой прозе
    сообщения, и такая мера показывала бы длину фразы, а не длину списка.
    """
    problems = journal.findings([f"scripts/файл{n}.py" for n in range(10)])
    assert problems[0].count("scripts/файл") == journal.SHOWN
    assert "…" in problems[0], "обрезка без маркера обрыва молчит (правило 016)"


def test_cyrillic_fragment_counts_as_a_record():
    """Ровно тот случай, ради которого читаем по NUL."""
    assert journal.findings(["scripts/facts.py", CYRILLIC]) == []


# --------------------------------------------------------------------------- #
# Чтение списка путей из git (правило 165)
# --------------------------------------------------------------------------- #


def git(root: Path, *args: str) -> None:
    """Тот же git по имени из PATH, что зовёт и сам гейт."""
    subprocess.run(  # noqa: S603
        ["git", *args],  # noqa: S607
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=journal.TIMEOUT,
    )


@pytest.fixture
def repository(tmp_path: Path) -> Path:
    """Крошечное дерево с одной веткой поверх основной."""
    git(tmp_path, "init", "--initial-branch=main", "--quiet")
    git(tmp_path, "config", "user.email", "проба@тут.рф")
    git(tmp_path, "config", "user.name", "Проба")
    (tmp_path / "README.md").write_text("основа\n", encoding="utf-8")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-qm", "основа")
    git(tmp_path, "checkout", "-q", "-b", "ветка")
    return tmp_path


def test_cyrillic_name_survives_the_reading(repository: Path):
    """ЗАМЕР ПРАВИЛА 165: без -z это имя приехало бы экранированным.

    Инцидент каталога дословно: из двадцати девяти файлов проверялось двадцать
    восемь, невидимым был ровно один — с кириллическим именем.
    """
    (repository / "changelog.d").mkdir()
    (repository / CYRILLIC.removeprefix("changelog.d/")).parent.mkdir(exist_ok=True)
    (repository / CYRILLIC).write_text("запись\n", encoding="utf-8")
    (repository / "scripts").mkdir()
    (repository / "scripts" / "что-то.py").write_text("x = 1\n", encoding="utf-8")
    git(repository, "add", "-A")
    git(repository, "commit", "-qm", "правка с записью")

    paths = journal.changed_paths("main", root=repository)
    assert CYRILLIC in paths, (
        "путь приехал экранированным — фрагмент, названный по-русски, стал бы "
        "невидимым, и гейт потребовал бы запись, которая лежит рядом"
    )
    assert journal.findings(paths) == []


def test_name_with_a_space_survives_too(repository: Path):
    (repository / "scripts").mkdir()
    (repository / "scripts" / "два слова.py").write_text("x = 1\n", encoding="utf-8")
    git(repository, "add", "-A")
    git(repository, "commit", "-qm", "правка без записи")

    paths = journal.changed_paths("main", root=repository)
    assert "scripts/два слова.py" in paths
    assert journal.findings(paths), "запись не приехала — это находка"


def test_unknown_base_is_the_third_outcome(repository: Path):
    with pytest.raises(journal.NotRunError) as refusal:
        journal.changed_paths("нет-такой-основы", root=repository)
    assert "нет-такой-основы" in str(refusal.value), "третий исход называет предмет"


def test_bad_base_returns_the_third_outcome_code(capsys):
    assert journal.main(["--base", "нет-такой-основы"]) == journal.NOT_RUN
    error = capsys.readouterr().err
    assert "не отработала" in error


def test_coverage_is_printed_always(capsys, monkeypatch):
    """Молчание без числа означает и «чисто», и «нечего смотреть» (075, 165)."""
    monkeypatch.setattr(journal, "changed_paths", lambda _base: ["README.md"])
    assert journal.main([]) == 0
    printed = capsys.readouterr().out
    assert "путей в изменении: 1" in printed
    assert "под наблюдением: 0" in printed


def test_finding_returns_one(capsys, monkeypatch):
    monkeypatch.setattr(journal, "changed_paths", lambda _base: ["scripts/что.py"])
    assert journal.main([]) == 1
    assert "не несёт" in capsys.readouterr().err


# --------------------------------------------------------------------------- #
# Утверждение о живом дереве (правило 037)
# --------------------------------------------------------------------------- #


@pytest.mark.live_surface
def test_repository_keeps_its_journal_directory():
    """У гейта есть предмет: каталога нет — записи класть некуда (075)."""
    fragments = project_root() / "changelog.d"
    assert fragments.is_dir(), f"каталога записей нет: {fragments}"
    assert any(fragments.glob("*.md")), "записей нет вовсе — гейт держал бы пустоту"


@pytest.mark.live_surface
def test_this_branch_carries_its_record():
    """Утверждение о живой ветке, отдельно от проверки разбора (правило 146)."""
    try:
        paths = journal.changed_paths(journal.DEFAULT_BASE)
    except journal.NotRunError as refusal:
        pytest.skip(f"основа недоступна в этом клоне: {refusal}")
    problems = journal.findings(paths)
    assert not problems, "\n".join(problems)
