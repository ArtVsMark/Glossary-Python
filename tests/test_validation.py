"""Тесты правил качества."""

from __future__ import annotations

import pytest

from glossary.models import Glossary, Text
from glossary.validation import (
    RULES,
    Issue,
    Severity,
    ValidationConfig,
    ValidationReport,
    rule_body_length,
    rule_color_group,
    rule_docs_url,
    rule_duplicate_title,
    rule_example_indent,
    rule_examples,
    rule_id_format,
    rule_kind,
    rule_non_empty,
    rule_related_resolves,
    rule_required_fields,
    rule_section_size,
    rule_summary_length,
    rule_translated,
    rule_unique_id,
    rule_version_format,
    validate,
)
from tests.factories import make_entry, make_glossary

CFG = ValidationConfig()


def rules_of(report: ValidationReport, rule: str) -> tuple[Issue, ...]:
    return tuple(i for i in report.issues if i.rule == rule)


def test_valid_glossary_has_no_issues(sample_glossary: Glossary):
    assert validate(sample_glossary).issues == ()


def test_report_ok_ignores_warnings():
    report = ValidationReport(issues=(Issue(Severity.WARNING, "правило", "текст"),))
    assert report.ok
    assert report.warnings and not report.errors


def test_report_not_ok_with_errors():
    report = ValidationReport(issues=(Issue(Severity.ERROR, "правило", "текст"),))
    assert not report.ok


def test_issue_format_uses_placeholder_without_entry():
    assert "<глоссарий>" in Issue(Severity.WARNING, "r", "сообщение").format()
    assert "alpha" in Issue(Severity.ERROR, "r", "сообщение", "alpha").format()


def test_non_empty_fires_on_empty_glossary():
    """Пустой вход — ошибка входа, а не успешная проверка (каталог, 075)."""
    issues = list(rule_non_empty(Glossary(entries=()), CFG))
    assert [i.severity for i in issues] == [Severity.ERROR]


def test_non_empty_silent_on_real_glossary(sample_glossary: Glossary):
    assert list(rule_non_empty(sample_glossary, CFG)) == []


def test_validate_fails_on_empty_glossary():
    """Полный прогон на пустых данных обязан быть красным, а не зелёным."""
    assert not validate(Glossary(entries=())).ok


@pytest.mark.parametrize("field", ["title", "kind", "section", "syntax", "docs_url"])
def test_required_fields_detects_blank(field: str):
    glossary = make_glossary(make_entry(**{field: "   "}))
    issues = list(rule_required_fields(glossary, CFG))
    assert [i.severity for i in issues] == [Severity.ERROR]
    assert field in issues[0].message


def test_id_format_rejects_anchor_breaking_characters():
    issues = list(rule_id_format(make_glossary(make_entry(id="a b#c")), CFG))
    assert len(issues) == 1
    assert issues[0].severity is Severity.ERROR


def test_id_format_accepts_cyrillic_and_uppercase():
    glossary = make_glossary(
        make_entry(id="числовые-литералы"), make_entry(id="ValueError")
    )
    assert list(rule_id_format(glossary, CFG)) == []


def test_id_format_skips_empty_id():
    """Пустой id — забота rule_required_fields, дублировать ошибку не нужно."""
    assert list(rule_id_format(make_glossary(make_entry(id="")), CFG)) == []


def test_unique_id_detects_duplicates():
    glossary = make_glossary(make_entry(id="dup"), make_entry(id="dup"))
    issues = list(rule_unique_id(glossary, CFG))
    assert len(issues) == 1
    assert issues[0].entry_id == "dup"


def test_kind_rejects_unknown_value():
    issues = list(rule_kind(make_glossary(make_entry(kind="заклинание")), CFG))
    assert issues and issues[0].severity is Severity.ERROR


def test_color_group_rejects_unknown_value():
    """Незнакомая группа — новый файл в источнике, о котором витрина не знает."""
    glossary = make_glossary(make_entry(color_group="drafts"))
    issues = list(rule_color_group(glossary, CFG))
    assert issues and issues[0].severity is Severity.ERROR


def test_translated_errors_on_missing_summary_language():
    glossary = make_glossary(make_entry(summary=Text(ru="Есть.", en="")))
    issues = list(rule_translated(glossary, CFG))
    assert [i.severity for i in issues] == [Severity.ERROR]
    assert "'en'" in issues[0].message


def test_translated_only_warns_on_missing_body():
    """Тело — не сводка: его отсутствие не делает карточку сломанной."""
    glossary = make_glossary(make_entry(body=Text(ru="Есть.", en="")))
    issues = list(rule_translated(glossary, CFG))
    assert [i.severity for i in issues] == [Severity.WARNING]


def test_docs_url_rejects_foreign_host():
    glossary = make_glossary(make_entry(docs_url="https://ya.ru"))
    issues = list(rule_docs_url(glossary, CFG))
    assert issues[0].severity is Severity.ERROR


def test_docs_url_warns_on_generic_root():
    glossary = make_glossary(make_entry(docs_url="https://docs.python.org/3/"))
    issues = list(rule_docs_url(glossary, CFG))
    assert issues[0].severity is Severity.WARNING


