"""Загрузка и сохранение файла-источника ``data/glossary.json``."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Final

from glossary.errors import DataFormatError
from glossary.models import SCHEMA_VERSION, Entry, Glossary

__all__ = [
    "DATA_FILENAME",
    "default_data_path",
    "dump_glossary",
    "load_glossary",
    "project_root",
]

DATA_FILENAME: Final = "glossary.json"
_ROOT_MARKERS: Final = ("pyproject.toml", ".git")
_SCHEMA_REF: Final = "./glossary.schema.json"


def project_root(start: Path | None = None) -> Path:
    """Найти корень репозитория, поднимаясь вверх от ``start``.

    Корнем считается ближайший каталог с ``pyproject.toml`` или ``.git``.
    Если маркеров нет (пакет установлен как зависимость), возвращается
    текущий рабочий каталог — тогда путь к данным задаётся явно.
    """
    origin = (start or Path(__file__)).resolve()
    for candidate in (origin, *origin.parents):
        if candidate.is_dir() and any((candidate / m).exists() for m in _ROOT_MARKERS):
            return candidate
    return Path.cwd()


def default_data_path() -> Path:
    """Путь к источнику истины по умолчанию — ``<корень>/data/glossary.json``."""
    return project_root() / "data" / DATA_FILENAME


def load_glossary(path: Path | None = None) -> Glossary:
    """Прочитать глоссарий из JSON-файла.

    Проверяется только структурная корректность — смысловые правила остаются
    за :mod:`glossary.validation`, чтобы одна битая карточка не мешала собрать
    полный отчёт по остальным.

    Raises:
        DataFormatError: файл отсутствует, не является валидным JSON,
            имеет неожиданную форму или несовместимую версию схемы.
    """
    source = path or default_data_path()
    try:
        raw_text = source.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise DataFormatError(f"Файл данных не найден: {source}") from exc
    except OSError as exc:  # pragma: no cover - зависит от окружения
        raise DataFormatError(f"Не удалось прочитать {source}: {exc}") from exc

    try:
        payload: Any = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise DataFormatError(f"{source}: некорректный JSON ({exc})") from exc

    if not isinstance(payload, dict):
        raise DataFormatError(
            f"{source}: ожидался объект с ключами 'schema_version' и 'entries', "
            f"получен {type(payload).__name__}"
        )

    version = payload.get("schema_version")
    if version != SCHEMA_VERSION:
        raise DataFormatError(
            f"{source}: несовместимая версия схемы {version!r}, "
            f"пакет поддерживает {SCHEMA_VERSION}"
        )

    raw_entries = payload.get("entries")
    if not isinstance(raw_entries, list):
        raise DataFormatError(f"{source}: 'entries' должен быть массивом")

    entries: list[Entry] = []
    for position, item in enumerate(raw_entries):
        if not isinstance(item, dict):
            raise DataFormatError(
                f"{source}: entries[{position}] должен быть объектом, "
                f"получен {type(item).__name__}"
            )
        entries.append(Entry.from_dict(item))

    return Glossary(entries=tuple(entries), schema_version=SCHEMA_VERSION)


def dump_glossary(glossary: Glossary, path: Path | None = None) -> Path:
    """Записать глоссарий обратно в файл-источник и вернуть путь.

    Формат фиксирован (``indent=2``, ``ensure_ascii=False``, перевод строки в
    конце), чтобы diff в git отражал смысловые правки, а не переформатирование.
    """
    target = path or default_data_path()
    payload = {
        "$schema": _SCHEMA_REF,
        "schema_version": glossary.schema_version,
        "entries": [entry.to_dict() for entry in glossary.entries],
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return target
