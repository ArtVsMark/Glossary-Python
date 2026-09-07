"""Ссылка проверяется разметкой, а не подстрокой адреса в тексте.

Правило каталога 166. Проверка «есть ли в README строка ``docs/architecture.md``»
выглядит проверкой ссылки и ею не является: подстрока находится в **подписи**, и
``[docs/architecture.md](docs/арх.md)`` проходит её зелёной, ведя в никуда.
Поэтому здесь ищется позиция цели — ``](адрес`` и ``]: адрес``, — а найденный
адрес разрешается в файл дерева.

Предмет — ссылки документов из ``DOCUMENTS``: друг на друга и на файлы дерева
(``scripts/*.py``, ``tests/*.py``, ``.github/workflows/*.yml`` в том числе).

Чего гейт **не** ловит (правило 056):

* **Внешние адреса не запрашиваются.** У прогона может не быть выхода наружу, а
  сетевой шаг недетерминирован: сегодня зелёный, завтра красный без единой
  правки. Битая ``https://``-ссылка здесь не ловится ничем.
* **Якорь не разрешается.** Соответствие ``#раздел`` заголовку строит GitHub
  своим алгоритмом слагов; повторять его тут — заводить второй источник истины.
  У ``файл.md#раздел`` проверяется файл, раздел — нет.
* **Ссылка внутри кода — пример, а не ссылка.** Ограда и обратные кавычки
  внутри строки гасятся: markdown ссылкой такое не делает, и гейт не делает.
* **Путь в обратных кавычках — не ссылка.** ``scripts/facts.py`` в тексте
  выглядит адресом и им не является: разрешать его значило бы искать путь
  в тексте — ровно то, что правило 166 и запрещает. Такое упоминание может
  устареть, и гейт этого не увидит.
* **Предмет — только названные документы**, а не всё дерево: ``CHANGELOG.md``,
  ``changelog.d/*.md`` и карточки глоссария не проверяются.
* **HTML-ссылка ``<a href=…>`` не ищется.** Разметка markdown — не HTML;
  в предмете таких ссылок нет, а искать обе формы одним выражением значит
  не искать толком ни одной.

Коды возврата (правило 158):

* ``0`` — все адреса разрешились;
* ``1`` — есть находки: адрес не разрешается в файл дерева;
* ``2`` — проверка не отработала.

``2`` не означает ни «ссылки целы», ни «ссылки битые»: о ссылках не известно
ничего. Сообщение при нём называет **предмет** отказа — какой именно документ не
прочитан, — а не только причину: «файл не найден» без имени файла не говорит,
что чинить.

Запуск::

    python scripts/check_links.py           # гейт
    python scripts/check_links.py --list    # показать найденные ссылки
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Final
from urllib.parse import unquote

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

ROOT: Final = Path(__file__).resolve().parent.parent

DOCUMENTS: Final[tuple[str, ...]] = (
    "README.md",
    "CLAUDE.md",
    "CONTRIBUTING.md",
    "docs/architecture.md",
    "docs/agent/roles.md",
    "docs/contracts.md",
)
"""Документы, чьи ссылки держит гейт.

