"""Общие фикстуры тестов."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from glossary.loader import default_data_path, load_glossary, project_root
from glossary.models import Glossary
from tests.factories import make_entry, make_glossary

# scripts/ — инструменты репозитория, а не часть пакета: пакет ставится
# в окружение, а скрипты живут рядом с ним и импортируются по пути.
sys.path.insert(0, str(project_root() / "scripts"))


@pytest.fixture(scope="session")
def real_data_path() -> Path:
    """Путь к боевому файлу данных репозитория."""
    path = default_data_path()
    if not path.exists():  # pragma: no cover - защита от запуска вне репозитория
        pytest.skip(f"файл данных не найден: {path}")
    return path


@pytest.fixture(scope="session")
def real_glossary(real_data_path: Path) -> Glossary:
    """Боевой глоссарий из data/glossary.json."""
    return load_glossary(real_data_path)


@pytest.fixture
def sample_glossary() -> Glossary:
    """Небольшой корректный глоссарий для юнит-тестов.

    Проходит все правила без единого замечания, поэтому любое сообщение в тесте
    относится к тому, что тест намеренно сломал. В каждом разделе не меньше двух
    карточек — иначе сработает правило ``section-size``.
    """
    return make_glossary(
        make_entry(id="alpha", title="alpha()", section="Первый"),
        make_entry(id="beta", title="beta()", section="Первый", subcat="другая"),
        make_entry(id="gamma", title="gamma()", section="Второй", color_group="module"),
        make_entry(id="delta", title="delta()", section="Второй", color_group="module"),
    )
