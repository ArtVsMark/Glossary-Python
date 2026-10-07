"""Витрина открывается в настоящем браузере, а не только собирается.

Правило каталога 032: вывод о работе продукта делается запуском, а не чтением
кода. ``glossary build --check`` сверяет, что витрина собрана из текущих данных,
но её JavaScript не исполняет ничто: страница, падающая на первой строке
сценария, проходит сборку зелёной. Здесь витрина открывается безголовым
Chromium (``--dump-dom``), и по отрисованному DOM проверяются два сценария
читателя:

* **страница открылась** — счётчик показывает «все карточки из всех», а в сетке
  стоят отрисованные карточки. Упади сценарий — счётчик остался бы пустым;
* **ссылка на карточку ведёт к ней** — берётся первая карточка, которой нет в
  начальной порции (сетка дорисовывается прокруткой), и витрина открывается
  с её якорем: карточка обязана появиться в DOM.

Новой зависимости это не требует: Chrome стоит на раннерах ubuntu, браузер
ищется в ``CHROME_BIN``, затем по известным именам в ``PATH``, затем в каталоге
браузеров Playwright облачного окна.

ЧЕГО СТОРОЖ НЕ ВИДИТ (правило 056): нажатий и ввода. Поиск, фильтры и тема
переключаются событиями, а ``--dump-dom`` их не порождает; это остаётся
ручной половиной сценария читателя (README, раздел «Статус»). Вёрстку и
читаемость он не оценивает вовсе — только что сценарий отработал.

Коды возврата (правило 158): ``0`` — оба сценария прошли; ``1`` — находки;
``2`` — проверка не отработала (нет браузера, нет витрины, браузер не ответил
в срок). ``2`` не значит «витрина работает»: о витрине не известно ничего.

Запуск::

    python scripts/check_showcase_runs.py
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Final

ROOT: Final = Path(__file__).resolve().parent.parent
SHOWCASE: Final = ROOT / "python_glossary.html"
GLOSSARY: Final = ROOT / "data" / "glossary.json"

NOT_RUN: Final = 2
"""Проверка не отработала. Не означает «витрина работает» — её не открывали."""

BROWSER_TIMEOUT: Final = 90
"""Секунд на один запуск браузера: старт плюс отрисовка двух тысяч карточек."""

BUDGET_MS: Final = 5000
"""Виртуальное время страницы до снимка DOM: сценарий успевает дорисовать сетку."""

BROWSER_NAMES: Final = (
    "google-chrome",
    "google-chrome-stable",
    "chromium",
    "chromium-browser",
)
PLAYWRIGHT_GLOB: Final = "chromium-*/chrome-linux/chrome"

COUNTER: Final = re.compile(
    r'id="counter">[^<]*<b>(?P<shown>\d+)</b>\s*\S+\s*(?P<total>\d+)'
)
CARD: Final = re.compile(r'<article class="card" id="(?P<id>[^"]+)"')


class NotRunError(RuntimeError):
    """Смотреть нечем или не на что: третий исход, а не находка."""


def find_browser() -> Path:
    """Путь к Chromium или Chrome: переменная, затем ``PATH``, затем Playwright."""
    explicit = os.environ.get("CHROME_BIN")
    if explicit:
        return Path(explicit)
    for name in BROWSER_NAMES:
        found = shutil.which(name)
        if found:
            return Path(found)
    browsers = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
    if browsers:
        candidates = sorted(Path(browsers).glob(PLAYWRIGHT_GLOB))
        if candidates:
            return candidates[-1]
    raise NotRunError(
        "браузер не найден: ни CHROME_BIN, ни " + ", ".join(BROWSER_NAMES) + " в PATH"
    )


def dump_dom(browser: Path, page: Path, anchor: str = "") -> str:
    """DOM страницы после исполнения её сценария."""
    url = page.resolve().as_uri() + (f"#{anchor}" if anchor else "")
    try:
        done = subprocess.run(  # noqa: S603 — браузер найден нами, адрес — файл дерева
            [
                str(browser),
                "--headless",
                "--no-sandbox",
                "--disable-gpu",
                f"--virtual-time-budget={BUDGET_MS}",
                "--dump-dom",
                url,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=BROWSER_TIMEOUT,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        raise NotRunError(f"{browser} не ответил за {BROWSER_TIMEOUT} с") from error
    except OSError as error:
        raise NotRunError(f"{browser} не запустился: {error}") from error
    if done.returncode != 0 or not done.stdout:
        raise NotRunError(f"{browser} вернул {done.returncode} и пустой DOM для {url}")
    return done.stdout


def rendered_ids(dom: str) -> list[str]:
    """Идентификаторы карточек, отрисованных в сетке, по порядку."""
    return [match.group("id") for match in CARD.finditer(dom)]


def opening_findings(dom: str, total: int) -> list[str]:
    """Сценарий «страница открылась»: счётчик полон, сетка не пуста."""
    match = COUNTER.search(dom)
    if match is None:
        return ["счётчик витрины пуст — сценарий страницы не дошёл до отрисовки"]
    findings: list[str] = []
    shown, counted = int(match.group("shown")), int(match.group("total"))
    if counted != total:
        findings.append(f"витрина считает {counted} карточек, а в сборке их {total}")
    if shown != counted:
        findings.append(f"без фильтров показано {shown} из {counted}")
    if not rendered_ids(dom):
        findings.append("сетка пуста: счётчик есть, карточек нет")
    return findings


def deep_target(ids: list[str], rendered: list[str]) -> str | None:
    """Первая карточка сборки, которой нет в начальной порции сетки."""
    shown = set(rendered)
    return next((card for card in ids if card not in shown), None)


def check(browser: Path, page: Path, ids: list[str]) -> list[str]:
    """Оба сценария читателя на настоящей странице."""
    first = dump_dom(browser, page)
    findings = opening_findings(first, len(ids))
    target = deep_target(ids, rendered_ids(first))
    if target is not None and target not in rendered_ids(dump_dom(browser, page, target)):
        findings.append(f"переход по якорю #{target} не отрисовал карточку")
    return findings


def main(argv: list[str] | None = None) -> int:
    """Точка входа: 0 — сценарии прошли, 1 — находки, 2 — не отработало."""
    parser = argparse.ArgumentParser(description="Витрина в настоящем браузере")
    parser.add_argument("--page", type=Path, default=SHOWCASE, help="файл витрины")
    args = parser.parse_args(argv)

    try:
        if not args.page.exists():
            raise NotRunError(f"витрины {args.page} нет — открывать нечего")
        entries = json.loads(GLOSSARY.read_text(encoding="utf-8"))["entries"]
        browser = find_browser()
        findings = check(browser, args.page, [entry["id"] for entry in entries])
    except NotRunError as refusal:
        print(f"проверка не отработала: {refusal}", file=sys.stderr)
        return NOT_RUN
    for finding in findings:
        print(f"{args.page.name}: {finding}", file=sys.stderr)
    if findings:
        return 1
    print(f"витрина открылась в {browser.name}: {len(entries)} карточек, якорь ведёт")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
