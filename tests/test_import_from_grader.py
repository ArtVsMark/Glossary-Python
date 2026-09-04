"""Тесты импорта из базы знаний грейдера.

Импорт — единственная дверь, через которую в проект попадает содержание.
Ошибка здесь не видна глазами: снимок соберётся, витрина построится, а карточки
окажутся не те. Поэтому проверяется не «отработало без исключения», а форма
результата: порядок, дедуп, отбор по статусу и происхождение цветовой группы.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

import import_from_grader as imp
from glossary.models import SCHEMA_VERSION


def card(**overrides: Any) -> dict[str, Any]:
    """Карточка в форме источника."""
    base: dict[str, Any] = {
        "id": "sample",
        "title": "sample()",
        "kind": "function",
        "summary": {"ru": "Сводка.", "en": "Summary."},
        "body": {"ru": "Тело.", "en": "Body."},
        "syntax": "sample()",
        "status": "ready",
        "docs_url": "https://docs.python.org/3/library/functions.html#sample",
        "version": "",
        "section": "Раздел",
        "subcat": "подкатегория",
        "examples": ["sample()"],
    }
    return base | overrides


def make_source(root: Path, files: dict[str, list[dict[str, Any]]]) -> Path:
    """Разложить карточки по файлам так, как это сделано в источнике."""
    data_dir = root / imp.DATA_SUBPATH
    data_dir.mkdir(parents=True)
    for name, cards in files.items():
        path = data_dir / f"{name}.json"
        path.write_text(json.dumps(cards, ensure_ascii=False), encoding="utf-8")
    return root


def test_color_group_comes_from_file_name(tmp_path: Path):
    """Рубрика источника выражена именем файла — при склейке её больше неоткуда взять."""
    source = make_source(
        tmp_path, {"str": [card(id="a")], "exc": [card(id="b", kind="exception")]}
    )
    groups = {c["id"]: c["color_group"] for c in imp.read_source(source)}
    assert groups == {"a": "str", "b": "exc"}


def test_file_name_wins_over_topical_tags(tmp_path: Path):
    """Теги источника тематические (`os`, `bytearray`) и группу не задают."""
    source = make_source(tmp_path, {"seq": [card(id="a", tags=["bytearray"])]})
    assert imp.read_source(source)[0]["color_group"] == "seq"


def test_missing_directory_is_an_input_error(tmp_path: Path):
    with pytest.raises(SystemExit, match="каталог карточек не найден"):
        imp.read_source(tmp_path)


def test_empty_directory_is_an_input_error(tmp_path: Path):
    """Ноль файлов — не пустой глоссарий, а неверно указанный источник."""
    (tmp_path / imp.DATA_SUBPATH).mkdir(parents=True)
    with pytest.raises(SystemExit, match="нет ни одного файла"):
        imp.read_source(tmp_path)


def test_non_list_payload_is_rejected(tmp_path: Path):
    data_dir = tmp_path / imp.DATA_SUBPATH
    data_dir.mkdir(parents=True)
    (data_dir / "str.json").write_text('{"id": "a"}', encoding="utf-8")
    with pytest.raises(SystemExit, match="ожидался массив карточек"):
        imp.read_source(tmp_path)


def test_build_keeps_only_published_cards():
    """Черновики остаются в источнике: витрина показывает готовое."""
    glossary = imp.build(
        [
            card(id="a", color_group="str"),
            card(id="b", color_group="str", status="draft"),
        ]
    )
    assert [e.id for e in glossary] == ["a"]


def test_build_orders_by_section_then_id():
    """Порядок не зависит от порядка файлов на диске — иначе снимок «дышит»."""
    glossary = imp.build(
        [
            card(id="я", section="Второй", color_group="str"),
            card(id="b", section="Первый", color_group="str"),
            card(id="a", section="Второй", color_group="str"),
        ]
    )
    assert [e.id for e in glossary] == ["a", "я", "b"]


def test_build_drops_duplicate_ids():
    """Дубликат id сломал бы якоря витрины, и молча."""
    glossary = imp.build(
        [
            card(id="dup", title="первая", color_group="str"),
            card(id="dup", title="вторая", color_group="str"),
        ]
    )
    assert len(glossary) == 1
    assert glossary.entries[0].title == "первая"


def test_build_stamps_current_schema_version():
    assert imp.build([card(color_group="str")]).schema_version == SCHEMA_VERSION


def test_import_is_idempotent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Один и тот же вход даёт побайтово одинаковый снимок."""
    source = make_source(tmp_path / "src", {"str": [card(id="a"), card(id="b")]})
    target = tmp_path / "glossary.json"
    monkeypatch.setattr(imp, "default_data_path", lambda: target)
    monkeypatch.setattr(imp, "ROOT", tmp_path)

    assert imp.main(["--source", str(source)]) == 0
    first = target.read_bytes()
    assert imp.main(["--source", str(source)]) == 0
    assert target.read_bytes() == first


def test_check_passes_on_matching_snapshot(tmp_path: Path, monkeypatch):
    source = make_source(tmp_path / "src", {"str": [card(id="a"), card(id="b")]})
    target = tmp_path / "glossary.json"
    monkeypatch.setattr(imp, "default_data_path", lambda: target)
    monkeypatch.setattr(imp, "ROOT", tmp_path)

    imp.main(["--source", str(source)])
    assert imp.main(["--source", str(source), "--check"]) == 0


def test_check_fails_when_snapshot_drifted(tmp_path: Path, monkeypatch):
    """Гейт проверяется тем, что он обязан отвергнуть (каталог, 140/145)."""
    source = make_source(tmp_path / "src", {"str": [card(id="a"), card(id="b")]})
    target = tmp_path / "glossary.json"
    monkeypatch.setattr(imp, "default_data_path", lambda: target)
    monkeypatch.setattr(imp, "ROOT", tmp_path)

    imp.main(["--source", str(source)])
    (source / imp.DATA_SUBPATH / "str.json").write_text(
        json.dumps([card(id="a")], ensure_ascii=False), encoding="utf-8"
    )
    assert imp.main(["--source", str(source), "--check"]) == 1


def test_check_fails_without_snapshot(tmp_path: Path, monkeypatch):
    source = make_source(tmp_path / "src", {"str": [card(id="a")]})
    monkeypatch.setattr(imp, "default_data_path", lambda: tmp_path / "нет.json")
    monkeypatch.setattr(imp, "ROOT", tmp_path)
    assert imp.main(["--source", str(source), "--check"]) == 1
