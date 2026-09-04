"""Разность инвентарей по версиям Python.

Ошибка здесь не видна глазами: неверно отсортированные версии дают разность
между не теми снимками, а результат выглядит правдоподобно — список имён,
похожих на новые. Поэтому проверяется порядок, а не только арифметика.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

import whatsnew
from glossary.inventory import Inventory, Item, difference


def dump(version: str, *qualnames: str) -> dict[str, Any]:
    """Выгрузка инвентаря одной версии."""
    return {
        "schema": 1,
        "python_version": version,
        "count": len(qualnames),
        "items": [
            {"qualname": name, "module": name.split(".")[0], "kind": "function"}
            for name in qualnames
        ],
    }


# --------------------------- разность снимков ---------------------------


def snapshot(version: str, *qualnames: str) -> Inventory:
    items = tuple(Item(qualname=n, module="builtins", kind="function") for n in qualnames)
    return Inventory(items=items, python_version=version)


def test_difference_finds_what_appeared():
    before = snapshot("3.13", "len")
    after = snapshot("3.14", "len", "новое")
    assert [item.qualname for item in difference(before, after)] == ["новое"]


def test_difference_reversed_finds_what_disappeared():
    """Та же операция, другой вопрос — удаления считаются обратным порядком."""
    before = snapshot("3.13", "len", "ушло")
    after = snapshot("3.14", "len")
    assert [item.qualname for item in difference(after, before)] == ["ушло"]


def test_difference_is_empty_between_identical_snapshots():
    assert difference(snapshot("3.13", "len"), snapshot("3.14", "len")) == ()


# --------------------------- порядок версий ---------------------------


@pytest.mark.parametrize(
    ("earlier", "later"),
    [("3.9", "3.10"), ("3.9", "3.13"), ("3.11", "3.12"), ("3.14", "3.15")],
)
def test_version_order_is_numeric_not_lexicographic(earlier: str, later: str):
    """`3.9` идёт перед `3.10`. Строковое сравнение говорит обратное."""
    assert whatsnew.version_key(earlier) < whatsnew.version_key(later)


def test_releases_are_built_in_version_order():
    dumps = [dump("3.13", "b"), dump("3.9", "a"), dump("3.10", "a", "b")]
    payload = whatsnew.build(dumps, frozenset())
    assert payload["versions"] == ["3.9", "3.10", "3.13"]
    assert [r["version"] for r in payload["releases"]] == ["3.10", "3.13"]


# --------------------------- содержание ---------------------------


def test_added_and_removed_are_reported():
    payload = whatsnew.build(
        [dump("3.13", "a", "b"), dump("3.14", "b", "c")], frozenset()
    )
    release = payload["releases"][0]
    assert [item["qualname"] for item in release["added"]] == ["c"]
    assert release["removed"] == ["a"]
    assert release["totals"] == {"added": 1, "removed": 1, "undocumented": 1}


def test_new_entity_with_a_card_is_marked_documented():
    """Смысл затеи — не список нового, а новое без карточки."""
    payload = whatsnew.build(
        [dump("3.13"), dump("3.14", "itertools.batched")],
        frozenset({"itertools.batched"}),
    )
    release = payload["releases"][0]
    assert release["added"][0]["documented"] is True
    assert release["totals"]["undocumented"] == 0


def test_documented_match_ignores_case():
    payload = whatsnew.build(
        [dump("3.13"), dump("3.14", "ValueError")], frozenset({"valueerror"})
    )
    assert payload["releases"][0]["added"][0]["documented"] is True


def test_single_dump_is_refused():
    """Разность считается между версиями, а не внутри одной."""
    assert whatsnew.build([dump("3.14", "a")], frozenset())["releases"] == []


def test_contract_names_its_schema():
    payload = whatsnew.build([dump("3.13"), dump("3.14")], frozenset())
    assert payload["schema"] == whatsnew.SCHEMA
    assert payload["schema_of"] == whatsnew.SCHEMA_OF


# --------------------------- вход ---------------------------


def test_broken_dump_is_an_error_not_a_silent_skip(tmp_path: Path):
    """Пропустив испорченную выгрузку, мы посчитали бы разность с не той версией."""
    bad = tmp_path / "inv.json"
    bad.write_text("{не json", encoding="utf-8")
    with pytest.raises(SystemExit, match="не прочитана"):
        whatsnew.read_dump(bad)


def test_foreign_json_is_rejected(tmp_path: Path):
    other = tmp_path / "inv.json"
    other.write_text('{"что-то": "иное"}', encoding="utf-8")
    with pytest.raises(SystemExit, match="не выгрузка инвентаря"):
        whatsnew.read_dump(other)


def test_cli_refuses_a_lone_dump(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    only = tmp_path / "inv.json"
    only.write_text(json.dumps(dump("3.14", "a")), encoding="utf-8")
    assert whatsnew.main([str(only)]) == 1
    assert "хотя бы" in capsys.readouterr().err


def test_cli_writes_the_contract(tmp_path: Path):
    paths = []
    for version, names in (("3.13", ("a",)), ("3.14", ("a", "b"))):
        path = tmp_path / f"inv-{version}.json"
        path.write_text(json.dumps(dump(version, *names)), encoding="utf-8")
        paths.append(str(path))
    target = tmp_path / "whatsnew.json"
    assert whatsnew.main([*paths, "-o", str(target)]) == 0
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["releases"][0]["totals"]["added"] == 1
