#!/usr/bin/env python3
"""Атрибуция сверяется со списком, действующим НА ОСНОВЕ изменения.

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

СТОРОЖ НЕ ПРАВИТ СОБСТВЕННЫЙ СПИСОК ТЕМ ЖЕ ЗАХОДОМ. Гейт сверяет имена с
``.github/authors.txt``, а файл лежит в том же дереве, что и код: заход, который
подписался чужой личностью, дописывал бы её в список одной строкой — и зеленел
на собственной подписи. Граница была названа в этом докстринге словами «гейт не
судит о законности списка» и оказалась живой: 7 сентября окно тринадцать раз
подписалось личностью, которую само же в список и внесло.

Поэтому список берётся дважды: **как он лежит на основе диапазона** и как он
лежит в рабочем дереве. В силе — пересечение:

* **расширение** вступает в силу СЛЕДУЮЩИМ заходом. Личность, объявленная тем
  же изменением, чьи коммиты ею подписаны, в силу не входит: сначала список
  расширяет человек отдельным изменением, потом под именем подписываются;
* **сужение** действует ЭТИМ ЖЕ: убрать имя — движение планки вниз, а его
  откладывать не на что.

ЗАКРЫТАЯ ЛИЧНОСТЬ — третье состояние, а не отсутствие в списке. Строка с
префиксом ``закрыто:`` говорит: имя лежит в истории и оттуда не переписывается
(историю общей ветки не перезаписывают), но новых коммитов под ним не
принимают. Без этого состояния фикс «убрать имя из списка» краснит утверждение
о существующей истории, и выбор сводится к «оставить дыру» или «сломать main».

ЗАМЕР, ИЗ-ЗА КОТОРОГО ГЕЙТ ЗАВЕДЁН. Один и тот же деятель приезжает в историю
под тремя личностями: ``Claude <noreply@anthropic.com>``,
``Claude <arvs.markitanov@gmail.com>`` и ``ArtVsMark <arvs.markitanov@gmail.com>``.
Ни одна проверка этого не замечала. Отдельно: с переходом на автомерж автором
коммитов слияния стал ``github-actions[bot]`` — прежде им был владелец.
Это не поломка, а названная цена автомержа, и список имён теперь говорит о ней
вслух.

РАЗБОР НАДВОЕ (правило 182). Кому принадлежит имя и законно ли оно — суждение,
и машинной эта половина не станет: список имён ведёт человек. **Что имя было в
списке ДО этого изменения** — следует из истории целиком, и держится здесь.

ЧЕГО ГЕЙТ НЕ ЛОВИТ, названо здесь, а не подразумевается (правило 056):

* **расширение списка отдельным изменением.** Механизм делает расширение
  отдельным и видимым, а не невозможным: заход, готовый потратить на подлог два
  изменения вместо одного, пройдёт. Запрет живёт вне дерева: ``CODEOWNERS``
  назначает владельца всему дереву, но ревью требует настройка защиты ветки,
  а изменения уезжают автомержем по зелёному CI;
* **верность самого списка.** Имя, добавленное в него ошибочно, гейт примет
  следующим заходом: он сверяет с объявленным, а не судит об объявленном;
* **подмену на записи.** Кем окно подпишется, из дерева не следует; это
  выясняется пробой — записью и взглядом на подпись (правило 135);
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

IN_TREE: Final = ".github/authors.txt"
"""Тот же список путём внутри дерева: им он читается из произвольной ревизии."""

DEFAULT_RANGE: Final = "origin/main..HEAD"
RANGE_SEPARATOR: Final = ".."
SEPARATOR: Final = "\x1e"
"""Разделитель записей в выводе git: в сообщении коммита он не встречается."""

RETIRED_MARK: Final = "закрыто:"
"""Префикс личности, закрытой для новых коммитов, но живущей в истории."""

TRAILER: Final = re.compile(r"^(?P<key>[A-Za-z][A-Za-z-]*): +(?P<value>.+)$")
COAUTHOR: Final = "co-authored-by"

AUTHOR: Final = "автор"
CO: Final = "соавтор"

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


class Roster(NamedTuple):
    """Список имён, каким он объявлен в одной ревизии дерева.

    Attributes:
        active: Действующие личности.
        retired: Закрытые: лежат в истории, новых коммитов не принимают.
    """

    active: frozenset[str]
    retired: frozenset[str]

    @property
    def declared(self) -> frozenset[str]:
        """Все объявленные личности — и действующие, и закрытые."""
        return self.active | self.retired


class InForce(NamedTuple):
    """Список, действующий для проверяемого диапазона.

    Attributes:
        allowed: Личности в силе.
        retired: Закрытые для новых коммитов.
        pending: Объявленные этим же изменением — в силу ещё не вошли.
    """

    allowed: frozenset[str]
    retired: frozenset[str] = frozenset()
    pending: frozenset[str] = frozenset()

    @classmethod
    def as_declared(cls, names: Roster) -> InForce:
        """Список как объявлен — для утверждения о СУЩЕСТВУЮЩЕЙ истории.

        История общей ветки не перезаписывается, поэтому закрытая личность в ней
        находкой не является: закрытие смотрит вперёд, а не назад.

        Args:
            names: Список имён одной ревизии.

        Returns:
            Список, где в силе всё объявленное.
        """
        return cls(names.declared)

    @classmethod
    def between(cls, base: Roster, head: Roster) -> InForce:
        """Пересечение основы и рабочего дерева.

        Args:
            base: Список, лежащий на основе диапазона.
            head: Список, лежащий в рабочем дереве.

        Returns:
            Список в силе: расширение отложено, сужение действует сразу.
        """
        return cls(
            allowed=base.active & head.active,
            retired=head.retired,
            pending=head.active - base.active,
        )


class NotRunError(RuntimeError):
    """История не прочитана: третий исход, а не находка."""


def run_git(*args: str) -> str:
    """Позвать git и вернуть его вывод.

    Args:
        *args: Аргументы команды.

    Returns:
        Стандартный вывод.

    Raises:
        NotRunError: git не запустился, не уложился в дедлайн или отказал.
    """
    command = " ".join(("git", *args))
    try:
        # S603/S607 сняты осознанно: git зовётся по имени из PATH — это тот же
        # git, которым пользуется разработчик и прогон, а команда собрана из
        # констант и аргументов, которые сюда передаёт вызывающий.
        result = subprocess.run(  # noqa: S603
            ["git", *args],  # noqa: S607
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=TIMEOUT,
            cwd=ROOT,
            check=False,
        )
    except OSError as error:
        raise NotRunError(f"git не запустился: {error}") from error
    except subprocess.TimeoutExpired as error:
        raise NotRunError(f"«{command}» не уложился в {TIMEOUT} с") from error
    if result.returncode != 0:
        raise NotRunError(f"«{command}» не отработал: {result.stderr.strip()}")
    return result.stdout


def parse_roster(text: str) -> Roster:
    """Разобрать список имён.

    Args:
        text: Содержимое файла со списком.

    Returns:
        Действующие и закрытые личности в форме ``Имя <почта>``.
    """
    active: set[str] = set()
    retired: set[str] = set()
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith(RETIRED_MARK):
            retired.add(line[len(RETIRED_MARK) :].strip())
        else:
            active.add(line)
    return Roster(frozenset(active), frozenset(retired))


def roster(path: Path = ALLOWED) -> Roster:
    """Список имён из рабочего дерева.

    Args:
        path: Файл со списком.

    Returns:
        Разобранный список.

    Raises:
        NotRunError: Файла нет — сверять не с чем.
    """
    if not path.exists():
        raise NotRunError(
            f"нет списка имён {path} — сверять авторство не с чем. Список ведёт "
            "человек: машина проверяет вхождение, а не законность имени"
        )
    return parse_roster(path.read_text(encoding="utf-8"))


def base_of(commit_range: str) -> str:
    """Основа диапазона — ревизия слева от ``..``.

    Args:
        commit_range: Диапазон в записи git.

    Returns:
        Имя ревизии.

    Raises:
        NotRunError: Диапазон основу не называет.
    """
    base, separator, head = commit_range.partition(RANGE_SEPARATOR)
    if not separator or not base or not head or head.startswith("."):
        raise NotRunError(
            f"диапазон «{commit_range}» не называет основу: список имён в силе "
            "берётся из ревизии слева от «..», а запись без левой стороны и "
            "трёхточечная запись такой ревизии не задают"
        )
    return base


def roster_at(revision: str) -> Roster:
    """Список имён, каким он лежит в заданной ревизии.

    Args:
        revision: Ревизия в записи git.

    Returns:
        Разобранный список.

    Raises:
        NotRunError: Ревизии нет или списка в ней нет — сверять не с чем.
    """
    return parse_roster(run_git("show", f"{revision}:{IN_TREE}"))


def roster_in_force(commit_range: str) -> InForce:
    """Список, действующий для диапазона.

    Args:
        commit_range: Диапазон в записи git.

    Returns:
        Пересечение списка на основе и списка в рабочем дереве.

    Raises:
        NotRunError: Основу не прочитать — сверять не с чем.
    """
    return InForce.between(roster_at(base_of(commit_range)), roster())


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
    output = run_git("log", commit_range, f"--format=%h%n%an <%ae>%n%B{SEPARATOR}")
    commits: list[Commit] = []
    for record in output.split(SEPARATOR):
        lines = record.strip("\n").splitlines()
        if len(lines) < RECORD_FIELDS:
            continue
        commits.append(Commit(lines[0], lines[1], "\n".join(lines[2:])))
    return commits


def verdict(identity: str, role: str, names: InForce) -> str | None:
    """Что не так с личностью.

    Args:
        identity: Личность в форме ``Имя <почта>``.
        role: Кем она выступает в коммите: автором или соавтором.
        names: Список, действующий для диапазона.

    Returns:
        Готовая к печати находка; ``None`` — личность в силе.
    """
    if identity in names.retired:
        return (
            f"{role} «{identity}» — закрытая личность: она лежит в истории и "
            "оттуда не переписывается, но новых коммитов под ней не принимают"
        )
    if identity in names.pending:
        return (
            f"{role} «{identity}» объявлен в {ALLOWED.name} этим же изменением — "
            "в силу список входит следующим заходом: расширяет его человек, "
            "отдельно от кода, который этим списком сторожится"
        )
    if identity not in names.allowed:
        return f"{role} «{identity}» не в списке {ALLOWED.name}"
    return None


def findings(commits: list[Commit], names: InForce) -> list[str]:
    """Кто в истории назвался именем, которого нет в силе.

    Args:
        commits: Коммиты диапазона.
        names: Список, действующий для диапазона.

    Returns:
        Готовые к печати находки.
    """
    problems: list[str] = []
    for commit in commits:
        note = verdict(commit.author, AUTHOR, names)
        if note is not None:
            problems.append(f"{commit.sha}: {note}")
        problems.extend(
            f"{commit.sha}: {note}"
            for coauthor in trailers(commit.message).get(COAUTHOR, ())
            if (note := verdict(coauthor, CO, names)) is not None
        )
    return problems


def print_identities(commit_range: str, commits: list[Commit]) -> None:
    """Напечатать личности диапазона и сколько раз каждая встретилась.

    Args:
        commit_range: Диапазон в записи git — он называется в заголовке.
        commits: Коммиты диапазона.
    """
    seen: dict[str, int] = {}
    for commit in commits:
        seen[commit.author] = seen.get(commit.author, 0) + 1
        for coauthor in trailers(commit.message).get(COAUTHOR, ()):
            seen[f"({CO}) {coauthor}"] = seen.get(f"({CO}) {coauthor}", 0) + 1
    print(f"личностей в {commit_range}: {len(seen)}")
    for identity, count in sorted(seen.items(), key=lambda pair: -pair[1]):
        mark = " " if identity.startswith(f"({CO}) ") else ""
        print(f"  {count:3} {mark}{identity}")


def summary(commits: list[Commit], names: InForce) -> str:
    """Строка охвата: что просмотрено и какой список при этом действовал.

    Молчание проверки означает и «ничего не нашла», и «ничего не смотрела»;
    различить их читателю нечем, пока не названо число просмотренного (075).

    Args:
        commits: Коммиты диапазона.
        names: Список, действующий для диапазона.

    Returns:
        Готовая к печати строка.
    """
    parts = [f"коммитов {len(commits)}", f"имён в силе {len(names.allowed)}"]
    if names.retired:
        parts.append(f"закрытых {len(names.retired)}")
    if names.pending:
        parts.append(
            f"объявлено этим же изменением {len(names.pending)} — "
            "в силу войдут следующим заходом"
        )
    return "атрибуция сходится: " + ", ".join(parts)


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
        if args.list:
            print_identities(args.range, commits)
            return 0
        if not commits:
            # Пустой диапазон — не «атрибуция в порядке», а «смотреть нечего».
            print(f"в диапазоне {args.range} нет коммитов — проверять нечего")
            return 0
        names = roster_in_force(args.range)
    except NotRunError as refusal:
        print(f"проверка не отработала: {refusal}", file=sys.stderr)
        return NOT_RUN

    problems = findings(commits, names)
    if problems:
        print("атрибуция в истории не сходится со списком имён:", file=sys.stderr)
        for problem in problems:
            print(f"  • {problem}", file=sys.stderr)
        print(
            f"\n  Список ведёт человек: {ALLOWED}. Имя, приехавшее в общую ветку\n"
            "  под чужой личностью, оттуда уже не переписать — историю общей\n"
            "  ветки не перезаписывают (правило 123). Расширение списка едет\n"
            "  отдельным изменением: тем же заходом оно в силу не входит.",
            file=sys.stderr,
        )
        return 1

    print(summary(commits, names))
    return 0


if __name__ == "__main__":
    sys.exit(main())
