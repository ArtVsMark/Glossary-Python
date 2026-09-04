"""Тесты экспортёров."""

from __future__ import annotations

import csv
import io
import json

import pytest

from glossary.errors import ExportError
from glossary.exporters import EXPORTERS, get_exporter
from glossary.exporters.html import PLACEHOLDER, HtmlExporter, load_template
from glossary.models import Glossary
from tests.factories import make_entry, make_glossary


@pytest.mark.parametrize("name", EXPORTERS)
def test_every_registered_format_renders(name: str, sample_glossary: Glossary):
    exporter = get_exporter(name)
    rendered = exporter.render(sample_glossary)
    assert rendered
    assert exporter.suffix.startswith(".")
    assert exporter.name == name


def test_unknown_format_raises():
    with pytest.raises(ExportError, match="Неизвестный формат"):
        get_exporter("pdf")


# --------------------------- HTML ---------------------------


def test_packaged_template_contains_placeholder():
    assert PLACEHOLDER in load_template()


def test_html_requires_placeholder():
    with pytest.raises(ExportError, match="плейсхолдер"):
        HtmlExporter(template="<html></html>")


def test_html_refuses_empty_glossary():
    """Пустая витрина выглядит исправной и молча заменила бы рабочую."""
    with pytest.raises(ExportError, match="пуст"):
        HtmlExporter(template=PLACEHOLDER).render(Glossary(entries=()))


def test_html_substitutes_data(sample_glossary: Glossary):
    exporter = HtmlExporter(template=f"<body>{PLACEHOLDER}</body>")
    rendered = exporter.render(sample_glossary)
    assert PLACEHOLDER not in rendered
    payload = json.loads(rendered.removeprefix("<body>").removesuffix("</body>"))
    assert [e["id"] for e in payload] == ["alpha", "beta", "gamma", "delta"]


def test_html_escapes_closing_tag_in_data():
    """`</script>` внутри данных не должен закрыть блок раньше времени."""
    glossary = make_glossary(make_entry(examples="print('</script>')"))
    rendered = HtmlExporter(template=PLACEHOLDER).render(glossary)
    assert "</script>" not in rendered
    assert json.loads(rendered)[0]["examples"] == "print('</script>')"


def test_html_payload_is_compact(sample_glossary: Glossary):
    rendered = HtmlExporter(template=PLACEHOLDER).render(sample_glossary)
    assert "\n" not in rendered
    assert '", "' not in rendered


def test_html_is_deterministic(sample_glossary: Glossary):
    exporter = HtmlExporter(template=PLACEHOLDER)
    assert exporter.render(sample_glossary) == exporter.render(sample_glossary)


# --------------------------- JSON ---------------------------


def test_json_exports_plain_array(sample_glossary: Glossary):
    payload = json.loads(get_exporter("json").render(sample_glossary))
    assert isinstance(payload, list)
    assert len(payload) == len(sample_glossary)
    assert "schema_version" not in payload[0]


def test_json_keeps_cyrillic_readable(sample_glossary: Glossary):
    assert "\\u" not in get_exporter("json").render(sample_glossary)


# --------------------------- CSV ---------------------------


def test_csv_has_header_and_row_per_entry(sample_glossary: Glossary):
    rendered = get_exporter("csv").render(sample_glossary)
    rows = list(csv.DictReader(io.StringIO(rendered, newline="")))
    assert len(rows) == len(sample_glossary)
    assert rows[0]["id"] == "alpha"


def test_csv_preserves_multiline_examples():
    glossary = make_glossary(make_entry(examples="строка 1\nстрока 2"))
    rendered = get_exporter("csv").render(glossary)
    rows = list(csv.DictReader(io.StringIO(rendered, newline="")))
    assert rows[0]["examples"] == "строка 1\nстрока 2"


# ------------------------- Markdown -------------------------


def test_markdown_has_headings_and_toc(sample_glossary: Glossary):
    rendered = get_exporter("markdown").render(sample_glossary)
    assert rendered.startswith("# Глоссарий Python")
    assert "## Содержание" in rendered
    assert "## Первый" in rendered
    assert "### alpha()" in rendered


def test_markdown_anchors_match_headings(sample_glossary: Glossary):
    rendered = get_exporter("markdown").render(sample_glossary)
    assert "[Первый](#первый)" in rendered


def test_markdown_shows_version_badge():
    glossary = make_glossary(make_entry(version="3.12+"))
    assert "`3.12+`" in get_exporter("markdown").render(glossary)


def test_markdown_omits_examples_block_when_empty():
    glossary = make_glossary(make_entry(examples="   "))
    assert "<details>" not in get_exporter("markdown").render(glossary)


def test_markdown_links_to_docs(sample_glossary: Glossary):
    rendered = get_exporter("markdown").render(sample_glossary)
    assert "[Документация](https://docs.python.org/3/" in rendered
