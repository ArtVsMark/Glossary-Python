"""Навигация витрины: семейства разделов и таблица для страницы."""

import json

import pytest

from glossary import taxonomy
from glossary.exporters.html import NAVIGATION, HtmlExporter, load_template
from glossary.loader import default_data_path, load_glossary
from tests.factories import make_entry, make_glossary


@pytest.mark.parametrize(
    ("section", "group"),
    [
        ("Модуль os", "modules"),
        ("Строки (str)", "types"),
        ("Исключения", "builtins"),
        # Удалённое из библиотеки — библиотека, как в «Removed Modules» (#164).
        ("Удалено из стандартной библиотеки", "modules"),
        ("Раздел, которого нет", taxonomy.OTHER),
    ],
)
def test_group_comes_from_section(section: str, group: str):
    assert taxonomy.group_of(section) == group


def test_module_label_drops_the_prefix_in_both_languages():
    assert taxonomy.section_label("Модуль os", "ru") == "os"
    assert taxonomy.section_label("Модуль os", "en") == "os"


def test_unknown_section_is_shown_as_is():
    assert taxonomy.section_label("Новый раздел", "en") == "Новый раздел"


def test_every_group_has_both_labels():
    for group in taxonomy.GROUPS:
        assert set(taxonomy.GROUP_LABELS[group]) == {"ru", "en"}


def test_every_classified_section_has_an_english_label():
    assert set(taxonomy.SECTION_GROUPS) == set(taxonomy.SECTION_LABELS_EN)


def test_page_receives_the_table():
    exporter = HtmlExporter(template=f"<a>{NAVIGATION}</a><b>{{{{GLOSSARY_DATA}}}}</b>")
    page = exporter.render(make_glossary(make_entry(id="x", section="Модуль re")))
    table = json.loads(page.split("<a>")[1].split("</a>")[0])
    assert table["sections"]["Модуль re"] == {"group": "modules", "ru": "re", "en": "re"}


@pytest.mark.live_surface
def test_shipped_template_has_the_navigation_slot():
    assert NAVIGATION in load_template()


@pytest.mark.live_surface
def test_every_section_in_the_snapshot_is_classified():
    """«Прочее» в снимке пусто: новый раздел обязан получить семейство явно."""
    sections = load_glossary(default_data_path()).sections
    loose = [s for s in sections if taxonomy.group_of(s) == taxonomy.OTHER]
    assert not loose, f"разделы без семейства: {loose}"
