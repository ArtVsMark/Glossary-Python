#!/usr/bin/env python3
"""Исключительные утверждения документа сверяются друг с другом по предмету.

Правило каталога 181: «X читают **только** отсюда» связывает **весь документ**,
а не тот раздел, где написано. Два таких утверждения об одном предмете друг
друга не уточняют — каждое запрещает второе, и оба перестают действовать:
читатель исполняет то, до которого дочитал.

ПРИЁМ ВЗЯТ У КАТАЛОГА, А МЕРА — НЕТ, И ЭТО ЗАМЕР, А НЕ ВКУС. У каталога пары
ищутся по близости формулировок (``scripts/check_exclusive.py``, мера
``check_duplicates.jaccard``), и на его инциденте настоящая пара встала вторым
местом. Здесь тот же способ прогнан по этому дереву — 17 утверждений, 33 пары
внутри документов, три меры (тройки слов, отдельные слова, слова с обрезанным
окончанием), — и живая пара README встала **22-м, 23-м и 24-м местом**. Причина
названа в самом правиле: близость здесь **смысловая, а не словесная**. У пары
«у содержания один хозяин» ↔ «правится только ``data/glossary.json``» общих слов
нет вовсе, а предмет один. Мера, скопированная отсюда туда, дала бы гейт, не
находящий собственного дефекта дерева, — то есть пустышку (правило 146).

ПОЭТОМУ МАШИНА НЕ СУДИТ, А ТРЕБУЕТ НАЗВАТЬ ПРЕДМЕТ (правило 182). Требование
181 разложено надвое: понять, один ли предмет у двух утверждений и какое из них
верно, машина не может; **что предмет назван** — проверяется целиком. Автор
пишет предмет невидимым маркером рядом с утверждением, гейт складывает
утверждения документа по предмету и краснеет, когда на одном предмете их два.
Перебор, которого правило требует от человека, становится механическим.

    <!--предмет:data/glossary.json-->Витрина — производный артефакт…
    <!--предмет:нет-->«Было. Единственный артефакт…» — это рассказ, а не указание

Форма маркера та же, что у чисел в документации (``scripts/facts.py``): в
собранном тексте его не видно, а в исходнике он стоит рядом с утверждением и
переживает правку соседнего раздела. Реестра при этом не заводится намеренно:
предмет, вынесенный в отдельный файл, разъезжается с текстом молча — тот самый
«один устаревший из двух источников», ради которого правило и написано.

ЧЕГО ГЕЙТ НЕ ЛОВИТ, названо здесь, а не подразумевается (правило 056):

* **два разных имени у одного предмета.** «содержание карточек» и
  ``data/glossary.json`` для машины разные строки; свести их может только
  человек. Это и есть та половина, которая машинной не станет;
* **исключительность без слова-маркера.** «У содержания один хозяин» не
  содержит ни «только», ни «единственный» — и в перебор не попадает;
* **разные документы.** 181 — про один документ, у которого несколько
  плоскостей; тема, разъехавшаяся по двум документам, это правило 022.

Запуск::

    python scripts/check_exclusive.py --list   # утверждения и их предметы
    python scripts/check_exclusive.py --check  # гейт

Исходы: 0 — чисто; 1 — есть находки; 2 — проверка не отработала.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import TYPE_CHECKING, Final, NamedTuple

if TYPE_CHECKING:
    from collections.abc import Iterator

ROOT: Final = Path(__file__).resolve().parent.parent

DOCUMENTS: Final = (
    "CLAUDE.md",
    "CONTRIBUTING.md",
    "README.md",
    "docs/architecture.md",
    "docs/agent/roles.md",
)
"""Документы, которые ИСПОЛНЯЮТ, а не описывают.

Список разрешительный: `CHANGELOG.md` и карточки глоссария сюда не входят —
там исключительность описывает мир, а не предписывает поведение. Внутри
включённого документа рассказ тоже встречается, и для него есть `нет`.
"""

MARKER: Final = re.compile(r"(только|лишь|единственн\w*|исключительно)", re.IGNORECASE)
"""Слова, делающие утверждение исключительным.

