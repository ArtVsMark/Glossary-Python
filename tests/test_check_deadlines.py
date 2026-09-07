"""Сроки ожидания: правило каталога 100.

Набор держит две разные вещи. **Разбор** — чистые функции над текстом, и их
проверяют предметами, которые они обязаны отвергнуть: порождение процесса без
``timeout=`` и задание конвейера без ``timeout-minutes``. **Утверждение о живом
дереве** проверяется отдельно и своими словами (правило 146).

Оба предмета отказа взяты из этого дерева, а не выдуманы. Первый — форма, в
которой ``subprocess.run`` стоял здесь до гейта на умолчания. Второй — живой
пробел, найденный этим самым гейтом: у СЕМИ работ ``ci.yml`` и у выкладки
страниц срока не было вовсе.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import check_deadlines as deadlines
from glossary.loader import project_root

SPAWN_WITHOUT = "result = subprocess.run(cmd, capture_output=True, text=True)\n"
SPAWN_WITH = "result = subprocess.run(cmd, capture_output=True, timeout=30)\n"

JOB_WITHOUT = """name: проба
jobs:
  build:
    name: Сборка
    runs-on: ubuntu-latest
    steps:
      - run: echo привет
"""

JOB_WITH = """name: проба
jobs:
  build:
    name: Сборка
    runs-on: ubuntu-latest
    timeout-minutes: 7
    steps:
      - run: echo привет
"""

TWO_JOBS = """name: проба
jobs:
  first:
    timeout-minutes: 5
    runs-on: ubuntu-latest
  second:
    runs-on: ubuntu-latest
"""


# --------------------------------------------------------------------------- #
# Процесс: срок назван у порождения
# --------------------------------------------------------------------------- #


def test_spawn_without_a_deadline_is_a_finding():
    found = deadlines.spawns_without_deadline(SPAWN_WITHOUT, "поддельный.py")
    assert len(found) == 1
    assert "поддельный.py:1" in str(found[0]), "находка обязана назвать строку (158)"


def test_spawn_with_a_deadline_is_silent():
    assert deadlines.spawns_without_deadline(SPAWN_WITH, "поддельный.py") == []


@pytest.mark.parametrize("name", sorted(deadlines.SPAWNERS))
def test_every_spawner_of_the_dictionary_is_read(name: str):
    """Словарь закрыт и короток: имя вне его гейт не узнает — и скажет об этом."""
    found = deadlines.spawns_without_deadline(f"subprocess.{name}(cmd)\n", "п.py")
    assert len(found) == 1


def test_other_call_is_not_a_spawn():
    assert deadlines.spawns_without_deadline("json.dumps(данные)\n", "п.py") == []


def test_source_without_calls_is_silent():
    assert deadlines.spawns_without_deadline("x = 1\n", "п.py") == []


# --------------------------------------------------------------------------- #
# Работа конвейера: срок назван у задания
# --------------------------------------------------------------------------- #


def test_job_without_a_deadline_is_a_finding():
    found = deadlines.jobs_without_deadline(JOB_WITHOUT, "проба.yml")
    assert len(found) == 1
    assert "build" in str(found[0])
    assert "шесть часов" in str(found[0]), "находка называет цену умолчания"


def test_job_with_a_deadline_is_silent():
    assert deadlines.jobs_without_deadline(JOB_WITH, "проба.yml") == []


def test_only_the_job_without_a_deadline_is_found():
    found = deadlines.jobs_without_deadline(TWO_JOBS, "проба.yml")
    assert len(found) == 1
    assert "second" in str(found[0])


def test_deadline_outside_jobs_does_not_count():
    """Срок вне блока работ не считается: висит работа, а не файл целиком.

    Идентификаторы работ здесь латиницей не по вкусу, а потому, что площадка
    других не принимает: подделка с кириллическим именем проверяла бы случай,
    которого в жизни не бывает (правило 170).
    """
    text = "timeout-minutes: 9\njobs:\n  build:\n    runs-on: ubuntu-latest\n"
    assert len(deadlines.jobs_without_deadline(text, "проба.yml")) == 1


def test_workflow_without_jobs_is_silent():
    assert deadlines.jobs_without_deadline("name: пусто\non: push\n", "п.yml") == []


# --------------------------------------------------------------------------- #
# Исходы команды
# --------------------------------------------------------------------------- #


def test_empty_tree_is_the_third_outcome(tmp_path: Path, capsys):
    assert deadlines.main(["--root", str(tmp_path)]) == deadlines.NOT_RUN
    error = capsys.readouterr().err
    assert "не отработала" in error
    assert str(tmp_path) in error, "третий исход обязан назвать предмет (правило 158)"


def test_findings_return_one(tmp_path: Path, capsys):
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "п.py").write_text(SPAWN_WITHOUT, encoding="utf-8")
    assert deadlines.main(["--root", str(tmp_path)]) == 1
    assert "без названного срока" in capsys.readouterr().err


def test_clean_tree_returns_zero(tmp_path: Path, capsys):
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "п.py").write_text(SPAWN_WITH, encoding="utf-8")
    assert deadlines.main(["--root", str(tmp_path)]) == 0
    assert "сроки названы" in capsys.readouterr().out


# --------------------------------------------------------------------------- #
# Утверждения о живом дереве (правило 037)
# --------------------------------------------------------------------------- #


@pytest.mark.live_surface
def test_repository_has_waits_to_look_at():
    """У гейта есть предмет: смотреть не на что — это не гейт (правило 075)."""
    _, seen = deadlines.scan(project_root())
    assert seen, "ни исходников, ни прогонов не найдено — разбор смотрел в пустоту"


@pytest.mark.live_surface
def test_every_wait_of_the_repository_names_its_deadline():
    findings, _ = deadlines.scan(project_root())
    assert not findings, "\n".join(str(finding) for finding in findings)


@pytest.mark.live_surface
def test_every_pipeline_job_is_bounded():
    """Отдельно от разбора: наружная граница есть у КАЖДОЙ работы.

    ЗАМЕР: до этого гейта её не было ни у одной работы ci.yml — семь заданий и
    выкладка страниц ждали по умолчанию площадки, то есть шесть часов.
    """
    workflows = sorted(project_root().glob(deadlines.WORKFLOWS))
    assert workflows, "прогонов не найдено — проверять нечего"
    problems = [
        finding
        for path in workflows
        for finding in deadlines.jobs_without_deadline(
            path.read_text(encoding="utf-8"), path.name
        )
    ]
    assert not problems, "\n".join(str(problem) for problem in problems)
