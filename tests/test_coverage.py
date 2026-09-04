"""Покрытие официального Python и инвентарь языка.

Инвентарь здесь почти не проверяется по составу: он снят с интерпретатора, и
тест, перечисляющий его содержимое, проверял бы Python, а не нас. Проверяется
то, что наше: форма снимка, детерминированность, отбор — и сопоставление,
где ошибка не видна глазами. Завышенное покрытие выглядит как хорошая новость.
"""

from __future__ import annotations

import json

import pytest

from glossary import coverage
from glossary.inventory import (
    BUILTIN_TYPES,
    INVENTORY_KINDS,
    STDLIB_MODULES,
    Inventory,
    Item,
    build_inventory,
    python_version,
)
from glossary.models import Glossary
from tests.factories import make_entry, make_glossary


def tiny(*items: Item) -> Inventory:
    """Язык из нескольких сущностей — чтобы проверять сопоставление, а не Python."""
    return Inventory(items=tuple(sorted(items)), python_version="3.11")


FN = Item(qualname="len", module="builtins", kind="function")
METHOD = Item(qualname="str.split", module="builtins", kind="method")
EXC = Item(qualname="ValueError", module="builtins", kind="exception")
MEMBER = Item(qualname="functools.reduce", module="functools", kind="function")


# --------------------------- инвентарь ---------------------------


def test_inventory_is_not_empty():
    """Пустой инвентарь — ошибка входа, а не «в Python ничего нет»."""
    assert len(build_inventory()) > 0


def test_inventory_is_deterministic():
    """Разность двух версий показывала бы шум, будь снимок неустойчив."""
    first, second = build_inventory(), build_inventory()
    assert [i.qualname for i in first] == [i.qualname for i in second]


def test_inventory_has_no_duplicates():
    names = [item.qualname for item in build_inventory()]
    assert len(names) == len(set(names))


def test_inventory_kinds_are_known():
    assert {item.kind for item in build_inventory()} <= INVENTORY_KINDS


def test_inventory_names_its_python_version():
    """Версия — ось измерения: файл без неё нечем сравнить со вчерашним."""
    assert build_inventory().python_version == python_version()


def test_inventory_skips_private_names():
    assert not [i for i in build_inventory() if i.qualname.split(".")[-1].startswith("_")]


def test_inventory_skips_private_modules():
    """Обход иерархии исключений добирается до внутренностей реализации.

    ``_csv.Error`` публично называется иначе, и требовать на него карточку
    значило бы требовать описания того, чего в языке нет.
    """
    modules = {item.module for item in build_inventory()}
    assert not [m for m in modules if m.split(".")[0].startswith("_")]


def test_inventory_covers_methods_of_builtin_types():
    """Пласт, которого сканер builtins не видит, — самый частый в глоссарии."""
    names = build_inventory().qualnames
    assert "str.split" in names and "list.append" in names


def test_inventory_covers_module_members():
    assert "functools.reduce" in build_inventory().qualnames


def test_inventory_covers_exceptions_of_curated_modules():
    """Плоский список из builtins не увидел бы исключение модуля."""
    assert "subprocess.CalledProcessError" in build_inventory().qualnames


def test_inventory_accepts_a_narrower_module_set():
    narrow = build_inventory(frozenset({"functools"}))
    assert "functools.reduce" in narrow.qualnames
    assert "itertools.chain" not in narrow.qualnames


def test_unknown_module_is_skipped_not_fatal():
    """Модуля может не быть в этой версии; набор общий для всей матрицы."""
    assert len(build_inventory(frozenset({"нет_такого_модуля"}))) > 0


def test_curated_sets_are_not_empty():
    """Пустой набор дал бы стопроцентное покрытие ни на чём."""
    assert STDLIB_MODULES and BUILTIN_TYPES


# --------------------------- сопоставление ---------------------------


def test_card_covers_matching_qualname():
    glossary = make_glossary(make_entry(id="functools.reduce"))
    assert coverage.build_coverage(glossary, tiny(MEMBER))["stdlib"].missing == ()


def test_missing_card_is_reported():
    report = coverage.build_coverage(make_glossary(), tiny(MEMBER))
    assert report["stdlib"].missing == ("functools.reduce",)


def test_title_counts_as_a_name():
    """Карточка исключения хранит id в нижнем регистре, а имя — заголовком."""
    glossary = make_glossary(make_entry(id="valueerror", title="ValueError"))
    assert coverage.build_coverage(glossary, tiny(EXC))["exceptions"].missing == ()


