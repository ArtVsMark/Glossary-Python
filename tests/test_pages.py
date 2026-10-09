"""Страницы карточек и sitemap.xml (#227).

Подделки показывают, что разбор устроен верно: три карточки дают шесть страниц и
семь адресов в карте сайта, языки ссылаются друг на друга, битая связь не роняет
сборку. Живая половина держит само дерево: страниц ровно вдвое больше, чем
карточек в сборке, и все id годятся в адрес.
"""

import json
import re
from pathlib import Path, PurePosixPath

import pytest

from glossary.cli import EXIT_OK, main
from glossary.contracts import PAGES_URL
from glossary.errors import ExportError
from glossary.exporters import pages
from glossary.models import Glossary
from tests.factories import make_entry, make_glossary


def trio() -> Glossary:
    """Три карточки: связь на соседа, битая связь, кириллический id."""
    return make_glossary(
        make_entry(id="alpha", title="alpha()", related=("beta", "нет-такой")),
        make_entry(id="beta", title="beta()", related_errors=("Alpha",)),
        make_entry(id="бинарный-поиск", title="Бинарный поиск"),
    )


def test_three_cards_give_six_pages_and_seven_addresses():
    files = pages.render_pages(trio())
    assert len([p for p in files if p.name == "index.html"]) == 6
    assert files[pages.SITEMAP].count("<loc>") == 7, "витрина и 2 × 3 страницы"
    assert pages.STYLESHEET in files


def test_english_pages_live_under_their_own_directory():
    assert pages.page_path("alpha", "ru") == PurePosixPath("alpha/index.html")
    assert pages.page_path("alpha", "en") == PurePosixPath("en/alpha/index.html")


def test_cyrillic_id_is_percent_encoded_in_the_address():
    url = pages.page_url("бинарный-поиск", "en")
    assert url.startswith(f"{PAGES_URL}en/%D0%B1")
    assert url.endswith("/")


def test_hreflang_is_mutual():
    files = pages.render_pages(trio())
    for lang in ("ru", "en"):
        page = files[pages.page_path("alpha", lang)]
        assert f'hreflang="ru" href="{pages.page_url("alpha", "ru")}"' in page
        assert f'hreflang="en" href="{pages.page_url("alpha", "en")}"' in page
        assert f'rel="canonical" href="{pages.page_url("alpha", lang)}"' in page


def _related_targets(page: str) -> list[str]:
    """Каталоги, на которые ведут ссылки «см. также» и «частые ошибки»."""
    blocks = re.findall(r'<nav class="related">(.*?)</nav>', page)
    return [m for block in blocks for m in re.findall(r'href="\.\./([^"]+)/"', block)]


def test_related_links_lead_to_existing_pages_and_broken_one_is_dropped():
    files = pages.render_pages(trio())
    ids = {"alpha", "beta"}
    for lang in ("ru", "en"):
        targets = _related_targets(files[pages.page_path("alpha", lang)])
        assert targets == ["beta"], "битая «нет-такой» ссылки не порождает"
        assert set(targets) <= ids
    # Ссылка по имени исключения разрешается без учёта регистра, как в витрине.
    assert _related_targets(files[pages.page_path("beta", "ru")]) == ["alpha"]


def test_full_glossary_button_leads_to_the_showcase_anchor():
    files = pages.render_pages(trio())
    assert 'href="../#alpha"' in files[pages.page_path("alpha", "ru")]
    assert 'href="../../#alpha"' in files[pages.page_path("alpha", "en")]


def test_language_switch_leads_to_the_twin():
    files = pages.render_pages(trio())
    assert 'href="../en/alpha/"' in files[pages.page_path("alpha", "ru")]
    assert 'href="../../alpha/"' in files[pages.page_path("alpha", "en")]


def test_text_is_escaped():
    glossary = make_glossary(make_entry(id="lt", title="a < b & </script>"))
    page = pages.render_pages(glossary)[pages.page_path("lt", "ru")]
    assert "a &lt; b &amp; &lt;/script&gt;" in page
    assert (
        "</script>"
        not in page.split('<script type="application/ld+json">')[1].split("</script>", 1)[
            0
        ]
    )


@pytest.mark.parametrize("bad", [".iterdir", "a/b", "en", "sitemap.xml", " "])
def test_id_unfit_for_a_directory_is_refused_by_name(bad: str):
    with pytest.raises(ExportError, match=re.escape(repr(bad))):
        pages.render_pages(make_glossary(make_entry(id=bad)))


def test_duplicate_id_is_refused():
    with pytest.raises(ExportError, match="две карточки"):
        pages.render_pages(make_glossary(make_entry(id="a"), make_entry(id="a")))


def test_empty_glossary_is_refused():
    with pytest.raises(ExportError, match="пуст"):
        pages.render_pages(Glossary(entries=()))


def test_command_writes_pages_and_counts_them(tmp_path: Path, capsys):
    data = tmp_path / "glossary.json"
    cards = [
        {
            "id": name,
            "title": {"ru": name, "en": name},
            "kind": "term",
            "summary": {"ru": "сводка", "en": "summary"},
            "body": {"ru": "", "en": ""},
        }
        for name in ("one", "two")
    ]
    data.write_text(json.dumps({"schema_version": 6, "entries": cards}), encoding="utf-8")
    out = tmp_path / "site"
    assert main(["pages", "--data", str(data), "-o", str(out)]) == EXIT_OK
    assert (out / "one" / "index.html").is_file()
    assert (out / "en" / "two" / "index.html").is_file()
    assert (out / "sitemap.xml").is_file()
    assert "Страниц карточек: 4 (2 × 2)" in capsys.readouterr().out


@pytest.mark.live_surface
def test_every_card_of_the_build_gets_both_pages(real_glossary: Glossary):
    files = pages.render_pages(real_glossary)
    count = len([p for p in files if p.name == "index.html"])
    assert count == 2 * len(real_glossary)
    assert files[pages.SITEMAP].count("<loc>") == count + 1