Список, а не обход всех ``*.md``: обход втянул бы ``changelog.d/`` и карточки,
где ссылка живёт по другим правилам, а предмет проверки должен быть назван,
а не выведен из раскладки файлов.
"""

CLEAN: Final = 0
FOUND: Final = 1
REFUSED: Final = 2
"""Коды возврата. Третий — «не отработала», а не «нашла» и не «не нашла»."""

FENCE: Final = re.compile(r"^\s{0,3}(?P<fence>`{3,}|~{3,})")
"""Ограда блока кода. Закрывает её маркер того же вида, что открыл."""

CODE_SPAN: Final = re.compile(r"(?P<ticks>`+)(?:(?!(?P=ticks)).)+(?P=ticks)")
"""Код внутри строки. ``[подпись](адрес)`` в нём — набор символов, не ссылка."""

INLINE: Final = re.compile(
    r"\]\(\s*(?:<(?P<angle>[^<>\n]*)>|(?P<plain>[^\s()]*(?:\([^\s()]*\)[^\s()]*)*))"
)
"""Цель обычной ссылки: всё, что стоит **после** ``](``, но не подпись до него."""

REFERENCE: Final = re.compile(
    r"^\s{0,3}\[(?!\^)[^\]\n]+\]:\s*(?:<(?P<angle>[^<>\n]*)>|(?P<plain>\S+))"
)
"""Цель ссылки-определения. ``[^1]:`` исключён: это сноска, а не ссылка."""

SKIPPED: Final = re.compile(r"#|//|[a-zA-Z][a-zA-Z0-9+.\-]*:")
"""Адрес, который гейт не разрешает: якорь, протокол-относительный, со схемой."""


@dataclass(frozen=True, slots=True)
class Link:
    """Ссылка, найденная разметкой: в ней есть цель и нет подписи."""

    document: str
    line: int
    target: str

    @property
    def where(self) -> str:
        """Место находки в виде ``документ:строка``."""
        return f"{self.document}:{self.line}"


def _uncoded(text: str) -> list[str]:
    """Строки документа, где код погашен: ограды целиком, код внутри строки — на месте.

    Гасится, а не выбрасывается: номера строк в находках обязаны совпадать с
    файлом, иначе находку негде смотреть. Код внутри строки заменяется пробелами
    той же длины по той же причине.

    Многострочный код внутри строки (открывающие обратные кавычки на одной
    строке, закрывающие на другой) не гасится: разбор идёт построчно.
    """
    lines: list[str] = []
    fence: str | None = None
    for raw in text.splitlines():
        marker = FENCE.match(raw)
        opening = marker.group("fence")[0] if marker is not None else None
        if fence is None:
            fence = opening
            lines.append("" if opening is not None else _uncoded_line(raw))
            continue
        # Ограду закрывает маркер того же вида: ``` внутри ~~~ — это текст.
        if opening == fence:
            fence = None
        lines.append("")
    return lines


def _uncoded_line(line: str) -> str:
    """Погасить код внутри строки, сохранив её длину."""
    return CODE_SPAN.sub(lambda m: " " * len(m.group(0)), line)


def find_links(text: str, document: str = "") -> list[Link]:
    """Найти ссылки разметкой: ``](адрес`` и ``]: адрес``.

    Ищется позиция цели, а не текст адреса. Поиск подстрокой («есть ли в README
    путь ``docs/architecture.md``») остаётся зелёным при подменённой цели:
    условие выполняется на подписи ссылки.

    Args:
        text: Содержимое markdown-документа.
        document: Имя документа — попадёт в сообщение о находке.

    Returns:
        Ссылки в порядке появления. Подписи в результат не попадают вовсе.
    """
    links: list[Link] = []
    for number, line in enumerate(_uncoded(text), start=1):
        # Определение привязано к началу строки, обычная ссылка — нет, поэтому
        # порядок пар совпадает с порядком в строке без сортировки.
        for pattern in (REFERENCE, INLINE):
            for match in pattern.finditer(line):
                angle = match.group("angle")
                plain = match.group("plain")
                target = angle if angle is not None else plain
                links.append(Link(document, number, target.strip()))
    return links


def read_documents(root: Path, documents: Sequence[str]) -> tuple[list[Link], list[str]]:
    """Прочитать документы и собрать из них ссылки.

    Args:
        root: Корень дерева, относительно которого лежат документы.
        documents: Пути документов относительно корня.

    Returns:
        Пара «ссылки, отказы». Непустые отказы означают, что проверка не
        отработала; каждый называет документ, а не только причину.
    """
    links: list[Link] = []
    refusals: list[str] = []
    for name in documents:
        path = root / name
        if not path.is_file():
            refusals.append(f"документ не прочитан: {name} — файла нет в {root}")
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            refusals.append(f"документ не прочитан: {name} — {exc}")
            continue
        links.extend(find_links(text, name))
    return links, refusals


def check(root: Path, links: Iterable[Link]) -> list[str]:
    """Найти ссылки, чья цель не разрешается в файл дерева.

    Внешние адреса пропускаются молча: в сеть гейт не ходит. Цель, уводящая за
    пределы дерева, — находка, даже если файл по ней есть: на GitHub такой
    ссылки нет.

    Args:
        root: Корень дерева.
        links: Ссылки, найденные разметкой.

    Returns:
        Замечания по одному на находку. Пустой список — все адреса разрешились.
    """
    problems: list[str] = []
    base = root.resolve()
    for link in links:
        if not link.target:
            problems.append(f"{link.where}: пустой адрес — ссылка ведёт в никуда")
            continue
        if SKIPPED.match(link.target) is not None:
            continue
        path_part = link.target.split("#", 1)[0].split("?", 1)[0]
        if not path_part:
            continue
        candidate = ((base / link.document).parent / unquote(path_part)).resolve()
        if not candidate.is_relative_to(base):
            problems.append(
                f"{link.where}: цель уходит за пределы дерева — "
                f"{link.target!r} → {candidate}"
            )
        elif not candidate.exists():
            problems.append(
                f"{link.where}: цель не разрешается — "
                f"{link.target!r} → {candidate.relative_to(base)}"
            )
    return problems


def main(argv: list[str] | None = None) -> int:
    """Точка входа. Возвращает 0, 1 или 2 — см. docstring модуля."""
    parser = argparse.ArgumentParser(description="Гейт на ссылки в документации")
    parser.add_argument(
        "documents",
        nargs="*",
        metavar="DOC",
        help=f"что проверять (по умолчанию: {', '.join(DOCUMENTS)})",
    )
    parser.add_argument(
        "--root", type=Path, default=ROOT, metavar="DIR", help="корень дерева"
    )
    parser.add_argument(
        "--list", action="store_true", dest="show", help="показать найденные ссылки"
    )
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    documents = tuple(args.documents) or DOCUMENTS
    links, refusals = read_documents(root, documents)

    if refusals:
        for refusal in refusals:
            print(refusal, file=sys.stderr)
        print(
            "\nПроверка не отработала: о ссылках не известно ничего. "
            "Поправьте список документов или путь --root.",
            file=sys.stderr,
        )
        return REFUSED

    # Правило 075: гейт, не нашедший предмета, обязан падать. Ноль ссылок
    # неотличим от нуля находок, и молчание тут читалось бы как «всё цело».
    if not links:
        print(
            f"ни одной ссылки не найдено в: {', '.join(documents)} — "
            "проверять нечего, а зелёный такой гейт читался бы как «всё цело»",
            file=sys.stderr,
        )
        return REFUSED

    if args.show:
        for link in links:
            print(f"{link.where}: {link.target}")

    problems = check(root, links)
    for problem in problems:
        print(problem, file=sys.stderr)
    if problems:
        print(
            f"\nБитых ссылок: {len(problems)}. Цель ищется разметкой, "
            "поэтому подпись с верным путём находку не прячет.",
            file=sys.stderr,
        )
        return FOUND

    external = sum(1 for link in links if SKIPPED.match(link.target) is not None)
    print(
        f"ссылок найдено: {len(links)} в {len(documents)} документах; "
        f"разрешено {len(links) - external}, внешних и якорей пропущено {external}"
    )
    return CLEAN


if __name__ == "__main__":
    raise SystemExit(main())
