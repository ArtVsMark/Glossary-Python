"""Английский двойник документа повторяет устройство русского оригинала.

Документация ведётся на двух языках: оригинал ``имя.md`` по-русски, двойник
``имя.en.md`` по-английски. Перевод расходится с оригиналом молча — правку
вносят в один файл, а второй остаётся зелёным и врёт. Смысл перевода машина не
сверит; сверяется **устройство**, которое без правки обоих файлов не совпадёт:

* у пары есть обе половины, и каждая ссылается на другую строкой-переключателем;
* заголовки идут тем же числом и тех же уровней в том же порядке;
* строк таблиц и блоков кода столько же.

Новый раздел, дописанный в одну половину, меняет последовательность
заголовков; новая строка таблицы правил — число строк таблиц. Обе находки
называют пару и место расхождения.

Чего гейт **не** ловит (правило 056):

* **Правку внутри абзаца.** Переписанное предложение устройства не меняет —
  проверить, что перевод говорит то же, может только читатель.
* **Документы вне ``PAIRS``.** Список назван явно: обход ``*.md`` втянул бы
  журнал и архив, которые намеренно не переводятся.

Коды возврата (правило 158):

* ``0`` — пары совпадают устройством;
* ``1`` — есть находки;
* ``2`` — проверка не отработала: оригинала из списка нет или он не читается.

Запуск::

    python scripts/check_translations.py
"""

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from collections.abc import Sequence

ROOT: Final = Path(__file__).resolve().parent.parent

PAIRS: Final[tuple[str, ...]] = (
    "README.md",
    "docs/README.md",
    "docs/use/README.md",
    "docs/use/status.md",
    "docs/use/outputs.md",
    "docs/use/contracts.md",
    "docs/dev/README.md",
    "docs/dev/getting-started.md",
    "docs/dev/quality.md",
    "docs/dev/contributing.md",
    "docs/dev/architecture.md",
    "docs/agent/README.md",
    "docs/agent/rules.md",
    "docs/agent/roles.md",
    "docs/agent/work.md",
    "changelog.d/README.md",
)
"""Русские оригиналы, у которых обязан быть английский двойник.

Не переводятся намеренно: ``CLAUDE.md`` — свод агентского окна, рабочий язык
которого русский; ``CHANGELOG.md``, его архив и фрагменты ``changelog.d/`` —
журнал, запись которого пишется один раз и не переписывается;
``docs/contracts.md`` — заглушка переехавшего адреса.
"""

CLEAN: Final = 0
FOUND: Final = 1
REFUSED: Final = 2

FENCE: Final = re.compile(r"^\s{0,3}(`{3,}|~{3,})")
HEADING: Final = re.compile(r"^(#{1,6})\s")
TABLE_ROW: Final = re.compile(r"^\s*\|")


@dataclass(frozen=True, slots=True)
class Shape:
    """Устройство документа: то, что совпадает у оригинала и перевода."""

    headings: tuple[tuple[int, str], ...]
    """Уровень и текст каждого заголовка вне блоков кода."""
    table_rows: int
    fences: int


def shape(text: str) -> Shape:
    """Снять устройство документа.

    Строки внутри блока кода не считаются ни заголовком, ни таблицей:
    комментарий ``# …`` в bash-примере заголовком не является.
    """
    headings: list[tuple[int, str]] = []
    rows = fences = 0
    fence: str | None = None
    for line in text.splitlines():
        marker = FENCE.match(line)
        if marker is not None:
            kind = marker.group(1)[0]
            if fence is None:
                fence, fences = kind, fences + 1
            elif kind == fence:
                fence = None
            continue
        if fence is not None:
            continue
        if (heading := HEADING.match(line)) is not None:
            headings.append((len(heading.group(1)), line.strip()))
        elif TABLE_ROW.match(line):
            rows += 1
    return Shape(tuple(headings), rows, fences)


