"""Планка Python читается из ``requires-python`` одним разбором."""

from pathlib import Path

import pytest

import python_floor


@pytest.mark.parametrize(
    ("spec", "expected"),
    [(">=3.11", (3, 11)), (">= 3.14", (3, 14)), (">=3.14,<4", (3, 14))],
)
def test_floor_is_the_lower_bound(spec: str, expected: tuple[int, int]):
    """Нижняя граница находится в любой из привычных записей."""
    text = f'[project]\nname = "x"\nrequires-python = "{spec}"\n'
    assert python_floor.floor(text) == expected


@pytest.mark.parametrize(
    "text",
    ['[project]\nname = "x"\n', '[project]\nrequires-python = "<4"\n'],
)
def test_missing_floor_is_refused(text: str):
    """Без нижней границы — отказ, а не догадка."""
    with pytest.raises(ValueError, match="requires-python"):
        python_floor.floor(text)


def test_unread_pyproject_is_the_third_outcome(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    """Файл не прочитан — исход 2 с адресом, а не пустая строка."""
    missing = tmp_path / "pyproject.toml"
    assert python_floor.main(missing) == python_floor.NOT_RUN
    assert str(missing) in capsys.readouterr().err


@pytest.mark.live_surface
def test_project_declares_a_floor(capsys: pytest.CaptureFixture[str]):
    """Живая половина: у проекта планка есть, и разбор её читает."""
    assert python_floor.main() == 0
    assert capsys.readouterr().out.strip().count(".") == 1
