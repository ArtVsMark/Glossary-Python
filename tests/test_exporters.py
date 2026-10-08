"""Тесты экспортёров."""

import csv
import io
import json
import re
import shutil
import subprocess

import pytest
import yaml

from glossary.contracts import PAGES_URL, REPOSITORY_URL
from glossary.errors import ExportError
from glossary.exporters import EXPORTERS, MarkdownExporter, get_exporter
from glossary.exporters.html import (
    HEAD,
    PLACEHOLDER,
    REPOSITORY,
    HtmlExporter,
    _count,
    head,
    load_template,
)
from glossary.loader import project_root
from glossary.models import Glossary
from tests.factories import (
    VALID_SUMMARY,
    VALID_SUMMARY_EN,
    make_entry,
    make_glossary,
)


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
    glossary = make_glossary(make_entry(examples=("print('</script>')",)))
    rendered = HtmlExporter(template=PLACEHOLDER).render(glossary)
    assert "</script>" not in rendered
    assert json.loads(rendered)[0]["examples"] == [["print('</script>')"]]


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
    """Блоки примеров (#125) едут в ячейку целиком, вместе с границами."""
    glossary = make_glossary(make_entry(examples=("строка 1", "строка 2")))
    rendered = get_exporter("csv").render(glossary)
    rows = list(csv.DictReader(io.StringIO(rendered, newline="")))
    assert rows[0]["examples"] == "[['строка 1', 'строка 2']]"


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
    glossary = make_glossary(make_entry(added="3.12"))
    assert "`3.12`" in get_exporter("markdown").render(glossary)


def test_markdown_omits_examples_block_when_empty():
    glossary = make_glossary(make_entry(examples=()))
    assert "<details>" not in get_exporter("markdown").render(glossary)


def test_markdown_switches_language():
    """Экспорт двуязычен: язык выбирается, а не зашит в код."""
    glossary = make_glossary(make_entry())
    ru = MarkdownExporter().render(glossary)
    en = MarkdownExporter(language="en").render(glossary)
    assert VALID_SUMMARY in ru and VALID_SUMMARY not in en
    assert VALID_SUMMARY_EN in en


def test_markdown_links_related_entries():
    glossary = make_glossary(
        make_entry(id="a", title="alpha()", related=("b",)),
        make_entry(id="b", title="beta()"),
    )
    assert "См. также: [b](#b)" in get_exporter("markdown").render(glossary)


def test_markdown_links_to_docs(sample_glossary: Glossary):
    rendered = get_exporter("markdown").render(sample_glossary)
    assert "[Документация](https://docs.python.org/3/" in rendered


def test_markdown_fences_each_example_block():
    glossary = make_glossary(make_entry(examples=(("a = 1",), ("b = 2",))))
    rendered = get_exporter("markdown").render(glossary)
    assert "```python\na = 1\n```" in rendered
    assert "```python\nb = 2\n```" in rendered


def _labels(template: str, lang: str) -> set[str]:
    """Ключи подписей одного языка из таблицы I18N шаблона."""
    body = template.split(f"  {lang}:{{", 1)[1].split("\n  }", 1)[0]
    return set(re.findall(r"(\w+):\"", body))


@pytest.mark.live_surface
def test_every_label_the_page_uses_exists_in_both_languages():
    """Подпись, забытая в одной таблице, показала бы на витрине ``undefined``."""
    template = load_template()
    used = set(re.findall(r"\bt\(\"(\w+)\"\)", template))
    assert used <= _labels(template, "ru")
    assert used <= _labels(template, "en")


@pytest.mark.live_surface
def test_every_lifecycle_mode_has_a_label_and_a_hint():
    """Подпись режима берётся по ключу из MODE_KEY — поиск по t("…") её не видит."""
    template = load_template()
    table = template.split("const MODE_KEY = {", 1)[1].split("}", 1)[0]
    keys = set(re.findall(r':"(\w+)"', table))
    assert keys == {"pyAdded", "pyDeprecated", "pyRemoved"}
    needed = keys | {f"{key}Hint" for key in keys}
    assert needed <= _labels(template, "ru")
    assert needed <= _labels(template, "en")


@pytest.mark.live_surface
def test_filter_counts_follow_the_other_filters():
    """Число на кнопке — «сколько останется», а не размер всего глоссария.

    Каждый ряд считает по остальным фильтрам и поиску без своего, а render()
    пересобирает ряды после каждого выбора: иначе числа в рядах расходятся с
    «Показано».
    """
    template = load_template()
    for row in (
        'pool("kind")',
        'pool("py")',
        'pool("fam", "section")',
        'pool("section")',
    ):
        assert row in template, f"ряд считает не по остальным фильтрам: нет {row}"
    body = template.split("function render(){", 1)[1].split("\n}", 1)[0]
    for builder in (
        "buildKindFilters",
        "buildFamilyFilters",
        "buildSectionFilters",
        "buildPyFilters",
    ):
        assert builder + "()" in body, f"render() не пересчитывает {builder}"


