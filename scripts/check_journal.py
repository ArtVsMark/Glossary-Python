#!/usr/bin/env python3
r"""Запись журнала едет вместе с изменением, а список путей читается по NUL.

Правило каталога 138: решение оседает артефактом **сразу**, а не в конце. То,
что оставлено «на потом», живёт в контексте окна и умирает вместе с ним — в
конце его приходится пересказывать, то есть нарушать то самое правило, ради
которого эстафета и заводится. У этого проекта артефакт есть и он дешёвый:
одна строка в ``changelog.d/``. Здесь она становится обязательной для изменений,
трогающих код и конвейер.

Правило каталога 165: перечисляя пути из git, передавай ``-z`` и разбирай вывод
по NUL. Без него git экранирует имена с не-ASCII символами и пробелами —
``changelog.d/сброс.added.md`` приезжает как ``"changelog.d/\321\201..."``, —
и путь не совпадает ни с одним образцом. Фрагмент, названный по-русски, стал бы
невидимым, и гейт потребовал бы запись, которая уже лежит рядом. Проект ведётся
по-русски: слепой оказалась бы не экзотика, а самый вероятный случай.

ОХВАТ ПЕЧАТАЕТСЯ ВСЕГДА, и это вторая половина правила 165, а не украшение.
Молчание проверки означает и «ничего не нашла», и «ничего не смотрела»;
различить их читателю нечем, пока не названо число просмотренного (правило 075).

РАЗБОР НАДВОЕ (правило 182). Что решение ПРИНЯТО, а не обсуждено, — суждение, и
машинной эта половина не станет. **Что оно осело артефактом тем же заходом** —
следует из состава изменения целиком, и держится здесь.

ЧЕГО ГЕЙТ НЕ ЛОВИТ, названо здесь, а не подразумевается (правило 056):

* **содержательность записи.** Фрагмент из одного слова гейт примет: форму
  записей держит ``scripts/changelog.py``, а смысл — читатель;
* **решения без правки кода.** Отвергнутый вариант, обсуждённый и не тронувший
  ни одного файла, сюда не попадает вовсе: у него нет состава изменения;
* **чужие ветки.** Разбирается заданный диапазон.

Запуск::

    python scripts/check_journal.py                 # ветка против origin/main
    python scripts/check_journal.py --base origin/develop

Исходы: 0 — чисто; 1 — запись не приехала; 2 — проверка не отработала.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Final

ROOT: Final = Path(__file__).resolve().parent.parent

DEFAULT_BASE: Final = "origin/main"

WATCHED: Final = ("scripts/", "src/", ".github/workflows/", ".github/actions/")
"""Что считается изменением кода и конвейера: у такого решения есть артефакт."""

JOURNAL: Final = "changelog.d/"
"""Где живёт запись. Одна строка на изменение — дешевле пересказа."""

NUL: Final = "\0"
"""Разделитель путей. Единственный символ, которого в имени файла не бывает."""

TIMEOUT: Final = 30
"""Дедлайн на вызов git: у запуска он свой и короткий (правило 100)."""

SHOWN: Final = 3
"""Сколько путей называет находка: остальное — счётом, а не списком."""

NOT_RUN: Final = 2
"""Проверка не отработала. Не означает «запись приехала» — её не искали."""


class NotRunError(RuntimeError):
    """Список путей не прочитан: третий исход, а не находка."""


def changed_paths(base: str, root: Path = ROOT) -> list[str]:
    """Пути, тронутые веткой, прочитанные по NUL.

    Args:
        base: С чем сравнивать.
        root: Корень репозитория.

    Returns:
        Пути от корня дерева, в том виде, в каком их отдал git.

    Raises:
        NotRunError: git не отработал — диапазон, репозиторий, права.
    """
    try:
        # S603/S607 сняты осознанно: git зовётся по имени из PATH — тот же, что
        # у разработчика и прогона, — а команда собрана из констант и одного
        # аргумента вызывающего. Ключ -z обязателен: см. правило 165 в шапке.
        result = subprocess.run(  # noqa: S603
            ["git", "diff", "-z", "--name-only", f"{base}...HEAD"],  # noqa: S607
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=TIMEOUT,
            cwd=root,
            check=False,
        )
    except OSError as error:
        raise NotRunError(f"git не запустился: {error}") from error
    if result.returncode != 0:
        raise NotRunError(f"git diff {base}...HEAD не отработал: {result.stderr.strip()}")
    return [path for path in result.stdout.split(NUL) if path]


def findings(paths: list[str]) -> list[str]:
    """Нужна ли изменению запись журнала и приехала ли она.

    Args:
        paths: Пути, тронутые изменением.

    Returns:
        Готовые к печати находки; пустой список — записи не требуется либо она есть.
    """
    touched = sorted(path for path in paths if path.startswith(WATCHED))
    if not touched:
        return []
    if any(path.startswith(JOURNAL) for path in paths):
        return []
    shown, note = touched[:SHOWN], "…" if len(touched) > SHOWN else ""
    listed = ", ".join(shown) + note
    return [
        f"изменение трогает код и конвейер ({listed}), а записи в {JOURNAL} не "
        "несёт. Решение, оставленное «на потом», живёт в контексте окна и умирает "
        "вместе с ним — одна строка сейчас дешевле пересказа потом (правило 138)"
    ]


def main(argv: list[str] | None = None) -> int:
    """Точка входа.

    Args:
        argv: Аргументы командной строки; ``None`` — взять из ``sys.argv``.

    Returns:
        Код возврата процесса.
    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base", default=DEFAULT_BASE, help="с чем сравнивать")
    args = parser.parse_args(argv)

    try:
        paths = changed_paths(args.base)
    except NotRunError as refusal:
        print(f"проверка не отработала: {refusal}", file=sys.stderr)
        return NOT_RUN

    # Охват печатается всегда: без числа просмотренного молчание означает и
    # «чисто», и «нечего смотреть» — разные вещи (правила 165, 075).
    watched = [path for path in paths if path.startswith(WATCHED)]
    print(f"путей в изменении: {len(paths)}, из них под наблюдением: {len(watched)}")

    problems = findings(paths)
    if problems:
        for problem in problems:
            print(f"  • {problem}", file=sys.stderr)
        return 1

    if not paths:
        print("изменение ничего не трогает — записи не требуется")
    return 0


if __name__ == "__main__":
    sys.exit(main())
