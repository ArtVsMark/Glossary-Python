"""Тесты загрузки и записи файла-источника."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from glossary.errors import DataFormatError
from glossary.loader import (
    default_data_path,
    dump_glossary,
    load_glossary,
    project_root,
)
from glossary.models import SCHEMA_VERSION
from tests.factories import make_entry, make_glossary


def write_data(path: Path, payload: object) -> Path:
    target = path / "glossary.json"
    target.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return target


def test_load_valid_file(tmp_path: Path):
    source = write_data(
        tmp_path,
        {"schema_version": SCHEMA_VERSION, "entries": [make_entry().to_dict()]},
    )
    glossary = load_glossary(source)
    assert len(glossary) == 1
    assert glossary.entries[0].id == "sample"


def test_missing_file_raises(tmp_path: Path):
    with pytest.raises(DataFormatError, match="не найден"):
        load_glossary(tmp_path / "нет.json")


def test_broken_json_raises(tmp_path: Path):
    target = tmp_path / "glossary.json"
    target.write_text("{не json", encoding="utf-8")
    with pytest.raises(DataFormatError, match="некорректный JSON"):
        load_glossary(target)


def test_top_level_array_raises(tmp_path: Path):
    source = write_data(tmp_path, [make_entry().to_dict()])
    with pytest.raises(DataFormatError, match="ожидался объект"):
        load_glossary(source)


def test_incompatible_schema_version_raises(tmp_path: Path):
    source = write_data(tmp_path, {"schema_version": 999, "entries": []})
    with pytest.raises(DataFormatError, match="несовместимая версия схемы"):
        load_glossary(source)


def test_entries_must_be_array(tmp_path: Path):
    source = write_data(tmp_path, {"schema_version": SCHEMA_VERSION, "entries": {}})
    with pytest.raises(DataFormatError, match="должен быть массивом"):
        load_glossary(source)


def test_entry_must_be_object(tmp_path: Path):
    source = write_data(
        tmp_path, {"schema_version": SCHEMA_VERSION, "entries": ["строка"]}
    )
    with pytest.raises(DataFormatError, match=r"entries\[0\]"):
        load_glossary(source)


def test_dump_then_load_roundtrip(tmp_path: Path):
    original = make_glossary(
        make_entry(id="alpha"), make_entry(id="beta", version="3.12+")
    )
    target = dump_glossary(original, tmp_path / "out.json")
    assert load_glossary(target).entries == original.entries


def test_dump_writes_stable_format(tmp_path: Path):
    target = dump_glossary(make_glossary(), tmp_path / "out.json")
    text = target.read_text(encoding="utf-8")
    assert text.endswith("}\n"), "файл должен заканчиваться переводом строки"
    assert '"$schema"' in text
    assert "\\u" not in text, "кириллица не должна экранироваться"


def test_dump_creates_parent_directories(tmp_path: Path):
    target = dump_glossary(make_glossary(), tmp_path / "вложенный" / "out.json")
    assert target.exists()


def test_project_root_finds_marker(tmp_path: Path):
    (tmp_path / "pyproject.toml").touch()
    nested = tmp_path / "a" / "b"
    nested.mkdir(parents=True)
    assert project_root(nested) == tmp_path.resolve()


def test_project_root_falls_back_to_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)
    isolated = tmp_path / "нет-маркеров"
    isolated.mkdir()
    assert project_root(isolated) == tmp_path.resolve()


def test_default_data_path_points_to_repository_file():
    assert default_data_path().name == "glossary.json"
    assert default_data_path().parent.name == "data"
