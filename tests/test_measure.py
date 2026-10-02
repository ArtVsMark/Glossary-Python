"""Точка входа замера: снимок языка — документ контракта, в файл или в поток."""

import json
from pathlib import Path

import pytest

from glossary import inventory, measure

SNAPSHOT = inventory.Inventory(
    items=(inventory.Item(qualname="len", module="builtins", kind="function"),),
    python_version="3.11",
)


@pytest.fixture(autouse=True)
def tiny_language(monkeypatch: pytest.MonkeyPatch) -> None:
    """Язык из одной сущности: проверяется оформление, а не интроспекция."""
    monkeypatch.setattr(inventory, "build_inventory", lambda: SNAPSHOT)


def test_render_carries_the_contract_header():
    payload = json.loads(measure.render(SNAPSHOT))
    assert payload["schema_of"] == inventory.SCHEMA_OF
    assert payload["python_version"] == "3.11"
    assert payload["count"] == 1
    assert payload["items"] == [
        {"qualname": "len", "module": "builtins", "kind": "function"}
    ]


def test_main_writes_the_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    target = tmp_path / "nested" / "inventory-3.11.json"
    assert measure.main(["-o", str(target)]) == 0
    assert json.loads(target.read_text(encoding="utf-8"))["count"] == 1
    assert "3.11: 1 сущностей" in capsys.readouterr().out


def test_main_without_output_prints_the_document(capsys: pytest.CaptureFixture[str]):
    assert measure.main([]) == 0
    assert json.loads(capsys.readouterr().out)["python_version"] == "3.11"
