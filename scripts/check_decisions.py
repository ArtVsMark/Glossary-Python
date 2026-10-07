#!/usr/bin/env python3
"""Запись решения называет отвергнутую альтернативу, а не только принятую.

Правило каталога 161: единица истории — поворот, и у записи о повороте есть
обязательная часть: **что отвергнуто и почему**. Без неё запись отвечает на
вопрос «что сделали» и молчит о том, ради чего запись заводится, — почему не
сделали иначе. Через год именно этот вопрос и задают: принятое видно из кода,
отвергнутое не видно ниоткуда, и его предлагают заново.

ПРЕДМЕТ У ПРОЕКТА ЕСТЬ, и прежний ответ это отрицал. Записи решений живут в
``docs/architecture.md`` § «Принятые решения», и форма у них своя: «Было ·
Стало · Зачем · Цена · Отвергнуто». Две записи её несут целиком.

ХРАПОВИК, А НЕ ЗАПРЕТ ЗАДНИМ ЧИСЛОМ. Девяти записям отвергнутая альтернатива не
дописывается: чего именно не выбрал автор решения, из текста не следует, и
сочинить это значило бы выдумать историю вместо того, чтобы её вести. Они
названы поимённо в ``tests/decisions_baseline.json``, и список движется только
вниз — как планка качества данных. Требование действует для СЛЕДУЮЩЕЙ записи.

РАЗБОР НАДВОЕ (правило 182). Отличить поворот от хода работ машина не может —
эту границу называет у себя и каталог. **Что запись поворота несёт обязательную
часть** следует из текста документа целиком, и держится здесь.

ЧЕГО ГЕЙТ НЕ ЛОВИТ, названо здесь, а не подразумевается (правило 056):

* **содержательность отвергнутого.** «Отвергнуто: другое» пройдёт: гейт видит
  часть записи, а не смысл;
* **решения вне документа.** Поворот, принятый в разговоре и никуда не
  записанный, сюда не попадает — его ловит правило 138 и гейт журнала;
* **верность отнесения.** Что запись описывает поворот, а не ход работ,
  решает автор.

РЕШЕНИЕ НЕ ПРАВИТСЯ ЗАДНИМ ЧИСЛОМ (правило 043). С ``--base REF`` гейт
сверяет документ с основой изменения: запись, бывшая там и исчезнувшая здесь,
— находка. Повернули решение — пишут новую запись, а прежнюю оставляют, пометив
«Заменено»: стёртая запись уносит и то, почему её когда-то приняли. Отличить
поворот от хода работ машина не может, а исчезновение заголовка видит — это
машинная половина. Переименование читается как исчезновение: заголовок записи
— её имя, на него ссылаются.

Запуск::

    python scripts/check_decisions.py             # дерево проекта
    python scripts/check_decisions.py --root DIR  # другое дерево
    python scripts/check_decisions.py --base origin/main  # и сверка с основой

Исходы: 0 — чисто; 1 — есть находки; 2 — проверка не отработала.
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Final

ROOT: Final = Path(__file__).resolve().parent.parent

DOCUMENT: Final = "docs/architecture.md"
SECTION: Final = "## Принятые решения"
ENTRY: Final = re.compile(r"^### (?P<title>.+)$", re.MULTILINE)
REQUIRED: Final = "**Отвергнуто.**"
"""Обязательная часть записи. Форма постоянна и видна в самих записях."""

BASELINE: Final = "tests/decisions_baseline.json"
"""Записи, заведённые до правила. Список движется только вниз."""

NOT_RUN: Final = 2
"""Проверка не отработала. Не означает «части на месте» — их не искали."""

SUPERSEDED: Final = "Заменено"
"""Пометка отменённого решения: запись остаётся, поворот пишется новой."""

GIT_TIMEOUT: Final = 30
"""Секунд на чтение основы: локальный git, сеть не нужна."""


def decisions(text: str) -> dict[str, str]:
    """Записи решений: заголовок и тело.

    Args:
        text: Содержимое документа.

    Returns:
        Отображение «заголовок → тело записи»; пусто — раздела нет.
    """
    if SECTION not in text:
        return {}
    section = text.split(SECTION, 1)[1].split("\n## ", 1)[0]
    found: dict[str, str] = {}
    matches = list(ENTRY.finditer(section))
    for number, match in enumerate(matches):
        end = matches[number + 1].start() if number + 1 < len(matches) else len(section)
        found[match.group("title").strip()] = section[match.end() : end]
    return found


def load_baseline(root: Path) -> set[str]:
    """Записи, освобождённые от требования.

    Args:
        root: Корень дерева.

    Returns:
        Заголовки записей; пустое множество — планки нет.
    """
    path = root / BASELINE
    if not path.exists():
        return set()
    payload = json.loads(path.read_text(encoding="utf-8"))
    return set(payload["grandfathered"])


def findings(text: str, exempt: set[str]) -> list[str]:
    """Записи без обязательной части.

    Args:
        text: Содержимое документа.
        exempt: Заголовки, освобождённые планкой.

    Returns:
        Готовые к печати находки.
    """
    return [
        f"{DOCUMENT} § «{title}»: нет части {REQUIRED} — запись отвечает, что "
        "сделали, и молчит, почему не сделали иначе. Через год спросят именно "
        "об этом: принятое видно из кода, отвергнутое не видно ниоткуда "
        "(правило 161)"
        for title, body in decisions(text).items()
        if title not in exempt and REQUIRED not in body
    ]


def stale_exemptions(text: str, exempt: set[str]) -> list[str]:
    """Освобождения, которым больше нечего освобождать.

    Планка, отставшая от документа, тихо освобождает переименованную запись —
    и требование перестаёт действовать там, где оно уже действовало.

    Args:
        text: Содержимое документа.
        exempt: Заголовки, освобождённые планкой.

    Returns:
        Готовые к печати находки.
    """
    written = decisions(text)
    return [
        f"{BASELINE}: «{title}» — "
        + (
            "такой записи в документе нет вовсе"
            if title not in written
            else f"часть {REQUIRED} у неё появилась, освобождение пора снять"
        )
        for title in sorted(exempt)
        if title not in written or REQUIRED in written[title]
    ]


def erased(base_text: str, text: str) -> list[str]:
    """Записи основы, которых в документе больше нет (правило 043).

    Args:
        base_text: Документ на основе изменения.
        text: Документ сейчас.

    Returns:
        Готовые к печати находки.
    """
    written = decisions(text)
    return [
        f"{DOCUMENT} § «{title}»: запись была на основе и исчезла. Решение не "
        "правят задним числом — его отменяет новая запись, а прежняя остаётся с "
        f"пометкой «{SUPERSEDED}» (правило 043)"
        for title in decisions(base_text)
        if title not in written
    ]


def base_document(base: str, root: Path) -> str | None:
    """Документ решений на основе изменения; ``None`` — прочитать нечем.

    Args:
        base: Ссылка git на основу.
        root: Корень дерева.

    Returns:
        Текст документа или ``None``, если git не ответил.
    """
    try:
        done = subprocess.run(  # noqa: S603 — аргументы наши, не чужой ввод
            ["git", "-C", str(root), "show", f"{base}:{DOCUMENT}"],  # noqa: S607
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
            timeout=GIT_TIMEOUT,
        )
    except OSError, subprocess.TimeoutExpired:
        return None
    return done.stdout if done.returncode == 0 else None


def main(argv: list[str] | None = None) -> int:
    """Точка входа.

    Args:
        argv: Аргументы командной строки; ``None`` — взять из ``sys.argv``.

    Returns:
        Код возврата процесса.
    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--base", default=None, help="основа изменения для сверки")
    args = parser.parse_args(argv)

    path = args.root / DOCUMENT
    if not path.exists():
        print(
            f"проверка не отработала: документа решений нет — {path}",
            file=sys.stderr,
        )
        return NOT_RUN

    text = path.read_text(encoding="utf-8")
    written = decisions(text)
    if not written:
        print(
            f"проверка не отработала: в {DOCUMENT} нет раздела «{SECTION}» либо "
            "он пуст — записей решений не найдено",
            file=sys.stderr,
        )
        return NOT_RUN

    exempt = load_baseline(args.root)
    problems = findings(text, exempt) + stale_exemptions(text, exempt)
    if args.base is not None:
        base_text = base_document(args.base, args.root)
        if base_text is None:
            print(
                f"проверка не отработала: {DOCUMENT} на основе {args.base} не "
                "прочитан — сверять стёртое не с чем",
                file=sys.stderr,
            )
            return NOT_RUN
        problems += erased(base_text, text)
    if problems:
        print("запись решения неполна или стёрта:", file=sys.stderr)
        for problem in problems:
            print(f"  • {problem}", file=sys.stderr)
        return 1

    print(
        f"записей решений: {len(written)}, из них с отвергнутой альтернативой: "
        f"{len(written) - len(exempt)}, освобождены планкой: {len(exempt)}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