def twin(original: str) -> str:
    """Имя английского двойника: ``docs/a.md`` → ``docs/a.en.md``."""
    return original.removesuffix(".md") + ".en.md"


def compare(original: str, ru: str, en: str) -> list[str]:
    """Сверить пару и вернуть находки, по одной на расхождение.

    Args:
        original: Путь русского оригинала — попадёт в сообщения.
        ru: Текст оригинала.
        en: Текст двойника.
    """
    english = twin(original)
    problems: list[str] = []
    if f"]({Path(english).name})" not in ru:
        problems.append(f"{original}: нет переключателя на {Path(english).name}")
    if f"]({Path(original).name})" not in en:
        problems.append(f"{english}: нет переключателя на {Path(original).name}")

    left, right = shape(ru), shape(en)
    levels_left = [level for level, _ in left.headings]
    levels_right = [level for level, _ in right.headings]
    if levels_left != levels_right:
        problems.append(_heading_drift(original, english, left, right))
    if left.table_rows != right.table_rows:
        problems.append(
            f"{original} ↔ {english}: строк таблиц {left.table_rows} против "
            f"{right.table_rows} — строка дописана в одну половину"
        )
    if left.fences != right.fences:
        problems.append(
            f"{original} ↔ {english}: блоков кода {left.fences} против {right.fences}"
        )
    return problems


def _heading_drift(original: str, english: str, left: Shape, right: Shape) -> str:
    """Назвать первый расходящийся заголовок пары."""
    for index, (one, two) in enumerate(
        zip(left.headings, right.headings, strict=False), start=1
    ):
        if one[0] != two[0]:
            return (
                f"{original} ↔ {english}: заголовок №{index} разного уровня — "
                f"{one[1]!r} против {two[1]!r}"
            )
    shorter, longer = (
        (english, left.headings[len(right.headings)])
        if len(left.headings) > len(right.headings)
        else (original, right.headings[len(left.headings)])
    )
    return (
        f"{original} ↔ {english}: заголовков {len(left.headings)} против "
        f"{len(right.headings)}; в {shorter} нет {longer[1]!r}"
    )


def check(root: Path, pairs: Sequence[str]) -> tuple[list[str], list[str]]:
    """Сверить пары дерева.

    Returns:
        Пара «находки, отказы». Отказ — оригинала из списка нет: проверять
        нечего, и это не «пары совпадают».
    """
    problems: list[str] = []
    refusals: list[str] = []
    for original in pairs:
        path = root / original
        if not path.is_file():
            refusals.append(f"оригинал не прочитан: {original} — файла нет в {root}")
            continue
        english = root / twin(original)
        if not english.is_file():
            problems.append(f"{original}: нет английского двойника {twin(original)}")
            continue
        problems.extend(
            compare(
                original,
                path.read_text(encoding="utf-8"),
                english.read_text(encoding="utf-8"),
            )
        )
    return problems, refusals


def main(argv: list[str] | None = None) -> int:
    """Точка входа. Возвращает 0, 1 или 2 — см. docstring модуля."""
    parser = argparse.ArgumentParser(description="Гейт на двуязычные документы")
    parser.add_argument(
        "--root", type=Path, default=ROOT, metavar="DIR", help="корень дерева"
    )
    args = parser.parse_args(argv)
    problems, refusals = check(Path(args.root).resolve(), PAIRS)
    if refusals:
        for refusal in refusals:
            print(refusal, file=sys.stderr)
        print("\nПроверка не отработала: поправьте PAIRS или --root.", file=sys.stderr)
        return REFUSED
    if problems:
        for problem in problems:
            print(problem, file=sys.stderr)
        print(
            f"\nпар с расхождением устройства: {len(problems)} находок — "
            "правка внесена в одну половину пары",
            file=sys.stderr,
        )
        return FOUND
    print(f"пар сверено: {len(PAIRS)}, устройство совпадает")
    return CLEAN


if __name__ == "__main__":
    sys.exit(main())
