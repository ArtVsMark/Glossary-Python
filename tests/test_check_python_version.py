"""Гейт версий: код конвейера исполняется на объявленной версии Python."""

from pathlib import Path
from typing import Any

import pytest
import yaml

import check_python_version as gate

FLOOR = (3, 14)


def _wf(text: str) -> dict[str, Any]:
    return {"x.yml": yaml.safe_load(text)}


def test_python_before_setup_is_found():
    """Подделка: вызов до установки — находка с именем работы."""
    found = gate.findings(
        _wf("jobs:\n  arm:\n    steps:\n      - run: python a.py\n"), FLOOR, FLOOR
    )
    assert any("arm" in f and "раньше setup-python" in f for f in found)


def test_setup_first_is_silent():
    """Установка выше вызова — находок нет."""
    text = (
        "jobs:\n  a:\n    steps:\n      - uses: actions/setup-python@v7\n"
        "        with: {python-version: '3.14'}\n      - run: python a.py\n"
    )
    assert gate.findings(_wf(text), FLOOR, FLOOR) == []


def test_matrix_of_numbers_resolves_and_low_version_is_found():
    """Матрица из чисел сводится к версиям; ниже планки — находка."""
    text = (
        "jobs:\n  t:\n    strategy: {matrix: {python-version: ['3.13', '3.14']}}\n"
        "    steps:\n      - uses: actions/setup-python@v7\n"
        "        with: {python-version: '${{ matrix.python-version }}'}\n"
    )
    found = gate.findings(_wf(text), FLOOR, FLOOR)
    assert len(found) == 1 and "3.13" in found[0]


def test_unresolvable_version_is_found():
    """Версия не числом — сверять не с чем."""
    text = (
        "jobs:\n  t:\n    steps:\n      - uses: actions/setup-python@v7\n"
        "        with: {python-version-file: .python-version}\n"
    )
    assert any("без числа" in f for f in gate.findings(_wf(text), FLOOR, FLOOR))


def test_preview_not_ahead_is_found():
    """Предварительная на той же версии ничего не спрашивает."""
    text = (
        "jobs:\n  n:\n    steps:\n      - uses: actions/setup-python@v7\n"
        "        with: {python-version: '3.14', allow-prereleases: true}\n"
    )
    assert any("предварительная" in f for f in gate.findings(_wf(text), FLOOR, FLOOR))


def test_measurement_job_may_go_below_the_floor():
    """Работа замера названа: её младшие версии — предмет, а не находка."""
    text = (
        "jobs:\n  inventory:\n    strategy: {matrix: {python-version: ['3.11']}}\n"
        "    steps:\n      - uses: actions/setup-python@v7\n"
        "        with: {python-version: '${{ matrix.python-version }}'}\n"
    )
    assert gate.findings({"badges.yml": yaml.safe_load(text)}, FLOOR, FLOOR) == []


def test_window_below_floor_is_found():
    """Окно ниже планки — «чисто локально» снято не там."""
    assert any("ниже" in f for f in gate.findings({}, FLOOR, (3, 11)))


def test_no_workflows_is_the_third_outcome(tmp_path: Path):
    """Прогонов нет — исход 2, а не зелёное на пустоте."""
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nrequires-python = ">=3.14"\n', encoding="utf-8"
    )
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    assert gate.main(tmp_path) == gate.NOT_RUN


@pytest.mark.live_surface
def test_repository_complies():
    """Живая половина: прогоны дерева исполняют код на планке."""
    assert gate.main() == 0
