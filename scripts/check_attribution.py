#!/usr/bin/env python3
"""Атрибуция проверяется в конечной истории, а трейлер — в хвостовом блоке.

Правило каталога 123: сообщение коммита, которое уедет в общую ветку,
**пересобирается** при слиянии. Всё, что автор написал в ветке, — лишь вход для
этой пересборки, и поля авторства платформа вправе подставить свои. Значит
проверять надо то, что легло в историю, а не то, что задумывалось.

Правило каталога 156: трейлер читается **только из хвостового блока** —
последнего абзаца, все непустые строки которого имеют форму ``Ключ: значение``.
Разбор по образцу «строка начинается с имени трейлера» принимает за директиву
прозаическое упоминание, и тем чаще, чем подробнее написано сообщение. Здесь
это не гипотеза: в собственной истории проекта ``Co-Authored-By`` встречается в
теле сообщений, а не только в хвосте.

ЗАМЕР, ИЗ-ЗА КОТОРОГО ГЕЙТ ЗАВЕДЁН. Один и тот же деятель приезжает в историю
под тремя личностями: ``Claude <noreply@anthropic.com>``,
``Claude <arvs.markitanov@gmail.com>`` и ``ArtVsMark <arvs.markitanov@gmail.com>``.
Ни одна проверка этого не замечала. Отдельно: с переходом на автомерж автором
коммитов слияния стал ``github-actions[bot]`` — прежде им был владелец.
Это не поломка, а названная цена автомержа, и список имён теперь говорит о ней
вслух.

РАЗБОР НАДВОЕ (правило 182). Кому принадлежит имя и законно ли оно — суждение,
и машинной эта половина не станет: список имён ведёт человек. **Что имя в
списке** — следует из истории целиком, и держится здесь.

ЧЕГО ГЕЙТ НЕ ЛОВИТ, названо здесь, а не подразумевается (правило 056):

* **подмену на записи.** Кем окно подпишется, из дерева не следует; это
  выясняется пробой — записью и взглядом на подпись (правило 135);
* **верность самого списка.** Имя, добавленное в него ошибочно, гейт примет:
  он сверяет с объявленным, а не судит об объявленном;
* **чужие ветки.** Разбирается заданный диапазон; что лежит в неслитых ветках
  соседей, отсюда не видно.

Запуск::

    python scripts/check_attribution.py                  # коммиты ветки против main
    python scripts/check_attribution.py --range A..B     # заданный диапазон
    python scripts/check_attribution.py --list           # кто встречается в истории

Исходы: 0 — чисто; 1 — есть находки; 2 — проверка не отработала.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path
from typing import Final, NamedTuple

ROOT: Final = Path(__file__).resolve().parent.parent
ALLOWED: Final = ROOT / ".github" / "authors.txt"

DEFAULT_RANGE: Final = "origin/main..HEAD"
SEPARATOR: Final = "\x1e"
"""Разделитель записей в выводе git: в сообщении коммита он не встречается."""

TRAILER: Final = re.compile(r"^(?P<key>[A-Za-z][A-Za-z-]*): +(?P<value>.+)$")
COAUTHOR: Final = "co-authored-by"

RECORD_FIELDS: Final = 2
"""Сколько строк несёт запись до сообщения: идентификатор и личность автора."""

NOT_RUN: Final = 2
"""Проверка не отработала. Не означает «атрибуция в порядке» — её не смотрели."""

TIMEOUT: Final = 30
"""Дедлайн на вызов git: у запуска он свой и короткий (правило 100)."""


class Commit(NamedTuple):
    """Коммит в том виде, в каком он лёг в историю.

    Attributes:
        sha: Короткий идентификатор.
        author: Личность автора в форме ``Имя <почта>``.
        message: Полное сообщение.
    """

    sha: str
    author: str
    message: str


class NotRunError(RuntimeError):
    """История не прочитана: третий исход, а не находка."""


def allowed_identities(path: Path = ALLOWED) -> set[str]:
    """Разрешительный список личностей.

    Args:
        path: Файл со списком.

    Returns:
        Личности в форме ``Имя <почта>``.

    Raises:
        NotRunError: Файла нет — сверять не с чем.
    """
    if not path.exists():
        raise NotRunError(
            f"нет списка имён {path} — сверять авторство не с чем. Список ведёт "
            "человек: машина проверяет вхождение, а не законность имени"
        )
    return {
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }


def trailer_block(message: str) -> list[str]:
    """Хвостовой блок сообщения: последний абзац, если он весь из трейлеров.

    Абзац, где хоть одна непустая строка не имеет формы ``Ключ: значение``,
    хвостовым блоком не является — целиком. Именно это отличает директиву от
    прозаического упоминания (правило 156).

    Args:
        message: Полное сообщение коммита.

    Returns:
        Строки хвостового блока; пустой список — блока нет.
    """
    paragraphs = [part for part in re.split(r"\n\s*\n", message.strip()) if part.strip()]
    if not paragraphs:
        return []
    lines = [line for line in paragraphs[-1].splitlines() if line.strip()]
    if not lines or not all(TRAILER.match(line) for line in lines):
        return []
    return lines


def trailers(message: str) -> dict[str, list[str]]:
    """Трейлеры из хвостового блока, ключ в нижнем регистре.

    Args:
        message: Полное сообщение коммита.

    Returns:
        Отображение «ключ → значения».
    """
    found: dict[str, list[str]] = {}
    for line in trailer_block(message):
        match = TRAILER.match(line)
        if match is None:  # pragma: no cover - блок уже проверен целиком
            continue
        found.setdefault(match.group("key").lower(), []).append(
            match.group("value").strip()
        )
    return found


def read_history(commit_range: str) -> list[Commit]:
    """Прочитать диапазон истории.

    Args:
        commit_range: Диапазон в записи git.

    Returns:
        Коммиты диапазона, новейшие первыми.

    Raises:
        NotRunError: git не отработал — диапазон, репозиторий, права.
    """
    try:
        # S603/S607 сняты осознанно: git зовётся по имени из PATH — это тот же
        # git, которым пользуется разработчик и прогон, а команда собрана из
        # констант и одного аргумента, который сюда передаёт вызывающий.
        result = subprocess.run(  # noqa: S603
            ["git", "log", commit_range, f"--format=%h%n%an <%ae>%n%B{SEPARATOR}"],  # noqa: S607
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=TIMEOUT,
            cwd=ROOT,
            check=False,
        )
    except OSError as error:
        raise NotRunError(f"git не запустился: {error}") from error
    if result.returncode != 0:
        raise NotRunError(f"git log {commit_range} не отработал: {result.stderr.strip()}")

    commits: list[Commit] = []
    for record in result.stdout.split(SEPARATOR):
        lines = record.strip("\n").splitlines()
        if len(lines) < RECORD_FIELDS:
            continue
        commits.append(Commit(lines[0], lines[1], "\n".join(lines[2:])))
    return commits


def findings(commits: list[Commit], known: set[str]) -> list[str]:
    """Кто в истории назвался именем, которого нет в списке.

    Args:
        commits: Коммиты диапазона.
        known: Разрешённые личности.

    Returns:
        Готовые к печати находки.
    """
    problems: list[str] = []
    for commit in commits:
        if commit.author not in known:
            problems.append(
                f"{commit.sha}: автор «{commit.author}» не в списке {ALLOWED.name}"
            )
        problems.extend(
            f"{commit.sha}: соавтор «{coauthor}» не в списке {ALLOWED.name}"
            for coauthor in trailers(commit.message).get(COAUTHOR, ())
            if coauthor not in known
        )
    return problems


def main(argv: list[str] | None = None) -> int:
    """Точка входа.

    Args:
        argv: Аргументы командной строки; ``None`` — взять из ``sys.argv``.

    Returns:
        Код возврата процесса.
    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--range", default=DEFAULT_RANGE, help="диапазон истории")
    parser.add_argument("--list", action="store_true", help="показать личности диапазона")
    args = parser.parse_args(argv)

    try:
        commits = read_history(args.range)
        known = allowed_identities()
    except NotRunError as refusal:
        print(f"проверка не отработала: {refusal}", file=sys.stderr)
        return NOT_RUN

    if args.list:
        seen: dict[str, int] = {}
        for commit in commits:
            seen[commit.author] = seen.get(commit.author, 0) + 1
            for coauthor in trailers(commit.message).get(COAUTHOR, ()):
                seen[f"(соавтор) {coauthor}"] = seen.get(f"(соавтор) {coauthor}", 0) + 1
        print(f"личностей в {args.range}: {len(seen)}")
        for identity, count in sorted(seen.items(), key=lambda pair: -pair[1]):
            mark = " " if identity.startswith("(соавтор) ") else ""
            print(f"  {count:3} {mark}{identity}")
        return 0

    if not commits:
        # Пустой диапазон — не «атрибуция в порядке», а «смотреть нечего».
        print(f"в диапазоне {args.range} нет коммитов — проверять нечего")
        return 0

    problems = findings(commits, known)
    if problems:
        print("атрибуция в истории не сходится со списком имён:", file=sys.stderr)
        for problem in problems:
            print(f"  • {problem}", file=sys.stderr)
        print(
            f"\n  Список ведёт человек: {ALLOWED}. Имя, приехавшее в общую ветку\n"
            "  под чужой личностью, оттуда уже не переписать — историю общей\n"
            "  ветки не перезаписывают (правило 123).",
            file=sys.stderr,
        )
        return 1

    print(f"атрибуция сходится: коммитов {len(commits)}, имён в списке {len(known)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
