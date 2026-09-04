"""Тесты доменных моделей."""

from __future__ import annotations

import pytest

from glossary.models import SCHEMA_VERSION, Entry, Glossary, Text
from tests.factories import make_entry, make_glossary


def test_entry_is_immutable():
    entry = make_entry()
    with pytest.raises(AttributeError):
        entry.title = "другое"  # type: ignore[misc]


def test_from_dict_ignores_unknown_keys():
    entry = Entry.from_dict({**make_entry().to_dict(), "лишнее": "значение"})
    assert entry.id == "sample"


def test_from_dict_fills_missing_fields():
    entry = Entry.from_dict({"id": "x", "title": "x()"})
    assert entry.summary == Text()
    assert entry.body == Text()
    assert entry.version == ""
    assert entry.examples == ()


def test_to_dict_preserves_field_order():
    assert list(make_entry().to_dict()) == [
        "id",
        "title",
        "kind",
        "summary",
        "body",
        "syntax",
        "status",
        "docs_url",
        "version",
        "section",
        "subcat",
        "color_group",
        "aliases",
        "keywords",
        "tags",
        "examples",
        "related",
        "related_errors",
    ]


def test_text_falls_back_to_russian_for_unknown_language():
    text = Text(ru="русский", en="english")
    assert text.get("en") == "english"
    assert text.get("de") == "русский"


def test_text_from_bare_string_lands_in_russian():
    """Источник может отдать голую строку — это русский текст, не пустота."""
    assert Text.from_any("строка") == Text(ru="строка", en="")


def test_roundtrip_dict():
    entry = make_entry(version="3.12")
    assert Entry.from_dict(entry.to_dict()) == entry


def test_searchable_includes_aliases_and_keywords():
    entry = make_entry(aliases=("двоичный",), keywords=("бисект",))
    haystack = entry.searchable()
    assert "двоичный" in haystack and "бисект" in haystack


def test_sections_keep_first_appearance_order(sample_glossary: Glossary):
    assert sample_glossary.sections == ("Первый", "Второй")


def test_in_section_filters_entries(sample_glossary: Glossary):
    assert [e.id for e in sample_glossary.in_section("Первый")] == ["alpha", "beta"]


def test_resolve_falls_back_to_case_insensitive_match():
    """Источник хранит имя ``IndexError``, id карточки-исключения — в нижнем.

    Конвенция нигде не записана, поэтому разрешение общее для всех ссылок:
    иначе оно разъедется между валидатором, экспортёрами и витриной.
    """
    entry = make_entry(id="indexerror", title="IndexError")
    glossary = make_glossary(entry)
    assert glossary.resolve("IndexError") is entry
    assert glossary.resolve("indexerror") is entry
    assert glossary.resolve("нет-такого") is None


def test_resolve_prefers_exact_match():
    """Точное совпадение выигрывает: регистр может различать карточки."""
    exact = make_entry(id="Ref", title="точная")
    lowered = make_entry(id="ref", title="в нижнем")
    glossary = make_glossary(lowered, exact)
    assert glossary.resolve("Ref") is exact


def test_get_returns_none_for_unknown_id(sample_glossary: Glossary):
    assert sample_glossary.get("alpha") is not None
    assert sample_glossary.get("нет-такого") is None


def test_len_and_iteration(sample_glossary: Glossary):
    assert len(sample_glossary) == 4
    assert [e.id for e in sample_glossary] == ["alpha", "beta", "gamma", "delta"]


def test_index_uses_first_entry_for_duplicate_ids():
    first = make_entry(id="dup", title="первая")
    second = make_entry(id="dup", title="вторая")
    glossary = make_glossary(first, second)
    assert glossary.get("dup") is first


def test_stats_aggregates(sample_glossary: Glossary):
    stats = sample_glossary.stats()
    assert stats.total == 4
    assert stats.sections["Первый"] == 2
    assert stats.color_groups["module"] == 2
    assert stats.kinds["function"] == 4
    assert stats.versioned == 0
    assert stats.translated == 4
    assert stats.with_errors == 0
    assert stats.avg_summary > 0


def test_stats_counts_translated_only_when_both_texts_exist():
    """Заполненная сводка при пустом теле — ещё не переведённая карточка."""
    glossary = make_glossary(make_entry(body=Text(ru="Есть.", en="")))
    assert glossary.stats().translated == 0


def test_stats_on_empty_glossary():
    stats = Glossary(entries=()).stats()
    assert stats.total == 0
    assert stats.avg_summary == 0.0


def test_default_schema_version():
    assert Glossary(entries=()).schema_version == SCHEMA_VERSION
