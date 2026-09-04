"""Тесты правил качества."""

from __future__ import annotations

import pytest

from glossary.models import Glossary
from glossary.validation import (
    RULES,
    Issue,
    Severity,
    ValidationConfig,
    ValidationReport,
    rule_color_group,
    rule_description_length,
    rule_docs_url,
    rule_duplicate_name,
    rule_examples_depth,
    rule_group_size,
    rule_id_format,
    rule_required_fields,
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


@pytest.mark.parametrize("field", ["name", "group", "subcat", "syntax", "docs"])
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


def test_color_group_rejects_unknown_value():
    issues = list(rule_color_group(make_glossary(make_entry(cg="нет")), CFG))
    assert issues and issues[0].severity is Severity.ERROR


def test_docs_url_rejects_foreign_host():
    issues = list(rule_docs_url(make_glossary(make_entry(docs="https://ya.ru")), CFG))
    assert issues[0].severity is Severity.ERROR


def test_docs_url_warns_on_generic_root():
    glossary = make_glossary(make_entry(docs="https://docs.python.org/3/"))
    issues = list(rule_docs_url(glossary, CFG))
    assert issues[0].severity is Severity.WARNING


def test_description_length_error_when_too_short():
    issues = list(
        rule_description_length(make_glossary(make_entry(description="Ко")), CFG)
    )
    assert issues[0].severity is Severity.ERROR


def test_description_length_warns_when_too_long():
    glossary = make_glossary(make_entry(description="д" * (CFG.max_description + 1)))
    issues = list(rule_description_length(glossary, CFG))
    assert issues[0].severity is Severity.WARNING


def test_description_length_ignores_empty_field():
    """Пустое описание — забота rule_required_fields, дублировать ошибку не нужно."""
    assert (
        list(rule_description_length(make_glossary(make_entry(description="")), CFG))
        == []
    )


def test_description_threshold_is_configurable():
    glossary = make_glossary(make_entry(description="д" * 70))
    assert list(rule_description_length(glossary, ValidationConfig(min_description=100)))


@pytest.mark.parametrize("version", ["3", "4.0+", "3.x", "python3.9"])
def test_version_format_rejects_malformed(version: str):
    issues = list(rule_version_format(make_glossary(make_entry(version=version)), CFG))
    assert issues[0].severity is Severity.ERROR


def test_version_format_warns_without_plus():
    issues = list(rule_version_format(make_glossary(make_entry(version="3.9")), CFG))
    assert issues[0].severity is Severity.WARNING
    assert "3.9+" in issues[0].message


def test_version_format_accepts_canonical_and_null():
    glossary = make_glossary(make_entry(version="3.12+"), make_entry(version=None))
    assert list(rule_version_format(glossary, CFG)) == []


def test_examples_depth_warns_on_single_line():
    issues = list(rule_examples_depth(make_glossary(make_entry(examples="x = 1")), CFG))
    assert issues[0].severity is Severity.WARNING


def test_duplicate_name_reports_all_locations():
    glossary = make_glossary(
        make_entry(id="a", name="len()", group="Первый"),
        make_entry(id="b", name="len()", group="Второй"),
    )
    issues = list(rule_duplicate_name(glossary, CFG))
    assert len(issues) == 1
    assert "Первый" in issues[0].message and "Второй" in issues[0].message


def test_group_size_warns_on_thin_group():
    glossary = make_glossary(make_entry(id="a", group="Крошечный"))
    issues = list(rule_group_size(glossary, CFG))
    assert issues[0].severity is Severity.WARNING


def test_validate_accepts_custom_rule_set():
    glossary = make_glossary(make_entry(id="плохой id", cg="нет"))
    report = validate(glossary, rules=[rule_color_group])
    assert report.by_rule() == {"color-group": 1}


def test_all_rules_are_registered():
    """Каждое правило модуля должно попасть в реестр — иначе оно не работает."""
    expected = {
        rule_color_group,
        rule_description_length,
        rule_docs_url,
        rule_duplicate_name,
        rule_examples_depth,
        rule_group_size,
        rule_id_format,
        rule_required_fields,
        rule_unique_id,
        rule_version_format,
    }
    assert set(RULES) == expected


def test_rule_names_are_unique_and_stable():
    """Имена правил — публичный контракт: по ним фильтруют отчёт в CI."""
    glossary = make_glossary(
        make_entry(id="a b", cg="нет", docs="https://ya.ru", version="4.0")
    )
    names = {i.rule for i in validate(glossary).issues}
    assert names <= {
        "color-group",
        "description-length",
        "docs-url",
        "duplicate-name",
        "examples-depth",
        "group-size",
        "id-format",
        "required-fields",
        "unique-id",
        "version-format",
    }