def test_summary_length_warns_when_too_short():
    glossary = make_glossary(make_entry(summary=Text(ru="Ко", en="Short")))
    issues = list(rule_summary_length(glossary, CFG))
    assert issues[0].severity is Severity.WARNING


def test_summary_length_warns_when_too_long():
    long_text = "д" * (CFG.max_summary + 1)
    glossary = make_glossary(make_entry(summary=Text(ru=long_text, en=long_text)))
    issues = list(rule_summary_length(glossary, CFG))
    assert issues[0].severity is Severity.WARNING


def test_summary_length_ignores_empty_field():
    """Пустая сводка — забота rule_translated, дублировать находку не нужно."""
    glossary = make_glossary(make_entry(summary=Text(ru="", en="")))
    assert list(rule_summary_length(glossary, CFG)) == []


def test_summary_threshold_is_configurable():
    glossary = make_glossary(make_entry(summary=Text(ru="д" * 70, en="x" * 70)))
    assert list(rule_summary_length(glossary, ValidationConfig(min_summary=100)))


def test_body_length_warns_on_stub():
    glossary = make_glossary(make_entry(body=Text(ru="Коротко.", en="Short.")))
    issues = list(rule_body_length(glossary, CFG))
    assert issues[0].severity is Severity.WARNING


@pytest.mark.parametrize("version", ["3", "3.x", "python3.9", "3.12+"])
def test_version_format_rejects_malformed(version: str):
    glossary = make_glossary(make_entry(version=version))
    issues = list(rule_version_format(glossary, CFG))
    assert issues[0].severity is Severity.ERROR


def test_version_format_accepts_canonical_and_empty():
    glossary = make_glossary(make_entry(version="3.12"), make_entry(version=""))
    assert list(rule_version_format(glossary, CFG)) == []


def test_examples_warns_when_absent():
    issues = list(rule_examples(make_glossary(make_entry(examples=())), CFG))
    assert issues[0].severity is Severity.WARNING


def test_example_indent_flags_block_without_indentation():
    """Блок без отступа — код, который не запустится (возражение источнику)."""
    glossary = make_glossary(make_entry(examples=("for x in range(3):", "print(x)")))
    issues = list(rule_example_indent(glossary, CFG))
    assert issues[0].severity is Severity.WARNING


def test_example_indent_silent_on_indented_block():
    glossary = make_glossary(make_entry(examples=("for x in range(3):", "    print(x)")))
    assert list(rule_example_indent(glossary, CFG)) == []


def test_example_indent_silent_without_block():
    assert list(rule_example_indent(make_glossary(make_entry()), CFG)) == []


def test_related_resolves_flags_dangling_link():
    glossary = make_glossary(make_entry(related=("нет-такого",)))
    issues = list(rule_related_resolves(glossary, CFG))
    assert issues[0].severity is Severity.WARNING
    assert "нет-такого" in issues[0].message


def test_related_resolves_accepts_existing_link():
    glossary = make_glossary(make_entry(id="a", related=("b",)), make_entry(id="b"))
    assert list(rule_related_resolves(glossary, CFG)) == []


def test_duplicate_title_reports_all_locations():
    glossary = make_glossary(
        make_entry(id="a", title="len()", section="Первый"),
        make_entry(id="b", title="len()", section="Второй"),
    )
    issues = list(rule_duplicate_title(glossary, CFG))
    assert len(issues) == 1
    assert "Первый" in issues[0].message and "Второй" in issues[0].message


def test_section_size_warns_on_thin_section():
    glossary = make_glossary(make_entry(id="a", section="Крошечный"))
    issues = list(rule_section_size(glossary, CFG))
    assert issues[0].severity is Severity.WARNING


def test_validate_accepts_custom_rule_set():
    glossary = make_glossary(make_entry(id="плохой id", color_group="нет"))
    report = validate(glossary, rules=[rule_color_group])
    assert report.by_rule() == {"color-group": 1}


def test_all_rules_are_registered():
    """Каждое правило модуля должно попасть в реестр — иначе оно не работает."""
    expected = {
        rule_body_length,
        rule_color_group,
        rule_docs_url,
        rule_duplicate_title,
        rule_example_indent,
        rule_examples,
        rule_id_format,
        rule_kind,
        rule_non_empty,
        rule_related_resolves,
        rule_required_fields,
        rule_section_size,
        rule_summary_length,
        rule_translated,
        rule_unique_id,
        rule_version_format,
    }
    assert set(RULES) == expected


def test_rule_names_are_unique_and_stable():
    """Имена правил — публичный контракт: по ним фильтруют отчёт в CI."""
    glossary = make_glossary(
        make_entry(
            id="a b",
            kind="ничто",
            color_group="нет",
            docs_url="https://ya.ru",
            version="4.0.1",
            related=("нет-такого",),
        )
    )
    names = {i.rule for i in validate(glossary).issues}
    assert names <= {
        "body-length",
        "color-group",
        "docs-url",
        "duplicate-title",
        "example-indent",
        "examples",
        "id-format",
        "kind",
        "related-resolves",
        "required-fields",
        "section-size",
        "summary-length",
        "translated",
        "unique-id",
        "version-format",
    }