def test_call_parentheses_in_title_do_not_break_the_match():
    glossary = make_glossary(make_entry(id="len", title="len()"))
    assert coverage.build_coverage(glossary, tiny(FN))["builtins"].missing == ()


def test_alias_counts_as_a_name():
    glossary = make_glossary(make_entry(id="иное", aliases=("functools.reduce",)))
    assert coverage.build_coverage(glossary, tiny(MEMBER))["stdlib"].missing == ()


def test_tail_of_a_qualname_does_not_count():
    """Одна карточка `split` не смеет закрыть методы всех типов сразу.

    Идентификаторы карточек полные, поэтому эвристика по хвосту здесь не
    помогает, а завышает покрытие — и завышенное выглядит как хорошая новость.
    """
    glossary = make_glossary(make_entry(id="split", title="split()"))
    assert coverage.build_coverage(glossary, tiny(METHOD))["methods"].missing == (
        "str.split",
    )


def test_categories_split_by_kind_and_module():
    report = coverage.build_coverage(make_glossary(), tiny(FN, METHOD, EXC, MEMBER))
    assert report["builtins"].total == 1
    assert report["methods"].total == 1
    assert report["exceptions"].total == 1
    assert report["stdlib"].total == 1


def test_empty_category_counts_as_covered():
    """Покрывать нечего — не то же самое, что не покрыто."""
    assert coverage.build_coverage(make_glossary(), tiny(FN))["stdlib"].ratio == 1.0


def test_ratio_is_a_fraction():
    report = coverage.build_coverage(
        make_glossary(make_entry(id="len")), tiny(FN, METHOD)
    )
    assert report["builtins"].ratio == 1.0
    assert report["methods"].ratio == 0.0
    assert report.ratio == pytest.approx(0.5)


def test_missing_is_sorted():
    other = Item(qualname="functools.cache", module="functools", kind="function")
    report = coverage.build_coverage(make_glossary(), tiny(MEMBER, other))
    assert report["stdlib"].missing == ("functools.cache", "functools.reduce")


def test_empty_inventory_is_fully_covered_and_says_so():
    """Ноль на ноль — единица, а не деление на ноль и не провал."""
    report = coverage.build_coverage(make_glossary(), tiny())
    assert report.total == 0 and report.ratio == 1.0


def test_real_glossary_covers_the_builtins(real_glossary: Glossary):
    """Встроенные функции — тот пласт, где пробел задевает каждого."""
    assert coverage.build_coverage(real_glossary)["builtins"].ratio == 1.0


# --------------------------- контракт ---------------------------


def test_contract_names_its_schema_and_axis():
    data = coverage.collect(make_glossary(), tiny(FN))
    assert data["schema"] == coverage.SCHEMA
    assert data["schema_of"] == coverage.SCHEMA_OF
    assert data["python_version"] == "3.11"


def test_contract_carries_the_snapshot_digest():
    """Тот же вопрос, что в замечаниях: о каком снимке речь."""
    data = coverage.collect(make_glossary(make_entry(id="a")), tiny(FN))
    assert len(data["snapshot"]["digest"]) == 12


def test_json_list_is_never_truncated():
    items = tiny(
        *[
            Item(qualname=f"functools.f{n}", module="functools", kind="function")
            for n in range(50)
        ]
    )
    payload = json.loads(coverage.as_json(make_glossary(), items))
    stdlib = next(c for c in payload["categories"] if c["name"] == "stdlib")
    assert len(stdlib["missing"]) == 50


def test_json_carries_no_timestamp():
    payload = json.loads(coverage.as_json(make_glossary(), tiny(FN)))
    assert not {"generated_at", "timestamp", "date"} & payload.keys()


def test_markdown_truncates_and_says_how_to_get_the_rest():
    items = tiny(
        *[
            Item(qualname=f"functools.f{n}", module="functools", kind="function")
            for n in range(30)
        ]
    )
    text = coverage.as_markdown(make_glossary(), items, limit=5)
    assert text.count("- `functools.f") == 5
    assert "…и ещё 25" in text


def test_markdown_names_what_it_cannot_see():
    """Инструмент, умалчивающий о своей границе, читается как полный."""
    text = coverage.as_markdown(make_glossary(), tiny(FN))
    assert "синтаксис" in text.lower()