Именно они превращают два верных ответа в один неверный: без «только» оба
утверждения совместимы — содержание живёт в источнике, а снимок его отражает.
"""

SUBJECT: Final = re.compile(r"<!--предмет:(?P<name>.*?)-->")
NOT_A_CLAIM: Final = "нет"
"""Предмет, которым автор говорит: это рассказ, а не указание.

Отдельное значение, а не отсутствие маркера: «не разобрано» и «разобрано и
предмета нет» — разные ответы, и склеивать их нельзя (правило 039).
"""

LIST_ITEM: Final = re.compile(r"^\s*(?:[-*+]|\d+\.)\s")
FENCE: Final = "```"
TABLE_ROW: Final = "|"
MIN_LENGTH: Final = 60
"""Короткие строки отбрасываются: «только» в заголовке предметом не является."""

PAIR: Final = 2
"""Сколько утверждений об одном предмете уже перестают действовать (правило 181)."""


class Claim(NamedTuple):
    """Исключительное утверждение документа.

    Attributes:
        document: Путь документа от корня репозитория.
        line: Номер первой строки окна — чтобы находку открыть, а не искать.
        subject: Предмет, названный автором; ``None`` — маркера нет вовсе.
        text: Текст утверждения без служебных маркеров.
    """

    document: str
    line: int
    subject: str | None
    text: str

    @property
    def address(self) -> str:
        """Адрес находки в привычной форме ``файл:строка`` (правило 158)."""
        return f"{self.document}:{self.line}"


def _windows(text: str) -> Iterator[tuple[int, str]]:
    """Разбить документ на окна разбора: абзац либо отдельный пункт списка.

    ОКНО — НЕ ПРЕДЛОЖЕНИЕ (правило 144): резать по точке нельзя, точка стоит
    внутри имён файлов и номеров версий, а предмет часто назван соседней фразой.

    ОКНО — И НЕ АБЗАЦ ЦЕЛИКОМ, и это найдено замером по этому дереву. Первая
    редакция брала абзац, и оба списка свода — «Чего не делать» и «Каталог
    правил» — склеивались в одно утверждение на семь предметов сразу: предмет
    у такого окна не назвать, а пара «список против списка» ничего не значит.
    Пункт списка — самостоятельное указание и своё окно.

    Args:
        text: Содержимое документа.

    Yields:
        Пары «номер первой строки окна, текст окна одной строкой».
    """
    current: list[str] = []
    start = 0
    fenced = False

    for number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()

        if stripped.startswith(FENCE):
            fenced = not fenced
            if current:
                yield start, " ".join(" ".join(current).split())
                current = []
            continue
        if fenced:
            # Код — не утверждение: «только» внутри команды ничего не предписывает.
            continue

        if current and (not stripped or LIST_ITEM.match(line)):
            yield start, " ".join(" ".join(current).split())
            current = []
        if not stripped or stripped.startswith(TABLE_ROW):
            # СТРОКА ТАБЛИЦЫ ОПИСЫВАЕТ ПРЕДМЕТ СВОЕЙ СТРОКИ и документа не
            # связывает: «только» в ячейке про один гейт ничего не запрещает
            # соседнему разделу.
            continue

        if not current:
            start = number
        current.append(line)

    if current:
        yield start, " ".join(" ".join(current).split())


def collect(root: Path) -> list[Claim]:
    """Собрать исключительные утверждения нормативных документов.

    Args:
        root: Корень репозитория.

    Returns:
        Утверждения в порядке обхода документов.
    """
    found: list[Claim] = []
    for name in DOCUMENTS:
        path = root / name
        if not path.exists():
            continue
        for line, window in _windows(path.read_text(encoding="utf-8")):
            match = SUBJECT.search(window)
            text = " ".join(SUBJECT.sub("", window).split())
            if len(text) < MIN_LENGTH or not MARKER.search(text):
                continue
            subject = match.group("name").strip() if match else None
            found.append(Claim(name, line, subject, text))
    return found


def findings(claims: list[Claim]) -> list[str]:
    """Найти утверждения без предмета и пары об одном предмете.

    Args:
        claims: Собранные утверждения.

    Returns:
        Готовые к печати находки; пустой список — чисто.
    """
    problems = [
        f"{claim.address}: утверждение исключительно, а предмет не назван.\n"
        f"      {claim.text[:150]}…\n"
        "      Поставьте рядом <!--предмет:чего именно касается-->, а если это "
        "рассказ,\n      а не указание — <!--предмет:нет-->."
        for claim in claims
        if claim.subject is None
    ]

    by_subject: dict[tuple[str, str], list[Claim]] = defaultdict(list)
    for claim in claims:
        if claim.subject is not None and claim.subject.casefold() != NOT_A_CLAIM:
            by_subject[(claim.document, claim.subject.casefold())].append(claim)

    for (document, subject), group in sorted(by_subject.items()):
        if len(group) < PAIR:
            continue
        where = ", ".join(claim.address for claim in group)
        problems.append(
            f"{document}: два исключительных утверждения об одном предмете "
            f"«{subject}» — {where}.\n"
            "      Каждое запрещает второе, и оба перестают действовать: "
            "читатель\n      исполняет то, до которого дочитал. Либо одно из "
            "них неверно и его\n      правят, либо предметы на деле разные — "
            "тогда чинят не\n      исключительность, а имя предмета (правило "
            "181)."
        )
    return problems


def _mode_list(root: Path) -> int:
    """Показать утверждения и названные у них предметы."""
    claims = collect(root)
    if not claims:
        return _nothing_to_check(root)
    print(f"исключительных утверждений {len(claims)} в {len(DOCUMENTS)} документах:\n")
    for claim in claims:
        subject = claim.subject if claim.subject is not None else "— предмет не назван"
        print(f"  {claim.address}  [{subject}]")
        print(f"      {claim.text[:120]}…")
    return 0


def _mode_check(root: Path) -> int:
    """Гейт: у каждого утверждения назван предмет, и на предмет он один."""
    claims = collect(root)
    if not claims:
        return _nothing_to_check(root)

    problems = findings(claims)
    if problems:
        print("исключительные утверждения не сверены друг с другом:", file=sys.stderr)
        for problem in problems:
            print(f"  • {problem}", file=sys.stderr)
        return 1

    named = sum(1 for claim in claims if claim.subject != NOT_A_CLAIM)
    print(
        f"исключительные утверждения сверены: их {len(claims)}, "
        f"с предметом {named}, столкновений нет"
    )
    return 0


def _nothing_to_check(root: Path) -> int:
    """Третий исход с адресом отказа: проверять нечего, и это не «чисто».

    Ноль утверждений означает не «противоречий нет», а «предмета нет»: так же
    выглядит опечатка в списке документов или запуск вне репозитория. Зеленеть
    на этом нельзя (правила 075, 158).
    """
    print(
        "проверка не отработала: под "
        f"{root} нет ни одного исключительного утверждения. Ожидались "
        f"документы {', '.join(DOCUMENTS)} — проверьте, что запуск идёт "
        "из репозитория",
        file=sys.stderr,
    )
    return 2


def main(argv: list[str] | None = None) -> int:
    """Точка входа.

    Args:
        argv: Аргументы командной строки; ``None`` — взять из ``sys.argv``.

    Returns:
        Код возврата процесса.
    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=ROOT)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--list", action="store_true", help="показать утверждения и их предметы"
    )
    mode.add_argument(
        "--check", action="store_true", help="гейт: предмет назван и на предмет он один"
    )
    args = parser.parse_args(argv)
    return _mode_list(args.root) if args.list else _mode_check(args.root)


if __name__ == "__main__":
    sys.exit(main())