def _run_in_python(cases: list[tuple[dict[str, str], str, str]]) -> list[bool]:
    """Исполнить ``inPython`` из шаблона на ``node`` и вернуть ответы по случаям."""
    node = shutil.which("node")
    if node is None:
        pytest.skip("node не установлен — функцию витрины исполнить нечем")
    template = load_template()
    source = (
        "function inPython"
        + template.split("function inPython", 1)[1].split("\n}", 1)[0]
        + "\n}"
    )
    script = (
        "const availableIn = () => true;\n"
        + source
        + f"\nconsole.log(JSON.stringify({json.dumps(cases)}.map("
        + "([d, v, m]) => inPython(d, v, m))));"
    )
    done = subprocess.run(  # noqa: S603 — исполняется наш шаблон
        [node, "-e", script],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
        timeout=30,
    )
    answers: list[bool] = json.loads(done.stdout)
    return answers


@pytest.mark.live_surface
def test_lifecycle_mode_without_version_keeps_only_python3_events():
    """«Появилось» без версии — появившееся в Python 3, а не все карточки.

    Поле ``added`` есть у каждой карточки, у старых — ``<3.0``. Когда режим без
    версии пропускал любую непустую дату, «появилось» не сужало ничего, и
    счётчики остальных рядов не менялись — в отличие от «устарело» и «удалено».
    """
    old = {"added": "<3.0", "deprecated": "", "removed": ""}
    new = {"added": "3.12", "deprecated": "", "removed": ""}
    gone = {"added": "<3.0", "deprecated": "3.4", "removed": "3.12"}
    assert _run_in_python(
        [
            (old, "", "added"),
            (new, "", "added"),
            (new, "3.12", "added"),
            (old, "", "deprecated"),
            (gone, "", "deprecated"),
            (gone, "", "removed"),
        ]
    ) == [False, True, True, False, True, True]


# --------------------------------------------------------------------------- #
# Метаданные страницы (#222)
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "number, expected",
    [
        (1, "1 карточка"),
        (2, "2 карточки"),
        (5, "5 карточек"),
        (11, "11 карточек"),
        (12, "12 карточек"),
        (21, "21 карточка"),
        (2656, "2656 карточек"),
    ],
)
def test_number_agrees_with_its_noun(number: int, expected: str):
    assert _count(number, "карточка", "карточки", "карточек") == expected


def test_head_names_the_published_address_and_the_count(sample_glossary: Glossary):
    page = HtmlExporter(template=f"<head>{HEAD}</head>{PLACEHOLDER}").render(
        sample_glossary
    )
    assert HEAD not in page
    assert f'<link rel="canonical" href="{PAGES_URL}">' in page
    assert '<meta name="description"' in page
    assert 'property="og:title"' in page
    block = head(sample_glossary).split('<script type="application/ld+json">', 1)[1]
    data = json.loads(block.split("</script>", 1)[0])
    term_set = next(n for n in data["@graph"] if n["@type"] == "DefinedTermSet")
    assert term_set["numberOfItems"] == len(sample_glossary.entries)


def test_head_text_cannot_close_the_script_block():
    assert head(Glossary(entries=())).count("</script>") == 1


@pytest.mark.live_surface
def test_shipped_template_carries_the_head_point():
    assert HEAD in load_template(), "метаданным витрины некуда встать"


# --------------------------------------------------------------------------- #
# Ссылка на проект и обратная связь (#233)
# --------------------------------------------------------------------------- #


def test_repository_point_takes_the_package_address(sample_glossary: Glossary):
    page = HtmlExporter(template=f'<a href="{REPOSITORY}">{PLACEHOLDER}</a>').render(
        sample_glossary
    )
    assert REPOSITORY not in page
    assert f'href="{REPOSITORY_URL}"' in page


def _form_ids(name: str) -> set[str]:
    """Id полей формы задачи — по ним GitHub подставляет параметры адреса."""
    form = yaml.safe_load(
        (project_root() / ".github" / "ISSUE_TEMPLATE" / name).read_text("utf-8")
    )
    return {field["id"] for field in form["body"] if "id" in field}


@pytest.mark.live_surface
def test_showcase_feedback_matches_the_issue_forms():
    """Имена параметров витрины совпадают с id полей формы.

    Переименуй поле в форме — и предзаполнение молча перестанет работать:
    GitHub незнакомый параметр просто пропускает.
    """
    template = load_template()
    assert 'template:"content_fix.yml"' in template
    assert 'id:"entry_id"' in template
    assert "entry_id" in _form_ids("content_fix.yml")
    assert 'template:"term_request.yml"' in template
    assert {"name", "group"} <= _form_ids("term_request.yml")
    assert 'name:"name", group:"group"' in template
    for form in ("content_fix.yml", "term_request.yml", "bug_report.yml"):
        assert f"template={form}" in template or f'template:"{form}"' in template
        assert (project_root() / ".github" / "ISSUE_TEMPLATE" / form).exists()


@pytest.mark.live_surface
def test_shipped_template_names_the_repository_by_the_point():
    template = load_template()
    assert REPOSITORY in template
    assert "github.com/ArtVsMark" not in template, "адрес проекта — точкой, не строкой"
