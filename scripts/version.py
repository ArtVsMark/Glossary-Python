"""Версия проекта по схеме семьи: тег ``vX.Y.0`` плюс принятые изменения.

Схема общая для проектов семьи — у каталога правил она в ``scripts/version.py``,
у грейдера в ``docs/dev/versioning.md`` — и это не SemVer::

    MAJOR . MINOR . PATCH
      │       │       └─ +1 на принятое изменение; обнуляется новым тегом
      │       └───────── +1 при постановке тега выпуска
      └───────────────── только фундаментальное

Инвариант «каждый тег — ``vX.Y.0``» делает ``0.1.17`` словами «семнадцать
принятых изменений после v0.1.0», а не «семнадцатый патч-выпуск»: выпуска с
таким номером нет, и двух версий с одним номером не бывает.

**Считаются номера изменений, а не рёбра графа.** Форма истории зависит от
клона: слияние ``git pull`` уводит пришедшее с площадки во второй родитель.
Номера собираются по всему диапазону и гасят двойной учёт; безномерные коммиты
— прямые толчки — берутся только с first-parent линии, иначе внутренние
коммиты слитой ветки считались бы поштучно.

**Поле version в pyproject.toml не второй источник, а начало отсчёта.** Оно
обязано совпадать с ``X.Y.0`` последнего тега — это держит
``tests/test_version.py``. Метаданные пакета отвечают на «какой выпуск
установлен», логическая версия — на «сколько принято после него».

Без тега версия недостоверна, и ответ — третий исход, а не правдоподобное
``0.1.N``: клон без тегов неотличим от проекта до первого выпуска.

Запуск::

    python scripts/version.py            # 0.1.37
    python scripts/version.py --release  # 0.1

Исходы: 0 — версия определена; 2 — тега схемы не видно.
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path
from typing import Final, NamedTuple

ROOT: Final = Path(__file__).resolve().parent.parent

NOT_RUN: Final = 2
"""Тега схемы не видно: версия не определена, а не «нулевая»."""

GIT_TIMEOUT: Final = 30
"""Дедлайн на вызов git (правило 100)."""

TAG_GLOB: Final = "v[0-9]*.[0-9]*.[0-9]*"
"""Маска для ``git describe``: сразу ищет теги нужной формы."""

TAG_RE: Final = re.compile(r"^v(\d+)\.(\d+)\.0$")
"""Тег выпуска строго ``vX.Y.0``: маска не отличает ``v1.0.0`` от ``v1.0.0-rc``."""

PR_RE: Final = re.compile(r"\(#(\d+)\)")
"""Номер изменения, дописанный уплотнением в конец темы."""

MERGE_PR_RE: Final = re.compile(r"^Merge pull request #(\d+)\b")
"""Номер изменения в теме обычного слияния."""

SYNC_MERGE_RE: Final = re.compile(
    r"^Merge (?:remote-tracking )?branch '[^']+' of |^Merge remote-tracking branch '"
)
"""Склейка ``git pull``: сводит копии ветки и своего изменения не несёт."""

BOT_COMMITS: Final = ("[skip ci]",)
"""Следы самих механизмов: публикация значков пишет коммиты с этой пометкой."""


class Version(NamedTuple):
    """Версия по схеме семьи.

    Attributes:
        tag: Тег выпуска, от которого идёт счёт, — ``v0.1.0``.
        release: Выпуск ``X.Y``.
        full: Полная версия ``X.Y.N``.
    """

    tag: str
    release: str
    full: str


def git(*args: str) -> str | None:
    """Вывод git без хвостового перевода строки; ``None`` при любом отказе."""
    try:
        done = subprocess.run(  # noqa: S603 — аргументы наши, не чужой ввод
            ["git", "-C", str(ROOT), *args],  # noqa: S607 — git ищется в PATH
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
            timeout=GIT_TIMEOUT,
        )
    except OSError, subprocess.TimeoutExpired:
        return None
    return done.stdout.strip() if done.returncode == 0 else None


def subjects(rev_range: str, *, first_parent: bool = False) -> list[str]:
    """Темы коммитов диапазона."""
    args = ["log", "--pretty=%s", *(["--first-parent"] if first_parent else [])]
    out = git(*args, rev_range)
    return [line for line in out.splitlines() if line] if out else []


def pr_numbers(lines: list[str]) -> set[str]:
    """Номера изменений, названные в темах — уплотнением или слиянием."""
    found: set[str] = set()
    for subject in lines:
        found.update(PR_RE.findall(subject))
        merged = MERGE_PR_RE.match(subject)
        if merged:
            found.add(merged.group(1))
    return found


def countable_unnumbered(subject: str) -> bool:
    """Коммит без номера — прямой толчок, и он реален. Кроме механизмов и склеек."""
    return not any(mark in subject for mark in BOT_COMMITS) and not SYNC_MERGE_RE.match(
        subject
    )


def accepted_since(rev_range: str) -> int:
    """Принятые изменения диапазона: номера по всей истории + безномерные first-parent."""
    numbered = pr_numbers(subjects(rev_range))
    unnumbered = [
        s
        for s in subjects(rev_range, first_parent=True)
        if not PR_RE.search(s) and not MERGE_PR_RE.match(s) and countable_unnumbered(s)
    ]
    return len(numbered) + len(unnumbered)


def latest_tag() -> str | None:
    """Ближайший тег выпуска или ``None``. Форма проверяется маской и регуляркой."""
    tag = git("describe", "--tags", "--abbrev=0", "--match", TAG_GLOB)
    return tag if tag and TAG_RE.match(tag) else None


def version() -> Version | None:
    """Версия по схеме семьи; ``None``, если тега схемы не видно."""
    tag = latest_tag()
    match = TAG_RE.match(tag) if tag else None
    if tag is None or match is None:
        return None
    release = f"{match.group(1)}.{match.group(2)}"
    return Version(tag, release, f"{release}.{accepted_since(f'{tag}..HEAD')}")


def main(argv: list[str] | None = None) -> int:
    """Точка входа: печатает версию или выпуск."""
    parser = argparse.ArgumentParser(description=__doc__, prog="version")
    parser.add_argument("--release", action="store_true", help="только выпуск «X.Y»")
    args = parser.parse_args(argv)

    got = version()
    if got is None:
        # Третий исход: клон без тегов неотличим от проекта до выпуска, и
        # правдоподобное число здесь хуже отказа (правила 039, 075).
        print(
            f"версия не определена: в {ROOT} тега выпуска вида vX.Y.0 не видно. "
            "Либо схема ещё не начата, либо клон без тегов — подтяните: "
            "git fetch --tags",
            file=sys.stderr,
        )
        return NOT_RUN
    print(got.release if args.release else got.full)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
