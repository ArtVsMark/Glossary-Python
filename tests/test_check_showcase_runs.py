"""Витрина в настоящем браузере: разбор DOM и два сценария читателя (правило 032).

Подделки показывают, что разбор снимка DOM устроен верно. Живая половина
открывает настоящую витрину и страницу, ломающуюся на первой строке сценария:
без браузера она пропускается с причиной — CI зовёт сторож отдельным шагом,
и там отсутствие браузера краснит прогон третьим исходом.
"""

import json
from pathlib import Path

import pytest

import check_showcase_runs as runs
from glossary.exporters import pages
from glossary.models import Entry, Glossary


def page(shown: int, total: int, ids: list[str]) -> str:
    """Снимок DOM витрины с заданным счётчиком и отрисованными карточками."""
    cards = "".join(f'<article class="card" id="{card}" style="">' for card in ids)
    return (
        f'<div class="counter" id="counter">Показано: <b>{shown}</b> из {total}</div>'
        f'<div class="grid" id="grid">{cards}</div>'
    )


def test_full_counter_with_cards_passes():
    assert runs.opening_findings(page(3, 3, ["a", "b"]), 3) == []


def test_empty_counter_means_the_script_did_not_run():
    dom = '<div class="counter" id="counter"></div><div class="grid" id="grid"></div>'
    findings = runs.opening_findings(dom, 3)
    assert findings and "счётчик" in findings[0]


def test_counter_disagreeing_with_the_build_is_a_finding():
    findings = runs.opening_findings(page(2, 2, ["a"]), 3)
    assert findings == ["витрина считает 2 карточек, а в сборке их 3"]


def test_filtered_start_is_a_finding():
    assert runs.opening_findings(page(1, 3, ["a"]), 3) == ["без фильтров показано 1 из 3"]


def test_empty_grid_is_a_finding():
    assert runs.opening_findings(page(3, 3, []), 3) == [
        "сетка пуста: счётчик есть, карточек нет"
    ]


def test_deep_target_is_the_first_card_beyond_the_first_batch():
    assert runs.deep_target(["a", "b", "c"], ["a", "c"]) == "b"
    assert runs.deep_target(["a"], ["a"]) is None


def test_browser_from_the_environment_wins(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("CHROME_BIN", "/нет/такого/chrome")
    assert runs.find_browser() == Path("/нет/такого/chrome")


def test_no_browser_is_not_run(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("CHROME_BIN", raising=False)
    monkeypatch.delenv("PLAYWRIGHT_BROWSERS_PATH", raising=False)
    monkeypatch.setattr("check_showcase_runs.shutil.which", lambda _name: None)
    with pytest.raises(runs.NotRunError):
        runs.find_browser()


def test_missing_page_is_not_run(tmp_path: Path):
    assert runs.main(["--page", str(tmp_path / "нет.html")]) == runs.NOT_RUN


def _browser() -> Path:
    """Браузер окна или пропуск: живая половина без него не смотрит ничего."""
    try:
        return runs.find_browser()
    except runs.NotRunError as refusal:
        pytest.skip(f"браузера нет: {refusal}")


@pytest.mark.live_surface
def test_live_showcase_opens_and_follows_an_anchor():
    browser = _browser()
    entries = json.loads(runs.GLOSSARY.read_text(encoding="utf-8"))["entries"]
    assert runs.check(browser, runs.SHOWCASE, [e["id"] for e in entries]) == []


@pytest.mark.live_surface
def test_live_broken_script_is_caught(tmp_path: Path):
    """Страница, чей сценарий падает до отрисовки, обязана дать находку."""
    browser = _browser()
    broken = tmp_path / "broken.html"
    broken.write_text(
        '<div class="counter" id="counter"></div>'
        "<script>throw new Error('сценарий упал');</script>",
        encoding="utf-8",
    )
    assert runs.check(browser, broken, ["a"]) != []


# --------------------------------------------------------------------------- #
# Обратная связь из карточки (#233)
# --------------------------------------------------------------------------- #


def test_card_with_its_report_link_is_silent():
    card = "бинарный-поиск"
    encoded = "".join(
        f"%{byte:02X}" if byte > 127 else chr(byte) for byte in card.encode()
    )
    dom = page(1, 1, [card])
    href = f"x?template=content_fix.yml&amp;entry_id={encoded}"
    dom += f'<a class="report-link" href="{href}">'
    assert runs.feedback_findings(dom) == []


def test_card_without_its_report_link_is_a_finding():
    findings = runs.feedback_findings(page(1, 1, ["a"]))
    assert len(findings) == 1
    assert "незаполненной" in findings[0]


def test_empty_grid_has_no_feedback_to_check():
    assert runs.feedback_findings(page(0, 0, [])) == []


# --------------------------------------------------------------------------- #
# Страница карточки ведёт в витрину (#227)
# --------------------------------------------------------------------------- #


def test_card_page_target_prefers_a_cyrillic_id():
    assert runs.card_page_target(["alpha", "бинарный-поиск"]) == "бинарный-поиск"
    assert runs.card_page_target(["alpha", "beta"]) == "alpha"
    assert runs.card_page_target([]) is None


@pytest.mark.live_surface
def test_live_card_page_leads_to_its_card():
    browser = _browser()
    entries = json.loads(runs.GLOSSARY.read_text(encoding="utf-8"))["entries"]
    target = runs.card_page_target([e["id"] for e in entries])
    assert target is not None
    assert runs.card_page_findings(browser, runs.SHOWCASE, target) == []


@pytest.mark.live_surface
def test_live_button_to_another_card_is_caught(monkeypatch: pytest.MonkeyPatch):
    """Кнопка, ведущая не на свою карточку, обязана дать находку."""
    browser = _browser()
    render = pages.render_page

    def wrong(glossary: Glossary, entry: Entry, lang: str) -> str:
        return render(glossary, entry, lang).replace('href="../#', 'href="../#x')

    monkeypatch.setattr(pages, "render_page", wrong)
    entries = json.loads(runs.GLOSSARY.read_text(encoding="utf-8"))["entries"]
    target = runs.card_page_target([e["id"] for e in entries])
    assert target is not None
    assert runs.card_page_findings(browser, runs.SHOWCASE, target) != []
